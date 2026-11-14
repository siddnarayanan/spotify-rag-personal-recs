"""Retrieval helpers: MMR search with optional doc-type filtering."""

from __future__ import annotations

from typing import Literal

from langchain_core.documents import Document

from app.rag.index import ensure_index, get_vectorstore

DocType = Literal["track", "artist", "period", "session", "playlists"]


def retrieve(query: str, doc_type: DocType | None = None, k: int = 8) -> list[Document]:
    """Maximal-marginal-relevance search, so results are relevant but not redundant."""
    ensure_index()
    vs = get_vectorstore()
    kwargs = {"filter": {"doc_type": doc_type}} if doc_type else {}
    return vs.max_marginal_relevance_search(query, k=k, fetch_k=max(30, k * 4), **kwargs)


def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(f"[{d.metadata.get('doc_type')}] {d.page_content}" for d in docs)
