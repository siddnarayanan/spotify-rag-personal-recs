import json

import app.agent.agent as agent_mod
from app.agent.tools import check_already_known, get_listening_stats
from app.schemas import Recommendation, RecommendationList


def _rec(title: str, artist: str) -> Recommendation:
    return Recommendation(title=title, artist=artist, reason="r", novelty="new_artist")


def test_check_already_known_uses_library():
    out = json.loads(
        check_already_known.invoke(
            {"candidates": ["Nights - Frank Ocean", "Ivy - Frank Ocean", "Song - Brand New Band"]}
        )
    )
    assert [o["track_already_known"] for o in out] == [True, False, False]
    assert [o["artist_new_to_listener"] for o in out] == [False, False, True]


def test_listening_stats_shape():
    stats = json.loads(get_listening_stats.invoke({}))
    assert "Tame Impala" in stats["top_artists_short_term (the last 4 weeks)"]
    assert stats["history_plays_cached"] > 0


def test_finalize_drops_known_and_duplicates_and_enriches(monkeypatch):
    monkeypatch.setattr(
        agent_mod,
        "search_track",
        lambda t, a: (
            {"url": f"https://open.spotify.com/track/{t}", "image": "img", "album": "LP"}
            if t != "Ghost"
            else None
        ),
    )
    result = RecommendationList(
        summary="s",
        recommendations=[
            _rec("Nights", "Frank Ocean"),  # already known -> dropped
            _rec("Ivy", "Frank Ocean"),  # familiar artist deep cut
            _rec("Ivy", "Frank Ocean"),  # duplicate -> dropped
            _rec("Ghost", "Unknown Artist"),  # not found on Spotify -> search link
            _rec("Archangel", "Burial"),
        ],
    )
    out = agent_mod.finalize(result, count=10).recommendations
    assert [r.title for r in out] == ["Ivy", "Ghost", "Archangel"]
    assert out[0].novelty == "familiar_artist" and out[0].verified and out[0].album == "LP"
    assert not out[1].verified and "search" in out[1].spotify_url
    assert out[2].novelty == "new_artist"


def test_finalize_respects_count(monkeypatch):
    monkeypatch.setattr(agent_mod, "search_track", lambda t, a: None)
    recs = [_rec(f"Song {i}", "Someone New") for i in range(5)]
    out = agent_mod.finalize(RecommendationList(summary="", recommendations=recs), count=2)
    assert len(out.recommendations) == 2
