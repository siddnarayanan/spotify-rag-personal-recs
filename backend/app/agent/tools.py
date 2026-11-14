"""LangChain tools the recommendation agent can call.

Only ``lookup_spotify_track`` touches the network, and it goes through a 7-day
on-disk HTTP cache. Everything else reads the local cache / vector store.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Literal

from langchain_core.tools import tool

from app.agent.library import get_library
from app.rag.documents import RANGE_LABEL
from app.rag.retriever import format_docs, retrieve
from app.spotify.client import search_track


@tool
def search_listening_history(
    query: str,
    doc_type: Literal["track", "artist", "period", "session", "playlists"] | None = None,
) -> str:
    """Semantic search over the listener's cached Spotify history (RAG retrieval).

    Use this to ground recommendations in what they actually listen to. Example
    queries: "high-energy songs", "artists I've played most recently", "chill
    late-night listening". Optionally restrict to one doc_type:
    track | artist | period (top charts per time range) | session (a day's plays) | playlists.
    """
    docs = retrieve(query, doc_type=doc_type)
    return format_docs(docs) or "No matching history found."


@tool
def get_listening_stats() -> str:
    """Aggregate stats: top artists per time range, most-played recent artists, top genres."""
    lib = get_library()
    data = lib.data
    out: dict = {}
    for tr, items in data["top_artists"].items():
        out[f"top_artists_{tr} ({RANGE_LABEL[tr]})"] = [a["name"] for a in items[:15]]
    genres = Counter(
        g for items in data["top_artists"].values() for a in items for g in a.get("genres") or []
    )
    out["top_genres"] = [g for g, _ in genres.most_common(15)] or "genres unavailable"
    recent = Counter(a for p in data["history"][-200:] for a in p.get("artists") or [])
    out["most_played_recent_artists"] = [a for a, _ in recent.most_common(15)]
    out["history_plays_cached"] = len(data["history"])
    out["liked_songs_cached"] = len(data["saved_tracks"])
    return json.dumps(out, indent=1)


@tool
def check_already_known(candidates: list[str]) -> str:
    """Check candidate tracks against the listener's library before recommending them.

    Pass a list of strings formatted "Title - Artist". Returns, for each, whether the
    track is already known and whether the artist is new to the listener.
    """
    lib = get_library()
    results = []
    for c in candidates:
        title, _, artist = c.partition(" - ")
        results.append(
            {
                "candidate": c,
                "track_already_known": lib.knows_track(title.strip(), artist.strip()),
                "artist_new_to_listener": not lib.knows_artist(artist.strip()),
            }
        )
    return json.dumps(results, indent=1)


@tool
def lookup_spotify_track(title: str, artist: str) -> str:
    """Verify a track exists in Spotify's catalog (cached). Returns its canonical
    title/artist/album or 'NOT FOUND'. Always verify before recommending."""
    t = search_track(title, artist)
    if t is None:
        return "NOT FOUND (or Spotify search unavailable)"
    return json.dumps({k: t[k] for k in ("name", "artists", "album", "release_year", "popularity")})


TOOLS = [search_listening_history, get_listening_stats, check_already_known, lookup_spotify_track]
