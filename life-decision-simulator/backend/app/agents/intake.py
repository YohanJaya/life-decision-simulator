from __future__ import annotations

# Milestone 2 — SYSTEM_PROMPT to be approved before implementation
SYSTEM_PROMPT = ""  # filled in M2

from .base import BaseAgent, AgentOutput
from ..state import SessionState


class IntakeAgent(BaseAgent):
    name = "intake"

    async def run(self, state: SessionState) -> AgentOutput:
        raise NotImplementedError("IntakeAgent implemented in Milestone 2")
