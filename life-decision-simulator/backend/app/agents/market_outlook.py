from __future__ import annotations

import asyncio
from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import MarketOutlook
from ..llm import chat_json_validated
from ..tools.web_search import async_search

QUERY_PROMPT = """\
You are a labor market research strategist. Given a decision scenario and user profile,
generate 4 targeted web search queries to assess the FUTURE job market for this path.

Focus on:
1. Role growth projections (BLS Occupational Outlook or equivalent)
2. Automation / AI displacement risk for this role
3. Hiring demand trend in the target region over the next 3-5 years
4. Whether the specific degree or credential will still be valued by the time the user finishes

The user's time horizon is provided — tailor queries to that timeframe.

Respond with ONLY valid JSON:
{"queries": ["query 1", "query 2", "query 3", "query 4"]}
"""

SYNTHESIS_PROMPT = """\
You are a labor market analyst assessing the future job market for a specific decision scenario.

Given search results and the user's profile (including their time horizon in years), produce a
structured market outlook. Be honest about uncertainty — prefer "uncertain" over false confidence.

Key things to assess:
- projected_growth: will this role/field grow over the user's time horizon?
- automation_risk: how much is this role at risk from AI/automation by the time user enters?
- demand_trend: is employer demand growing, stable, or declining?
- key_risks: specific threats (e.g. visa uncertainty, AI coding tools, degree inflation)
- key_tailwinds: specific positive forces (e.g. cloud infrastructure, healthcare AI, green energy)
- time_horizon_fit: does the market timing align with when the user will actually enter/peak?

Respond with ONLY valid JSON:
{
  "target_role": "<role they will be targeting>",
  "region": "<target region>",
  "projected_growth": "much_faster|faster|average|slower|declining|uncertain",
  "projected_growth_rationale": "<one sentence with source if available>",
  "automation_risk": "low|medium|high",
  "automation_risk_rationale": "<one sentence>",
  "demand_trend": "growing|stable|declining|uncertain",
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "key_tailwinds": ["<tailwind 1>", "<tailwind 2>"],
  "time_horizon_fit": "strong|mixed|weak",
  "time_horizon_rationale": "<one sentence explaining timing alignment>",
  "sources": ["<url 1>", "<url 2>"]
}
"""


class _Queries(BaseModel):
    queries: list[str]


class MarketOutlookOutput(AgentOutput):
    results: list[MarketOutlook]


class MarketOutlookAgent(BaseAgent):
    name = "market_outlook"

    async def _outlook_for_scenario(self, scenario, profile) -> MarketOutlook:
        profile_json = profile.model_dump_json(indent=2)
        scenario_json = scenario.model_dump_json(indent=2)

        # Step 1: generate forward-looking search queries
        queries_result = await chat_json_validated(
            messages=[
                {"role": "system", "content": QUERY_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User profile (time horizon: {profile.time_horizon_years} years):\n{profile_json}\n\n"
                        f"Scenario:\n{scenario_json}"
                    ),
                },
            ],
            model_class=_Queries,
            agent_name=f"{self.name}/queries",
            temperature=0.3,
        )

        # Step 2: run searches concurrently
        search_tasks = [async_search(q, max_results=4) for q in queries_result.queries]
        all_results = await asyncio.gather(*search_tasks)

        seen_urls: set[str] = set()
        flat_results = []
        for batch in all_results:
            for r in batch:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    flat_results.append(r)

        # Step 3: synthesize market outlook
        search_context = "\n\n".join(
            f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content'][:500]}"
            for r in flat_results[:12]
        ) or "No web search results available — use general knowledge, flag as uncertain."

        raw = await chat_json_validated(
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User profile (time horizon: {profile.time_horizon_years} years):\n{profile_json}\n\n"
                        f"Scenario:\n{scenario_json}\n\n"
                        f"Search results:\n{search_context}"
                    ),
                },
            ],
            model_class=MarketOutlook,
            agent_name=f"{self.name}/synthesis",
            temperature=0.2,
        )

        # Inject the scenario_id (LLM doesn't know it)
        raw.scenario_id = scenario.id
        return raw

    async def run(self, state: SessionState) -> MarketOutlookOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before running market outlook")
        if not state.scenarios:
            raise ValueError("Scenarios must be generated before running market outlook")

        tasks = [self._outlook_for_scenario(s, state.profile) for s in state.scenarios]
        results = await asyncio.gather(*tasks)
        return MarketOutlookOutput(results=list(results))
