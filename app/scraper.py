import re


async def scrape(browser, url: str) -> dict:
    """Extrae título, descripción, og:image, logo, texto e imágenes candidatas
    (gestionando carga diferida y filtrando logos/banners)."""
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(800)

        # Provoca la carga diferida (lazy-load) recorriendo la página.
        await page.evaluate(
            """async () => {
                await new Promise(res => {
                    let y = 0;
                    const id = setInterval(() => {
                        window.scrollBy(0, 900); y += 900;
                        if (y >= document.body.scrollHeight || y > 9000) { clearInterval(id); res(); }
                    }, 110);
                });
                window.scrollTo(0, 0);
            }"""
        )
        await page.wait_for_timeout(600)

        title = await page.title()

        meta = await page.evaluate(
            """() => {
                const g = (s) => { const m = document.querySelector(s); return m ? (m.content || '') : ''; };
                const logoEl = document.querySelector('link[rel="apple-touch-icon"]')
                            || document.querySelector('link[rel="icon"][sizes]')
                            || document.querySelector('link[rel~="icon"]');
                return {
                    desc: g('meta[name="description"]') || g('meta[property="og:description"]'),
                    og_image: g('meta[property="og:image"]'),
                    logo: logoEl ? logoEl.href : ''
                };
            }"""
        )

        # Imágenes: lee atributos (no depende de que estén cargadas), filtra
        # logos/iconos/banners de menú y prioriza imágenes de producto.
        images = await page.evaluate(
            """() => {
                const bad = /sprite|logo|icon|placeholder|loader|spinner|pixel|blank|\\.svg(\\?|$)|^data:|\\/img\\/pmenu\\/|\\/img\\/cms\\/|\\/themes\\/|\\/modules\\//i;
                const urls = [];
                const add = u => { if (u && /^https?:\\/\\//.test(u) && !bad.test(u)) urls.push(u); };
                document.querySelectorAll('img').forEach(img => {
                    const ss = img.getAttribute('srcset') || img.getAttribute('data-srcset');
                    if (ss) add(ss.split(',').map(s => s.trim().split(' ')[0]).pop());
                    add(img.getAttribute('data-full-size-image-url'));
                    add(img.getAttribute('data-src'));
                    add(img.currentSrc || img.src);
                });
                const score = u => (/_default\\//.test(u) ? 0 : 1);   // producto primero
                return [...new Set(urls)].sort((a, b) => score(a) - score(b)).slice(0, 20);
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
            "description": meta["desc"],
            "og_image": meta["og_image"],
            "logo_url": meta["logo"],
            "images": images,
            "text": text,
        }
    finally:
        await page.close()
