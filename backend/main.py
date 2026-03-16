from contextlib import asynccontextmanager
import asyncio
import logging
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from logger import setup_logging, log_path
from routers import chat, models, conversations, settings, support, tasks, management
from database import init_db
from services.support_daemon import init_support_tables, run_support_daemon
from services.management import run_management_daemon

load_dotenv()
setup_logging()
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Caret backend v0.1.9 starting")
    await init_db()
    await init_support_tables()
    stop_event = asyncio.Event()
    support_task = asyncio.create_task(run_support_daemon(stop_event))
    mgmt_task = asyncio.create_task(run_management_daemon(stop_event))
    log.info("Backend ready — listening on port 8000")
    try:
        yield
    finally:
        log.info("Backend shutting down")
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


@app.get("/v1/logs")
def get_logs(lines: int = Query(default=200, le=2000)):
    """Return the last N lines from the backend log file."""
    path = log_path()
    if not path.exists():
        return {"path": str(path), "lines": []}
    with open(path, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    tail = [l.rstrip("\n") for l in all_lines[-lines:]]
    return {"path": str(path), "lines": tail}
