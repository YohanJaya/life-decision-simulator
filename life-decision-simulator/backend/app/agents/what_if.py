from __future__ import annotations

from pydantic import BaseModel
from typing import Literal

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import WhatIfDiff, QuantChange, TradeoffChange
from ..llm import chat_json_validated

SYSTEM_PROMPT = """\
You are a scenario analyst computing the differential impact of a hypothetical change
on an existing set of decision scenarios.

Given the current analysis (quant results + tradeoff matrix) and a perturbation
(a hypothetical change), compute ONLY what changes. Do not re-describe what stays the same.

For quant changes: include only scenarios where at least one financial figure shifts meaningfully.
For tradeoff changes: include only dimension scores that flip or shift.

Respond with ONLY valid JSON:
{
  "perturbation": "<restate the perturbation clearly>",
  "affected_scenario_ids": ["<id>"],
  "quant_changes": [
    {
      "scenario_id": "<id>",
      "field": "<e.g. five_year_cumulative_net>",
      "before_usd": 0.0,
      "after_usd": 0.0,
      "delta_usd": 0.0
    }
  ],
  "tradeoff_changes": [
    {
      "scenario_id": "<id>",
      "dimension": "<dimension>",
      "before_score": "strong|mixed|weak|unclear",
      "after_score": "strong|mixed|weak|unclear",
      "rationale": "<why it changed>"
    }
  ]
}
"""


class WhatIfOutput(AgentOutput):
    diff: WhatIfDiff


class WhatIfSimulatorAgent(BaseAgent):
    name = "what_if"

    async def run(self, state: SessionState) -> WhatIfOutput:
        if not state.scenarios:
            raise ValueError("Scenarios must exist before running what-if simulation")
        if not state.tradeoff_matrix:
            raise ValueError("Tradeoff matrix must exist before running what-if simulation")
        if not state.perturbation:
            raise ValueError("A perturbation must be set on the state before running what-if")

        scenarios_json = "[" + ", ".join(s.model_dump_json(indent=2) for s in state.scenarios) + "]"
        quant_json = "[" + ", ".join(q.model_dump_json(indent=2) for q in state.quant_results) + "]"
        tradeoff_json = state.tradeoff_matrix.model_dump_json(indent=2)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Perturbation: {state.perturbation}\n\n"
                    f"Scenarios:\n{scenarios_json}\n\n"
                    f"Current quant results:\n{quant_json}\n\n"
                    f"Current tradeoff matrix:\n{tradeoff_json}"
                ),
            },
        ]

        diff = await chat_json_validated(
            messages=messages,
            model_class=WhatIfDiff,
            agent_name=self.name,
            temperature=0.2,
        )

        return WhatIfOutput(diff=diff)
