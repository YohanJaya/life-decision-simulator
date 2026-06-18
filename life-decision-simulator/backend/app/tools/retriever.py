from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

_STORE_DIR = Path(__file__).parent.parent.parent / "qdrant_store"
_STORE_DIR.mkdir(parents=True, exist_ok=True)

# Loaded once at import time — first load downloads ~80 MB, then cached
try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("all-MiniLM-L6-v2")
    _VECTOR_SIZE = 384
    _EMBED_AVAILABLE = True
    logger.info("Sentence-transformer model loaded (dim=%d)", _VECTOR_SIZE)
except Exception as exc:
    _EMBED_AVAILABLE = False
    logger.warning("sentence-transformers unavailable, retriever disabled: %s", exc)


def _chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks or [text]


def _embed(texts: list[str]) -> list[list[float]]:
    return _model.encode(texts, show_progress_bar=False).tolist()


class ScenarioIndex:
    """Qdrant-backed persistent vector index for one scenario's search results.

    All heavy ops (embedding, disk I/O) run in a thread pool to keep the
    async event loop free.
    """

    def __init__(self, collection_name: str) -> None:
        # Collection names must be alphanumeric + underscore, max 255 chars
        self._name = collection_name.replace("-", "_")[:100]

    # ── sync helpers ─────────────────────────────────────────────────────────

    def _add_sync(self, results: list[dict]) -> int:
        if not _EMBED_AVAILABLE:
            return 0

        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct

        docs, metas, ids = [], [], []
        for r in results:
            text = f"{r.get('title', '')}\n{r.get('content', '')}"
            for i, chunk in enumerate(_chunk_text(text)):
                uid = hashlib.md5(f"{r.get('url', '')}:{i}".encode()).hexdigest()
                docs.append(chunk)
                metas.append({"url": r.get("url", ""), "title": r.get("title", "")})
                ids.append(uid)

        if not docs:
            return 0

        vectors = _embed(docs)

        client = QdrantClient(path=str(_STORE_DIR))

        # Create collection if it doesn't exist yet
        existing = [c.name for c in client.get_collections().collections]
        if self._name not in existing:
            client.create_collection(
                collection_name=self._name,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )

        points = [
            PointStruct(
                id=abs(int(uid[:8], 16)),   # Qdrant needs integer or UUID ids
                vector=vec,
                payload={"text": doc, "url": meta["url"], "title": meta["title"]},
            )
            for uid, vec, doc, meta in zip(ids, vectors, docs, metas)
        ]
        client.upsert(collection_name=self._name, points=points)
        logger.info("Stored %d chunks in Qdrant collection '%s'", len(points), self._name)
        return len(points)

    def _query_sync(self, question: str, top_k: int) -> list[dict]:
        if not _EMBED_AVAILABLE:
            return []

        from qdrant_client import QdrantClient

        client = QdrantClient(path=str(_STORE_DIR))
        existing = [c.name for c in client.get_collections().collections]
        if self._name not in existing:
            return []

        q_vec = _embed([question])[0]
        hits = client.search(
            collection_name=self._name,
            query_vector=q_vec,
            limit=top_k,
        )
        return [
            {
                "content": h.payload.get("text", ""),
                "url": h.payload.get("url", ""),
                "title": h.payload.get("title", ""),
            }
            for h in hits
        ]

    # ── async API ─────────────────────────────────────────────────────────────

    async def add_results(self, results: list[dict]) -> int:
        try:
            return await asyncio.to_thread(self._add_sync, results)
        except Exception as exc:
            logger.error("Qdrant add failed: %s", exc)
            return 0

    async def query(self, question: str, top_k: int = 6) -> list[dict]:
        try:
            return await asyncio.to_thread(self._query_sync, question, top_k)
        except Exception as exc:
            logger.error("Qdrant query failed: %s", exc)
            return []
