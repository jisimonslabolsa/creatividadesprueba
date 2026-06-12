from pathlib import Path

from . import animate, assets, composer, imagegen, llm, models, runtime, scraper
from .config import settings
from .platforms import PLATFORMS

GIF_SECONDS = 3      # segundos por imagen
GIF_MAX_FRAMES = 5   # máximo de imágenes que rotan


def _gen_dims(spec) -> tuple[int, int]:
    long = max(spec.width, spec.height)
    scale = min(1280 / long, 1.0)
    w = max((int(spec.width * scale) // 8) * 8, 256)
    h = max((int(spec.height * scale) // 8) * 8, 256)
    return w, h


def _process(raw: bytes | None) -> dict | None:
    """Procesa una imagen de producto: recorte (primer plano) o, si no se
    puede, imagen completa (fondo a sangre)."""
    if not raw:
        return None
    cut = assets.cutout(raw) if settings.remove_product_bg else None
    if cut:
        return {"cutout": cut, "full": None}
    full = assets.normalize_image(raw)
    return {"full": full, "cutout": None} if full else None


async def _processed_list(req, info, product_bytes) -> list:
    """Lista de imágenes de producto procesadas.
    Prioridad: imagen subida > imágenes elegidas en la UI > primeras de la web."""
    if not req.use_product:
        return []
    raws: list[bytes] = []
    if product_bytes:
        raws = [product_bytes]
    elif req.product_images:
        for u in req.product_images:
            b = await assets.fetch_bytes(u)
            if b:
                raws.append(b)
    else:
        candidates = ([info["og_image"]] if info.get("og_image") else []) + \
            info.get("images", [])
        for u in candidates[:GIF_MAX_FRAMES]:
            b = await assets.fetch_bytes(u)
            if b:
                raws.append(b)
    return [p for p in (_process(r) for r in raws) if p]


async def _layout(spec, p, i, ratio_key, cache, context, v):
    """Decide (fondo, producto, es_foto_producto) para un tamaño e imagen."""
    if spec.height <= 120:                          # tira ancha: producto junto al logo
        prod_raw = (p.get("cutout") or p.get("full")) if p else None
        return None, prod_raw, False
    if p and p.get("full"):                         # foto como fondo
        return p["full"], None, True
    if ratio_key not in cache[i]:                   # fondo generado
        gw, gh = _gen_dims(spec)
        cache[i][ratio_key] = await imagegen.generate_image(
            v.get("image_prompt") or context[:200], gw, gh
        )
    return cache[i][ratio_key], (p["cutout"] if p else None), False


async def run_pipeline(jid, req, logo_bytes, product_bytes) -> None:
    try:
        await models.update_job(jid, status="running")

        info = {}
        if req.url:
            info = await scraper.scrape(runtime.browser, req.url)
            context = f"{info['title']}\n{info['description']}\n{info['text']}"
            if req.brief:
                context += f"\n\nNotas del usuario: {req.brief}"
        else:
            context = req.brief or ""

        logo = assets.normalize_image(logo_bytes)
        if logo is None and info.get("logo_url"):
            logo = assets.normalize_image(await assets.fetch_bytes(info["logo_url"]))

        if req.manual_headline or req.manual_body or req.manual_cta:
            # Usar textos manuales: crear n_variants copias del mismo copy
            v = {
                "angle": "manual",
                "headline": req.manual_headline or "",
                "body": req.manual_body or "",
                "cta": req.manual_cta or "",
                "image_prompt": context[:200],
            }
            variants = [v] * req.n_variants
        else:
            variants = await llm.generate_copy(
                context, n=req.n_variants, language=req.language
            )



        
        n = len(variants)

        processed = await _processed_list(req, info, product_bytes)
        products = ([processed[i % len(processed)] for i in range(n)]
                    if processed else [None] * n)
        gif_srcs = processed[:GIF_MAX_FRAMES] or [None]   # imágenes que rotan

        fmt = (req.output_format or "png").lower()
        ext = {"gif": "gif", "jpg": "jpg"}.get(fmt, "png")

        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cache: list[dict] = [{} for _ in variants]
        creatives: list[dict] = []

        for plat in req.platforms:
            spec = PLATFORMS[plat]
            ratio_key = round(spec.width / spec.height, 2)
            for i, v in enumerate(variants):
               kw = dict(
                   headline=v.get("headline", ""), body=v.get("body", ""),
                   cta=v.get("cta", ""), brand_color=req.brand_color,
                   accent_color=req.accent_color, logo=logo, template=req.template,
                   font_url=req.manual_font_url or info.get("typography", {}).get("google_fonts", [None])[0],
                   # ↑ usa la fuente manual si existe, sino la primera detectada en la web
               )
                if fmt == "gif":
                    frames = []
                    for p in gif_srcs:
                        bg, product, isp = await _layout(
                            spec, p, i, ratio_key, cache, context, v
                        )
                        frames.append(await composer.compose(
                            runtime.browser, spec, background=bg,
                            product=product, image_is_product=isp, **kw,
                        ))
                    data = animate.make_gif(frames, GIF_SECONDS)
                else:
                    bg, product, isp = await _layout(
                        spec, products[i], i, ratio_key, cache, context, v
                    )
                    png, last_html = await composer.compose(
                        runtime.browser, spec, background=bg,
                        product=product, image_is_product=isp, **kw,
                    )
                    data = animate.to_jpg(png) if ext == "jpg" else png

                fname = f"{jid}_{plat}_{i + 1}.{ext}"
                (out_dir / fname).write_bytes(data)
                creatives.append({
                    "platform": plat, "label": spec.label,
                    "width": spec.width, "height": spec.height,
                    "angle": v.get("angle", ""), "headline": v.get("headline", ""),
                    "body": v.get("body", ""), "cta": v.get("cta", ""),
                    "image_path": f"/outputs/{fname}",
                    "html_path": f"/outputs/{html_fname}",   # ← añadir
                })
                await models.update_job(jid, creatives=creatives)

        await models.update_job(jid, status="done", creatives=creatives)
    except Exception as e:  # noqa: BLE001
        await models.update_job(jid, status="error", error=f"{type(e).__name__}: {e}")
