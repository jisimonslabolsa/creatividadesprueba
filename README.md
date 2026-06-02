# AdGen — generador de anuncios (uso personal)

Backend + capa de composición para generar creatividades de anuncio (imagen)
a partir de una URL de producto o un brief. Un solo proceso, sin créditos,
sin login. El vídeo queda fuera por ahora.

## Cómo funciona

```
URL / brief  ─►  Scraper (Playwright)  ─►  LLM copy+ángulos (Ollama)
                                                   │
                          ┌────────────────────────┘
                          ▼
            Imagen de fondo (ComfyUI / placeholder)
                          │
                          ▼
   Composición: plantilla HTML + texto en CAPA REAL ─► PNG por plataforma
```

La idea clave de la composición: **el visual lo genera la IA, pero el texto NO**.
El texto se compone como una capa HTML/CSS que Playwright renderiza a PNG al
tamaño exacto de cada plataforma. Así el texto siempre sale nítido y legible
(los modelos de difusión rotulan mal).

## Requisitos

- Python 3.11+
- Una clave de la API de [Mistral](https://console.mistral.ai) para el copy
  (su tier gratuito basta para uso personal). Alternativa local: Ollama.
- (Opcional) [ComfyUI](https://github.com/comfyanonymous/ComfyUI) para imágenes reales

Sin ComfyUI el sistema usa el proveedor de imagen `placeholder` (gradientes),
así que puedes ver el pipeline completo en cuanto tengas la clave de Mistral.

## Instalación

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### Recorte de fondo del producto (opcional)

Para que el producto aparezca recortado en primer plano (en vez de como fondo),
instala `rembg`:

```bash
pip install rembg onnxruntime
```

La primera vez descarga un modelo (~170 MB). Para incluirlo en Docker, añade esa
línea al `Dockerfile`. Si no lo instalas, todo sigue funcionando: la imagen del
producto se usa como fondo a sangre.

## Arrancar (local)

```bash
export ADGEN_MISTRAL_API_KEY="tu-clave"     # imprescindible para el copy
uvicorn app.main:app --reload
```

Abre `http://localhost:8000` y usa la interfaz web. Docs de la API en `/docs`.

## Despliegue en Portainer

El proyecto se sirve en un único contenedor (API + interfaz). Dos métodos:

**A) Build desde repositorio (recomendado).** En Portainer → Stacks → Add stack →
Build method: *Repository*. Apunta a tu repositorio Git con este proyecto y a
`docker-compose.yml`. En *Environment variables* añade al menos
`ADGEN_MISTRAL_API_KEY`. Deploy.

**B) Imagen prebuilt.** Construye la imagen una vez en el host del Docker:

```bash
docker build -t adgen:latest .
```

Edita `docker-compose.yml` (comenta `build: .`, descomenta `image: adgen:latest`),
crea el stack pegando el compose en el editor web de Portainer y define
`ADGEN_MISTRAL_API_KEY` en las variables del stack.

La app queda en `http://<host>:8000`. Los datos (creatividades + base de datos)
persisten en el volumen `adgen_data`.

> Si usas ComfyUI en el propio host, `host.docker.internal` ya está mapeado en el
> compose para alcanzarlo desde el contenedor.

## Interfaz web

En `http://localhost:8000`:

- **URL** de la página sobre la que crear las creatividades.
- **Briefing** opcional (tono, ofertas, ideas de imagen). Si se deja vacío, la IA
  se basa solo en el contenido de la URL.
- **Logotipo** opcional. Si no se sube, se intenta extraer de la web
  (apple-touch-icon / favicon).
- **Imagen de producto** opcional. Si no se sube, se toma de la web (`og:image`
  o la imagen más grande). Si `rembg` está instalado y `ADGEN_REMOVE_PRODUCT_BG`
  está activo, se recorta el fondo y se compone el producto en primer plano sobre
  un fondo diseñado; si no, la imagen se usa como fondo a sangre. Desactívala con
  el checkbox si prefieres creatividades sin producto.
- **Elegir imágenes de la web**: el botón "Buscar imágenes de la URL" lista las
  imágenes detectadas en la página. Selecciona hasta tantas como variantes vayas
  a crear y se usará una distinta en cada variante (si eliges menos, se reutilizan
  en orden; si no eliges ninguna, se toman automáticamente).

Cuando la imagen principal es una foto de producto (sin recorte de fondo), la
creatividad usa un **layout en bandas**: la foto ocupa una zona y el texto va en
un panel sólido del color de marca en la zona libre, sin superposiciones ni
transparencias sobre la imagen. El logo se coloca en ese panel, por lo que
siempre queda visible. El reparto es lateral en formatos horizontales y
superior/inferior en verticales y cuadrados.
- **Tamaños**: catálogo completo IAB + Facebook + Instagram + TikTok, con botón
  "Todos" por categoría.

Las creatividades aparecen en la galería según se generan, con descarga directa.

## Uso por API (alternativa a la UI)

El endpoint es `multipart/form-data` (permite subir el logo):

```bash
curl localhost:8000/platforms      # catálogo de tamaños agrupado

curl -X POST localhost:8000/ads/generate \
  -F url="https://tu-producto.com" \
  -F brief="Tono fresco, oferta de lanzamiento" \
  -F platforms=ig_stories -F platforms=fb_feed_landscape -F platforms=iab_medium_rectangle \
  -F n_variants=3 \
  -F brand_color="#1b2a4a" -F accent_color="#ff5a36" \
  -F logo=@mi-logo.png        # opcional

curl localhost:8000/jobs/<job_id>  # estado + creatividades (incremental)
```

Los PNG quedan en el volumen de datos y se sirven en `/outputs/<archivo>.png`.

## Configuración

Variables de entorno con prefijo `ADGEN_` (ver `app/config.py`):

| Variable                 | Por defecto              | Qué hace                              |
|--------------------------|--------------------------|---------------------------------------|
| `ADGEN_LLM_PROVIDER`     | `mistral`                | `mistral` o `ollama`                  |
| `ADGEN_MISTRAL_API_KEY`  | *(vacío)*                | Tu clave de Mistral (obligatoria)     |
| `ADGEN_MISTRAL_MODEL`    | `mistral-large-latest`   | Modelo de Mistral para el copy        |
| `ADGEN_OLLAMA_MODEL`     | `qwen2.5:14b`            | Modelo si usas Ollama en local        |
| `ADGEN_LLM_TEMPERATURE`  | `0.8`                    | Creatividad del copy (0–1)            |
| `ADGEN_IMAGE_PROVIDER`   | `placeholder`            | `placeholder` o `comfyui`             |
| `ADGEN_REMOVE_PRODUCT_BG`| `true`                   | Recortar fondo del producto (usa rembg)|
| `ADGEN_COMFYUI_URL`      | `http://localhost:8188`  | Endpoint de ComfyUI                   |
| `ADGEN_COMFYUI_WORKFLOW` | `composition/workflows/txt2img.json` | Workflow exportado        |

### Cambiar de modelo o proveedor

Por defecto usa `mistral-large-latest` (mejor copy). Para gastar menos cuota del
tier gratuito puedes usar uno más ligero con `ADGEN_MISTRAL_MODEL=mistral-small-latest`.
Para volver a local sin API: `ADGEN_LLM_PROVIDER=ollama`.

### Conectar ComfyUI

1. En ComfyUI monta un workflow txt2img (FLUX, SDXL, etc.).
2. Renombra (botón derecho → Title) el nodo del prompt positivo a
   `adgen_prompt` y el nodo de latente vacío a `adgen_latent`.
3. Exporta con **Save (API Format)** a `composition/workflows/txt2img.json`.
4. Arranca con `ADGEN_IMAGE_PROVIDER=comfyui`.

El generador inyecta el `image_prompt` de cada variante en `adgen_prompt` y el
tamaño en `adgen_latent`. El resto del workflow es tuyo.

## Plantillas de composición

En `composition/templates/`:

- `spotlight.html` — visual a sangre + titular/CTA abajo con scrim. Para feeds,
  portrait, stories, landscape.
- `banner.html` — compacta, para formatos de display pequeños (300x250, 728x90…).

El compositor elige plantilla automáticamente según tamaño/proporción, o puedes
forzarla con `"template": "spotlight.html"` en la petición. Para añadir estilos
nuevos, crea otro `.html` con las mismas variables Jinja
(`headline`, `body`, `cta`, `background`, `logo`, `brand_color`, `accent_color`,
`width`, `height`, `wide`, fuentes) y referéncialo en la petición.

## Estructura

```
adgen/
  app/
    main.py        FastAPI: lifespan, endpoints, sirve la UI
    config.py      Settings
    platforms.py   Catálogo IAB + redes (agrupado)
    models.py      Esquemas + almacén SQLite de jobs
    scraper.py     URL -> info de producto + logo
    llm.py         Copy y ángulos (Mistral / Ollama)
    imagegen.py    Imagen (placeholder / ComfyUI)
    composer.py    *** capa de composición (HTML -> PNG) ***
    jobs.py        Orquestación (multi-tamaño, caché por proporción)
    runtime.py     Navegador compartido
  composition/
    templates/     plantillas HTML
    workflows/     workflow de ComfyUI (lo pones tú)
  web/
    index.html     interfaz de usuario (SPA vanilla JS)
  Dockerfile
  docker-compose.yml   stack para Portainer
  .env.example
  requirements.txt
```
