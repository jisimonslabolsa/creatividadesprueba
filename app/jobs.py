from pathlib import Path

from . import assets, composer, imagegen, llm, models, runtime, scraper
from .config import settings
from .platforms import PLATFORMS


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


async def _resolve_products(req, info, product_bytes, n) -> list:
    """Devuelve una lista de longitud n (una entrada por variante). Cada entrada
    es {cutout|full} o None.
    Prioridad: imagen subida (misma para todas) > imágenes elegidas en la UI
    (una por variante) > primeras imágenes de la web (una por variante)."""
    if not req.use_product:
        return [None] * n

    raws: list[bytes] = []
    if product_bytes:
        raws = [product_bytes]                       # subida: una para todas
    elif req.product_images:                         # selección manual (URLs)
        for u in req.product_images:
            b = await assets.fetch_bytes(u)
            if b:
                raws.append(b)
    else:                                            # auto: primeras de la web
        candidates = ([info["og_image"]] if info.get("og_image") else []) + \
            info.get("images", [])
        for u in candidates[:n]:
            b = await assets.fetch_bytes(u)
            if b:
                raws.append(b)

    processed = [p for p in (_process(r) for r in raws) if p]
    if not processed:
        return [None] * n
    # alinea con variantes; si hay menos imágenes, se reutilizan en ciclo
    return [processed[i % len(processed)] for i in range(n)]


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

        variants = await llm.generate_copy(
            context, n=req.n_variants, language=req.language
        )
        n = len(variants)
        products = await _resolve_products(req, info, product_bytes, n)

        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cache: list[dict] = [{} for _ in variants]   # fondos generados, por proporción
        creatives: list[dict] = []

        for plat in req.platforms:
            spec = PLATFORMS[plat]
            ratio_key = round(spec.width / spec.height, 2)
            for i, v in enumerate(variants):
                p = products[i] if i < len(products) else None
                if p and p.get("full"):
                    bg, product = p["full"], None          # imagen como fondo
                    img_is_product = True
                else:
                    if ratio_key not in cache[i]:          # fondo generado
                        gw, gh = _gen_dims(spec)
                        cache[i][ratio_key] = await imagegen.generate_image(
                            v.get("image_prompt") or context[:200], gw, gh
                        )
                    bg = cache[i][ratio_key]
                    product = p["cutout"] if p else None   # producto en primer plano
                    img_is_product = False

                png = await composer.compose(
                    runtime.browser, spec,
                    background=bg,
                    headline=v.get("headline", ""),
                    body=v.get("body", ""),
                    cta=v.get("cta", ""),
                    brand_color=req.brand_color,
                    accent_color=req.accent_color,
                    logo=logo,
                    product=product,
                    image_is_product=img_is_product,
                    template=req.template,
                )
                fname = f"{jid}_{plat}_{i + 1}.png"
                (out_dir / fname).write_bytes(png)
                creatives.append({
                    "platform": plat, "label": spec.label,
                    "width": spec.width, "height": spec.height,
                    "angle": v.get("angle", ""), "headline": v.get("headline", ""),
                    "body": v.get("body", ""), "cta": v.get("cta", ""),
                    "image_path": f"/outputs/{fname}",
                })
                await models.update_job(jid, creatives=creatives)

        await models.update_job(jid, status="done", creatives=creatives)
    except Exception as e:  # noqa: BLE001
        await models.update_job(jid, status="error", error=f"{type(e).__name__}: {e}")
