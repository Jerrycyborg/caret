from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import chat, models, conversations, settings, tasks
from database import init_db, get_db_path
import aiosqlite

load_dotenv()


PROVIDER_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "azure": "AZURE_API_KEY",
    "ollama": "OLLAMA_API_BASE",
}


async def _load_api_keys():
    """Load API keys from DB into env vars so LiteLLM picks them up."""
    try:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT provider, key_value FROM api_keys") as cur:
                rows = await cur.fetchall()
        for r in rows:
            env_key = PROVIDER_ENV_MAP.get(r["provider"])
            if env_key:
                os.environ.setdefault(env_key, r["key_value"])
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _load_api_keys()
    yield


app = FastAPI(title="Oxy Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "http://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/v1")
app.include_router(models.router, prefix="/v1")
app.include_router(conversations.router, prefix="/v1")
app.include_router(settings.router, prefix="/v1")
app.include_router(tasks.router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
