import os
from fastapi import APIRouter
import httpx

router = APIRouter()

COPILOT_MODEL = "azure/gpt-4o"


def _copilot_configured() -> bool:
    """Copilot is ready when an Azure OpenAI key and base URL are present."""
    return bool(os.environ.get("AZURE_API_KEY", "").strip()) and \
           bool(os.environ.get("AZURE_API_BASE", "").strip())


@router.get("/models")
async def list_models():
    return {"models": [{"id": COPILOT_MODEL, "provider": "copilot", "name": "Microsoft Copilot"}]}


@router.get("/models/status")
async def model_status():
    """Returns whether Microsoft Copilot is configured and ready."""
    if _copilot_configured():
        return {"ready": True, "source": "copilot"}
    return {
        "ready": False,
        "source": None,
        "hint": "Microsoft Copilot is not configured for this device. Contact IT to enable the assistant.",
    }
