from __future__ import annotations

# Milestone 5 — SYSTEM_PROMPT to be approved before implementation
SYSTEM_PROMPT = ""  # filled in M5

from .base import BaseAgent, AgentOutput
from ..state import SessionState


class WhatIfSimulatorAgent(BaseAgent):
    name = "what_if"

    async def run(self, state: SessionState) -> AgentOutput:
        raise NotImplementedError("WhatIfSimulatorAgent implemented in Milestone 5")
