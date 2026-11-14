"""Application settings loaded from environment / backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"), extra="ignore"
    )

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/auth/callback"
    spotify_scopes: str = (
        "user-read-recently-played user-top-read user-library-read playlist-read-private"
    )

    # LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    # Embeddings / RAG
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Behaviour
    demo_mode: bool = False
    sync_interval_hours: int = 24
    manual_sync_cooldown_minutes: int = 60
    saved_tracks_limit: int = 500
    frontend_origin: str = "http://127.0.0.1:5173"

    data_dir: Path = REPO_ROOT / "data"

    @property
    def cache_dir(self) -> Path:
        """Where listening data is read from: the bundled sample in demo mode."""
        return self.data_dir / ("sample" if self.demo_mode else "cache")

    @property
    def live_cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma" / ("demo" if self.demo_mode else "live")

    @property
    def token_cache_path(self) -> Path:
        return self.live_cache_dir / ".spotify_token"

    @property
    def http_cache_path(self) -> Path:
        return self.data_dir / "http_cache_search.sqlite"

    @property
    def has_spotify_credentials(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
