from __future__ import annotations

import asyncio
import hashlib
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)

CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

# ── Shared Docker client (initialized once at import time) ────────────────────
# check_compatibility=False skips the version-probe HTTP call the client otherwise
# makes at construction — that call adds latency and emits a warning when Qdrant
# isn't running (e.g. during tests or before the Docker container is up).
_qdrant = QdrantClient("localhost", port=6333, check_compatibility=False)
logger.info("Qdrant client connected to localhost:6333")

# ── Embedding model (loaded lazily on first use, then cached for the process) ──
# Loading is deferred out of import time so the app — and its test suite — import
# without downloading ~90 MB or pulling torch into memory. The model is fetched
# once on the first embedding call and reused thereafter.
_VECTOR_SIZE = 384
_model = None
_model_load_attempted = False


def _get_model():
    """Return the embedding model, loading it on first call. Returns None if
    sentence-transformers is unavailable, so callers degrade gracefully."""
    global _model, _model_load_attempted
    if not _model_load_attempted:
        _model_load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence-transformer model loaded (dim=%d)", _VECTOR_SIZE)
        except Exception as exc:
            _model = None
            logger.warning("sentence-transformers unavailable, retriever disabled: %s", exc)
    return _model


def _embeddings_available() -> bool:
    return _get_model() is not None


def _chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks or [text]


def _embed(texts: list[str]) -> list[list[float]]:
    return _get_model().encode(texts, show_progress_bar=False).tolist()


def _ensure_collection(name: str) -> None:
    """Create the collection if it doesn't already exist."""
    existing = {c.name for c in _qdrant.get_collections().collections}
    if name not in existing:
        _qdrant.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s'", name)


class ScenarioIndex:
    """Vector index for one scenario's search results, backed by Docker Qdrant.

    The collection is created in __init__ so that by the time add_results or
    query is called, the collection is guaranteed to exist.
    """

    def __init__(self, collection_name: str) -> None:
        self._name = collection_name.replace("-", "_")[:100]
        if _embeddings_available():
            _ensure_collection(self._name)

    # ── sync helpers ──────────────────────────────────────────────────────────

    def _add_sync(self, results: list[dict]) -> int:
        if not _embeddings_available():
            return 0

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
        points = [
            PointStruct(
                id=abs(int(uid[:8], 16)),
                vector=vec,
                payload={"text": doc, "url": meta["url"], "title": meta["title"]},
            )
            for uid, vec, doc, meta in zip(ids, vectors, docs, metas)
        ]
        _qdrant.upsert(collection_name=self._name, points=points)
        logger.info("Stored %d chunks in '%s'", len(points), self._name)
        return len(points)

    def _query_sync(self, question: str, top_k: int) -> list[dict]:
        if not _embeddings_available():
            return []

        q_vec = _embed([question])[0]
        result = _qdrant.query_points(
            collection_name=self._name,
            query=q_vec,
            limit=top_k,
        )
        return [
            {
                "content": h.payload.get("text", ""),
                "url": h.payload.get("url", ""),
                "title": h.payload.get("title", ""),
            }
            for h in result.points
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
