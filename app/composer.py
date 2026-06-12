import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import settings
from .platforms import PlatformSpec

TEMPLATE_DIR = Path(__file__).parent.parent / "composition" / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

# Tamaños con tratamiento especial del logo / imagen.
NARROW = {(160, 600), (120, 600), (300, 600)}      # logo a todo el ancho
CONTAIN = {(120, 600), (300, 1050)}                # imagen sin recortar (contain)


def _data_uri(image_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def _text_on(hex_color: str) -> str:
    """Negro o blanco según el brillo del color de marca (para el panel)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#ffffff"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#0c0c0e" if lum > 140 else "#ffffff"


def _is_banner(spec: PlatformSpec) -> bool:
    area = spec.width * spec.height
    ratio = spec.width / spec.height
    # Cajas pequeñas casi cuadradas, tiras anchas, o muy bajas.
    return (area <= 336 * 280 and 0.5 <= ratio <= 2) or ratio >= 3 or spec.height <= 120


def _pick_template(spec, requested, has_product, image_is_product) -> str:
    if requested:
        return requested
    if _is_banner(spec):
        return "banner.html"
    if has_product:
        return "product.html"        # producto recortado en primer plano
    return "spotlight.html"          # texto sobre la imagen (sin bandas)


async def compose(
    browser,
    spec: PlatformSpec,
    *,
    background: bytes | None,
    headline: str,
    body: str,
    cta: str,
    brand_color: str = "#111114",
    accent_color: str = "#ff4d2e",
    logo: bytes | None = None,
    product: bytes | None = None,        # recorte del producto (primer plano)
    image_is_product: bool = False,      # el fondo es una foto de producto
    template: str | None = None,
    font_url: str | None = None,   # ← añadir
) -> tuple[bytes, str]:            # ← cambiar tipo de retorno
    template_name = _pick_template(
        spec, template, product is not None, image_is_product
    )
    tmpl = _env.get_template(template_name)

    html = tmpl.render(
        width=spec.width,
        height=spec.height,
        wide=spec.height <= 120,                       # banner ancho (tira)
        narrow=(spec.width, spec.height) in NARROW,    # logo a todo el ancho
        contain=(spec.width, spec.height) in CONTAIN,  # imagen sin recortar
        layout="side" if (spec.width / spec.height) > 1.3 else "stack",
        orient="v" if (spec.width / spec.height) >= 1.2 else "h",
        background=_data_uri(background) if background else None,
        logo=_data_uri(logo) if logo else None,
        product=_data_uri(product) if product else None,
        headline=headline,
        body=body,
        cta=cta,
        brand_color=brand_color,
        accent_color=accent_color,
        panel_text=_text_on(brand_color),
        font_url=settings.default_font_url,
        display_font=settings.default_display_font,
        body_font=settings.default_body_font,
        font_url=font_url or settings.default_font_url,  # ← sustituir settings.default_font_url
        display_font=settings.default_display_font,
        body_font=settings.default_body_font,
    )

    page = await browser.new_page(
        viewport={"width": spec.width, "height": spec.height},
        device_scale_factor=1,
    )
    try:
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate("() => document.fonts.ready")
        png = await page.screenshot(type="png")
        return png, html    finally:
        await page.close()
