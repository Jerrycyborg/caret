from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

import aiosqlite

from database import get_db_path
from services.config import get_config_section


@dataclass
class TicketAdapterDefinition:
    id: str
    label: str
    mode: str
    health: str


class TicketingError(RuntimeError):
    pass


def ticket_adapter_registry() -> list[dict[str, str]]:
    return [
        {
            "id": "jira",
            "label": "Jira",
            "mode": "api",
            "health": "configurable",
        }
    ]


async def create_support_ticket(task_id: str, incident_detail: dict[str, Any]) -> dict[str, Any]:
    task = incident_detail["task"]
    if task.get("external_ticket_key"):
        raise TicketingError("This incident already has a linked ticket.")

    config = await get_config_section("ticketing")
    adapter = config.get("adapter_type", "jira")
    if adapter != "jira":
        raise TicketingError(f"Unsupported ticket adapter: {adapter}")

    _validate_jira_config(config)
    payload = _build_jira_payload(config, incident_detail)
    created = await _jira_create_issue(config, payload)
    ticket_key = created.get("key", "")
    ticket_id = created.get("id", "")
    ticket_url = _jira_ticket_url(config, ticket_key)
    attachment_count = await _attach_support_artifacts(config, ticket_id, incident_detail)

    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            UPDATE tasks
            SET external_ticket_system = ?, external_ticket_key = ?, external_ticket_url = ?,
                external_ticket_status = ?, external_ticket_created_at = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            ("jira", ticket_key, ticket_url, "created", created_at, task_id),
        )
        await db.execute(
            """
            INSERT INTO policy_events (id, task_id, step_id, event_type, message, metadata_json)
            VALUES (?, ?, NULL, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                task_id,
                "support_ticket_created",
                f"Created Jira ticket {ticket_key}.",
                json.dumps({"ticket_key": ticket_key, "ticket_url": ticket_url, "attachments": attachment_count}),
            ),
        )
        await db.commit()
    return {
        "ticket_system": "jira",
        "ticket_key": ticket_key,
        "ticket_url": ticket_url,
        "ticket_status": "created",
        "attachment_count": attachment_count,
    }


def _validate_jira_config(config: dict[str, Any]) -> None:
    required = ["jira_base_url", "jira_project_key", "jira_issue_type", "jira_user_email", "jira_api_token"]
    missing = [field for field in required if not str(config.get(field, "")).strip()]
    if missing:
        raise TicketingError(f"Jira settings are incomplete: {', '.join(missing)}")


def _build_jira_payload(config: dict[str, Any], incident_detail: dict[str, Any]) -> dict[str, Any]:
    task = incident_detail["task"]
    incident = incident_detail["incident"]
    description = _build_jira_description(incident_detail)
    fields: dict[str, Any] = {
        "project": {"key": config["jira_project_key"]},
        "summary": f"[{task.get('support_category') or 'support'}] {task['title']}",
        "issuetype": {"name": config["jira_issue_type"]},
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}],
                }
            ],
        },
        "labels": ["oxy", "support_incident", *(config.get("jira_default_labels") or [])],
    }
    components = config.get("jira_default_components") or []
    if components:
        fields["components"] = [{"name": component} for component in components]
    if incident["decision_kind"]:
        fields["labels"].append(f"severity_{incident['decision_kind']}")
    return {"fields": fields}


def _build_jira_description(incident_detail: dict[str, Any]) -> str:
    task = incident_detail["task"]
    incident = incident_detail["incident"]
    policy_events = incident_detail.get("policy_events", [])[:6]
    timeline = incident_detail.get("timeline", [])[:6]
    lines = [
        f"Incident: {task['title']}",
        f"Category: {task.get('support_category') or 'unknown'}",
        f"Severity: {task.get('support_severity') or incident['decision_kind']}",
        f"Reason: {incident.get('decision_reason') or 'n/a'}",
        f"Detected: {incident.get('detected_at') or task.get('created_at')}",
        f"Suggested next action: {task.get('next_suggested_action') or 'review in Oxy'}",
        "",
        "Recommended fixes:",
    ]
    for item in incident.get("recommended_fixes") or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Recent audit:")
    for event in policy_events:
        lines.append(f"- {event['created_at']}: {event['message']}")
    lines.append("")
    lines.append("Recent timeline:")
    for item in timeline:
        lines.append(f"- {item['timestamp']}: {item['title']} — {item['detail']}")
    return "\n".join(lines)


async def _jira_create_issue(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    url = config["jira_base_url"].rstrip("/") + "/rest/api/3/issue"
    return await _jira_request_json(config, url, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"})


async def _attach_support_artifacts(config: dict[str, Any], ticket_id: str, incident_detail: dict[str, Any]) -> int:
    if not ticket_id:
        return 0
    attachment_text = _build_attachment_text(incident_detail)
    filename = f"oxy-incident-{incident_detail['task']['id'][:8]}.txt"
    content_type = mimetypes.guess_type(filename)[0] or "text/plain"
    body, boundary = _multipart_body(filename, attachment_text.encode("utf-8"), content_type)
    url = config["jira_base_url"].rstrip("/") + f"/rest/api/3/issue/{ticket_id}/attachments"
    await _jira_request_bytes(
        config,
        url,
        body,
        {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Atlassian-Token": "no-check",
        },
    )
    return 1


def _build_attachment_text(incident_detail: dict[str, Any]) -> str:
    task = incident_detail["task"]
    return json.dumps(
        {
            "task": task,
            "incident": incident_detail["incident"],
            "policy_events": incident_detail.get("policy_events", []),
            "timeline": incident_detail.get("timeline", []),
        },
        indent=2,
    )


async def _jira_request_json(config: dict[str, Any], url: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
    raw = await _jira_request_bytes(config, url, body, headers)
    return json.loads(raw.decode("utf-8"))


async def _jira_request_bytes(config: dict[str, Any], url: str, body: bytes, headers: dict[str, str]) -> bytes:
    auth = base64.b64encode(f"{config['jira_user_email']}:{config['jira_api_token']}".encode("utf-8")).decode("utf-8")
    request_headers = {"Authorization": f"Basic {auth}", "Accept": "application/json", **headers}

    def _send() -> bytes:
        req = request.Request(url, data=body, headers=request_headers, method="POST")
        try:
            with request.urlopen(req, timeout=15) as response:
                return response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise TicketingError(f"Jira request failed ({exc.code}): {detail or exc.reason}") from exc
        except error.URLError as exc:
            raise TicketingError(f"Could not reach Jira: {exc.reason}") from exc

    import asyncio

    return await asyncio.to_thread(_send)


def _multipart_body(filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = "oxy-" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), boundary


def _jira_ticket_url(config: dict[str, Any], ticket_key: str) -> str:
    return config["jira_base_url"].rstrip("/") + f"/browse/{ticket_key}"
