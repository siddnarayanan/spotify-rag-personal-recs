"""FastAPI entrypoint: `uv run fastapi dev app/main.py`."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import scheduler
from app.config import get_settings
from app.routes import api, auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Sync/index in the background so the server is reachable immediately
    # (the embedding model can take a few seconds to load on first run).
    threading.Thread(target=scheduler.startup, name="startup-sync", daemon=True).start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Spotify RAG Recommender", version="0.1.0", lifespan=lifespan)
s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.frontend_origin, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(api.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
