from __future__ import annotations

# Milestone 4 — SYSTEM_PROMPT to be approved before implementation
SYSTEM_PROMPT = ""  # filled in M4

from .base import BaseAgent, AgentOutput
from ..state import SessionState


class TradeoffAnalyzerAgent(BaseAgent):
    name = "tradeoff_analyzer"

    async def run(self, state: SessionState) -> AgentOutput:
        raise NotImplementedError("TradeoffAnalyzerAgent implemented in Milestone 4")
