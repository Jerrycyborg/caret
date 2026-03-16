from __future__ import annotations

import asyncio
import json
import os
import secrets
import urllib.error as _err
import urllib.request as _req
from datetime import datetime, timedelta, timezone

import aiosqlite

from database import get_db_path

ATLASSIAN_AUTH_URL = "https://auth.atlassian.com/authorize"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
REDIRECT_URI = "http://localhost:8000/v1/settings/jira/oauth/callback"
SCOPES = "read:jira-work write:jira-work offline_access"

_STATE_TTL_SECONDS = 600  # 10 minutes — enough time to complete a browser login
_STATE_MAX = 20           # cap; prevents unbounded growth from repeated starts

# In-memory state tokens: {state: expires_at}
_pending_states: dict[str, datetime] = {}


def _prune_states() -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, exp in _pending_states.items() if now >= exp]
    for k in expired:
        del _pending_states[k]
    # Hard cap — drop oldest if still over limit
    while len(_pending_states) >= _STATE_MAX:
        del _pending_states[next(iter(_pending_states))]


def build_auth_url(client_id: str) -> tuple[str, str]:
    _prune_states()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS)
    from urllib.parse import urlencode
    params = {
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return ATLASSIAN_AUTH_URL + "?" + urlencode(params), state


async def exchange_code(code: str, state: str, client_id: str, client_secret: str) -> dict:
    _prune_states()
    exp = _pending_states.pop(state, None)
    if exp is None or datetime.now(timezone.utc) >= exp:
        raise ValueError("Invalid or expired OAuth state — please start the login flow again.")

    payload = json.dumps({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode()

    tokens = await asyncio.to_thread(_post_json, ATLASSIAN_TOKEN_URL, payload)

    access_token = tokens["access_token"]
    resources = await asyncio.to_thread(_get_json, ATLASSIAN_RESOURCES_URL, access_token)
    if not resources:
        raise ValueError("No Jira Cloud sites are accessible with this account.")

    site = resources[0]
    cloud_id = site["id"]
    cloud_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"

    await _store_tokens(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token", ""),
        expires_in=tokens.get("expires_in", 3600),
        scope=tokens.get("scope", ""),
        cloud_id=cloud_id,
        cloud_url=cloud_url,
    )
    return {"cloud_id": cloud_id, "cloud_url": cloud_url, "site_name": site.get("name", cloud_id)}


async def get_token() -> dict | None:
    """Returns {access_token, cloud_url} refreshing if needed, or None if not authenticated."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM oauth_tokens WHERE provider = 'jira'") as cur:
            row = await cur.fetchone()
    if not row or not row["access_token"]:
        return None

    expires_at = row["expires_at"]
    if expires_at:
        try:
            if datetime.now(timezone.utc) >= datetime.fromisoformat(expires_at):
                return await _refresh(dict(row))
        except ValueError:
            pass

    return {"access_token": row["access_token"], "cloud_url": row["cloud_url"]}


async def get_status() -> dict:
    from services.config import get_config_section
    config = await get_config_section("ticketing")
    app_configured = bool(
        config.get("jira_oauth_client_id", "").strip()
        and os.environ.get("CARET_JIRA_OAUTH_CLIENT_SECRET", "").strip()
    )

    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT cloud_id, cloud_url, scope, updated_at FROM oauth_tokens WHERE provider = 'jira'"
        ) as cur:
            row = await cur.fetchone()
    if not row or not row["cloud_id"]:
        return {"app_configured": app_configured, "connected": False}
    return {
        "app_configured": app_configured,
        "connected": True,
        "cloud_id": row["cloud_id"],
        "cloud_url": row["cloud_url"],
        "scope": row["scope"],
        "updated_at": row["updated_at"],
    }


async def clear_tokens() -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute("DELETE FROM oauth_tokens WHERE provider = 'jira'")
        await db.commit()


async def _refresh(row: dict) -> dict | None:
    from services.config import get_config_section
    config = await get_config_section("ticketing")
    client_id = config.get("jira_oauth_client_id", "").strip()
    client_secret = os.environ.get("CARET_JIRA_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = row.get("refresh_token", "")
    if not client_id or not client_secret or not refresh_token:
        return None

    payload = json.dumps({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }).encode()

    try:
        tokens = await asyncio.to_thread(_post_json, ATLASSIAN_TOKEN_URL, payload)
    except Exception:
        return None

    await _store_tokens(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token", refresh_token),
        expires_in=tokens.get("expires_in", 3600),
        scope=tokens.get("scope", row.get("scope", "")),
        cloud_id=row["cloud_id"],
        cloud_url=row["cloud_url"],
    )
    return {"access_token": tokens["access_token"], "cloud_url": row["cloud_url"]}


async def _store_tokens(
    access_token: str,
    refresh_token: str,
    expires_in: int,
    scope: str,
    cloud_id: str,
    cloud_url: str,
) -> None:
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)).isoformat()
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO oauth_tokens (provider, access_token, refresh_token, expires_at, scope, cloud_id, cloud_url)
            VALUES ('jira', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                scope = excluded.scope,
                cloud_id = excluded.cloud_id,
                cloud_url = excluded.cloud_url,
                updated_at = datetime('now')
            """,
            (access_token, refresh_token, expires_at, scope, cloud_id, cloud_url),
        )
        await db.commit()


def _post_json(url: str, payload: bytes) -> dict:
    req = _req.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with _req.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except _err.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"Atlassian request failed ({exc.code}): {detail or exc.reason}") from exc
    except _err.URLError as exc:
        raise ValueError(f"Could not reach Atlassian: {exc.reason}") from exc


def _get_json(url: str, access_token: str) -> list:
    req = _req.Request(url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
    try:
        with _req.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except _err.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"Atlassian request failed ({exc.code}): {detail or exc.reason}") from exc
    except _err.URLError as exc:
        raise ValueError(f"Could not reach Atlassian: {exc.reason}") from exc
