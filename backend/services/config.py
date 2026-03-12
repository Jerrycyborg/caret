from __future__ import annotations

import json
import os
from typing import Any

import aiosqlite

from database import get_db_path


CONFIG_DEFAULTS: dict[str, dict[str, Any]] = {
    "org": {
        "org_name": os.environ.get("OXY_ORG_NAME", "Oxy Internal"),
        "environment_label": os.environ.get("OXY_ENV_LABEL", "development"),
    },
    "ticketing": {
        "adapter_type": os.environ.get("OXY_TICKETING_ADAPTER", "jira"),
        "jira_base_url": os.environ.get("OXY_JIRA_BASE_URL", ""),
        "jira_project_key": os.environ.get("OXY_JIRA_PROJECT_KEY", ""),
        "jira_issue_type": os.environ.get("OXY_JIRA_ISSUE_TYPE", "Task"),
        "jira_user_email": os.environ.get("OXY_JIRA_USER_EMAIL", ""),
        "jira_api_token": os.environ.get("OXY_JIRA_API_TOKEN", ""),
        "jira_default_labels": [label for label in os.environ.get("OXY_JIRA_LABELS", "").split(",") if label.strip()],
        "jira_default_components": [component for component in os.environ.get("OXY_JIRA_COMPONENTS", "").split(",") if component.strip()],
    },
    "support_policy": {
        "auto_fix_enabled": os.environ.get("OXY_SUPPORT_AUTO_FIX_ENABLED", "true").lower() != "false",
        "default_escalation_policy": os.environ.get("OXY_SUPPORT_ESCALATION_POLICY", "manual_review"),
        "allowed_remediation_classes": ["cleanup_candidates", "diagnostics", "readiness_refresh"],
    },
    "workflow_policy": {
        "task_plan_approval_default": True,
        "openclaw_enabled": os.environ.get("OXY_OPENCLAW_ENABLED", "true").lower() != "false",
        "wraith_enabled": os.environ.get("OXY_WRAITH_ENABLED", "true").lower() != "false",
    },
    "integrations": {
        "telegram_enabled": os.environ.get("OXY_TELEGRAM_ENABLED", "false").lower() == "true",
        "whatsapp_enabled": os.environ.get("OXY_WHATSAPP_ENABLED", "false").lower() == "true",
        "openclaw_enabled": os.environ.get("OXY_OPENCLAW_ENABLED", "true").lower() != "false",
        "wraith_enabled": os.environ.get("OXY_WRAITH_ENABLED", "true").lower() != "false",
    },
}


async def get_all_config() -> dict[str, dict[str, Any]]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT section, value_json FROM app_config") as cur:
            rows = await cur.fetchall()
    values = {row["section"]: json.loads(row["value_json"] or "{}") for row in rows}
    return {section: _merged_config(section, values.get(section, {})) for section in CONFIG_DEFAULTS}


async def get_config_section(section: str) -> dict[str, Any]:
    if section not in CONFIG_DEFAULTS:
        raise ValueError(f"Unknown config section: {section}")
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute("SELECT value_json FROM app_config WHERE section = ?", (section,)) as cur:
            row = await cur.fetchone()
    stored = json.loads(row[0]) if row and row[0] else {}
    merged = _merged_config(section, stored)
    if section == "ticketing":
        merged["jira_api_token"] = os.environ.get("OXY_JIRA_API_TOKEN", "")
    return merged


async def set_config_section(section: str, value: dict[str, Any]) -> dict[str, Any]:
    if section not in CONFIG_DEFAULTS:
        raise ValueError(f"Unknown config section: {section}")
    existing = await get_config_section(section)
    payload = dict(value)
    if section == "ticketing":
        secret = str(payload.get("jira_api_token", "")).strip()
        if secret:
            os.environ["OXY_JIRA_API_TOKEN"] = secret
        payload["jira_api_token"] = ""
    merged = _merged_config(section, payload)
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO app_config (section, value_json) VALUES (?, ?)
            ON CONFLICT(section) DO UPDATE SET value_json = excluded.value_json, updated_at = datetime('now')
            """,
            (section, json.dumps(merged)),
        )
        await db.commit()
    return merged


def masked_config(all_config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    ticketing = dict(all_config.get("ticketing", {}))
    ticketing["jira_api_token"] = ""
    return {**all_config, "ticketing": ticketing}


def _merged_config(section: str, stored: dict[str, Any]) -> dict[str, Any]:
    default = CONFIG_DEFAULTS[section]
    merged = dict(default)
    merged.update(stored or {})
    return merged
