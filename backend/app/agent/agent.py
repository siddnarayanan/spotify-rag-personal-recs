"""LangChain agents: a structured recommender and a conversational chat agent."""

from __future__ import annotations

from functools import cached_property, lru_cache
from typing import Any

from anthropic.lib.credentials import default_credentials
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.library import get_library
from app.agent.prompts import CHAT_PROMPT, SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.config import get_settings
from app.schemas import Recommendation, RecommendationList
from app.spotify.client import search_track


class AgentConfigError(RuntimeError):
    pass


class ProfileAwareChatAnthropic(ChatAnthropic):
    """ChatAnthropic that can also authenticate with an `ant auth login` profile.

    ChatAnthropic always passes ``api_key`` to the SDK, even when it's empty, which
    stops the SDK from running its credential chain. When no key is configured we
    leave ``api_key`` out, so the SDK finds the profile in ~/.config/anthropic and
    refreshes the OAuth token itself.
    """

    @cached_property
    def _client_params(self) -> dict[str, Any]:
        params = dict(super()._client_params)
        if not params.get("api_key"):
            params.pop("api_key", None)
        return params


def llm_credentials_available() -> bool:
    """True if an API key is configured or the SDK can find profile/env credentials."""
    if get_settings().anthropic_api_key:
        return True
    try:
        return default_credentials() is not None
    except Exception:  # e.g. no config dir / profile found
        return False


def _model() -> ChatAnthropic:
    s = get_settings()
    if not llm_credentials_available():
        raise AgentConfigError(
            "No Anthropic credentials found. Set ANTHROPIC_API_KEY or run `ant auth login`."
        )
    kwargs: dict[str, Any] = {"api_key": s.anthropic_api_key} if s.anthropic_api_key else {}
    return ProfileAwareChatAnthropic(
        model=s.anthropic_model, max_tokens=4096, timeout=120, **kwargs
    )


@lru_cache
def recommender_agent():
    return create_agent(
        _model(),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        # Native structured output (Claude's JSON-schema output), not a forced tool call:
        # newer Claude models don't accept tool_choice="any", which ToolStrategy relies on.
        response_format=ProviderStrategy(RecommendationList),
    )


@lru_cache
def chat_agent():
    return create_agent(
        _model(), tools=TOOLS, system_prompt=CHAT_PROMPT, checkpointer=InMemorySaver()
    )


def build_request(prompt: str | None, count: int) -> str:
    msg = f"Recommend {count} tracks for me based on my listening history."
    if prompt:
        msg += f"\nWhat I'm in the mood for: {prompt}"
    return msg


def finalize(result: RecommendationList, count: int) -> RecommendationList:
    """Deterministic post-processing: drop known tracks and attach Spotify links/art.

    The LLM is asked to do this too, but we enforce it in code so the UI never
    shows a song the listener already has or a dead link.
    """
    lib = get_library()
    seen: set[str] = set()
    final: list[Recommendation] = []
    for rec in result.recommendations:
        key = f"{rec.title.lower()}|{rec.artist.lower()}"
        if key in seen or lib.knows_track(rec.title, rec.artist):
            continue
        seen.add(key)
        match = search_track(rec.title, rec.artist)
        if match:
            rec.spotify_url, rec.image_url, rec.verified = match["url"], match["image"], True
            rec.album = rec.album or match["album"]
        else:
            rec.spotify_url = (
                "https://open.spotify.com/search/" + f"{rec.title} {rec.artist}".replace(" ", "%20")
            )
        rec.novelty = "familiar_artist" if lib.knows_artist(rec.artist) else "new_artist"
        final.append(rec)
    result.recommendations = final[:count]
    return result
