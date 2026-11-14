"""Generate the committed demo dataset in data/sample/.

This is a FICTIONAL listener profile built from well-known public tracks, so the app
can be run without Spotify credentials (DEMO_MODE=true). It is not anyone's real
listening history. Output is deterministic (fixed seed).

Usage (from backend/):  uv run python -m scripts.build_sample
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app import store
from app.config import REPO_ROOT
from app.spotify.sync import write_snapshot

OUT = REPO_ROOT / "data" / "sample"

# (title, artist, album, year, genres-of-artist)
CATALOG = [
    # indie / alt rock — the listener's core
    ("Do I Wanna Know?", "Arctic Monkeys", "AM", "2013", ["indie rock", "garage rock"]),
    ("505", "Arctic Monkeys", "Favourite Worst Nightmare", "2007", ["indie rock", "garage rock"]),
    ("R U Mine?", "Arctic Monkeys", "AM", "2013", ["indie rock", "garage rock"]),
    ("The Less I Know The Better", "Tame Impala", "Currents", "2015", ["psychedelic rock"]),
    ("Let It Happen", "Tame Impala", "Currents", "2015", ["psychedelic rock"]),
    ("Borderline", "Tame Impala", "The Slow Rush", "2020", ["psychedelic rock"]),
    ("Reptilia", "The Strokes", "Room on Fire", "2003", ["indie rock", "garage rock"]),
    ("Last Nite", "The Strokes", "Is This It", "2001", ["indie rock", "garage rock"]),
    ("Alright", "Mac DeMarco", "Salad Days", "2014", ["indie rock", "slacker rock"]),
    ("Chamber of Reflection", "Mac DeMarco", "Salad Days", "2014", ["indie rock", "slacker rock"]),
    ("Kyoto", "Phoebe Bridgers", "Punisher", "2020", ["indie folk", "indie rock"]),
    ("Motion Sickness", "Phoebe Bridgers", "Stranger in the Alps", "2017", ["indie folk"]),
    ("Seventeen", "Sharon Van Etten", "Remind Me Tomorrow", "2019", ["indie rock"]),
    ("Sofia", "Clairo", "Immunity", "2019", ["bedroom pop", "indie pop"]),
    ("Bags", "Clairo", "Immunity", "2019", ["bedroom pop", "indie pop"]),
    # R&B / neo-soul
    ("Nights", "Frank Ocean", "Blonde", "2016", ["alternative r&b"]),
    ("Pink + White", "Frank Ocean", "Blonde", "2016", ["alternative r&b"]),
    ("Thinkin Bout You", "Frank Ocean", "channel ORANGE", "2012", ["alternative r&b"]),
    ("Good Days", "SZA", "SOS", "2022", ["r&b", "alternative r&b"]),
    ("Kill Bill", "SZA", "SOS", "2022", ["r&b"]),
    (
        "See You Again",
        "Tyler, The Creator",
        "Flower Boy",
        "2017",
        ["hip hop", "alternative hip hop"],
    ),
    ("EARFQUAKE", "Tyler, The Creator", "IGOR", "2019", ["hip hop", "alternative hip hop"]),
    ("Redbone", "Childish Gambino", '"Awaken, My Love!"', "2016", ["funk", "neo soul"]),
    ("Come Down", "Anderson .Paak", "Malibu", "2016", ["neo soul", "funk"]),
    # electronic / chill
    ("Midnight City", "M83", "Hurry Up, We're Dreaming", "2011", ["synthpop", "shoegaze"]),
    ("Nightcall", "Kavinsky", "OutRun", "2013", ["synthwave"]),
    ("Kiara", "Bonobo", "Black Sands", "2010", ["downtempo", "electronica"]),
    ("Loud Places", "Jamie xx", "In Colour", "2015", ["electronica", "uk garage"]),
    ("Gosh", "Jamie xx", "In Colour", "2015", ["electronica", "uk garage"]),
    ("Breathe Deeper", "Tame Impala", "The Slow Rush", "2020", ["psychedelic rock"]),
    ("Space Song", "Beach House", "Depression Cherry", "2015", ["dream pop"]),
    ("Myth", "Beach House", "Bloom", "2012", ["dream pop"]),
    # older favourites (long-term only)
    ("Karma Police", "Radiohead", "OK Computer", "1997", ["art rock", "alternative rock"]),
    ("Weird Fishes/Arpeggi", "Radiohead", "In Rainbows", "2007", ["art rock"]),
    ("Heroes", "David Bowie", '"Heroes"', "1977", ["art rock", "glam rock"]),
    ("Dreams", "Fleetwood Mac", "Rumours", "1977", ["soft rock"]),
    ("Hey Jude", "The Beatles", "Hey Jude", "1968", ["rock", "british invasion"]),
]

PLAYLISTS = [
    {"name": "late night drives", "description": "synths and neon"},
    {"name": "sunday morning", "description": "slow, warm, coffee"},
    {"name": "gym", "description": ""},
    {"name": "indie sleaze revival", "description": "2000s guitar bands"},
    {"name": "focus", "description": "instrumental + downtempo"},
]


def _track(i: int, row: tuple) -> dict:
    title, artist, album, year, _ = row
    return {
        "id": f"sample-{i:03d}",
        "name": title,
        "artists": [artist],
        "artist_ids": [f"sample-artist-{artist.lower().replace(' ', '-')}"],
        "album": album,
        "release_year": year,
        "url": None,
        "image": None,
        "popularity": None,
    }


def build() -> dict:
    rng = random.Random(42)
    tracks = [_track(i, row) for i, row in enumerate(CATALOG)]
    genres = {row[1]: row[4] for row in CATALOG}

    recent_pool = tracks[:32]  # older favourites rarely appear in recent plays
    weights = [
        3 if t["artists"][0] in {"Tame Impala", "Frank Ocean", "Jamie xx"} else 1
        for t in recent_pool
    ]
    now = datetime(2026, 11, 12, 23, 0, tzinfo=UTC)
    plays = []
    for day in range(21):
        start = now - timedelta(days=day, hours=rng.randint(0, 10))
        for n in range(rng.randint(6, 16)):
            t = rng.choices(recent_pool, weights)[0]
            played_at = (start - timedelta(minutes=4 * n)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            plays.append({"played_at": played_at, **t})

    def ranked_artists(names: list[str]) -> list[dict]:
        return [
            {
                "id": f"sample-artist-{n.lower().replace(' ', '-')}",
                "name": n,
                "genres": genres[n],
                "popularity": None,
                "url": None,
                "image": None,
            }
            for n in names
        ]

    by_artist = {a: [t for t in tracks if t["artists"][0] == a] for a in genres}
    short = [
        "Tame Impala",
        "Frank Ocean",
        "Jamie xx",
        "Beach House",
        "Clairo",
        "SZA",
        "Arctic Monkeys",
        "Bonobo",
        "Phoebe Bridgers",
        "Kavinsky",
    ]
    medium = [
        "Arctic Monkeys",
        "Tame Impala",
        "Frank Ocean",
        "The Strokes",
        "Mac DeMarco",
        "Phoebe Bridgers",
        "Tyler, The Creator",
        "SZA",
        "M83",
        "Clairo",
    ]
    long_ = [
        "Radiohead",
        "Arctic Monkeys",
        "The Strokes",
        "Frank Ocean",
        "Tame Impala",
        "David Bowie",
        "Fleetwood Mac",
        "Childish Gambino",
        "The Beatles",
        "Mac DeMarco",
    ]

    def ranked_tracks(names: list[str]) -> list[dict]:
        return [t for n in names for t in by_artist[n][:2]]

    saved = [
        {"added_at": f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}T12:00:00Z", **t}
        for t in rng.sample(tracks, 18)
    ]
    return {
        "plays": plays,
        "top_tracks": {
            "short_term": ranked_tracks(short),
            "medium_term": ranked_tracks(medium),
            "long_term": ranked_tracks(long_),
        },
        "top_artists": {
            "short_term": ranked_artists(short),
            "medium_term": ranked_artists(medium),
            "long_term": ranked_artists(long_),
        },
        "saved_tracks": saved,
        "playlists": PLAYLISTS,
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "history.jsonl").unlink(missing_ok=True)  # regenerate from scratch
    meta = write_snapshot(build(), cache_dir=OUT)
    meta["note"] = "FICTIONAL demo listener generated by backend/scripts/build_sample.py"
    store.write_json_atomic(OUT / "meta.json", meta)
    print(f"Wrote sample dataset to {OUT}: {meta['counts']}")
