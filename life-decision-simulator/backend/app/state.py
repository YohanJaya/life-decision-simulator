from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional
from pydantic import BaseModel

from .schemas import (
    UserProfile,
    Scenario,
    QuantResult,
    ResearchResult,
    TradeoffMatrix,
    DecisionBrief,
)


class SessionState(BaseModel):
    session_id: str
    phase: Literal["intake", "scenarios", "analysis", "exploration", "brief"] = "intake"
    chat_history: list[dict] = []          # list of {"role": "user"|"assistant", "content": str}
    profile: Optional[UserProfile] = None
    scenarios: list[Scenario] = []
    quant_results: list[QuantResult] = []
    research_results: list[ResearchResult] = []
    tradeoff_matrix: Optional[TradeoffMatrix] = None
    brief: Optional[DecisionBrief] = None


class MemoryStore(ABC):
    """Interface — swap InMemoryStore for Redis/SQLite without touching callers."""

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionState]: ...

    @abstractmethod
    def set(self, session_id: str, state: SessionState) -> None: ...

    @abstractmethod
    def delete(self, session_id: str) -> None: ...


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._store: dict[str, SessionState] = {}

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._store.get(session_id)

    def set(self, session_id: str, state: SessionState) -> None:
        self._store[session_id] = state

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)


# Singleton used by the FastAPI app
store: MemoryStore = InMemoryStore()
