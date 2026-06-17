from __future__ import annotations

import asyncio
from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import ResearchResult, ResearchBullet
from ..llm import chat_json_validated
from ..tools.web_search import async_search

QUERY_PROMPT = """\
You are a research strategist. Given a decision scenario and user profile, generate 3 focused
web search queries that would surface the most useful real-world information for evaluating this path.

Respond with ONLY valid JSON:
{"queries": ["query 1", "query 2", "query 3"]}
"""

SYNTHESIS_PROMPT = """\
You are a research analyst synthesizing web search results into concise, actionable insights.

Given search results for a decision scenario, extract 4-6 key bullet points that would help
someone evaluate this path. Each bullet must be grounded in one of the search results.

Respond with ONLY valid JSON:
{
  "bullets": [
    {"text": "<concise insight>", "source_url": "<url from search results>"}
  ]
}
"""


class _Queries(BaseModel):
    queries: list[str]


class _Bullets(BaseModel):
    bullets: list[ResearchBullet]


class ResearchOutput(AgentOutput):
    results: list[ResearchResult]


class ResearchAgent(BaseAgent):
    name = "research"

    async def _research_scenario(self, scenario, profile) -> ResearchResult:
        profile_json = profile.model_dump_json(indent=2)
        scenario_json = scenario.model_dump_json(indent=2)

        # Step 1: generate search queries
        queries_result = await chat_json_validated(
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

        # Step 2: run searches concurrently
        search_tasks = [async_search(q, max_results=4) for q in queries_result.queries]
        all_results = await asyncio.gather(*search_tasks)

        # Flatten and deduplicate by URL
        seen_urls: set[str] = set()
        flat_results = []
        for batch in all_results:
            for r in batch:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    flat_results.append(r)

        # Step 3: synthesize bullets (even if search returned nothing)
        search_context = "\n\n".join(
            f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content'][:400]}"
            for r in flat_results[:10]
        ) or "No web search results available."

        bullets_result = await chat_json_validated(
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Scenario:\n{scenario_json}\n\n"
                        f"Search results:\n{search_context}"
                    ),
                },
            ],
            model_class=_Bullets,
            agent_name=f"{self.name}/synthesis",
            temperature=0.3,
        )

        return ResearchResult(
            scenario_id=scenario.id,
            bullets=bullets_result.bullets,
            search_queries_used=queries_result.queries,
        )

    async def run(self, state: SessionState) -> ResearchOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before running research")
        if not state.scenarios:
            raise ValueError("Scenarios must be generated before running research")

        tasks = [self._research_scenario(s, state.profile) for s in state.scenarios]
        results = await asyncio.gather(*tasks)
        return ResearchOutput(results=list(results))
