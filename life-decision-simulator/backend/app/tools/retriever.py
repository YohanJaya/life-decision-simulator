from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 400   # chars per chunk
CHUNK_OVERLAP = 80


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks or [text]


def _embed_sync(texts: list[str]) -> list[list[float]]:
    embeddings = []
    with httpx.Client(timeout=30.0) as client:
        for text in texts:
            try:
                resp = client.post(
                    OLLAMA_EMBED_URL,
                    json={"model": EMBED_MODEL, "prompt": text},
                )
                resp.raise_for_status()
                embeddings.append(resp.json()["embedding"])
            except Exception as exc:
                logger.error("Embedding failed: %s", exc)
                # fall back to zero vector — retrieval will still work, just less precise
                embeddings.append([0.0] * 768)
    return embeddings


async def _embed(texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(_embed_sync, texts)


class ScenarioIndex:
    """In-memory ChromaDB collection for one scenario's search results."""

    def __init__(self, collection_name: str) -> None:
        import chromadb
        self._client = chromadb.EphemeralClient()
        safe_name = collection_name.replace(" ", "_")[:63]
        self._col = self._client.create_collection(safe_name)

    async def add_results(self, results: list[dict]) -> None:
        """Chunk, embed, and store search results."""
        docs: list[str] = []
        metas: list[dict] = []
        ids: list[str] = []

        for r in results:
            full_text = f"{r.get('title', '')}\n{r.get('content', '')}"
            for i, chunk in enumerate(_chunk_text(full_text)):
                uid = hashlib.md5(f"{r['url']}:{i}".encode()).hexdigest()
                docs.append(chunk)
                metas.append({"url": r.get("url", ""), "title": r.get("title", "")})
                ids.append(uid)

        if not docs:
            return

        embeddings = await _embed(docs)
        self._col.add(documents=docs, embeddings=embeddings, metadatas=metas, ids=ids)

    async def query(self, question: str, top_k: int = 8) -> list[dict]:
        """Return top_k most relevant chunks with metadata."""
        if self._col.count() == 0:
            return []

        q_embed = await _embed([question])
        results = self._col.query(
            query_embeddings=q_embed,
            n_results=min(top_k, self._col.count()),
            include=["documents", "metadatas"],
        )
        out = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            out.append({"content": doc, "url": meta.get("url", ""), "title": meta.get("title", "")})
        return out
