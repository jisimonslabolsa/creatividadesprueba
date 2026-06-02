import json
import time
import uuid

import aiosqlite
from pydantic import BaseModel

from .config import settings


# --------------------------- esquemas de API ---------------------------
class GenerateRequest(BaseModel):
    url: str | None = None
    brief: str | None = None
    platforms: list[str]               # uno o varios tamaños
    template: str | None = None
    n_variants: int = 4
    language: str = "es"
    brand_color: str = "#111114"
    accent_color: str = "#ff4d2e"
    use_product: bool = True           # incluir imagen de producto (subida o web)
    product_images: list[str] = []     # URLs elegidas en la UI (una por variante)


class Creative(BaseModel):
    platform: str                      # clave del tamaño
    label: str                         # etiqueta legible
    width: int
    height: int
    angle: str
    headline: str
    body: str
    cta: str
    image_path: str


class Job(BaseModel):
    id: str
    status: str                        # queued | running | done | error
    platforms: list[str] = []
    error: str | None = None
    creatives: list[Creative] = []


# --------------------------- almacén SQLite ----------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
    id       TEXT PRIMARY KEY,
    status   TEXT,
    summary  TEXT,
    error    TEXT,
    data     TEXT,
    created  REAL
)
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(_SCHEMA)
        await db.commit()


async def create_job(platforms: list[str]) -> str:
    jid = uuid.uuid4().hex[:12]
    data = {"creatives": [], "platforms": platforms}
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO jobs VALUES (?,?,?,?,?,?)",
            (jid, "queued", f"{len(platforms)} tamaños", None, json.dumps(data), time.time()),
        )
        await db.commit()
    return jid


async def update_job(jid: str, *, status=None, error=None, creatives=None) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute("SELECT status, error, data FROM jobs WHERE id=?", (jid,))
        row = await cur.fetchone()
        if not row:
            return
        cur_status, cur_err, data = row
        d = json.loads(data)
        if creatives is not None:
            d["creatives"] = creatives
        await db.execute(
            "UPDATE jobs SET status=?, error=?, data=? WHERE id=?",
            (
                status or cur_status,
                error if error is not None else cur_err,
                json.dumps(d),
                jid,
            ),
        )
        await db.commit()


async def get_job(jid: str) -> Job | None:
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT id, status, error, data FROM jobs WHERE id=?", (jid,)
        )
        row = await cur.fetchone()
    if not row:
        return None
    id_, status, error, data = row
    d = json.loads(data)
    return Job(
        id=id_,
        status=status,
        error=error,
        platforms=d.get("platforms", []),
        creatives=[Creative(**c) for c in d.get("creatives", [])],
    )


async def list_jobs(limit: int = 20) -> list[dict]:
    """Resumen ligero de los jobs recientes, para el historial de la UI."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT id, status, summary, data, created FROM jobs "
            "ORDER BY created DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
    out = []
    for id_, status, summary, data, created in rows:
        d = json.loads(data)
        creatives = d.get("creatives", [])
        out.append(
            {
                "id": id_,
                "status": status,
                "summary": summary,
                "created": created,
                "count": len(creatives),
                "thumb": creatives[0]["image_path"] if creatives else None,
            }
        )
    return out
