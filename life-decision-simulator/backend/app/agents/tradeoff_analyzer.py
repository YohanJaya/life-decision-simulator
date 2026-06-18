from __future__ import annotations

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import TradeoffMatrix, TRADEOFF_DIMENSIONS
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

    @staticmethod
    def _summarize(state: SessionState) -> str:
        """Compact per-scenario summary — keeps the prompt well under 2k tokens."""
        quant_by_id    = {q.scenario_id: q for q in state.quant_results}
        outlook_by_id  = {o.scenario_id: o for o in state.market_outlooks}
        mc_by_id       = {m.scenario_id: m for m in state.monte_carlo_results}
        research_by_id = {r.scenario_id: r for r in state.research_results}

        lines = []
        for s in state.scenarios:
            sid = s.id
            q = quant_by_id.get(sid)
            o = outlook_by_id.get(sid)
            m = mc_by_id.get(sid)
            r = research_by_id.get(sid)

            lines.append(f"## {s.name} (id={sid})")
            if q:
                lines.append(
                    f"  Finance: salary_p50=${q.starting_salary_p50.value_usd:,.0f}, "
                    f"5yr_net=${q.five_year_cumulative_net.value_usd:,.0f}, "
                    f"debt=${q.debt_load.value_usd:,.0f}"
                )
            if o:
                lines.append(
                    f"  Market: growth={o.projected_growth}, automation_risk={o.automation_risk}, "
                    f"demand={o.demand_trend}, horizon_fit={o.time_horizon_fit}"
                )
            if m:
                lines.append(
                    f"  MonteCarlo: p50_net=${m.cumulative_net_p50:,.0f}, "
                    f"prob_positive={m.prob_positive:.0%}, risk={m.risk_label}"
                )
            if r:
                bullet_texts = "; ".join(b.text for b in r.bullets[:3])
                lines.append(f"  Key insights: {bullet_texts}")
            lines.append("")

        return "\n".join(lines)

    async def run(self, state: SessionState) -> TradeoffOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before analyzing tradeoffs")
        if not state.scenarios:
            raise ValueError("Scenarios must be generated before analyzing tradeoffs")

        profile_json     = state.profile.model_dump_json(indent=2)
        scenario_summary = self._summarize(state)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User profile:\n{profile_json}\n\n"
                    f"Scenario summaries:\n{scenario_summary}"
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
