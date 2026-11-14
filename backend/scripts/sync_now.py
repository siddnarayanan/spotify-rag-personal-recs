"""Force a Spotify sync + reindex from the command line.

Usage (from backend/):  uv run python -m scripts.sync_now [--if-stale]
"""

import argparse
import logging
import sys

from app.scheduler import sync_and_index
from app.spotify import auth

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-stale", action="store_true", help="only sync if >24h old")
    args = parser.parse_args()
    if not auth.is_authenticated():
        sys.exit("Not connected to Spotify. Start the server and visit /auth/login first.")
    meta = sync_and_index(force=not args.if_stale)
    print(meta or "Cache is fresh; nothing to do.")
