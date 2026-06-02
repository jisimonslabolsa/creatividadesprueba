import re


async def scrape(browser, url: str) -> dict:
    """Extrae título, descripción, og:image, una posible URL de logo y el
    texto principal de una landing."""
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(800)

        title = await page.title()

        desc = await page.evaluate(
            """() => {
                const m = document.querySelector('meta[name="description"]')
                       || document.querySelector('meta[property="og:description"]');
                return m ? m.content : '';
            }"""
        )

        og_image = await page.evaluate(
            """() => {
                const m = document.querySelector('meta[property="og:image"]');
                return m ? m.content : '';
            }"""
        )

        # Mejor candidato a logo: apple-touch-icon o icono de mayor tamaño.
        logo_url = await page.evaluate(
            """() => {
                const pick = document.querySelector('link[rel="apple-touch-icon"]')
                          || document.querySelector('link[rel="icon"][sizes]')
                          || document.querySelector('link[rel~="icon"]');
                return pick ? pick.href : '';
            }"""
        )

        text = await page.evaluate(
            """() => {
                ['script','style','nav','footer','header','noscript','svg']
                    .forEach(t => document.querySelectorAll(t).forEach(e => e.remove()));
                return document.body ? document.body.innerText : '';
            }"""
        )
        text = re.sub(r"\n{2,}", "\n", text or "").strip()[:4000]

        return {
            "url": url,
            "title": title,
            "description": desc,
            "og_image": og_image,
            "logo_url": logo_url,
            "text": text,
        }
    finally:
        await page.close()
