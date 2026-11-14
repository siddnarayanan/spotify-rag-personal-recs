"""Test fixtures: isolated data dir (copy of the sample dataset) + fake embeddings.

No network, no model downloads, no API keys required.
"""

import shutil

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.config import REPO_ROOT, get_settings


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    shutil.copytree(REPO_ROOT / "data" / "sample", data / "sample")
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_PROFILE", raising=False)
    # Hide any local `ant auth login` profile so tests behave the same everywhere.
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path / "no-anthropic-config"))
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "")

    import app.agent.agent as agent_mod
    import app.agent.library as library
    import app.rag.index as index
    import app.spotify.client as client

    for fn in (
        get_settings,
        index.get_embeddings,
        index.get_vectorstore,
        client.search_client,
        agent_mod.recommender_agent,
        agent_mod.chat_agent,
    ):
        fn.cache_clear()
    library._cache = None
    monkeypatch.setattr(index, "get_embeddings", lambda: DeterministicFakeEmbedding(size=64))
    yield data
    index.get_vectorstore.cache_clear()
    get_settings.cache_clear()
