from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from app import store
from app.config import get_settings
from app.spotify import sync


def _raw_track(i: int) -> dict:
    return {
        "id": f"t{i}",
        "name": f"Song {i}",
        "artists": [{"id": f"a{i}", "name": f"Artist {i}"}],
        "album": {"name": "Album", "release_date": "2021-05-01", "images": [{"url": "img"}]},
        "external_urls": {"spotify": f"https://open.spotify.com/track/t{i}"},
        "popularity": 50,
    }


def _mock_spotify() -> MagicMock:
    sp = MagicMock()
    sp.current_user_recently_played.return_value = {
        "items": [
            {"played_at": f"2026-11-1{i}T10:00:00Z", "track": _raw_track(i)} for i in range(3)
        ]
    }
    sp.current_user_top_tracks.return_value = {"items": [_raw_track(1)]}
    sp.current_user_top_artists.return_value = {
        "items": [{"id": "a1", "name": "Artist 1", "genres": ["indie"], "images": []}]
    }
    sp.current_user_saved_tracks.return_value = {
        "items": [{"added_at": "2026-01-01T00:00:00Z", "track": _raw_track(9)}],
        "next": None,
    }
    sp.current_user_playlists.return_value = {
        "items": [{"name": "Chill", "description": None}],
        "next": None,
    }
    return sp


def test_merge_history_dedupes_and_sorts():
    a = {"played_at": "2026-11-02T00:00:00Z", "id": "x"}
    b = {"played_at": "2026-11-01T00:00:00Z", "id": "y"}
    merged = sync.merge_history([a], [a, b])
    assert merged == [b, a]


def test_snapshot_normalizes_and_history_accumulates():
    cache = get_settings().live_cache_dir
    snap = sync.fetch_snapshot(_mock_spotify())
    assert snap["plays"][0]["artists"] == ["Artist 0"]
    assert snap["plays"][0]["release_year"] == "2021"
    assert set(snap["top_tracks"]) == set(store.TIME_RANGES)

    sync.write_snapshot(snap, cache)
    sync.write_snapshot(snap, cache)  # same plays again -> no duplicates
    assert len(store.read_history(cache)) == 3

    snap["plays"].append({**snap["plays"][0], "played_at": "2026-11-20T10:00:00Z"})
    meta = sync.write_snapshot(snap, cache)
    assert meta["counts"]["history"] == 4
    assert store.read_json("playlists.json", None, cache) == [{"name": "Chill", "description": ""}]


def test_is_stale():
    cache = get_settings().live_cache_dir
    assert sync.is_stale()  # never synced
    fresh = datetime.now(UTC) - timedelta(hours=2)
    store.write_json_atomic(cache / "meta.json", {"last_sync": fresh.isoformat()})
    assert not sync.is_stale()
    old = datetime.now(UTC) - timedelta(hours=25)
    store.write_json_atomic(cache / "meta.json", {"last_sync": old.isoformat()})
    assert sync.is_stale()


def test_run_sync_refuses_in_demo_mode():
    try:
        sync.run_sync()
    except sync.SyncError as e:
        assert "demo" in str(e).lower()
    else:
        raise AssertionError("expected SyncError")
