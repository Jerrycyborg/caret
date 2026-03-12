from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import channels, chat, models, conversations, settings, support, tasks
from database import init_db
from services.support_daemon import init_support_tables, run_support_daemon

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_support_tables()
    stop_event = asyncio.Event()
    daemon_task = asyncio.create_task(run_support_daemon(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await daemon_task


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
app.include_router(channels.router, prefix="/v1")
app.include_router(settings.router, prefix="/v1")
app.include_router(support.router, prefix="/v1")
app.include_router(tasks.router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
