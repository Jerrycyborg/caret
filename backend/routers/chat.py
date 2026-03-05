import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import litellm

router = APIRouter()

litellm.set_verbose = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "ollama/llama3.2"
    stream: bool = True


@router.post("/chat")
async def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    if request.stream:
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
                        yield f"data: {json.dumps({'content': delta})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'content': f'Error: {str(e)}'})}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    response = await litellm.acompletion(
        model=request.model,
        messages=messages,
    )
    return {"content": response.choices[0].message.content}
