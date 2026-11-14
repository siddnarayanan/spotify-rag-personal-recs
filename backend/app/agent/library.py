"""In-memory view of the user's library, used for stats and 'already known' checks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app import store


@dataclass
class Library:
    known_tracks: set[str] = field(default_factory=set)  # normalize_key(title, artist)
    artist_plays: Counter[str] = field(default_factory=Counter)  # lowercase artist -> count
    data: dict = field(default_factory=dict)

    def knows_track(self, title: str, artist: str) -> bool:
        return store.normalize_key(title, artist) in self.known_tracks

    def knows_artist(self, artist: str) -> bool:
        return self.artist_plays.get(artist.lower(), 0) > 0


_cache: tuple[str, Library] | None = None


def get_library() -> Library:
    """Load the library, re-reading the cache only when its content hash changes."""
    global _cache
    meta = store.read_meta()
    key = meta.get("content_hash") or meta.get("last_sync") or ""
    if _cache and _cache[0] == key:
        return _cache[1]

    data = store.load_all()
    lib = Library(data=data)
    tracks = list(data["history"]) + list(data["saved_tracks"])
    for items in data["top_tracks"].values():
        tracks.extend(items)
    for t in tracks:
        for a in t.get("artists") or []:
            lib.known_tracks.add(store.normalize_key(t["name"], a))
    for p in tracks:
        for a in p.get("artists") or []:
            lib.artist_plays[a.lower()] += 1
    for items in data["top_artists"].values():
        for a in items:
            lib.artist_plays[a["name"].lower()] += 1
    _cache = (key, lib)
    return lib
