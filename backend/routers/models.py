import os
from fastapi import APIRouter
import httpx

router = APIRouter()

_PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "azure": "AZURE_API_KEY",
    "ollama": "OLLAMA_API_BASE",
}

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


@router.get("/models/status")
async def model_status():
    """Returns whether at least one model is usable right now."""
    # Check Ollama
    ollama_ready = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                ollama_ready = bool(r.json().get("models"))
    except Exception:
        pass

    # Check cloud API keys
    cloud_provider = next(
        (p for p, env in _PROVIDER_ENV.items() if p != "ollama" and os.environ.get(env, "").strip()),
        None,
    )

    if ollama_ready:
        return {"ready": True, "source": "ollama"}
    if cloud_provider:
        return {"ready": True, "source": cloud_provider}
    return {
        "ready": False,
        "source": None,
        "hint": "No AI model is configured for this device. Contact IT to enable the Help assistant.",
    }
