import io
from pathlib import Path

import httpx
from PIL import Image

from . import composer, imagegen, llm, models, runtime, scraper
from .config import settings
from .platforms import PLATFORMS


def _gen_dims(spec) -> tuple[int, int]:
    """Tamaño de generación con la proporción de la plataforma, lado largo
    ~1280, múltiplos de 8."""
    long = max(spec.width, spec.height)
    scale = min(1280 / long, 1.0)
    w = max((int(spec.width * scale) // 8) * 8, 256)
    h = max((int(spec.height * scale) // 8) * 8, 256)
    return w, h


def _normalize_logo(raw: bytes | None) -> bytes | None:
    """Convierte cualquier logo (png/jpg/webp) a PNG RGBA y lo acota.
    Devuelve None si no se puede (p.ej. SVG)."""
    if not raw:
        return None
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img.thumbnail((1024, 1024))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


async def _fetch_bytes(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            return r.content
    except Exception:
        return None


async def run_pipeline(jid: str, req: models.GenerateRequest, logo_bytes: bytes | None) -> None:
    try:
        await models.update_job(jid, status="running")

        # 1) Contexto del producto
        info = {}
        if req.url:
            info = await scraper.scrape(runtime.browser, req.url)
            context = f"{info['title']}\n{info['description']}\n{info['text']}"
            if req.brief:
                context += f"\n\nNotas del usuario: {req.brief}"
        else:
            context = req.brief or ""

        # Logo: el subido tiene prioridad; si no, se intenta el de la web.
        logo = _normalize_logo(logo_bytes)
        if logo is None and info.get("logo_url"):
            logo = _normalize_logo(await _fetch_bytes(info["logo_url"]))

        # 2) Copy y ángulos (una sola vez, compartidos entre tamaños)
        variants = await llm.generate_copy(
            context, n=req.n_variants, language=req.language
        )

        # 3) + 4) Imagen (cacheada por proporción) y composición por tamaño
        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # caché[indice_variante][proporcion] = bytes de la imagen de fondo
        cache: list[dict] = [{} for _ in variants]
        creatives: list[dict] = []

        for plat in req.platforms:
            spec = PLATFORMS[plat]
            ratio_key = round(spec.width / spec.height, 2)
            for i, v in enumerate(variants):
                if ratio_key not in cache[i]:
                    gw, gh = _gen_dims(spec)
                    cache[i][ratio_key] = await imagegen.generate_image(
                        v.get("image_prompt") or context[:200], gw, gh
                    )
                bg = cache[i][ratio_key]
                png = await composer.compose(
                    runtime.browser,
                    spec,
                    background=bg,
                    headline=v.get("headline", ""),
                    body=v.get("body", ""),
                    cta=v.get("cta", ""),
                    brand_color=req.brand_color,
                    accent_color=req.accent_color,
                    logo=logo,
                    template=req.template,
                )
                fname = f"{jid}_{plat}_{i + 1}.png"
                (out_dir / fname).write_bytes(png)
                creatives.append(
                    {
                        "platform": plat,
                        "label": spec.label,
                        "width": spec.width,
                        "height": spec.height,
                        "angle": v.get("angle", ""),
                        "headline": v.get("headline", ""),
                        "body": v.get("body", ""),
                        "cta": v.get("cta", ""),
                        "image_path": f"/outputs/{fname}",
                    }
                )
                await models.update_job(jid, creatives=creatives)  # progreso

        await models.update_job(jid, status="done", creatives=creatives)
    except Exception as e:  # noqa: BLE001
        await models.update_job(jid, status="error", error=f"{type(e).__name__}: {e}")
