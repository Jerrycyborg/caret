from __future__ import annotations

import uuid
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db_path

router = APIRouter()


class CreateConversation(BaseModel):
    title: str = "New Chat"
    model: str = "ollama/llama3.2"
    channel_type: str = "desktop"
    channel_user_id: Optional[str] = None
    channel_thread_id: Optional[str] = None


@router.get("/conversations")
async def list_conversations():
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, title, model, channel_type, channel_user_id, channel_thread_id,
                   session_status, last_task_id, last_executor, last_agent_state, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
            """
        ) as cur:
            rows = await cur.fetchall()
    return {"conversations": [dict(r) for r in rows]}


@router.post("/conversations")
async def create_conversation(body: CreateConversation):
    conv_id = str(uuid.uuid4())
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO conversations (
                id, title, model, channel_type, channel_user_id, channel_thread_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                body.title,
                body.model,
                body.channel_type,
                body.channel_user_id,
                body.channel_thread_id,
            ),
        )
        await db.commit()
    return {
        "id": conv_id,
        "title": body.title,
        "model": body.model,
        "channel_type": body.channel_type,
        "channel_user_id": body.channel_user_id,
        "channel_thread_id": body.channel_thread_id,
    }


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)) as cur:
            conv = await cur.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        async with db.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        ) as cur:
            msgs = await cur.fetchall()
    return {**dict(conv), "messages": [dict(m) for m in msgs]}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await db.commit()
    return {"ok": True}


async def find_or_create_channel_conversation(
    channel_type: str,
    channel_user_id: str,
    channel_thread_id: str | None,
    model: str,
    title: str,
) -> dict[str, str]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, title, model
            FROM conversations
            WHERE channel_type = ? AND channel_user_id = ? AND COALESCE(channel_thread_id, '') = COALESCE(?, '')
            LIMIT 1
            """,
            (channel_type, channel_user_id, channel_thread_id),
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            return dict(existing)

        conv_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO conversations (
                id, title, model, channel_type, channel_user_id, channel_thread_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, title, model, channel_type, channel_user_id, channel_thread_id),
        )
        await db.commit()
        return {"id": conv_id, "title": title, "model": model}
