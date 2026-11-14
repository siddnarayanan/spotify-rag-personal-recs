"""Pydantic models shared by the agent and the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    title: str = Field(description="Track title")
    artist: str = Field(description="Primary artist name")
    album: str | None = None
    reason: str = Field(description="1–2 sentences on why this fits the listener's taste")
    evidence: list[str] = Field(
        default_factory=list,
        description="Specific tracks/artists from the listener's history that motivated this pick",
    )
    novelty: Literal["new_artist", "familiar_artist"] = Field(
        description="new_artist if the listener has no cached plays of this artist"
    )
    # Filled in server-side from the cached Spotify lookup:
    spotify_url: str | None = None
    image_url: str | None = None
    verified: bool = False


class RecommendationList(BaseModel):
    summary: str = Field(description="One-sentence read of the listener's current taste")
    recommendations: list[Recommendation]


class RecommendRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=500)
    count: int = Field(default=8, ge=1, le=15)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str = Field(default="default", max_length=100)
