from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import DecisionBrief
from ..llm import chat_json_validated

SYSTEM_PROMPT = """\
You are a senior advisor synthesizing a decision analysis into a concise brief.

Given all the analysis (scenarios, tradeoff matrix, quant results, research), produce:
- uncertainties: 3-5 key unknowns or risks that could change the recommendation
- user_questions: EXACTLY 3 clarifying questions the user should reflect on before deciding

Respond with ONLY valid JSON:
{
  "uncertainties": ["<uncertainty 1>", ...],
  "user_questions": ["<question 1>", "<question 2>", "<question 3>"]
}
"""


class _BriefMeta(BaseModel):
    uncertainties: list[str]
    user_questions: list[str]


class OrchestratorOutput(AgentOutput):
    brief: DecisionBrief


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"

    async def run(self, state: SessionState) -> OrchestratorOutput:
        if not state.scenarios:
            raise ValueError("Scenarios must exist before compiling brief")
        if not state.tradeoff_matrix:
            raise ValueError("Tradeoff matrix must exist before compiling brief")

        profile_json = state.profile.model_dump_json(indent=2) if state.profile else "{}"
        scenarios_json = "[" + ", ".join(s.model_dump_json(indent=2) for s in state.scenarios) + "]"
        quant_json = "[" + ", ".join(q.model_dump_json(indent=2) for q in state.quant_results) + "]"
        research_json = "[" + ", ".join(r.model_dump_json(indent=2) for r in state.research_results) + "]"
        outlook_json = "[" + ", ".join(o.model_dump_json(indent=2) for o in state.market_outlooks) + "]"
        mc_json = "[" + ", ".join(m.model_dump_json(indent=2) for m in state.monte_carlo_results) + "]"
        tradeoff_json = state.tradeoff_matrix.model_dump_json(indent=2)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User profile:\n{profile_json}\n\n"
                    f"Scenarios:\n{scenarios_json}\n\n"
                    f"Quant results:\n{quant_json}\n\n"
                    f"Research results:\n{research_json}\n\n"
                    f"Market outlooks (future job market signals):\n{outlook_json}\n\n"
                    f"Monte Carlo simulations (probability distributions across 5000 runs):\n{mc_json}\n\n"
                    f"Tradeoff matrix:\n{tradeoff_json}"
                ),
            },
        ]

        meta = await chat_json_validated(
            messages=messages,
            model_class=_BriefMeta,
            agent_name=self.name,
            temperature=0.3,
        )

        brief = DecisionBrief(
            session_id=state.session_id,
            scenarios=state.scenarios,
            tradeoff_matrix=state.tradeoff_matrix,
            named_tradeoffs=state.tradeoff_matrix.named_tradeoffs,
            uncertainties=meta.uncertainties,
            user_questions=meta.user_questions[:3],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        return OrchestratorOutput(brief=brief)
