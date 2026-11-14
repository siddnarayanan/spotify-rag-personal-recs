"""Daily sync: pull listening data from Spotify into the local cache.

Spotify only exposes the last 50 plays, so ``history.jsonl`` is append-only and
de-duplicated on (played_at, track_id); the RAG corpus grows every day.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime

import spotipy

from app import store
from app.config import get_settings
from app.spotify.client import normalize_artist, normalize_track, user_client

log = logging.getLogger(__name__)
_lock = threading.Lock()


class SyncError(RuntimeError):
    pass


def is_stale() -> bool:
    s = get_settings()
    h = store.hours_since_sync(s.live_cache_dir)
    return h is None or h >= s.sync_interval_hours


def _paginate(sp: spotipy.Spotify, page: dict, cap: int) -> list[dict]:
    items = list(page.get("items", []))
    while page.get("next") and len(items) < cap:
        page = sp.next(page)
        items.extend(page.get("items", []))
    return items[:cap]


def fetch_snapshot(sp: spotipy.Spotify) -> dict:
    s = get_settings()
    recent = sp.current_user_recently_played(limit=50).get("items", [])
    plays = [
        {"played_at": it["played_at"], **normalize_track(it["track"])}
        for it in recent
        if it.get("track")
    ]
    top_tracks, top_artists = {}, {}
    for tr in store.TIME_RANGES:
        top_tracks[tr] = [
            normalize_track(t) for t in sp.current_user_top_tracks(50, time_range=tr)["items"]
        ]
        top_artists[tr] = [
            normalize_artist(a) for a in sp.current_user_top_artists(50, time_range=tr)["items"]
        ]
    saved = _paginate(sp, sp.current_user_saved_tracks(limit=50), s.saved_tracks_limit)
    saved_tracks = [
        {"added_at": it["added_at"], **normalize_track(it["track"])}
        for it in saved
        if it.get("track")
    ]
    playlists = [
        {"name": p["name"], "description": p.get("description") or ""}
        for p in _paginate(sp, sp.current_user_playlists(limit=50), 200)
        if p
    ]
    return {
        "plays": plays,
        "top_tracks": top_tracks,
        "top_artists": top_artists,
        "saved_tracks": saved_tracks,
        "playlists": playlists,
    }


def merge_history(existing: list[dict], new: list[dict]) -> list[dict]:
    seen = {(p["played_at"], p["id"]) for p in existing}
    merged = existing + [p for p in new if (p["played_at"], p["id"]) not in seen]
    return sorted(merged, key=lambda p: p["played_at"])


def write_snapshot(snapshot: dict, cache_dir=None) -> dict:
    cache_dir = cache_dir or get_settings().live_cache_dir
    history = merge_history(store.read_history(cache_dir), snapshot["plays"])
    store.write_history(history, cache_dir)
    store.write_json_atomic(cache_dir / "top_tracks.json", snapshot["top_tracks"])
    store.write_json_atomic(cache_dir / "top_artists.json", snapshot["top_artists"])
    store.write_json_atomic(cache_dir / "saved_tracks.json", snapshot["saved_tracks"])
    store.write_json_atomic(cache_dir / "playlists.json", snapshot["playlists"])
    digest = hashlib.sha256(
        json.dumps(
            [history, snapshot["top_tracks"], snapshot["top_artists"], snapshot["saved_tracks"]],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    meta = {
        "last_sync": datetime.now(UTC).isoformat(),
        "content_hash": digest,
        "counts": {
            "history": len(history),
            "saved_tracks": len(snapshot["saved_tracks"]),
            "playlists": len(snapshot["playlists"]),
        },
    }
    store.write_json_atomic(cache_dir / "meta.json", meta)
    return meta


def run_sync(force: bool = False) -> dict | None:
    """Sync if the cache is stale (or ``force``). Returns new meta, or None if skipped."""
    s = get_settings()
    if s.demo_mode:
        raise SyncError("Sync is disabled in demo mode.")
    if not _lock.acquire(blocking=False):
        raise SyncError("A sync is already running.")
    try:
        if not force and not is_stale():
            log.info("Cache is fresh (%.1fh old); skipping sync.", store.hours_since_sync())
            return None
        log.info("Syncing Spotify listening data…")
        meta = write_snapshot(fetch_snapshot(user_client()))
        log.info("Sync complete: %s", meta["counts"])
        return meta
    finally:
        _lock.release()
