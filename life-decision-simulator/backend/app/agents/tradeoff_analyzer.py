from __future__ import annotations

from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import TradeoffMatrix, TradeoffEntry, TRADEOFF_DIMENSIONS
from ..llm import chat_json_validated

SYSTEM_PROMPT = f"""\
You are a strategic analyst evaluating decision scenarios across multiple dimensions.

The 8 dimensions to score are:
{", ".join(TRADEOFF_DIMENSIONS)}

For each scenario × dimension pair, assign a score:
- "strong": clearly positive outcome on this dimension
- "mixed": trade-offs present, not clearly good or bad
- "weak": clearly negative outcome on this dimension
- "unclear": insufficient information to judge

Also identify 3-5 named tradeoffs — plain English phrases capturing the key tensions
across scenarios, e.g. "salary now vs. optionality later".

Respond with ONLY valid JSON:
{{
  "entries": [
    {{
      "scenario_id": "<id>",
      "dimension": "<dimension>",
      "score": "strong|mixed|weak|unclear",
      "rationale": "<one sentence>"
    }}
  ],
  "named_tradeoffs": ["<tradeoff 1>", "<tradeoff 2>"]
}}
"""


class TradeoffOutput(AgentOutput):
    matrix: TradeoffMatrix


class TradeoffAnalyzerAgent(BaseAgent):
    name = "tradeoff_analyzer"

    async def run(self, state: SessionState) -> TradeoffOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before analyzing tradeoffs")
        if not state.scenarios:
            raise ValueError("Scenarios must be generated before analyzing tradeoffs")

        profile_json = state.profile.model_dump_json(indent=2)
        scenarios_json = "[" + ", ".join(s.model_dump_json(indent=2) for s in state.scenarios) + "]"
        quant_json = "[" + ", ".join(q.model_dump_json(indent=2) for q in state.quant_results) + "]"
        research_json = "[" + ", ".join(r.model_dump_json(indent=2) for r in state.research_results) + "]"
        outlook_json = "[" + ", ".join(o.model_dump_json(indent=2) for o in state.market_outlooks) + "]"
        mc_json = "[" + ", ".join(m.model_dump_json(indent=2) for m in state.monte_carlo_results) + "]"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User profile:\n{profile_json}\n\n"
                    f"Scenarios:\n{scenarios_json}\n\n"
                    f"Quantitative results:\n{quant_json}\n\n"
                    f"Research results:\n{research_json}\n\n"
                    f"Market outlooks (future job market signals):\n{outlook_json}\n\n"
                    f"Monte Carlo simulations (probability distributions across 5000 runs):\n{mc_json}"
                ),
            },
        ]

        matrix = await chat_json_validated(
            messages=messages,
            model_class=TradeoffMatrix,
            agent_name=self.name,
            temperature=0.2,
        )

        return TradeoffOutput(matrix=matrix)
