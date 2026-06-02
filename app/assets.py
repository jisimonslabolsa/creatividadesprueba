import io

import httpx
from PIL import Image

# Cabeceras de navegador: muchas tiendas/CDN bloquean clientes sin User-Agent.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}


async def fetch_bytes(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            timeout=25, follow_redirects=True, headers=_HEADERS
        ) as c:
            r = await c.get(url)
            r.raise_for_status()
            return r.content
    except Exception:
        return None


def scale(raw: bytes | None, factor: float) -> bytes | None:
    """Reduce un PNG por un factor (0.6 = -40%) manteniendo transparencia."""
    if not raw:
        return None
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        w, h = int(img.width * factor), int(img.height * factor)
        img = img.resize((max(w, 1), max(h, 1)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return raw

def normalize_image(raw: bytes | None, max_side: int = 1600) -> bytes | None:
    """Convierte a PNG RGBA y acota el tamaño (logos, o imagen como fondo)."""
    if not raw:
        return None
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def cutout(raw: bytes | None, max_side: int = 1600) -> bytes | None:
    """Recorta el fondo del producto con rembg. PNG RGBA, o None si no se puede."""
    if not raw:
        return None
    try:
        from rembg import remove  # dependencia opcional, import perezoso
    except Exception:
        return None
    try:
        cut = remove(raw)
        img = Image.open(io.BytesIO(cut)).convert("RGBA")
        bbox = img.split()[-1].getbbox()
        if bbox:
            img = img.crop(bbox)
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None
