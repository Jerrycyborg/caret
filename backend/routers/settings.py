import os
import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db_path

router = APIRouter()

PROVIDER_ENV_MAP: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "azure": "AZURE_API_KEY",
    "ollama": "OLLAMA_API_BASE",
}


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("/settings/keys")
async def list_keys():
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT provider, key_value, updated_at FROM api_keys"
        ) as cur:
            rows = await cur.fetchall()
    return {
        "keys": [
            {"provider": r["provider"], "masked": _mask(r["key_value"]), "updated_at": r["updated_at"]}
            for r in rows
        ]
    }


class SetKeyBody(BaseModel):
    value: str


@router.put("/settings/keys/{provider}")
async def set_key(provider: str, body: SetKeyBody):
    if provider not in PROVIDER_ENV_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    if not body.value.strip():
        raise HTTPException(status_code=422, detail="Key value cannot be empty")
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO api_keys (provider, key_value) VALUES (?, ?) "
            "ON CONFLICT(provider) DO UPDATE SET key_value=excluded.key_value, "
            "updated_at=datetime('now')",
            (provider, body.value.strip()),
        )
        await db.commit()
    # Apply immediately to running process so LiteLLM uses it without restart
    os.environ[PROVIDER_ENV_MAP[provider]] = body.value.strip()
    return {"ok": True, "provider": provider}


@router.delete("/settings/keys/{provider}")
async def delete_key(provider: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute("DELETE FROM api_keys WHERE provider = ?", (provider,))
        await db.commit()
    env_key = PROVIDER_ENV_MAP.get(provider)
    if env_key and env_key in os.environ:
        del os.environ[env_key]
    return {"ok": True}
