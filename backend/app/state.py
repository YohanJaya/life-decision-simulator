from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SESSIONS_DIR = Path(__file__).parent.parent / "sessions"
_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

from .schemas import (
    UserProfile,
    Scenario,
    QuantResult,
    ResearchResult,
    MarketOutlook,
    MonteCarloResult,
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
    market_outlooks: list[MarketOutlook] = []
    monte_carlo_results: list[MonteCarloResult] = []
    tradeoff_matrix: Optional[TradeoffMatrix] = None
    brief: Optional[DecisionBrief] = None
    perturbation: Optional[str] = None


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


class FileStore(MemoryStore):
    """Persists each session as a JSON file under backend/sessions/."""

    def _path(self, session_id: str) -> Path:
        return _SESSIONS_DIR / f"{session_id}.json"

    def get(self, session_id: str) -> Optional[SessionState]:
        p = self._path(session_id)
        if not p.exists():
            return None
        try:
            return SessionState.model_validate_json(p.read_text())
        except Exception as exc:
            logger.warning("Failed to load session %s: %s", session_id, exc)
            return None

    def set(self, session_id: str, state: SessionState) -> None:
        try:
            self._path(session_id).write_text(state.model_dump_json())
        except Exception as exc:
            logger.warning("Failed to save session %s: %s", session_id, exc)

    def delete(self, session_id: str) -> None:
        self._path(session_id).unlink(missing_ok=True)


# Singleton used by the FastAPI app
store: MemoryStore = FileStore()
