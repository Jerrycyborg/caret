import os
import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db_path
from services.config import get_all_config, masked_config, set_config_section

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
    keys = []
    for provider, env_key in PROVIDER_ENV_MAP.items():
        value = os.environ.get(env_key, "").strip()
        if value:
            keys.append({"provider": provider, "masked": _mask(value), "updated_at": "runtime"})
    return {
        "keys": keys
    }


class SetKeyBody(BaseModel):
    value: str


@router.put("/settings/keys/{provider}")
async def set_key(provider: str, body: SetKeyBody):
    if provider not in PROVIDER_ENV_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    if not body.value.strip():
        raise HTTPException(status_code=422, detail="Key value cannot be empty")
    os.environ[PROVIDER_ENV_MAP[provider]] = body.value.strip()
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute("DELETE FROM api_keys WHERE provider = ?", (provider,))
        await db.commit()
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


@router.get("/settings/config")
async def get_settings_config():
    config = await get_all_config()
    return {"config": masked_config(config)}


class ConfigSectionBody(BaseModel):
    value: dict


@router.put("/settings/config/{section}")
async def update_settings_config(section: str, body: ConfigSectionBody):
    try:
        config = await set_config_section(section, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "section": section, "config": masked_config({section: config})[section]}
