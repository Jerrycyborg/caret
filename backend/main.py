from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import chat, models, conversations, settings, support, tasks, management
from database import init_db
from services.support_daemon import init_support_tables, run_support_daemon
from services.management import run_management_daemon

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_support_tables()
    stop_event = asyncio.Event()
    support_task = asyncio.create_task(run_support_daemon(stop_event))
    mgmt_task = asyncio.create_task(run_management_daemon(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await support_task
        await mgmt_task


app = FastAPI(title="Caret Backend", version="0.1.9", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "http://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Atlassian-Token"],
)

app.include_router(chat.router, prefix="/v1")
app.include_router(models.router, prefix="/v1")
app.include_router(conversations.router, prefix="/v1")
app.include_router(settings.router, prefix="/v1")
app.include_router(support.router, prefix="/v1")
app.include_router(tasks.router, prefix="/v1")
app.include_router(management.router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.9"}
