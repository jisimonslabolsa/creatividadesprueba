# Navegador Playwright compartido entre scraper y composer.
# Se inicializa en el lifespan de main.py y se reutiliza en todo el proceso
# para no pagar el arranque de Chromium en cada render.
browser = None  # type: ignore
