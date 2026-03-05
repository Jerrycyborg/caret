from fastapi import APIRouter
import httpx

router = APIRouter()

# Cloud provider model lists (static — keeps things fast and offline-capable)
CLOUD_MODELS = [
    {"id": "openai/gpt-4o", "provider": "openai", "name": "gpt-4o"},
    {"id": "openai/gpt-4o-mini", "provider": "openai", "name": "gpt-4o-mini"},
    {"id": "anthropic/claude-3-5-sonnet-20241022", "provider": "anthropic", "name": "claude-3-5-sonnet"},
    {"id": "anthropic/claude-3-haiku-20240307", "provider": "anthropic", "name": "claude-3-haiku"},
    {"id": "gemini/gemini-1.5-pro", "provider": "gemini", "name": "gemini-1.5-pro"},
    {"id": "gemini/gemini-1.5-flash", "provider": "gemini", "name": "gemini-1.5-flash"},
    {"id": "azure/gpt-4o", "provider": "azure", "name": "azure/gpt-4o"},
]


@router.get("/models")
async def list_models():
    models = []

    # Dynamic: fetch locally running Ollama models
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    name = m["name"]
                    models.append({"id": f"ollama/{name}", "provider": "ollama", "name": name})
    except Exception:
        pass  # Ollama not running — that's fine

    # Append static cloud models
    models.extend(CLOUD_MODELS)

    return {"models": models}
