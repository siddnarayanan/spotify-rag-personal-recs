"""Rate-limit-aware Spotify clients.

* ``user_client()``  — authenticated as the user, used only by the daily sync.
* ``search_client()`` — client-credentials, with an on-disk HTTP cache so the agent
  can verify the same track many times while hitting Spotify only once per week.

Both use spotipy's urllib3 retry, which honours ``Retry-After`` on HTTP 429.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from functools import lru_cache

import requests_cache
import spotipy
from requests_cache import DO_NOT_CACHE
from spotipy.oauth2 import SpotifyClientCredentials

from app.config import get_settings
from app.spotify.auth import get_oauth

log = logging.getLogger(__name__)

_RETRY_KW = dict(retries=5, status_retries=5, backoff_factor=0.6, requests_timeout=15)


def user_client() -> spotipy.Spotify:
    return spotipy.Spotify(auth_manager=get_oauth(), **_RETRY_KW)


@lru_cache
def search_client() -> spotipy.Spotify | None:
    s = get_settings()
    if not s.has_spotify_credentials:
        return None
    session = requests_cache.CachedSession(
        str(s.http_cache_path),
        backend="sqlite",
        allowable_methods=("GET",),
        urls_expire_after={"*/v1/search*": timedelta(days=7), "*": DO_NOT_CACHE},
    )
    return spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(s.spotify_client_id, s.spotify_client_secret),
        requests_session=session,
        **_RETRY_KW,
    )


def search_track(title: str, artist: str) -> dict | None:
    """Find a track in the Spotify catalog. Returns a normalized track or None."""
    sp = search_client()
    if sp is None:
        return None
    query = f'track:"{title}" artist:"{artist}"'
    try:
        res = sp.search(q=query, type="track", limit=5)
        items = res.get("tracks", {}).get("items", [])
        if not items:  # field filters can be strict; fall back to free text
            res = sp.search(q=f"{title} {artist}", type="track", limit=5)
            items = res.get("tracks", {}).get("items", [])
    except spotipy.SpotifyException as e:
        log.warning("Spotify search failed for %s / %s: %s", title, artist, e)
        return None
    if not items:
        return None
    artist_l = artist.lower()
    best = next(
        (t for t in items if any(a["name"].lower() == artist_l for a in t["artists"])), items[0]
    )
    return normalize_track(best)


def normalize_track(t: dict) -> dict:
    album = t.get("album") or {}
    images = album.get("images") or []
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "artists": [a["name"] for a in t.get("artists", [])],
        "artist_ids": [a.get("id") for a in t.get("artists", [])],
        "album": album.get("name"),
        "release_year": (album.get("release_date") or "")[:4] or None,
        "url": (t.get("external_urls") or {}).get("spotify"),
        "image": images[0]["url"] if images else None,
        "popularity": t.get("popularity"),
    }


def normalize_artist(a: dict) -> dict:
    images = a.get("images") or []
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        # Spotify has been phasing out genres for new apps; treat as optional.
        "genres": a.get("genres") or [],
        "popularity": a.get("popularity"),
        "url": (a.get("external_urls") or {}).get("spotify"),
        "image": images[0]["url"] if images else None,
    }
