"""Spotify login: /auth/login redirects to Spotify, /auth/callback stores the token."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.scheduler import sync_and_index
from app.spotify import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def login() -> RedirectResponse:
    s = get_settings()
    if s.demo_mode:
        raise HTTPException(400, "Login is disabled in demo mode.")
    if not s.has_spotify_credentials:
        raise HTTPException(500, "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET are not set.")
    return RedirectResponse(auth.authorize_url())


@router.get("/callback")
def callback(
    background: BackgroundTasks, code: str | None = None, error: str | None = None
) -> RedirectResponse:
    s = get_settings()
    if error or not code:
        return RedirectResponse(f"{s.frontend_origin}/?auth_error={error or 'missing_code'}")
    auth.exchange_code(code)
    background.add_task(sync_and_index, False)  # first sync right after login
    return RedirectResponse(f"{s.frontend_origin}/?connected=1")
