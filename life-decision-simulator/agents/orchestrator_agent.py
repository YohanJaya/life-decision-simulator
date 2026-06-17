"""
Agent 2 — Orchestrator Agent (LangGraph version)
===================================================
Same job as the plain-Python version: receive the structured profile, decide
which downstream agents fire and in what order, apply the "low confidence ->
go get more data" routing rule, and bundle the final package. The difference
is that the control flow is now an explicit graph (nodes + edges) instead of
nested if/else — which buys you a few things plain Python doesn't give you
for free:

- The graph itself IS the documentation of your execution plan. You can call
  `graph.get_graph().draw_mermaid()` and drop a real flowchart into your
  Devpost writeup instead of describing the flow in prose.
- The confidence-based "go back to Research Agent" loop is a genuine cycle
  in the graph (conditional edge pointing backward), not a manual re-call —
  LangGraph handles re-entering analytical_node correctly.
- State is a single typed object threaded through every node, so adding an
  8th agent later means adding one node + one edge, not touching existing
  branching logic.

This still has NO LLM call in it — the routing decisions are the same plain
Python functions as before, just wired together as a graph instead of called
sequentially. That "boring and auditable" property from the original version
is preserved on purpose.
"""

from typing import Optional, Protocol, TypedDict

from langgraph.graph import StateGraph, START, END


# --- Contracts for the agents this orchestrator depends on -----------------
# Same Protocols as the plain-Python version — Agents 3/4/5/6/7 still don't
# exist yet, so these just define the method shape each real agent must
# implement later.

class DMNEngineProtocol(Protocol):
    def evaluate(self, profile: dict) -> dict: ...


class AnalyticalAgentProtocol(Protocol):
    def score(self, profile: dict, dmn_result: dict, research_data: Optional[dict]) -> dict: ...


class ResearchAgentProtocol(Protocol):
    def fetch(self, profile: dict) -> dict: ...


class UncertaintyAgentProtocol(Protocol):
    def review(self, analytical_result: dict) -> dict: ...


class DecisionFramerProtocol(Protocol):
    def frame(self, dmn_result: dict, analytical_result: dict, uncertainty_result: dict) -> dict: ...


CONFIDENCE_THRESHOLD = 0.55


# --- Graph state -------------------------------------------------------------
# This is the shared state object from your design doc, made concrete as a
# typed dict. Every node receives the full state and returns only the keys
# it changed — LangGraph merges the update in automatically.

class OrchestratorState(TypedDict):
    profile: dict
    dmn_result: Optional[dict]
    research_data: Optional[dict]
    research_called: bool
    analytical_result: Optional[dict]
    uncertainty_result: Optional[dict]
    decision_brief: Optional[dict]
    trace: list


class OrchestratorGraph:
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
        self.graph = self._build_graph()

    # --- nodes ---------------------------------------------------------------
    # Each node is a plain function: (state) -> dict of fields to update.

    def _dmn_node(self, state: OrchestratorState) -> dict:
        dmn_result = self.dmn_engine.evaluate(state["profile"])
        trace_entry = f"DMN evaluated: {len(dmn_result.get('flags', []))} flag(s) raised."
        return {"dmn_result": dmn_result, "trace": state["trace"] + [trace_entry]}

    def _research_node(self, state: OrchestratorState) -> dict:
        research_data = self.research_agent.fetch(state["profile"])
        trace_entry = "Research Agent called."
        return {
            "research_data": research_data,
            "research_called": True,
            "trace": state["trace"] + [trace_entry],
        }

    def _analytical_node(self, state: OrchestratorState) -> dict:
        result = self.analytical_agent.score(
            state["profile"], state["dmn_result"], state.get("research_data")
        )
        trace_entry = f"Analytical Agent returned confidence={result.get('confidence')}."
        return {"analytical_result": result, "trace": state["trace"] + [trace_entry]}

    def _uncertainty_node(self, state: OrchestratorState) -> dict:
        result = self.uncertainty_agent.review(state["analytical_result"])
        trace_entry = "Uncertainty Agent reviewed output for overconfident claims."
        return {"uncertainty_result": result, "trace": state["trace"] + [trace_entry]}

    def _decision_framer_node(self, state: OrchestratorState) -> dict:
        brief = self.decision_framer.frame(
            state["dmn_result"], state["analytical_result"], state["uncertainty_result"]
        )
        trace_entry = "Decision Framer produced final briefing."
        return {"decision_brief": brief, "trace": state["trace"] + [trace_entry]}

    # --- conditional edges -----------------------------------------------
    # These replace the if/else branches from the plain-Python version.
    # They return a string key, which path_map below resolves to a node name.

    @staticmethod
    def _route_after_dmn(state: OrchestratorState) -> str:
        profile_field = (state["profile"].get("field") or "").strip().lower()
        country = (state["profile"].get("country") or "").strip().lower()
        vague_terms = {"", "not sure", "undecided", "unknown"}
        specific_enough = profile_field not in vague_terms and country not in vague_terms
        return "research" if specific_enough else "analytical"

    @staticmethod
    def _route_after_analytical(state: OrchestratorState) -> str:
        confidence = state["analytical_result"].get("confidence", 1.0)
        if confidence < CONFIDENCE_THRESHOLD and not state["research_called"]:
            return "research"  # loop back — this is the genuine cycle in the graph
        return "uncertainty"

    # --- graph assembly ----------------------------------------------------

    def _build_graph(self):
        graph = StateGraph(OrchestratorState)

        graph.add_node("dmn", self._dmn_node)
        graph.add_node("research", self._research_node)
        graph.add_node("analytical", self._analytical_node)
        graph.add_node("uncertainty", self._uncertainty_node)
        graph.add_node("decision_framer", self._decision_framer_node)

        graph.add_edge(START, "dmn")
        graph.add_conditional_edges(
            "dmn",
            self._route_after_dmn,
            {"research": "research", "analytical": "analytical"},
        )
        graph.add_edge("research", "analytical")
        graph.add_conditional_edges(
            "analytical",
            self._route_after_analytical,
            {"research": "research", "uncertainty": "uncertainty"},
        )
        graph.add_edge("uncertainty", "decision_framer")
        graph.add_edge("decision_framer", END)

        return graph.compile()

    def run(self, profile: dict) -> dict:
        initial_state: OrchestratorState = {
            "profile": profile,
            "dmn_result": None,
            "research_data": None,
            "research_called": False,
            "analytical_result": None,
            "uncertainty_result": None,
            "decision_brief": None,
            "trace": ["Received profile from Conversational Agent."],
        }
        return self.graph.invoke(initial_state)


# --- smoke test, same stubs and same profile as the plain-Python version ---
# so you can diff the output and confirm identical behavior.
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

    orchestrator = OrchestratorGraph(
        dmn_engine=StubDMN(),
        analytical_agent=StubAnalytical(),
        research_agent=StubResearch(),
        uncertainty_agent=StubUncertainty(),
        decision_framer=StubDecisionFramer(),
    )

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

    # Bonus: this is the line that gets you a real flowchart for your Devpost
    # writeup instead of a prose description of the architecture.
    print("\n--- Mermaid diagram of this graph ---")
    print(orchestrator.graph.get_graph().draw_mermaid())