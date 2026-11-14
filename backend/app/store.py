"""Read/write access to the local listening-data cache.

Cache layout (``data/cache`` for live data, ``data/sample`` in demo mode)::

    meta.json           last_sync timestamp, counts, content hash
    history.jsonl       append-only, de-duplicated play history (grows each sync)
    top_tracks.json     {"short_term": [...], "medium_term": [...], "long_term": [...]}
    top_artists.json    same shape, artists
    saved_tracks.json   liked songs (capped)
    playlists.json      playlist names/descriptions
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

TIME_RANGES = ("short_term", "medium_term", "long_term")


def _dir(cache_dir: Path | None) -> Path:
    return cache_dir or get_settings().cache_dir


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON via temp file + rename so a crash never leaves a half-written cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_json(name: str, default: Any, cache_dir: Path | None = None) -> Any:
    path = _dir(cache_dir) / name
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_history(cache_dir: Path | None = None) -> list[dict]:
    path = _dir(cache_dir) / "history.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_history(plays: list[dict], cache_dir: Path | None = None) -> None:
    path = _dir(cache_dir) / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for p in plays:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_meta(cache_dir: Path | None = None) -> dict:
    return read_json("meta.json", {}, cache_dir)


def last_sync(cache_dir: Path | None = None) -> datetime | None:
    ts = read_meta(cache_dir).get("last_sync")
    return datetime.fromisoformat(ts) if ts else None


def hours_since_sync(cache_dir: Path | None = None) -> float | None:
    ls = last_sync(cache_dir)
    if ls is None:
        return None
    return (datetime.now(UTC) - ls).total_seconds() / 3600


def load_all(cache_dir: Path | None = None) -> dict[str, Any]:
    """Load the full cache into memory (it is small: a few thousand items at most)."""
    return {
        "history": read_history(cache_dir),
        "top_tracks": read_json("top_tracks.json", {}, cache_dir),
        "top_artists": read_json("top_artists.json", {}, cache_dir),
        "saved_tracks": read_json("saved_tracks.json", [], cache_dir),
        "playlists": read_json("playlists.json", [], cache_dir),
        "meta": read_meta(cache_dir),
    }


def normalize_key(title: str, artist: str) -> str:
    """Loose key used to tell whether a track is already in the user's library."""

    def clean(s: str) -> str:
        s = s.lower().split(" - ")[0].split(" (")[0].split(" [")[0]
        return "".join(ch for ch in s if ch.isalnum())

    return f"{clean(title)}|{clean(artist)}"
