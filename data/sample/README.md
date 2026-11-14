# Sample dataset (fictional)

This folder holds a **fictional** listener's data in the same format the daily Spotify sync writes to `data/cache/`. It lets anyone run the app without a Spotify account:

```bash
DEMO_MODE=true uv run fastapi dev app/main.py   # from backend/
```

It is generated deterministically by `backend/scripts/build_sample.py` from well-known public tracks. It is not anyone's real listening history. Track IDs are placeholders (`sample-XXX`), so Spotify links fall back to search URLs. If Spotify client credentials are set, they resolve to real tracks.

Real personal data lives in `data/cache/`, which is gitignored.
