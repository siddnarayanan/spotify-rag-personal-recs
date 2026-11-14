"""LangChain agents: a structured recommender and a conversational chat agent."""

from __future__ import annotations

from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
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


def _model() -> ChatAnthropic:
    s = get_settings()
    if not s.anthropic_api_key:
        raise AgentConfigError("ANTHROPIC_API_KEY is not set.")
    return ChatAnthropic(
        model=s.anthropic_model, api_key=s.anthropic_api_key, max_tokens=4096, timeout=120
    )


@lru_cache
def recommender_agent():
    return create_agent(
        _model(),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(RecommendationList),
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
