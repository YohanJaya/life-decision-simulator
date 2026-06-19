"""Unit tests for the Monte Carlo engine (app/simulation/monte_carlo.py).

Pure-Python, deterministic under a fixed seed — no LLM, network, or Qdrant.
"""
from __future__ import annotations

import random

import pytest

from app.schemas import FinancialProjection, MarketOutlook, QuantResult
from app.simulation import simulate_all
from app.simulation.monte_carlo import N_SIMULATIONS, SAMPLE_PATHS, simulate


# ── Fixtures / factories ──────────────────────────────────────────────────────

def _fin(value: float, confidence: str = "medium", label: str = "x") -> FinancialProjection:
    return FinancialProjection(label=label, value_usd=value, confidence=confidence, source_rows=[])


def make_quant(
    scenario_id: str = "s1",
    *,
    p25: float = 50_000,
    p50: float = 70_000,
    p75: float = 95_000,
    five_year_net: float = 200_000,
    debt: float = 0,
) -> QuantResult:
    return QuantResult(
        scenario_id=scenario_id,
        starting_salary_p25=_fin(p25),
        starting_salary_p50=_fin(p50),
        starting_salary_p75=_fin(p75),
        five_year_cumulative_net=_fin(five_year_net),
        debt_load=_fin(debt),
        break_even_years=None,
        notes=[],
    )


def make_outlook(
    scenario_id: str = "s1",
    *,
    growth: str = "average",
    automation: str = "low",
    demand: str = "growing",
) -> MarketOutlook:
    return MarketOutlook(
        scenario_id=scenario_id,
        target_role="Engineer",
        region="USA",
        projected_growth=growth,
        projected_growth_rationale="test",
        automation_risk=automation,
        automation_risk_rationale="test",
        demand_trend=demand,
        key_risks=[],
        key_tailwinds=[],
        time_horizon_fit="strong",
        time_horizon_rationale="test",
        sources=[],
    )


# ── Shape & invariants ─────────────────────────────────────────────────────────

def test_n_simulations_matches_documented_value():
    # The README advertises 5,000 simulations per scenario — pin it here.
    assert N_SIMULATIONS == 5_000


def test_result_shape_and_invariants():
    random.seed(42)
    result = simulate(make_quant(), make_outlook(), time_horizon=5)

    assert result.scenario_id == "s1"
    assert result.n_simulations == N_SIMULATIONS

    # Cumulative percentiles are monotonically non-decreasing.
    assert (
        result.cumulative_net_p10
        <= result.cumulative_net_p25
        <= result.cumulative_net_p50
        <= result.cumulative_net_p75
        <= result.cumulative_net_p90
    )

    assert 0.0 <= result.prob_positive <= 1.0
    assert 0.0 <= result.prob_major_disruption <= 1.0
    assert result.risk_label in {"low", "medium", "high"}

    # downside = p10 - p50 (<= 0); upside = p90 - p50 (>= 0)
    assert result.downside_risk_usd <= 0 <= result.upside_potential_usd

    # One distribution per year, each internally ordered, years labelled 1..N.
    assert len(result.yearly) == 5
    assert [y.year for y in result.yearly] == [1, 2, 3, 4, 5]
    for y in result.yearly:
        assert y.p10 <= y.p25 <= y.p50 <= y.p75 <= y.p90

    # Visualization sample: SAMPLE_PATHS cumulative trajectories, one point per year,
    # stratified so they arrive sorted by final value and span the p10–p90 envelope.
    assert len(result.sample_paths) == SAMPLE_PATHS
    assert all(len(p) == 5 for p in result.sample_paths)
    finals = [p[-1] for p in result.sample_paths]
    assert finals == sorted(finals)
    assert finals[0] <= result.cumulative_net_p50 <= finals[-1]


@pytest.mark.parametrize("horizon", [1, 3, 10])
def test_time_horizon_respected(horizon: int):
    random.seed(1)
    result = simulate(make_quant(), make_outlook(), time_horizon=horizon)
    assert len(result.yearly) == horizon
    assert [y.year for y in result.yearly] == list(range(1, horizon + 1))


def test_reproducible_under_same_seed():
    random.seed(7)
    a = simulate(make_quant(), make_outlook(), time_horizon=5)
    random.seed(7)
    b = simulate(make_quant(), make_outlook(), time_horizon=5)
    assert a.model_dump() == b.model_dump()


# ── Behavioural sanity (deterministic comparisons under a fixed seed) ──────────

def test_debt_lowers_net():
    random.seed(123)
    no_debt = simulate(make_quant(debt=0), make_outlook(), time_horizon=5)
    random.seed(123)
    with_debt = simulate(make_quant(debt=120_000), make_outlook(), time_horizon=5)
    # Debt service is subtracted from net income with no extra random draws,
    # so the heavily-indebted path is strictly worse at the median.
    assert with_debt.cumulative_net_p50 < no_debt.cumulative_net_p50


def test_positive_scenario_more_likely_than_negative():
    random.seed(99)
    good = simulate(
        make_quant(p25=90_000, p50=120_000, p75=160_000, five_year_net=400_000, debt=0),
        make_outlook(growth="faster", automation="low", demand="growing"),
        time_horizon=5,
    )
    random.seed(99)
    bad = simulate(
        make_quant(p25=20_000, p50=28_000, p75=36_000, five_year_net=-40_000, debt=150_000),
        make_outlook(growth="declining", automation="high", demand="declining"),
        time_horizon=5,
    )
    assert good.prob_positive > bad.prob_positive


def test_higher_automation_risk_increases_disruption():
    random.seed(2024)
    low = simulate(make_quant(), make_outlook(automation="low"), time_horizon=5)
    random.seed(2024)
    high = simulate(make_quant(), make_outlook(automation="high"), time_horizon=5)
    assert high.prob_major_disruption > low.prob_major_disruption


# ── simulate_all orchestration ─────────────────────────────────────────────────

def test_simulate_all_matches_by_scenario_id():
    quants = [make_quant("s1"), make_quant("s2")]
    outlooks = [make_outlook("s1"), make_outlook("s2")]
    results = simulate_all(quants, outlooks, time_horizon=5)
    assert {r.scenario_id for r in results} == {"s1", "s2"}


def test_simulate_all_skips_quant_without_outlook():
    quants = [make_quant("s1"), make_quant("s2")]
    outlooks = [make_outlook("s1")]  # no outlook for s2
    results = simulate_all(quants, outlooks, time_horizon=5)
    assert [r.scenario_id for r in results] == ["s1"]
