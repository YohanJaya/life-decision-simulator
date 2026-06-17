from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Intake ────────────────────────────────────────────────────────────────────

class FormData(BaseModel):
    name: str
    current_situation: str        # e.g. "final-year CS undergrad at XYZ"
    decision_domain: str          # e.g. "higher studies vs industry job"
    location: str                 # current location
    options_of_interest: list[str]  # rough options they're already considering


class UserProfile(BaseModel):
    name: str
    current_situation: str
    decision_domain: str
    location: str
    stated_values: list[str]        # e.g. ["financial security", "research impact"]
    hard_constraints: list[str]     # e.g. ["cannot take >$30k debt"]
    soft_preferences: list[str]     # e.g. ["prefer warm climate"]
    options_of_interest: list[str]
    risk_tolerance: Literal["low", "medium", "high"]
    time_horizon_years: int = Field(ge=1, le=20)
    additional_context: str = ""


# ── Scenarios ─────────────────────────────────────────────────────────────────

class Assumption(BaseModel):
    key: str
    value: str


class Scenario(BaseModel):
    id: str
    name: str
    description: str
    assumptions: list[Assumption]


# ── Quantitative analysis ─────────────────────────────────────────────────────

class FinancialProjection(BaseModel):
    label: str
    value_usd: float
    confidence: Literal["high", "medium", "low"]
    source_rows: list[str]      # e.g. ["software_engineer|usa|entry"]


class QuantResult(BaseModel):
    scenario_id: str
    starting_salary_p25: FinancialProjection
    starting_salary_p50: FinancialProjection
    starting_salary_p75: FinancialProjection
    five_year_cumulative_net: FinancialProjection
    debt_load: FinancialProjection
    break_even_years: Optional[FinancialProjection] = None
    notes: list[str] = []


# ── Research ──────────────────────────────────────────────────────────────────

class ResearchBullet(BaseModel):
    text: str
    source_url: str


class ResearchResult(BaseModel):
    scenario_id: str
    bullets: list[ResearchBullet]
    search_queries_used: list[str]


# ── Tradeoff analysis ─────────────────────────────────────────────────────────

TRADEOFF_DIMENSIONS = [
    "financial_outcome",
    "debt_exposure",
    "time_to_stability",
    "optionality",
    "reversibility",
    "alignment_with_stated_values",
    "lifestyle",
    "risk_exposure",
]


class TradeoffEntry(BaseModel):
    scenario_id: str
    dimension: str
    score: Literal["strong", "mixed", "weak", "unclear"]
    rationale: str


class TradeoffMatrix(BaseModel):
    entries: list[TradeoffEntry]
    named_tradeoffs: list[str]   # plain-English tradeoff names, e.g. "salary now vs. optionality later"


# ── What-If ───────────────────────────────────────────────────────────────────

class QuantChange(BaseModel):
    scenario_id: str
    field: str
    before_usd: float
    after_usd: float
    delta_usd: float


class TradeoffChange(BaseModel):
    scenario_id: str
    dimension: str
    before_score: Literal["strong", "mixed", "weak", "unclear"]
    after_score: Literal["strong", "mixed", "weak", "unclear"]
    rationale: str


class WhatIfDiff(BaseModel):
    perturbation: str
    affected_scenario_ids: list[str]
    quant_changes: list[QuantChange]
    tradeoff_changes: list[TradeoffChange]


# ── Decision Brief ────────────────────────────────────────────────────────────

class DecisionBrief(BaseModel):
    session_id: str
    scenarios: list[Scenario]
    tradeoff_matrix: TradeoffMatrix
    named_tradeoffs: list[str]
    uncertainties: list[str]
    user_questions: list[str] = Field(..., min_length=3, max_length=3)
    generated_at: str   # ISO timestamp


# ── API request / response models ─────────────────────────────────────────────

class SessionResponse(BaseModel):
    session_id: str


class IntakeRequest(BaseModel):
    session_id: str
    message: str
    form_data: Optional[FormData] = None


class IntakeResponse(BaseModel):
    reply: str
    profile_complete: bool
    profile: Optional[UserProfile] = None


class ScenariosRequest(BaseModel):
    session_id: str


class ScenariosResponse(BaseModel):
    scenarios: list[Scenario]


class AnalysisRequest(BaseModel):
    session_id: str


class AnalysisResponse(BaseModel):
    quant: list[QuantResult]
    research: list[ResearchResult]
    tradeoffs: TradeoffMatrix


class WhatIfRequest(BaseModel):
    session_id: str
    perturbation: str


class WhatIfResponse(BaseModel):
    diff: WhatIfDiff


class BriefRequest(BaseModel):
    session_id: str


class BriefResponse(BaseModel):
    brief: DecisionBrief
