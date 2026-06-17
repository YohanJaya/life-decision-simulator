from __future__ import annotations

import asyncio
from pydantic import BaseModel
from typing import Optional

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import ResearchResult, ResearchBullet, QuantResult, FinancialProjection
from ..llm import chat_json_validated
from ..tools.web_search import async_search

QUERY_PROMPT = """\
You are a research strategist. Given a decision scenario and user profile, generate 6 focused
web search queries split into two categories:

- 3 QUALITATIVE queries: job market insights, employer sentiment, program quality, career trajectory
- 3 QUANTITATIVE queries: salary ranges, education/tuition costs, cost of living for this path

Respond with ONLY valid JSON:
{
  "qualitative": ["query 1", "query 2", "query 3"],
  "quantitative": ["query 1", "query 2", "query 3"]
}
"""

QUALITATIVE_SYNTHESIS_PROMPT = """\
You are a research analyst synthesizing web search results into concise, actionable insights.

Extract 4-6 key bullet points that would help someone evaluate this decision path.
Each bullet must be grounded in one of the search results provided.

Respond with ONLY valid JSON:
{
  "bullets": [
    {"text": "<concise insight>", "source_url": "<url from search results>"}
  ]
}
"""

QUANTITATIVE_SYNTHESIS_PROMPT = """\
You are a financial analyst estimating realistic financial projections from web search data.

Given salary, education cost, and cost of living search results for a specific scenario,
compute the following all in annual USD:
- starting_salary p25/p50/p75
- five_year_cumulative_net (total income minus costs over 5 years)
- debt_load (total debt if any education financing is involved, else 0)
- break_even_years (years until cumulative net turns positive vs cheapest alternative, null if N/A)

Set confidence to "high" if you found direct data, "medium" if inferred, "low" if estimated.

Respond with ONLY valid JSON:
{
  "starting_salary_p25": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": ["<source url or label>"]},
  "starting_salary_p50": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "starting_salary_p75": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "five_year_cumulative_net": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "debt_load": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "break_even_years": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []} | null,
  "notes": ["<any caveats>"]
}
"""


class _Queries(BaseModel):
    qualitative: list[str]
    quantitative: list[str]


class _Bullets(BaseModel):
    bullets: list[ResearchBullet]


class _QuantRaw(BaseModel):
    starting_salary_p25: FinancialProjection
    starting_salary_p50: FinancialProjection
    starting_salary_p75: FinancialProjection
    five_year_cumulative_net: FinancialProjection
    debt_load: FinancialProjection
    break_even_years: Optional[FinancialProjection] = None
    notes: list[str] = []


class ResearchOutput(AgentOutput):
    research_results: list[ResearchResult]
    quant_results: list[QuantResult]


class ResearchAgent(BaseAgent):
    name = "research"

    async def _research_scenario(
        self, scenario, profile
    ) -> tuple[ResearchResult, QuantResult]:
        profile_json = profile.model_dump_json(indent=2)
        scenario_json = scenario.model_dump_json(indent=2)

        # Step 1: generate both qualitative and quantitative queries
        queries = await chat_json_validated(
            messages=[
                {"role": "system", "content": QUERY_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User profile:\n{profile_json}\n\n"
                        f"Scenario:\n{scenario_json}"
                    ),
                },
            ],
            model_class=_Queries,
            agent_name=f"{self.name}/queries",
            temperature=0.4,
        )

        # Step 2: run all 6 searches concurrently
        all_queries = queries.qualitative + queries.quantitative
        search_tasks = [async_search(q, max_results=4) for q in all_queries]
        all_results = await asyncio.gather(*search_tasks)

        def _dedup(batches: list[list[dict]]) -> list[dict]:
            seen: set[str] = set()
            out = []
            for batch in batches:
                for r in batch:
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        out.append(r)
            return out

        qual_results = _dedup(all_results[:3])
        quant_results_raw = _dedup(all_results[3:])

        def _fmt(results: list[dict], limit: int = 10) -> str:
            return "\n\n".join(
                f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content'][:500]}"
                for r in results[:limit]
            ) or "No search results available."

        # Step 3: synthesize qualitative bullets and quant projections concurrently
        bullets_result, quant_raw = await asyncio.gather(
            chat_json_validated(
                messages=[
                    {"role": "system", "content": QUALITATIVE_SYNTHESIS_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Scenario:\n{scenario_json}\n\n"
                            f"Search results:\n{_fmt(qual_results)}"
                        ),
                    },
                ],
                model_class=_Bullets,
                agent_name=f"{self.name}/qual",
                temperature=0.3,
            ),
            chat_json_validated(
                messages=[
                    {"role": "system", "content": QUANTITATIVE_SYNTHESIS_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"User profile:\n{profile_json}\n\n"
                            f"Scenario:\n{scenario_json}\n\n"
                            f"Search results:\n{_fmt(quant_results_raw)}"
                        ),
                    },
                ],
                model_class=_QuantRaw,
                agent_name=f"{self.name}/quant",
                temperature=0.1,
            ),
        )

        research = ResearchResult(
            scenario_id=scenario.id,
            bullets=bullets_result.bullets,
            search_queries_used=all_queries,
        )

        quant = QuantResult(
            scenario_id=scenario.id,
            starting_salary_p25=quant_raw.starting_salary_p25,
            starting_salary_p50=quant_raw.starting_salary_p50,
            starting_salary_p75=quant_raw.starting_salary_p75,
            five_year_cumulative_net=quant_raw.five_year_cumulative_net,
            debt_load=quant_raw.debt_load,
            break_even_years=quant_raw.break_even_years,
            notes=quant_raw.notes,
        )

        return research, quant

    async def run(self, state: SessionState) -> ResearchOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before running research")
        if not state.scenarios:
            raise ValueError("Scenarios must be generated before running research")

        tasks = [self._research_scenario(s, state.profile) for s in state.scenarios]
        pairs = await asyncio.gather(*tasks)

        return ResearchOutput(
            research_results=[p[0] for p in pairs],
            quant_results=[p[1] for p in pairs],
        )
