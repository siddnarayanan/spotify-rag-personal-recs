"""Turn the cached listening data into LangChain Documents for the vector store.

Four document types, each tagged with ``doc_type`` metadata so the retriever can
filter on it:

* ``track``    one per unique track, with how and how often you listened to it
* ``artist``   one per artist, with top-chart ranks, genres and your tracks by them
* ``period``   your top artists/tracks for each Spotify time range
* ``session``  what you played on each day (lets the agent pick up recent moods)
"""

from __future__ import annotations

from collections import Counter, defaultdict

from langchain_core.documents import Document

from app import store

RANGE_LABEL = {
    "short_term": "the last 4 weeks",
    "medium_term": "the last 6 months",
    "long_term": "all time",
}


def _artists(t: dict) -> str:
    return ", ".join(t.get("artists") or [])


def build_documents(data: dict) -> list[Document]:
    history, top_tracks = data["history"], data["top_tracks"]
    top_artists, saved = data["top_artists"], data["saved_tracks"]

    # ---- tracks -------------------------------------------------------------
    tracks: dict[str, dict] = {}
    plays: Counter[str] = Counter()
    last_played: dict[str, str] = {}
    top_rank: dict[str, dict[str, int]] = defaultdict(dict)
    saved_at: dict[str, str] = {}

    for p in history:
        tracks.setdefault(p["id"], p)
        plays[p["id"]] += 1
        last_played[p["id"]] = max(last_played.get(p["id"], ""), p["played_at"])
    for tr, items in top_tracks.items():
        for i, t in enumerate(items, 1):
            tracks.setdefault(t["id"], t)
            top_rank[t["id"]][tr] = i
    for t in saved:
        tracks.setdefault(t["id"], t)
        saved_at[t["id"]] = t.get("added_at", "")

    docs: list[Document] = []
    for tid, t in tracks.items():
        facts = []
        if plays[tid]:
            facts.append(f"played {plays[tid]} time(s) recently, last on {last_played[tid][:10]}")
        for tr, rank in top_rank[tid].items():
            facts.append(f"#{rank} in your top tracks for {RANGE_LABEL[tr]}")
        if tid in saved_at:
            facts.append(f"saved to Liked Songs on {saved_at[tid][:10]}")
        year = f" ({t['release_year']})" if t.get("release_year") else ""
        content = (
            f"Track: {t['name']} by {_artists(t)}. Album: {t.get('album')}{year}.\n"
            f"Your listening: {'; '.join(facts) or 'in your library'}."
        )
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "doc_type": "track",
                    "track_id": tid,
                    "name": t["name"],
                    "artists": _artists(t),
                    "play_count": plays[tid],
                    "in_top": bool(top_rank[tid]),
                    "saved": tid in saved_at,
                    "url": t.get("url") or "",
                },
            )
        )

    # ---- artists ------------------------------------------------------------
    artist_info: dict[str, dict] = {}
    artist_rank: dict[str, dict[str, int]] = defaultdict(dict)
    for tr, items in top_artists.items():
        for i, a in enumerate(items, 1):
            artist_info.setdefault(a["name"], a)
            artist_rank[a["name"]][tr] = i
    artist_tracks: dict[str, set[str]] = defaultdict(set)
    artist_plays: Counter[str] = Counter()
    for tid, t in tracks.items():
        for name in t.get("artists") or []:
            artist_tracks[name].add(t["name"])
            artist_plays[name] += plays[tid]

    for name in set(artist_info) | {a for a, ts in artist_tracks.items() if len(ts) >= 2}:
        info = artist_info.get(name, {})
        facts = [
            f"#{r} in your top artists for {RANGE_LABEL[tr]}" for tr, r in artist_rank[name].items()
        ]
        genres = ", ".join(info.get("genres") or []) or "unknown"
        sample = ", ".join(sorted(artist_tracks[name])[:10]) or "none cached"
        content = (
            f"Artist: {name}. Genres: {genres}.\n"
            f"Your listening: {'; '.join(facts) or 'appears in your library'}; "
            f"{artist_plays[name]} recent play(s).\n"
            f"Tracks of theirs you know: {sample}."
        )
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "doc_type": "artist",
                    "name": name,
                    "genres": genres,
                    "play_count": artist_plays[name],
                    "in_top": bool(artist_rank[name]),
                    "url": info.get("url") or "",
                },
            )
        )

    # ---- periods ------------------------------------------------------------
    for tr in store.TIME_RANGES:
        arts = [a["name"] for a in top_artists.get(tr, [])[:20]]
        trks = [f"{t['name']} – {_artists(t)}" for t in top_tracks.get(tr, [])[:20]]
        if not arts and not trks:
            continue
        genres = Counter(g for a in top_artists.get(tr, []) for g in a.get("genres") or [])
        content = (
            f"Your taste over {RANGE_LABEL[tr]}.\n"
            f"Top artists: {', '.join(arts)}.\n"
            f"Top tracks: {'; '.join(trks)}.\n"
            f"Top genres: {', '.join(g for g, _ in genres.most_common(10)) or 'unknown'}."
        )
        docs.append(
            Document(page_content=content, metadata={"doc_type": "period", "time_range": tr})
        )

    # ---- daily sessions -----------------------------------------------------
    by_day: dict[str, list[dict]] = defaultdict(list)
    for p in history:
        by_day[p["played_at"][:10]].append(p)
    for day, ps in sorted(by_day.items()):
        listed = "; ".join(f"{p['name']} – {_artists(p)}" for p in ps[:40])
        docs.append(
            Document(
                page_content=f"Listening session on {day} ({len(ps)} plays): {listed}.",
                metadata={"doc_type": "session", "date": day, "play_count": len(ps)},
            )
        )

    # ---- playlists (mood/context cues) --------------------------------------
    if data["playlists"]:
        names = "; ".join(
            p["name"] + (f" ({p['description']})" if p["description"] else "")
            for p in data["playlists"][:100]
        )
        docs.append(
            Document(page_content=f"Your playlists: {names}.", metadata={"doc_type": "playlists"})
        )
    return docs
