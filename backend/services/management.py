from __future__ import annotations

import asyncio
import os
import platform
from datetime import datetime, timezone
from typing import Any

import httpx

from services.config import get_config_section
from services.support_platform import (
    collect_cpu_load_pct,
    collect_memory_used_pct,
)

CHECKIN_INTERVAL_SECONDS = int(os.environ.get("CARET_MANAGEMENT_CHECKIN_INTERVAL", "60"))
CARET_VERSION = os.environ.get("CARET_VERSION", "0.1.2")

_mgmt_state: dict[str, Any] = {
    "configured": False,
    "last_checkin_at": None,
    "last_status": "not_configured",
    "last_error": "",
}


def management_status() -> dict[str, Any]:
    return dict(_mgmt_state)


async def run_management_daemon(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await _run_checkin()
        except Exception as exc:
            _mgmt_state["last_status"] = "error"
            _mgmt_state["last_error"] = str(exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECKIN_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def _run_checkin() -> None:
    config = await get_config_section("management")
    server_url = (config.get("server_url") or "").strip().rstrip("/")

    if not server_url:
        _mgmt_state["configured"] = False
        _mgmt_state["last_status"] = "not_configured"
        _mgmt_state["last_error"] = ""
        return

    _mgmt_state["configured"] = True

    cpu_pct = await asyncio.to_thread(collect_cpu_load_pct)
    mem_pct = await asyncio.to_thread(collect_memory_used_pct)

    payload = {
        "hostname": platform.node(),
        "caret_version": CARET_VERSION,
        "health": {
            "cpu_pct": round(cpu_pct, 1),
            "mem_used_pct": round(mem_pct, 1),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    token = os.environ.get("CARET_MANAGEMENT_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{server_url}/v1/devices/checkin", json=payload, headers=headers)
        response.raise_for_status()
        _mgmt_state["last_checkin_at"] = payload["timestamp"]
        _mgmt_state["last_status"] = "ok"
        _mgmt_state["last_error"] = ""
    except httpx.HTTPStatusError as exc:
        _mgmt_state["last_status"] = "error"
        _mgmt_state["last_error"] = f"HTTP {exc.response.status_code}"
        _mgmt_state["last_checkin_at"] = payload["timestamp"]
    except httpx.RequestError as exc:
        _mgmt_state["last_status"] = "unreachable"
        _mgmt_state["last_error"] = str(exc)
