"""Spotify OAuth (Authorization Code flow) for the single local user."""

from __future__ import annotations

from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from app.config import get_settings


def get_oauth() -> SpotifyOAuth:
    s = get_settings()
    s.live_cache_dir.mkdir(parents=True, exist_ok=True)
    return SpotifyOAuth(
        client_id=s.spotify_client_id,
        client_secret=s.spotify_client_secret,
        redirect_uri=s.spotify_redirect_uri,
        scope=s.spotify_scopes,
        cache_handler=CacheFileHandler(cache_path=str(s.token_cache_path)),
        open_browser=False,
    )


def is_authenticated() -> bool:
    s = get_settings()
    if not s.has_spotify_credentials:
        return False
    oauth = get_oauth()
    token = oauth.cache_handler.get_cached_token()
    return bool(token and oauth.validate_token(token))


def authorize_url() -> str:
    return get_oauth().get_authorize_url()


def exchange_code(code: str) -> None:
    get_oauth().get_access_token(code, as_dict=False, check_cache=False)
