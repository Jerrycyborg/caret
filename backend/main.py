from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, models

app = FastAPI(title="Oxy Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "http://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/v1")
app.include_router(models.router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
