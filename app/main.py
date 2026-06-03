import io
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright

from . import jobs, models, runtime, scraper
from .config import settings
from .platforms import CATEGORY_ORDER, PLATFORMS

_pw = None
WEB_DIR = Path(__file__).parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pw
    await models.init_db()
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    _pw = await async_playwright().start()
    runtime.browser = await _pw.chromium.launch(args=["--no-sandbox"])
    yield
    await runtime.browser.close()
    await _pw.stop()


app = FastAPI(title="AdGen (uso personal)", lifespan=lifespan)
Path(settings.output_dir).mkdir(parents=True, exist_ok=True)  # debe existir al montar
app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/platforms")
def list_platforms():
    """Catálogo agrupado por categoría para la interfaz."""
    groups = []
    for cat in CATEGORY_ORDER:
        sizes = [
            {"key": p.key, "label": p.label, "width": p.width, "height": p.height}
            for p in PLATFORMS.values()
            if p.category == cat
        ]
        groups.append({"category": cat, "sizes": sizes})
    return groups


@app.post("/scrape-images")
async def scrape_images(url: str = Form(...)):
    """Devuelve las imágenes candidatas (>=300x300) de una URL para elegir."""
    import io
    from PIL import Image
    from . import assets

    info = await scraper.scrape(runtime.browser, url)
    imgs = ([info["og_image"]] if info.get("og_image") else []) + info.get("images", [])
    seen, out = set(), []
    for u in imgs:
        if not u or u in seen:
            continue
        seen.add(u)
        raw = await assets.fetch_bytes(u)
        if not raw:
            continue
        try:
            w, h = Image.open(io.BytesIO(raw)).size
        except Exception:
            continue
        if w >= 300 and h >= 300:
            out.append(u)
        if len(out) >= 24:
            break
    return {"images": out}


@app.post("/ads/generate")
async def generate(
    bg: BackgroundTasks,
    platforms: list[str] = Form(...),
    url: str | None = Form(None),
    brief: str | None = Form(None),
    n_variants: int = Form(4),
    language: str = Form("es"),
    brand_color: str = Form("#111114"),
    accent_color: str = Form("#ff4d2e"),
    template: str | None = Form(None),
    use_product: bool = Form(True),
    product_images: list[str] = Form([]),
    logo: UploadFile | None = File(None),
    product: UploadFile | None = File(None),
):
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        raise HTTPException(400, f"tamaños desconocidos: {unknown}")
    if not url and not brief:
        raise HTTPException(400, "indica 'url' o 'brief' (o ambos)")

    logo_bytes = await logo.read() if logo is not None else None
    product_bytes = await product.read() if product is not None else None

    req = models.GenerateRequest(
        url=url or None,
        brief=brief or None,
        platforms=platforms,
        n_variants=max(1, min(n_variants, 8)),
        language=language,
        brand_color=brand_color,
        accent_color=accent_color,
        template=template or None,
        use_product=use_product,
        product_images=[u for u in product_images if u],
    )
    jid = await models.create_job(platforms)
    bg.add_task(jobs.run_pipeline, jid, req, logo_bytes, product_bytes)
    return {"job_id": jid, "status": "queued",
            "expected": len(platforms) * req.n_variants}


@app.get("/jobs")
async def jobs_list():
    """Historial de jobs recientes."""
    return await models.list_jobs()


@app.get("/jobs/{jid}")
async def job_status(jid: str):
    job = await models.get_job(jid)
    if not job:
        raise HTTPException(404, "job no encontrado")
    return job


@app.get("/jobs/{jid}/download")
async def download_job(jid: str, category: str | None = None):
    """Empaqueta las creatividades del job en un ZIP con nombres legibles.
    Con ?category=Instagram solo incluye las de esa categoría."""
    job = await models.get_job(jid)
    if not job or not job.creatives:
        raise HTTPException(404, "sin creatividades para descargar")

    out_dir = Path(settings.output_dir)
    buf = io.BytesIO()
    seen: dict[str, int] = {}
    added = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in job.creatives:
            spec = PLATFORMS.get(c.platform)
            if category and (not spec or spec.category != category):
                continue
            fpath = out_dir / Path(c.image_path).name
            if not fpath.exists():
                continue
            safe = re.sub(r"[^A-Za-z0-9]+", "-", c.label).strip("-")
            base = f"{c.platform}_{safe}_{c.width}x{c.height}"
            seen[base] = seen.get(base, 0) + 1
            zf.write(fpath, f"{base}_v{seen[base]}.png")
            added += 1
    if not added:
        raise HTTPException(404, "sin creatividades para esa categoría")
    buf.seek(0)
    suffix = f"_{category}" if category else ""
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="adgen_{jid}{suffix}.zip"'},
    )
