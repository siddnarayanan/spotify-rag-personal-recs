"""Persistent Chroma index over the listening-data documents.

The index is rebuilt only when the documents change (tracked by a content hash),
so restarting the server or re-running a sync with no new plays costs nothing.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app import store
from app.config import get_settings
from app.rag.documents import build_documents

log = logging.getLogger(__name__)
COLLECTION = "listening_history"
_lock = threading.Lock()


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=get_settings().embedding_model,
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache
def get_vectorstore() -> Chroma:
    s = get_settings()
    s.chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(s.chroma_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )


def _hash_path():
    return get_settings().chroma_dir / "index_hash.txt"


def build_index(force: bool = False) -> int:
    """(Re)build the index from the cache if its contents changed. Returns doc count."""
    with _lock:
        docs = build_documents(store.load_all())
        digest = hashlib.sha256(
            "\n".join(sorted(d.page_content for d in docs)).encode()
        ).hexdigest()
        hp = _hash_path()
        if not force and hp.exists() and hp.read_text() == digest:
            log.info("Index up to date (%d docs).", len(docs))
            return len(docs)

        vs = get_vectorstore()
        existing = vs.get(include=[])["ids"]
        if existing:
            vs.delete(ids=existing)
        if docs:
            vs.add_documents(docs, ids=[f"doc-{i}" for i in range(len(docs))])
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(digest)
        log.info("Indexed %d documents.", len(docs))
        return len(docs)


def ensure_index() -> None:
    if not _hash_path().exists():
        build_index()
