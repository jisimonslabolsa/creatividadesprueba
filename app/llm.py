import json

import httpx

from .config import settings

SYSTEM = (
    "Eres un director creativo experto en publicidad de respuesta directa. "
    "Generas conceptos de anuncio listos para producir. "
    "Respondes SIEMPRE con JSON válido y nada más."
)

PROMPT = """Producto / oferta:
{context}

Idioma de salida del copy: {language}

Genera {n} conceptos de anuncio DISTINTOS. Cada uno debe usar un ángulo diferente
(beneficio principal, dolor/problema, prueba social, urgencia, curiosidad, etc.).

Devuelve EXACTAMENTE este JSON:
{{"variants":[
  {{"angle":"nombre corto del ángulo",
    "headline":"titular de máx. 8 palabras, con gancho",
    "body":"una frase de apoyo, máx. 18 palabras",
    "cta":"llamada a la acción de 2-4 palabras",
    "image_prompt":"prompt EN INGLÉS para un modelo de imagen: escena, sujeto, estilo, iluminación, composición. SIN texto en la imagen."}}
]}}"""


async def generate_copy(context: str, n: int = 4, language: str = "es") -> list[dict]:
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": PROMPT.format(context=context[:6000], n=n, language=language),
        },
    ]
    if settings.llm_provider == "ollama":
        return await _ollama(messages, n)
    return await _mistral(messages, n)


# ------------------------------- Mistral --------------------------------
async def _mistral(messages: list[dict], n: int) -> list[dict]:
    if not settings.mistral_api_key:
        raise RuntimeError(
            "Falta la clave de Mistral. Define ADGEN_MISTRAL_API_KEY "
            "(consíguela en https://console.mistral.ai)."
        )
    payload = {
        "model": settings.mistral_model,
        "messages": messages,
        "response_format": {"type": "json_object"},  # modo JSON de Mistral
        "temperature": settings.llm_temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{settings.mistral_url}/chat/completions", json=payload, headers=headers
        )
        r.raise_for_status()
        data = r.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content).get("variants", [])[:n]


# ------------------------------- Ollama ---------------------------------
async def _ollama(messages: list[dict], n: int) -> list[dict]:
    payload = {
        "model": settings.ollama_model,
        "format": "json",
        "stream": False,
        "messages": messages,
        "options": {"temperature": settings.llm_temperature},
    }
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
    content = data["message"]["content"]
    return json.loads(content).get("variants", [])[:n]
