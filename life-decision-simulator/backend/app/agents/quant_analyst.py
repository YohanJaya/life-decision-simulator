from __future__ import annotations

import asyncio
from typing import Optional
from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import QuantResult, FinancialProjection
from ..llm import chat_json_validated
from ..tools.csv_lookup import (
    async_lookup_salary,
    async_lookup_education_cost,
    async_lookup_cost_of_living,
)

SYSTEM_PROMPT = """\
You are a financial analyst extracting structured lookup parameters from a decision scenario.

Given a scenario and user profile, extract the parameters needed to look up financial data.
Respond with ONLY valid JSON:
{
  "role": "<job role, e.g. software_engineer>",
  "region": "<region, e.g. usa, europe, india>",
  "level": "<entry | mid | senior>",
  "program_type": "<ms | phd | mba | bootcamp | null if not studying>",
  "study_country": "<country if studying, else null>",
  "living_city": "<city for cost of living lookup>",
  "living_country": "<country for cost of living lookup>",
  "duration_years": <number of years for this path>,
  "notes": "<any caveats>"
}
"""

SYNTHESIS_PROMPT = """\
You are a financial analyst computing 5-year financial projections for a decision scenario.

Given the scenario, user profile, and raw data lookups, compute:
- starting_salary_p25/p50/p75 (annual USD)
- five_year_cumulative_net (total net income after costs over 5 years)
- debt_load (total debt incurred, 0 if none)
- break_even_years (years until cumulative net turns positive vs the alternative, null if N/A)

Account for: education costs, cost of living, salary ramp-up, and debt repayment.

Respond with ONLY valid JSON matching this schema:
{
  "starting_salary_p25": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "starting_salary_p50": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "starting_salary_p75": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "five_year_cumulative_net": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "debt_load": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []},
  "break_even_years": {"label": "...", "value_usd": 0.0, "confidence": "high|medium|low", "source_rows": []} | null,
  "notes": ["..."]
}
"""


class _LookupParams(BaseModel):
    role: Optional[str] = None
    region: Optional[str] = None
    level: Optional[str] = None
    program_type: Optional[str] = None
    study_country: Optional[str] = None
    living_city: Optional[str] = None
    living_country: Optional[str] = None
    duration_years: Optional[int] = None
    notes: Optional[str] = None


class _QuantResultRaw(BaseModel):
    starting_salary_p25: FinancialProjection
    starting_salary_p50: FinancialProjection
    starting_salary_p75: FinancialProjection
    five_year_cumulative_net: FinancialProjection
    debt_load: FinancialProjection
    break_even_years: Optional[FinancialProjection] = None
    notes: list[str] = []


class QuantOutput(AgentOutput):
    results: list[QuantResult]


class QuantitativeAnalystAgent(BaseAgent):
    name = "quant_analyst"

    async def _analyse_scenario(self, scenario, profile) -> QuantResult:
        profile_json = profile.model_dump_json(indent=2)
        scenario_json = scenario.model_dump_json(indent=2)

        # Step 1: extract lookup parameters
        params = await chat_json_validated(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User profile:\n{profile_json}\n\n"
                        f"Scenario:\n{scenario_json}"
                    ),
                },
            ],
            model_class=_LookupParams,
            agent_name=f"{self.name}/params",
            temperature=0.1,
        )

        # Step 2: run CSV lookups concurrently
        salary_task = None
        edu_task = None
        col_task = None

        if params.role and params.region and params.level:
            salary_task = async_lookup_salary(params.role, params.region, params.level)
        if params.program_type and params.study_country:
            edu_task = async_lookup_education_cost(params.program_type, params.study_country)
        if params.living_city and params.living_country:
            col_task = async_lookup_cost_of_living(params.living_city, params.living_country)

        results = await asyncio.gather(
            salary_task if salary_task else asyncio.sleep(0),
            edu_task if edu_task else asyncio.sleep(0),
            col_task if col_task else asyncio.sleep(0),
        )
        salary_data = results[0] if salary_task else None
        edu_data = results[1] if edu_task else None
        col_data = results[2] if col_task else None

        # Step 3: synthesize projections
        data_context = (
            f"Salary lookup: {salary_data}\n"
            f"Education cost lookup: {edu_data}\n"
            f"Cost of living lookup: {col_data}\n"
            f"Duration: {params.duration_years} years\n"
        )

        raw = await chat_json_validated(
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User profile:\n{profile_json}\n\n"
                        f"Scenario:\n{scenario_json}\n\n"
                        f"Raw data:\n{data_context}"
                    ),
                },
            ],
            model_class=_QuantResultRaw,
            agent_name=f"{self.name}/synthesis",
            temperature=0.1,
        )

        return QuantResult(
            scenario_id=scenario.id,
            starting_salary_p25=raw.starting_salary_p25,
            starting_salary_p50=raw.starting_salary_p50,
            starting_salary_p75=raw.starting_salary_p75,
            five_year_cumulative_net=raw.five_year_cumulative_net,
            debt_load=raw.debt_load,
            break_even_years=raw.break_even_years,
            notes=raw.notes,
        )

    async def run(self, state: SessionState) -> QuantOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before running quant analysis")
        if not state.scenarios:
            raise ValueError("Scenarios must be generated before running quant analysis")

        tasks = [self._analyse_scenario(s, state.profile) for s in state.scenarios]
        results = await asyncio.gather(*tasks)
        return QuantOutput(results=list(results))
