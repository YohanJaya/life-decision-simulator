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
    break_even_years: Optional[float] = None   # count of years, not a USD figure
    notes: list[str] = []


# ── Research ──────────────────────────────────────────────────────────────────

class ResearchBullet(BaseModel):
    text: str
    source_url: str


class ResearchResult(BaseModel):
    scenario_id: str
    bullets: list[ResearchBullet]
    search_queries_used: list[str]


# ── Monte Carlo ───────────────────────────────────────────────────────────────

class YearlyDistribution(BaseModel):
    year: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


class MonteCarloResult(BaseModel):
    scenario_id: str
    n_simulations: int
    cumulative_net_p10: float
    cumulative_net_p25: float
    cumulative_net_p50: float
    cumulative_net_p75: float
    cumulative_net_p90: float
    prob_positive: float            # % simulations where 5yr net > 0
    prob_major_disruption: float    # % simulations with at least one income shock year
    downside_risk_usd: float        # p10 - p50
    upside_potential_usd: float     # p90 - p50
    yearly: list[YearlyDistribution]
    risk_label: Literal["low", "medium", "high"]
    # Representative subset of cumulative-net trajectories for visualization.
    # Each path is the running cumulative net per year; stratified by final value
    # so the on-screen fan spans the full p0–p100 spread, not all N_SIMULATIONS.
    sample_paths: list[list[float]] = []


# ── Market Outlook ────────────────────────────────────────────────────────────

class MarketOutlook(BaseModel):
    scenario_id: str
    target_role: str
    region: str
    projected_growth: Literal["much_faster", "faster", "average", "slower", "declining", "uncertain"]
    projected_growth_rationale: str
    automation_risk: Literal["low", "medium", "high"]
    automation_risk_rationale: str
    demand_trend: Literal["growing", "stable", "declining", "uncertain"]
    key_risks: list[str]          # e.g. ["AI replacing entry-level tasks", "visa cap uncertainty"]
    key_tailwinds: list[str]      # e.g. ["cloud infra still growing", "healthcare AI expansion"]
    time_horizon_fit: Literal["strong", "mixed", "weak"]
    time_horizon_rationale: str   # e.g. "Market peaks in ~3 yrs; user's 5yr horizon is well-aligned"
    sources: list[str]            # URLs from search results


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


# ── Ranked Scenarios ──────────────────────────────────────────────────────────

class RankedScenario(BaseModel):
    rank: int
    score: float
    scenario: Scenario
    tradeoff_entries: list[TradeoffEntry]
    research: Optional[ResearchResult] = None
    quant: Optional[QuantResult] = None
    monte_carlo: Optional[MonteCarloResult] = None
    market_outlook: Optional[MarketOutlook] = None


class RankedScenariosResponse(BaseModel):
    ranked: list[RankedScenario]
    total: int


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
    market_outlooks: list[MarketOutlook]
    monte_carlo: list[MonteCarloResult]
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
