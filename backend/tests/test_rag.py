from collections import Counter

from app import store
from app.rag.documents import build_documents
from app.rag.index import build_index
from app.rag.retriever import retrieve


def test_documents_cover_all_types_with_scalar_metadata():
    docs = build_documents(store.load_all())
    types = Counter(d.metadata["doc_type"] for d in docs)
    assert {"track", "artist", "period", "session", "playlists"} <= set(types)
    assert types["period"] == 3
    for d in docs:  # Chroma only accepts scalar metadata
        assert all(isinstance(v, str | int | float | bool) for v in d.metadata.values())


def test_track_doc_mentions_listening_facts():
    docs = build_documents(store.load_all())
    nights = next(d for d in docs if d.metadata.get("name") == "Nights")
    assert "Frank Ocean" in nights.page_content
    assert "top tracks" in nights.page_content


def test_index_is_rebuilt_only_when_content_changes():
    n = build_index()
    assert n > 0
    assert build_index() == n  # hash unchanged -> no-op, same count
    from app.rag.index import get_vectorstore

    assert len(get_vectorstore().get(include=[])["ids"]) == n


def test_parallel_retrieval_on_cold_store_is_safe():
    # The agent's ToolNode runs parallel tool calls in threads; the first calls
    # must not race to create the Chroma client.
    from concurrent.futures import ThreadPoolExecutor

    build_index()
    from app.rag.index import get_vectorstore

    get_vectorstore.cache_clear()
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda q: retrieve(q, k=3), [f"query {i}" for i in range(16)]))
    assert all(len(r) == 3 for r in results)


def test_retrieve_filters_by_doc_type():
    build_index()
    docs = retrieve("anything", doc_type="artist", k=5)
    assert docs and all(d.metadata["doc_type"] == "artist" for d in docs)
