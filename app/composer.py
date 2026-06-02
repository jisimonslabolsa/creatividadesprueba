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


def _data_uri(image_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def _pick_template(spec: PlatformSpec, requested: str | None) -> str:
    """Selección automática: los formatos pequeños de display usan la
    plantilla compacta; el resto, el full-bleed."""
    if requested:
        return requested
    area = spec.width * spec.height
    ratio = spec.width / spec.height
    if area <= 336 * 280 or ratio >= 3 or spec.height <= 120:
        return "banner.html"
    return "spotlight.html"


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
    template: str | None = None,
) -> bytes:
    """Compone un anuncio: visual de fondo + texto como capa real, al tamaño
    exacto de la plataforma. Devuelve PNG en bytes."""
    template_name = _pick_template(spec, template)
    tmpl = _env.get_template(template_name)

    html = tmpl.render(
        width=spec.width,
        height=spec.height,
        wide=(spec.width / spec.height) > 2.5,
        background=_data_uri(background) if background else None,
        logo=_data_uri(logo) if logo else None,
        headline=headline,
        body=body,
        cta=cta,
        brand_color=brand_color,
        accent_color=accent_color,
        font_url=settings.default_font_url,
        display_font=settings.default_display_font,
        body_font=settings.default_body_font,
    )

    page = await browser.new_page(
        viewport={"width": spec.width, "height": spec.height},
        device_scale_factor=1,
    )
    try:
        # networkidle espera a que cargue la fuente de Google; fonts.ready
        # garantiza que el texto se mida con la tipografía correcta.
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate("() => document.fonts.ready")
        return await page.screenshot(type="png")  # viewport = tamaño exacto
    finally:
        await page.close()
