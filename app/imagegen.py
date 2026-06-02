import asyncio
import io
import json
import random

import httpx
from PIL import Image

from .config import settings


async def generate_image(prompt: str, width: int, height: int) -> bytes:
    """Devuelve PNG (bytes). El composer lo recorta con CSS cover, así que
    el tamaño exacto no es crítico, solo la proporción."""
    if settings.image_provider == "comfyui":
        return await _comfyui(prompt, width, height)
    return _placeholder(prompt, width, height)


# ------------------------- placeholder (sin GPU) -------------------------
def _placeholder(prompt: str, width: int, height: int) -> bytes:
    """Gradiente determinista derivado del prompt. Permite probar el
    pipeline completo sin modelo de imagen."""
    random.seed(sum(ord(c) for c in prompt) or 1)
    c1 = tuple(random.randint(15, 80) for _ in range(3))
    c2 = tuple(random.randint(90, 210) for _ in range(3))
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        row = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        for x in range(width):
            px[x, y] = row
    return _to_png(img)


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ------------------------------- ComfyUI --------------------------------
# Convención: en el workflow JSON, marca el nodo de prompt con
# _meta.title == "adgen_prompt" y el nodo de latente con "adgen_latent".
async def _comfyui(prompt: str, width: int, height: int) -> bytes:
    with open(settings.comfyui_workflow) as f:
        wf = json.load(f)

    for node in wf.values():
        title = node.get("_meta", {}).get("title", "")
        if title == "adgen_prompt":
            node["inputs"]["text"] = prompt
        elif title == "adgen_latent":
            node["inputs"]["width"] = width
            node["inputs"]["height"] = height

    async with httpx.AsyncClient(timeout=600) as client:
        q = await client.post(f"{settings.comfyui_url}/prompt", json={"prompt": wf})
        q.raise_for_status()
        pid = q.json()["prompt_id"]

        # Espera a que el historial tenga el resultado.
        for _ in range(600):  # ~600 s máx
            h = await client.get(f"{settings.comfyui_url}/history/{pid}")
            hist = h.json()
            if pid in hist:
                outputs = hist[pid].get("outputs", {})
                for node_out in outputs.values():
                    if "images" in node_out:
                        info = node_out["images"][0]
                        img = await client.get(
                            f"{settings.comfyui_url}/view",
                            params={
                                "filename": info["filename"],
                                "subfolder": info.get("subfolder", ""),
                                "type": info.get("type", "output"),
                            },
                        )
                        return img.content
            await asyncio.sleep(1.0)

    raise RuntimeError("ComfyUI: timeout esperando la imagen")
