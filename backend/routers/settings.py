import os
import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db_path
from fastapi.responses import HTMLResponse
from services.config import get_all_config, get_config_section, masked_config, set_config_section
from services.jira_oauth import build_auth_url, clear_tokens, exchange_code, get_status
from services.ticketing import TicketingError, _validate_jira_config
from services.jira_oauth import get_token as get_oauth_token

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


@router.post("/settings/jira/oauth/start")
async def jira_oauth_start():
    config = await get_config_section("ticketing")
    client_id = config.get("jira_oauth_client_id", "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail="Jira OAuth client_id is not configured. Add it in Settings → Jira.")
    auth_url, _state = build_auth_url(client_id)
    return {"auth_url": auth_url}


@router.get("/settings/jira/oauth/callback")
async def jira_oauth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        return HTMLResponse(
            f"<html><body><h2>Jira login failed</h2><p>{error_description or error}</p>"
            "<p>You can close this tab and return to Caret.</p></body></html>",
            status_code=400,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state in OAuth callback.")
    config = await get_config_section("ticketing")
    client_id = config.get("jira_oauth_client_id", "").strip()
    client_secret = os.environ.get("CARET_JIRA_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return HTMLResponse(
            "<html><body><h2>Configuration error</h2><p>OAuth credentials are not fully configured in Caret.</p></body></html>",
            status_code=400,
        )
    try:
        result = await exchange_code(code, state, client_id, client_secret)
    except ValueError as exc:
        return HTMLResponse(
            f"<html><body><h2>Jira login failed</h2><p>{exc}</p>"
            "<p>You can close this tab and return to Caret.</p></body></html>",
            status_code=400,
        )
    return HTMLResponse(
        f"<html><body><h2>Connected to Jira</h2>"
        f"<p>Site: <strong>{result['site_name']}</strong></p>"
        "<p>You can close this tab and return to Caret.</p></body></html>"
    )


@router.get("/settings/jira/oauth/status")
async def jira_oauth_status():
    return await get_status()


@router.delete("/settings/jira/oauth")
async def jira_oauth_signout():
    await clear_tokens()
    return {"ok": True}


@router.post("/settings/jira/test")
async def test_jira_connection():
    import asyncio, base64, json, urllib.request as _req, urllib.error as _err

    try:
        config = await get_config_section("ticketing")
        oauth = await get_oauth_token()
        if oauth:
            base_url = oauth["cloud_url"]
            auth_header = f"Bearer {oauth['access_token']}"
        else:
            _validate_jira_config(config)
            base_url = config["jira_base_url"].rstrip("/")
            auth_header = "Basic " + base64.b64encode(
                f"{config['jira_user_email']}:{config['jira_api_token']}".encode()
            ).decode()

        url = base_url + "/rest/api/3/myself"

        def _check():
            r = _req.Request(url, headers={"Authorization": auth_header, "Accept": "application/json"})
            try:
                with _req.urlopen(r, timeout=10) as resp:
                    data = json.loads(resp.read())
                    return data.get("displayName") or data.get("emailAddress") or "OK"
            except _err.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                raise TicketingError(f"Jira auth failed ({exc.code}): {detail or exc.reason}") from exc
            except _err.URLError as exc:
                raise TicketingError(f"Could not reach Jira: {exc.reason}") from exc

        display_name = await asyncio.to_thread(_check)
        return {"ok": True, "authenticated_as": display_name, "method": "oauth" if oauth else "basic"}
    except TicketingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/settings/config/{section}")
async def update_settings_config(section: str, body: ConfigSectionBody):
    try:
        config = await set_config_section(section, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "section": section, "config": masked_config({section: config})[section]}
