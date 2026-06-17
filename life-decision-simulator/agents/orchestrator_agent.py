"""
Agent 2 — Orchestrator Agent
=============================
The "project manager" layer. Never talks to the user, never talks to an LLM.
It receives the structured profile from the Conversational Agent, decides
which downstream agents to call and in what order, applies routing logic
(e.g. "analytical confidence too low -> go get more data before proceeding"),
and bundles everything into one package for the Conversational Agent to
present back to the user.

Deliberately deterministic: orchestration is plain Python control flow plus
a visible execution trace, not a model call. That's what makes "why did the
system do X" answerable in one log line instead of buried in hidden
reasoning — which matters a lot when you're explaining this to judges.
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol


# --- Contracts for the agents this orchestrator depends on -----------------
# Written as Protocols (structural typing), not imports, because Agents
# 3/4/5/6/7 don't exist yet. Once you build analytical_agent.py etc., as
# long as the class exposes a matching method, you inject the real thing
# here with zero changes to this file.

class DMNEngineProtocol(Protocol):
    def evaluate(self, profile: dict) -> dict: ...
    # expected return shape: {"flags": [...], "hard_constraints": {...}}


class AnalyticalAgentProtocol(Protocol):
    def score(self, profile: dict, dmn_result: dict, research_data: Optional[dict]) -> dict: ...
    # expected return shape: {"scores": {...}, "confidence": 0.0-1.0}


class ResearchAgentProtocol(Protocol):
    def fetch(self, profile: dict) -> dict: ...
    # expected return shape: structured facts from curated/synthetic datasets


class UncertaintyAgentProtocol(Protocol):
    def review(self, analytical_result: dict) -> dict: ...
    # expected return shape: audited output with ranges, not point estimates


class DecisionFramerProtocol(Protocol):
    def frame(self, dmn_result: dict, analytical_result: dict, uncertainty_result: dict) -> dict: ...
    # expected return shape: {"core_tension":..., "key_variable":..., "open_question":...}


# --- Orchestrator ------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.55  # below this, Orchestrator goes back for more data


@dataclass
class OrchestrationTrace:
    """Human-readable log of what fired and why — this is your auditability story."""
    steps: list = field(default_factory=list)

    def log(self, message: str) -> None:
        self.steps.append(message)


class OrchestratorAgent:
    def __init__(
        self,
        dmn_engine: DMNEngineProtocol,
        analytical_agent: AnalyticalAgentProtocol,
        research_agent: ResearchAgentProtocol,
        uncertainty_agent: UncertaintyAgentProtocol,
        decision_framer: DecisionFramerProtocol,
    ):
        self.dmn_engine = dmn_engine
        self.analytical_agent = analytical_agent
        self.research_agent = research_agent
        self.uncertainty_agent = uncertainty_agent
        self.decision_framer = decision_framer

    def run(self, profile: dict) -> dict:
        trace = OrchestrationTrace()
        trace.log("Received profile from Conversational Agent.")

        # Step 1 — rules fire before any scoring happens, per the architecture
        dmn_result = self.dmn_engine.evaluate(profile)
        trace.log(f"DMN evaluated: {len(dmn_result.get('flags', []))} flag(s) raised.")

        # Step 2 — decide up front whether this profile is specific enough
        # to be worth grounding in real-world data
        research_data = None
        if self._should_call_research(profile):
            research_data = self.research_agent.fetch(profile)
            trace.log("Research Agent called — profile specific enough for a useful lookup.")
        else:
            trace.log("Research Agent skipped — profile too generic for a useful lookup yet.")

        # Step 3 — run the scoring simulation
        analytical_result = self.analytical_agent.score(profile, dmn_result, research_data)
        trace.log(f"Analytical Agent returned confidence={analytical_result.get('confidence')}.")

        # Step 4 — routing logic: low confidence and no real data grounding it
        # yet -> go get the data, then re-score once. This is the "Orchestrator
        # can decide to call the Research Agent for more data" behavior from
        # the design doc.
        if analytical_result.get("confidence", 1.0) < CONFIDENCE_THRESHOLD and research_data is None:
            trace.log("Confidence below threshold with no research data — calling Research Agent now.")
            research_data = self.research_agent.fetch(profile)
            analytical_result = self.analytical_agent.score(profile, dmn_result, research_data)
            trace.log(f"Re-scored with research data — confidence now {analytical_result.get('confidence')}.")

        # Step 5 — audit for false certainty
        uncertainty_result = self.uncertainty_agent.review(analytical_result)
        trace.log("Uncertainty Agent reviewed output for overconfident claims.")

        # Step 6 — synthesize into a human decision, not a recommendation
        decision_brief = self.decision_framer.frame(dmn_result, analytical_result, uncertainty_result)
        trace.log("Decision Framer produced final briefing.")

        return {
            "dmn_result": dmn_result,
            "analytical_result": analytical_result,
            "uncertainty_result": uncertainty_result,
            "decision_brief": decision_brief,
            "execution_trace": trace.steps,
        }

    @staticmethod
    def _should_call_research(profile: dict) -> bool:
        """
        Heuristic gate, not a model call: a dataset lookup is only useful
        once the profile names a specific enough field and country. A
        profile that's still vague on both doesn't benefit from it yet.
        """
        profile_field = (profile.get("field") or "").strip().lower()
        country = (profile.get("country") or "").strip().lower()
        vague_terms = {"", "not sure", "undecided", "unknown"}
        return profile_field not in vague_terms and country not in vague_terms


# --- smoke test with stand-ins, so this file runs before Agents 3-7 exist --
if __name__ == "__main__":
    import json

    class StubDMN:
        def evaluate(self, profile):
            return {"flags": ["financial_risk_high"], "hard_constraints": {}}

    class StubAnalytical:
        def score(self, profile, dmn_result, research_data):
            confidence = 0.8 if research_data else 0.4
            return {"scores": {"job": 0.68, "grad_school": 0.71}, "confidence": confidence}

    class StubResearch:
        def fetch(self, profile):
            return {"median_salary": 62000, "employment_rate": 0.91}

    class StubUncertainty:
        def review(self, analytical_result):
            return {
                "ranges": {"job": "60-76%", "grad_school": "63-79%"},
                "flagged_assumptions": ["small comparable sample size"],
            }

    class StubDecisionFramer:
        def frame(self, dmn_result, analytical_result, uncertainty_result):
            return {
                "core_tension": "Certainty now vs. higher upside later",
                "key_variable": "Whether the job offer becomes confirmed in time",
                "open_question": "Can you afford 6 more months of uncertainty?",
            }

    orchestrator = OrchestratorAgent(
        dmn_engine=StubDMN(),
        analytical_agent=StubAnalytical(),
        research_agent=StubResearch(),
        uncertainty_agent=StubUncertainty(),
        decision_framer=StubDecisionFramer(),
    )

    # country left vague on purpose — this triggers the heuristic skip,
    # then the low-confidence override calls Research Agent anyway,
    # exercising both routing paths in one run.
    sample_profile = {
        "field": "data science",
        "country": "not sure",
        "goal_5yr": "stable, well-paid role",
        "job_offer_type": "unconfirmed",
        "financial_situation": "no savings - family support needed",
        "risk_tolerance": "low",
    }

    result = orchestrator.run(sample_profile)
    print(json.dumps(result, indent=2))