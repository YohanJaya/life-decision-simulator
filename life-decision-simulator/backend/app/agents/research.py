from __future__ import annotations

# Milestone 3 — SYSTEM_PROMPT to be approved before implementation
SYSTEM_PROMPT = ""  # filled in M3

from .base import BaseAgent, AgentOutput
from ..state import SessionState


class ResearchAgent(BaseAgent):
    name = "research"

    async def run(self, state: SessionState) -> AgentOutput:
        raise NotImplementedError("ResearchAgent implemented in Milestone 3")
