from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 400
CHUNK_OVERLAP = 80


def _chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks or [text]


class ScenarioIndex:
    """In-memory ChromaDB collection using the built-in embedding function.

    ChromaDB's default embedder (all-MiniLM-L6-v2) runs locally via
    sentence-transformers — no Ollama or external API required.
    It downloads the model (~80 MB) on first use and caches it.
    """

    def __init__(self, collection_name: str) -> None:
        import chromadb
        self._client = chromadb.EphemeralClient()
        safe_name = collection_name.replace(" ", "_")[:63]
        # No embedding_function arg = use ChromaDB's built-in (sentence-transformers)
        self._col = self._client.create_collection(safe_name)

    async def add_results(self, results: list[dict]) -> None:
        docs: list[str] = []
        metas: list[dict] = []
        ids: list[str] = []

        for r in results:
            full_text = f"{r.get('title', '')}\n{r.get('content', '')}"
            for i, chunk in enumerate(_chunk_text(full_text)):
                uid = hashlib.md5(f"{r.get('url', '')}:{i}".encode()).hexdigest()
                docs.append(chunk)
                metas.append({"url": r.get("url", ""), "title": r.get("title", "")})
                ids.append(uid)

        if not docs:
            return

        try:
            self._col.add(documents=docs, metadatas=metas, ids=ids)
        except Exception as exc:
            logger.error("ChromaDB add failed: %s", exc)

    async def query(self, question: str, top_k: int = 8) -> list[dict]:
        if self._col.count() == 0:
            return []
        try:
            results = self._col.query(
                query_texts=[question],
                n_results=min(top_k, self._col.count()),
                include=["documents", "metadatas"],
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return [
                {"content": doc, "url": m.get("url", ""), "title": m.get("title", "")}
                for doc, m in zip(docs, metas)
            ]
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []
