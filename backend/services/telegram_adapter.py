from __future__ import annotations

import os
from typing import Any

import httpx


def telegram_secret() -> str | None:
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET") or None


def telegram_bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def parse_telegram_update(update: dict[str, Any]) -> dict[str, Any] | None:
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    chat_id = chat.get("id")
    if chat_id is None:
        return None
    return {
        "channel_type": "telegram",
        "channel_user_id": str(sender.get("id") or chat_id),
        "channel_thread_id": str(chat_id),
        "chat_id": str(chat_id),
        "content": text.strip(),
    }


async def send_telegram_message(chat_id: str, text: str) -> None:
    token = telegram_bot_token()
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})
