from __future__ import annotations

import json
import uuid
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException
from fastapi import Header
from pydantic import BaseModel

from database import get_db_path
from routers.conversations import find_or_create_channel_conversation
from services.orchestrator import get_task, maybe_create_task
from services.telegram_adapter import parse_telegram_update, send_telegram_message, telegram_secret

router = APIRouter()


class ChannelMessageRequest(BaseModel):
    channel_type: str
    channel_user_id: str
    channel_thread_id: Optional[str] = None
    content: str
    model: str = "ollama/llama3.2"


@router.post("/channels/message")
async def receive_channel_message(body: ChannelMessageRequest):
    if body.channel_type not in {"telegram", "whatsapp"}:
        raise HTTPException(status_code=400, detail="Unsupported channel_type.")

    result = await process_channel_message(
        channel_type=body.channel_type,
        channel_user_id=body.channel_user_id,
        channel_thread_id=body.channel_thread_id,
        content=body.content,
        model=body.model,
    )
    return result


@router.post("/channels/telegram/webhook")
async def receive_telegram_webhook(
    body: dict,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    secret = telegram_secret()
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret.")
    message = parse_telegram_update(body)
    if not message:
        return {"ok": True, "ignored": True}
    result = await process_channel_message(
        channel_type="telegram",
        channel_user_id=message["channel_user_id"],
        channel_thread_id=message["channel_thread_id"],
        content=message["content"],
        model="ollama/llama3.2",
    )
    await send_telegram_message(message["chat_id"], result["reply"])
    return {"ok": True, "conversation_id": result["conversation_id"], "task_handoff": result["task_handoff"]}


async def process_channel_message(
    channel_type: str,
    channel_user_id: str,
    channel_thread_id: Optional[str],
    content: str,
    model: str,
):
    conv = await find_or_create_channel_conversation(
        channel_type=channel_type,
        channel_user_id=channel_user_id,
        channel_thread_id=channel_thread_id,
        model=model,
        title=f"{channel_type}:{channel_user_id}",
    )
    await _save_message(conv["id"], "user", content)

    task_handoff = await maybe_create_task(content, conv["id"])
    reply = _build_channel_reply(content, task_handoff)
    await _save_message(conv["id"], "assistant", reply)
    await _touch_conversation(conv["id"], model)

    task_detail = await get_task(task_handoff["task_id"]) if task_handoff else None
    return {
        "conversation_id": conv["id"],
        "reply": reply,
        "task_handoff": task_handoff,
        "agent_state": task_detail["agent_state"] if task_detail else None,
    }


def _build_channel_reply(content: str, task_handoff: dict | None) -> str:
    if not task_handoff:
        return f"Received: {content[:120]}. No supervised task was created."
    report = task_handoff.get("task_report") or {}
    parts = [f"Task: {task_handoff['title']}"]
    if report.get("headline"):
        parts.append(report["headline"])
    parts.append(f"Executor: {task_handoff['assigned_executor']} / {task_handoff['execution_domain']}")
    parts.extend(report.get("details") or [])
    return "\n".join(part for part in parts if part)


async def _save_message(conv_id: str, role: str, content: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), conv_id, role, content),
        )
        await db.commit()


async def _touch_conversation(conv_id: str, model: str):
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute("SELECT last_agent_state FROM conversations WHERE id = ?", (conv_id,)) as cur:
            row = await cur.fetchone()
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now'), model = ?, last_agent_state = ? WHERE id = ?",
            (model, row[0] if row and row[0] else json.dumps({}), conv_id),
        )
        await db.commit()
