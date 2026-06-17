from __future__ import annotations

import asyncio
from pydantic import BaseModel
from typing import Optional

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import ResearchResult, ResearchBullet, QuantResult, FinancialProjection
from ..llm import chat_json_validated
from ..tools.web_search import async_search
from ..tools.retriever import ScenarioIndex

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


def _fmt_chunks(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"Title: {c['title']}\nURL: {c['url']}\nContent: {c['content']}"
        for c in chunks
    ) or "No search results available."


class ResearchAgent(BaseAgent):
    name = "research"

    async def _research_scenario(
        self, scenario, profile
    ) -> tuple[ResearchResult, QuantResult]:
        profile_json = profile.model_dump_json(indent=2)
        scenario_json = scenario.model_dump_json(indent=2)

        # Step 1: generate 6 targeted queries
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

        # Step 2: run all 6 searches with 12 results each, concurrently
        all_queries = queries.qualitative + queries.quantitative
        search_tasks = [async_search(q, max_results=12) for q in all_queries]
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

        qual_raw = _dedup(all_results[:3])   # up to 36 results
        quant_raw = _dedup(all_results[3:])  # up to 36 results

        # Step 3: index both pools into their own ChromaDB collections
        qual_index  = ScenarioIndex(f"{scenario.id}_qual")
        quant_index = ScenarioIndex(f"{scenario.id}_quant")
        await asyncio.gather(
            qual_index.add_results(qual_raw),
            quant_index.add_results(quant_raw),
        )

        # Step 4: retrieve the most relevant chunks for each synthesis question
        qual_query  = f"job market career trajectory insights for: {scenario.name}"
        quant_query = f"salary ranges tuition cost of living financial data for: {scenario.name}"

        qual_chunks, quant_chunks = await asyncio.gather(
            qual_index.query(qual_query, top_k=8),
            quant_index.query(quant_query, top_k=8),
        )

        # Step 5: synthesize using only the top retrieved chunks
        bullets_result, quant_result = await asyncio.gather(
            chat_json_validated(
                messages=[
                    {"role": "system", "content": QUALITATIVE_SYNTHESIS_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Scenario:\n{scenario_json}\n\n"
                            f"Search results:\n{_fmt_chunks(qual_chunks)}"
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
                            f"Search results:\n{_fmt_chunks(quant_chunks)}"
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
            starting_salary_p25=quant_result.starting_salary_p25,
            starting_salary_p50=quant_result.starting_salary_p50,
            starting_salary_p75=quant_result.starting_salary_p75,
            five_year_cumulative_net=quant_result.five_year_cumulative_net,
            debt_load=quant_result.debt_load,
            break_even_years=quant_result.break_even_years,
            notes=quant_result.notes,
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
