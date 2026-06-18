"""Shared pytest fixtures.

These run with no API keys, no Qdrant, and no network: the LLM/web-search/retriever
layers are never exercised here, and session state is kept in memory so tests don't
write JSON files into backend/sessions/.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.state import InMemoryStore


@pytest.fixture(autouse=True)
def in_memory_store(monkeypatch):
    """Swap the on-disk FileStore for an in-memory store for the duration of a test."""
    store = InMemoryStore()
    monkeypatch.setattr(main_module, "store", store)
    return store


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def session_id(client: TestClient) -> str:
    """A freshly created session in the default (intake) phase."""
    return client.post("/api/session").json()["session_id"]
