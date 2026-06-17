from __future__ import annotations

import random
from typing import Literal

from ..schemas import (
    QuantResult,
    MarketOutlook,
    MonteCarloResult,
    YearlyDistribution,
)

N_SIMULATIONS = 5_000

# Growth rate ranges (low, high) per projected_growth label
_GROWTH_RANGES: dict[str, tuple[float, float]] = {
    "much_faster": (0.06, 0.14),
    "faster":      (0.05, 0.11),
    "average":     (0.03, 0.08),
    "slower":      (0.01, 0.05),
    "declining":   (-0.02, 0.04),
    "uncertain":   (0.02, 0.09),
}

# Months idle before first job per demand_trend
_IDLE_MONTHS: dict[str, tuple[int, int]] = {
    "growing":   (1, 3),
    "stable":    (2, 6),
    "declining": (4, 12),
    "uncertain": (2, 9),
}

# Annual probability of an income-shock event per automation_risk
_DISRUPTION_PROB: dict[str, float] = {
    "low":    0.03,
    "medium": 0.08,
    "high":   0.15,
}

# Debt interest rate range
_INTEREST_RANGE = (0.04, 0.08)


def _percentile(data: list[float], p: float) -> float:
    sorted_data = sorted(data)
    idx = (p / 100.0) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_data) - 1)
    return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (idx - lo)


def _sample_starting_salary(quant: QuantResult) -> float:
    p25 = quant.starting_salary_p25.value_usd
    p50 = quant.starting_salary_p50.value_usd
    p75 = quant.starting_salary_p75.value_usd
    iqr = p75 - p25
    low = max(p25 - iqr * 0.5, 0.0)
    high = p75 + iqr * 0.5
    return random.triangular(low, high, p50)


def _simulate_one(
    quant: QuantResult,
    outlook: MarketOutlook,
    time_horizon: int,
) -> tuple[list[float], bool]:
    """
    Returns (yearly_net_income list, had_disruption flag).
    yearly_net_income[i] = net income for year i+1 after costs.
    """
    salary = _sample_starting_salary(quant)
    growth_lo, growth_hi = _GROWTH_RANGES.get(outlook.projected_growth, (0.03, 0.08))
    annual_growth = random.uniform(growth_lo, growth_hi)

    idle_lo, idle_hi = _IDLE_MONTHS.get(outlook.demand_trend, (2, 6))
    months_idle = random.randint(idle_lo, idle_hi)

    disruption_prob = _DISRUPTION_PROB.get(outlook.automation_risk, 0.06)
    col_inflation = random.uniform(0.02, 0.05)

    # Implied annual cost of living: derive from LLM's five_year_net estimate
    # avg_annual_income ≈ salary growing at mid-growth over 5 years
    mid_growth = (growth_lo + growth_hi) / 2
    avg_annual_income = salary * (1 + mid_growth) ** 2  # rough midpoint
    implied_annual_cost = max(avg_annual_income - quant.five_year_cumulative_net.value_usd / 5, 0)
    # Clamp: never let implied cost exceed 80% of starting salary (sanity guard)
    implied_annual_cost = min(implied_annual_cost, salary * 0.80)

    # Debt repayment spread over time_horizon
    interest_rate = random.uniform(*_INTEREST_RANGE)
    total_debt = quant.debt_load.value_usd * (1 + interest_rate)
    annual_debt_repayment = total_debt / max(time_horizon, 1)

    yearly_net: list[float] = []
    had_disruption = False

    for year in range(1, time_horizon + 1):
        current_salary = salary * (1 + annual_growth) ** (year - 1)
        annual_col = implied_annual_cost * (1 + col_inflation) ** (year - 1)

        if year == 1:
            # Penalty for months idle before landing the job
            active_fraction = max((12 - months_idle) / 12, 0.0)
            gross = current_salary * active_fraction
        else:
            if random.random() < disruption_prob:
                # Income shock: layoff, health issue, market crash, etc.
                shock_fraction = random.uniform(0.10, 0.40)
                gross = current_salary * (1 - shock_fraction)
                had_disruption = True
            else:
                gross = current_salary

        net = gross - annual_col - annual_debt_repayment
        yearly_net.append(net)

    return yearly_net, had_disruption


def _build_yearly_distributions(
    all_yearly: list[list[float]],
    time_horizon: int,
) -> list[YearlyDistribution]:
    distributions = []
    for year_idx in range(time_horizon):
        year_values = [sim[year_idx] for sim in all_yearly]
        distributions.append(YearlyDistribution(
            year=year_idx + 1,
            p10=_percentile(year_values, 10),
            p25=_percentile(year_values, 25),
            p50=_percentile(year_values, 50),
            p75=_percentile(year_values, 75),
            p90=_percentile(year_values, 90),
        ))
    return distributions


def _risk_label(prob_positive: float, downside: float, p50: float) -> Literal["low", "medium", "high"]:
    downside_ratio = abs(downside) / max(abs(p50), 1)
    if prob_positive >= 0.85 and downside_ratio < 0.3:
        return "low"
    if prob_positive >= 0.60 and downside_ratio < 0.6:
        return "medium"
    return "high"


def simulate(
    quant: QuantResult,
    outlook: MarketOutlook,
    time_horizon: int,
) -> MonteCarloResult:
    all_yearly: list[list[float]] = []
    disruption_count = 0

    for _ in range(N_SIMULATIONS):
        yearly, had_disruption = _simulate_one(quant, outlook, time_horizon)
        all_yearly.append(yearly)
        if had_disruption:
            disruption_count += 1

    # Cumulative net per simulation (sum of all years)
    cumulative = [sum(sim) for sim in all_yearly]

    p10  = _percentile(cumulative, 10)
    p25  = _percentile(cumulative, 25)
    p50  = _percentile(cumulative, 50)
    p75  = _percentile(cumulative, 75)
    p90  = _percentile(cumulative, 90)

    prob_positive        = sum(1 for v in cumulative if v > 0) / N_SIMULATIONS
    prob_major_disruption = disruption_count / N_SIMULATIONS
    downside_risk        = p10 - p50
    upside_potential     = p90 - p50

    return MonteCarloResult(
        scenario_id=quant.scenario_id,
        n_simulations=N_SIMULATIONS,
        cumulative_net_p10=round(p10, 2),
        cumulative_net_p25=round(p25, 2),
        cumulative_net_p50=round(p50, 2),
        cumulative_net_p75=round(p75, 2),
        cumulative_net_p90=round(p90, 2),
        prob_positive=round(prob_positive, 4),
        prob_major_disruption=round(prob_major_disruption, 4),
        downside_risk_usd=round(downside_risk, 2),
        upside_potential_usd=round(upside_potential, 2),
        yearly=_build_yearly_distributions(all_yearly, time_horizon),
        risk_label=_risk_label(prob_positive, downside_risk, p50),
    )


def simulate_all(
    quant_results: list[QuantResult],
    market_outlooks: list[MarketOutlook],
    time_horizon: int,
) -> list[MonteCarloResult]:
    outlook_by_scenario = {o.scenario_id: o for o in market_outlooks}
    results = []
    for quant in quant_results:
        outlook = outlook_by_scenario.get(quant.scenario_id)
        if outlook is None:
            continue
        results.append(simulate(quant, outlook, time_horizon))
    return results
