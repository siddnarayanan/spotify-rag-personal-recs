import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import app.agent.agent as agent_mod
import app.routes.api as api_mod
from app.schemas import Recommendation, RecommendationList


@pytest.fixture
def client(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.scheduler, "startup", lambda: None)  # no background work in tests
    with TestClient(main.app) as c:
        yield c


def _sse_events(text: str) -> list[tuple[str, dict]]:
    events = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        lines = frame.strip().splitlines()
        ev = next((ln[6:].strip() for ln in lines if ln.startswith("event:")), None)
        data = next((ln[5:].strip() for ln in lines if ln.startswith("data:")), None)
        if ev and data:
            events.append((ev, json.loads(data)))
    return events


def test_status_and_history(client):
    s = client.get("/api/status").json()
    assert s["demo_mode"] and s["authenticated"] and not s["llm_configured"]
    h = client.get("/api/history?limit=5").json()
    assert len(h["recent"]) == 5 and h["top_artists"]


def test_sync_disabled_in_demo(client):
    assert client.post("/api/sync").status_code == 400


def test_recommend_without_api_key(client):
    r = client.post("/api/recommend", json={})
    assert r.status_code == 500 and "ant auth login" in r.json()["detail"]


def test_recommend_streams_tool_steps_and_cards(client, monkeypatch):
    structured = RecommendationList(
        summary="You love psych-pop.",
        recommendations=[
            Recommendation(title="Ivy", artist="Frank Ocean", reason="r", novelty="new_artist")
        ],
    )

    class FakeAgent:
        def stream(self, inputs, stream_mode):
            call = {"name": "search_listening_history", "args": {"query": "q"}, "id": "1"}
            yield {"model": {"messages": [AIMessage("", tool_calls=[call])]}}
            yield {"model": {"messages": [], "structured_response": structured}}

    monkeypatch.setattr(api_mod, "recommender_agent", lambda: FakeAgent())
    monkeypatch.setattr(agent_mod, "search_track", lambda t, a: None)

    r = client.post("/api/recommend", json={"prompt": "upbeat", "count": 3})
    events = _sse_events(r.text)
    names = [e for e, _ in events]
    assert names[0] == "status" and events[0][1]["tool"] == "search_listening_history"
    assert "summary" in names and names[-1] == "done"
    rec = next(d for e, d in events if e == "recommendation")
    assert rec["title"] == "Ivy" and rec["novelty"] == "familiar_artist"
