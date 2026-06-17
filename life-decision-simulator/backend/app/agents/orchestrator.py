from __future__ import annotations

# Milestone 4 — compile_brief() implemented there
SYSTEM_PROMPT = ""  # filled in M4

from .base import BaseAgent, AgentOutput
from ..state import SessionState


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"

    async def run(self, state: SessionState) -> AgentOutput:
        raise NotImplementedError("OrchestratorAgent implemented in Milestone 4")
