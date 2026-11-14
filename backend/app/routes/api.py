"""JSON + Server-Sent-Events API consumed by the React frontend."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from app import store
from app.agent.agent import (
    AgentConfigError,
    build_request,
    chat_agent,
    finalize,
    llm_credentials_available,
    recommender_agent,
)
from app.agent.tools import TOOLS
from app.config import get_settings
from app.rag.index import build_index
from app.scheduler import next_sync_time, sync_and_index
from app.schemas import ChatRequest, RecommendationList, RecommendRequest
from app.spotify import auth
from app.spotify.sync import SyncError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])
TOOL_NAMES = {t.name for t in TOOLS}


def _event(event: str, data) -> dict:
    return {"event": event, "data": json.dumps(data)}


def _tool_status(msg: AIMessage) -> Iterator[dict]:
    for call in msg.tool_calls:
        if call["name"] in TOOL_NAMES:
            yield _event("status", {"tool": call["name"], "args": call["args"]})


@router.get("/status")
def status() -> dict:
    s = get_settings()
    meta = store.read_meta()
    return {
        "demo_mode": s.demo_mode,
        "spotify_configured": s.has_spotify_credentials,
        "authenticated": s.demo_mode or auth.is_authenticated(),
        "llm_configured": llm_credentials_available(),
        "last_sync": meta.get("last_sync"),
        "next_sync": next_sync_time(),
        "counts": meta.get("counts", {}),
    }


@router.get("/history")
def history(limit: int = 30) -> dict:
    data = store.load_all()
    return {
        "recent": list(reversed(data["history"][-limit:])),
        "top_artists": data["top_artists"].get("short_term", [])[:12],
        "top_tracks": data["top_tracks"].get("short_term", [])[:12],
    }


@router.post("/sync")
def sync() -> dict:
    s = get_settings()
    hrs = store.hours_since_sync(s.live_cache_dir)
    if hrs is not None and hrs * 60 < s.manual_sync_cooldown_minutes:
        raise HTTPException(
            429,
            f"Synced {hrs * 60:.0f} min ago; wait {s.manual_sync_cooldown_minutes} min "
            "between manual syncs to respect Spotify's rate limits.",
        )
    try:
        meta = sync_and_index(force=True)
    except SyncError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "meta": meta}


@router.post("/reindex")
def reindex() -> dict:
    return {"documents": build_index(force=True)}


@router.post("/recommend")
async def recommend(req: RecommendRequest) -> EventSourceResponse:
    try:
        agent = recommender_agent()
    except AgentConfigError as e:
        raise HTTPException(500, str(e)) from e

    def run() -> Iterator[dict]:
        try:
            inputs = {"messages": [HumanMessage(build_request(req.prompt, req.count))]}
            result: RecommendationList | None = None
            for update in agent.stream(inputs, stream_mode="updates"):
                for node_state in update.values():
                    if not isinstance(node_state, dict):
                        continue
                    for m in node_state.get("messages", []):
                        if isinstance(m, AIMessage):
                            yield from _tool_status(m)
                    if node_state.get("structured_response"):
                        result = node_state["structured_response"]
            if result is None:
                yield _event("error", {"message": "The agent returned no recommendations."})
                return
            yield _event("status", {"tool": "verify", "args": {}})
            result = finalize(result, req.count)
            yield _event("summary", {"summary": result.summary})
            for rec in result.recommendations:
                yield _event("recommendation", rec.model_dump())
            yield _event("done", {})
        except Exception as e:  # surface errors to the UI instead of a dropped stream
            log.exception("recommend failed")
            yield _event("error", {"message": str(e)})

    return EventSourceResponse(iterate_in_threadpool(run()))


@router.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    try:
        agent = chat_agent()
    except AgentConfigError as e:
        raise HTTPException(500, str(e)) from e

    def run() -> Iterator[dict]:
        try:
            config = {"configurable": {"thread_id": req.thread_id}}
            inputs = {"messages": [HumanMessage(req.message)]}
            for mode, payload in agent.stream(
                inputs, config=config, stream_mode=["messages", "updates"]
            ):
                if mode == "messages":
                    chunk, meta = payload
                    if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "model":
                        if text := chunk.text:
                            yield _event("token", {"text": text})
                else:
                    for node_state in payload.values():
                        if isinstance(node_state, dict):
                            for m in node_state.get("messages", []):
                                if isinstance(m, AIMessage):
                                    yield from _tool_status(m)
            yield _event("done", {})
        except Exception as e:
            log.exception("chat failed")
            yield _event("error", {"message": str(e)})

    return EventSourceResponse(iterate_in_threadpool(run()))
