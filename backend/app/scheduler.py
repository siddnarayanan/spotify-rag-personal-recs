"""Background scheduler: keep the cache at most one day old."""

from __future__ import annotations

import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app import store
from app.config import get_settings
from app.rag.index import build_index
from app.spotify import auth
from app.spotify.sync import SyncError, run_sync

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
JOB_ID = "daily_sync"


def sync_and_index(force: bool = False) -> dict | None:
    """Sync from Spotify (if stale or forced) and refresh the vector index."""
    meta = run_sync(force=force)
    build_index()  # no-op if nothing changed
    return meta


def _scheduled_job() -> None:
    if not auth.is_authenticated():
        log.info("Skipping scheduled sync: Spotify not connected.")
        return
    try:
        sync_and_index(force=False)
    except SyncError as e:
        log.warning("Scheduled sync skipped: %s", e)
    except Exception:
        log.exception("Scheduled sync failed")


def startup() -> None:
    """Called once from the FastAPI lifespan, in a background thread."""
    global _scheduler
    s = get_settings()
    if s.demo_mode:
        build_index()
        return
    _scheduled_job()  # catch up if the server was off for >24h
    build_index()
    _scheduler = BackgroundScheduler(daemon=True)
    # Hourly check, but run_sync only hits Spotify when the cache is >24h old,
    # so a sync happens once a day regardless of restarts.
    _scheduler.add_job(_scheduled_job, "interval", hours=1, id=JOB_ID, coalesce=True)
    _scheduler.start()


def shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)


def next_sync_time() -> str | None:
    s = get_settings()
    last = store.last_sync(s.live_cache_dir)
    if s.demo_mode or last is None:
        return None
    return (last + timedelta(hours=s.sync_interval_hours)).isoformat()
