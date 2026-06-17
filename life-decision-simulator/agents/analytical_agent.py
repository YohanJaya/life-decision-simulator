"""
Agent 3 — Analytical Agent
=============================
The "ML simulation layer" — your technical differentiator. To be precise
about what this actually is: it is NOT a trained model and doesn't learn
anything at runtime. It's a transparent, weighted scoring function that
mimics what a small decision-tree/logistic-regression classifier would
output, built from:

  1. synthetic historical baseline data (clearly labeled as illustrative
     placeholders below — swap in real cited datasets before drawing any
     real-world conclusion from this)
  2. profile features (field, financial situation, risk tolerance, job
     offer status)
  3. DMN flags (soft, multiplicative adjustments) and hard constraints
     (overrides) from Agent 4
  4. optional real-data calibration from the Research Agent (Agent 5)

Matches AnalyticalAgentProtocol.score(profile, dmn_result, research_data)
already wired into both Orchestrator versions (plain-Python and LangGraph)
— drop this in with zero changes to either.
"""

from typing import Optional


# --- Synthetic historical baselines ----------------------------------------
# Illustrative placeholders only — "% of similar profiles who hit their
# 5-year goal" per path. Replace with real datasets (BLS, NCES, national
# labor-market data, etc.) before treating these as real-world figures.
# Kept as one dictionary, not scattered through code, so it's obvious at a
# glance exactly what's swappable later.
HISTORICAL_BASELINES = {
    "data science": {"job": 0.70, "grad_school": 0.66},
    "medicine":     {"job": 0.40, "grad_school": 0.82},
    "law":          {"job": 0.42, "grad_school": 0.78},
    "business":     {"job": 0.72, "grad_school": 0.69},
    "engineering":  {"job": 0.74, "grad_school": 0.70},
    "default":      {"job": 0.65, "grad_school": 0.68},
}

CONFIDENCE_WITH_RESEARCH = 0.75
CONFIDENCE_WITHOUT_RESEARCH = 0.40
CONFIDENCE_PENALTY_UNKNOWN_FIELD = 0.10


class AnalyticalAgent:
    def score(self, profile: dict, dmn_result: dict, research_data: Optional[dict]) -> dict:
        trace = []

        # Step 1 — pick the closest baseline bucket
        field = (profile.get("field") or "").strip().lower()
        baseline = HISTORICAL_BASELINES.get(field, HISTORICAL_BASELINES["default"])
        used_default = field not in HISTORICAL_BASELINES
        trace.append(
            f"No specific baseline for '{field}' — used default bucket"
            if used_default else f"Baseline source: '{field}'"
        )

        scores = {"job": baseline["job"], "grad_school": baseline["grad_school"]}

        # Step 2 — profile-driven adjustments
        risk = profile.get("risk_tolerance")
        if risk == "low":
            scores["job"] += 0.04
            scores["grad_school"] -= 0.04
            trace.append("Low risk tolerance: +0.04 job, -0.04 grad_school (favors near-term certainty)")
        elif risk == "high":
            scores["job"] -= 0.04
            scores["grad_school"] += 0.04
            trace.append("High risk tolerance: -0.04 job, +0.04 grad_school (favors deferred upside)")

        job_offer = profile.get("job_offer_type")
        if job_offer == "confirmed":
            scores["job"] += 0.05
            trace.append("Confirmed job offer: +0.05 job")
        elif job_offer == "none":
            scores["job"] -= 0.15
            trace.append("No job offer on the table: -0.15 job")

        financial = profile.get("financial_situation")
        funding = profile.get("grad_school_funding")
        if financial == "no savings - family support needed" and funding == "self-funded":
            scores["grad_school"] -= 0.08
            trace.append("No savings + self-funded grad school: -0.08 grad_school (completion risk)")

        # Step 3 — apply DMN flags (soft, multiplicative — Agent 4's output)
        for flag_item in dmn_result.get("flags", []):
            if isinstance(flag_item, dict) and "weight_job_path" in flag_item:
                multiplier = flag_item["weight_job_path"]
                scores["job"] *= multiplier
                trace.append(f"DMN flag applied: job score x{multiplier}")
            # plain-string flags (e.g. "financial_risk_high") are informational
            # only — this agent doesn't act on them, the Uncertainty Agent does

        # Step 4 — apply DMN hard constraints (these override the simulation
        # outright, they don't just nudge it)
        rule_locked = False
        constraints = dmn_result.get("hard_constraints", {})
        if constraints.get("grad_school_required"):
            scores["grad_school"] = 0.95
            scores["job"] = 0.15
            rule_locked = True
            trace.append("Hard constraint fired: grad_school_required — scores overridden, not data-driven")

        # Step 5 — calibrate with real data if the Research Agent ran
        confidence = CONFIDENCE_WITHOUT_RESEARCH
        if research_data:
            employment_rate = research_data.get("employment_rate")
            if employment_rate is not None:
                adjustment = (employment_rate - 0.85) * 0.2
                scores["job"] += adjustment
                trace.append(f"Research calibration: employment_rate={employment_rate} -> {adjustment:+.3f} job")
            confidence = CONFIDENCE_WITH_RESEARCH
            trace.append("Confidence raised — grounded in Research Agent data")
        else:
            trace.append("No research data available — confidence reflects category-level extrapolation only")

        if used_default:
            confidence -= CONFIDENCE_PENALTY_UNKNOWN_FIELD
            trace.append(f"Confidence penalty applied for unrecognized field ('{field}')")

        # clamp into [0, 1] — additive adjustments can drift out of range
        for key in scores:
            scores[key] = max(0.0, min(1.0, round(scores[key], 3)))
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        return {
            "scores": scores,
            "confidence": confidence,
            "rule_locked": rule_locked,
            "trace": trace,
        }


# --- smoke test covering the three cases that matter --------------------
if __name__ == "__main__":
    import json

    agent = AnalyticalAgent()

    base_profile = {
        "field": "data science",
        "risk_tolerance": "low",
        "job_offer_type": "unconfirmed",
        "financial_situation": "no savings - family support needed",
        "grad_school_funding": "self-funded",
    }
    dmn_with_flag = {"flags": [{"weight_job_path": 0.7}], "hard_constraints": {}}
    dmn_with_constraint = {"flags": [], "hard_constraints": {"grad_school_required": True}}

    print("--- No research data (should be low confidence) ---")
    print(json.dumps(agent.score(base_profile, dmn_with_flag, None), indent=2))

    print("\n--- With research data (confidence should rise) ---")
    research = {"median_salary": 78000, "employment_rate": 0.91}
    print(json.dumps(agent.score(base_profile, dmn_with_flag, research), indent=2))

    print("\n--- Hard constraint fires (medicine/law style profile) ---")
    locked_profile = {**base_profile, "field": "medicine"}
    print(json.dumps(agent.score(locked_profile, dmn_with_constraint, None), indent=2))