from __future__ import annotations

from abc import ABC, abstractmethod
from pydantic import BaseModel

from ..state import SessionState


class AgentOutput(BaseModel):
    """Base class for all agent outputs. Each agent defines its own subclass."""
    pass


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    async def run(self, state: SessionState) -> AgentOutput:
        """Execute the agent against the current session state."""
        ...
