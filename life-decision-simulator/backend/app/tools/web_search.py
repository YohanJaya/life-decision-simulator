from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

try:
    from tavily import TavilyClient as _TavilyClient
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False
    logger.warning("tavily-python not installed — web search disabled")


def search(query: str, max_results: int = 5) -> list[dict]:
    """Synchronous Tavily search.

    Returns list of {"title": str, "url": str, "content": str}.
    Returns empty list if Tavily is unavailable or key is missing.
    """
    if not _TAVILY_AVAILABLE or not settings.tavily_api_key:
        logger.warning("Tavily search skipped (unavailable or no key): %s", query)
        return []

    client = _TavilyClient(api_key=settings.tavily_api_key)
    try:
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            })
        return results
    except Exception as exc:
        logger.error("Tavily search error for query '%s': %s", query, exc)
        return []


async def async_search(query: str, max_results: int = 5) -> list[dict]:
    return await asyncio.to_thread(search, query, max_results)
