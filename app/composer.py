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


def _is_banner(spec: PlatformSpec) -> bool:
    area = spec.width * spec.height
    ratio = spec.width / spec.height
    return area <= 336 * 280 or ratio >= 3 or spec.height <= 120


def _pick_template(spec, requested, has_product) -> str:
    if requested:
        return requested
    if _is_banner(spec):
        return "banner.html"
    if has_product:
        return "product.html"   # producto recortado en primer plano
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
    product: bytes | None = None,   # recorte del producto (RGBA) en primer plano
    template: str | None = None,
) -> bytes:
    template_name = _pick_template(spec, template, product is not None)
    tmpl = _env.get_template(template_name)

    html = tmpl.render(
        width=spec.width,
        height=spec.height,
        wide=(spec.width / spec.height) > 2.5,
        layout="side" if (spec.width / spec.height) > 1.3 else "stack",
        background=_data_uri(background) if background else None,
        logo=_data_uri(logo) if logo else None,
        product=_data_uri(product) if product else None,
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
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate("() => document.fonts.ready")
        return await page.screenshot(type="png")
    finally:
        await page.close()
