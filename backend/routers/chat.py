import json
import uuid as _uuid
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import litellm
import aiosqlite
from database import get_db_path

router = APIRouter()

litellm.set_verbose = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "ollama/llama3.2"
    stream: bool = True
    conversation_id: Optional[str] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Persist user message before sending to LLM
    if request.conversation_id and messages and messages[-1]["role"] == "user":
        await _save_message(request.conversation_id, "user", messages[-1]["content"])

    if request.stream:
        collected: list[str] = []

        async def stream_response():
            try:
                response = await litellm.acompletion(
                    model=request.model,
                    messages=messages,
                    stream=True,
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        collected.append(delta)
                        yield f"data: {json.dumps({'content': delta})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'content': f'Error: {str(e)}'})}\n\n"
            finally:
                if request.conversation_id and collected:
                    await _save_message(request.conversation_id, "assistant", "".join(collected))
                    await _bump_conversation(request.conversation_id, request.model)
                yield "data: [DONE]\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    response = await litellm.acompletion(model=request.model, messages=messages)
    content = response.choices[0].message.content
    if request.conversation_id:
        await _save_message(request.conversation_id, "assistant", content)
        await _bump_conversation(request.conversation_id, request.model)
    return {"content": content}


async def _save_message(conv_id: str, role: str, content: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
            (str(_uuid.uuid4()), conv_id, role, content),
        )
        await db.commit()


async def _bump_conversation(conv_id: str, model: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now'), model = ? WHERE id = ?",
            (model, conv_id),
        )
        await db.commit()
