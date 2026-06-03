import io

from PIL import Image


def make_gif(frames_png: list[bytes], seconds_per_frame: int = 3) -> bytes:
    """Ensambla un GIF animado a partir de PNGs (un fotograma por imagen)."""
    imgs = []
    for f in frames_png:
        im = Image.open(io.BytesIO(f)).convert("RGB")
        imgs.append(im.convert("P", palette=Image.ADAPTIVE, colors=256))
    out = io.BytesIO()
    imgs[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=imgs[1:],
        duration=int(seconds_per_frame * 1000),
        loop=0,
        disposal=2,
        optimize=True,
    )
    return out.getvalue()


def to_jpg(png: bytes, quality: int = 88) -> bytes:
    """Convierte un PNG a JPEG (aplana el alfa sobre blanco)."""
    im = Image.open(io.BytesIO(png)).convert("RGB")
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()
