from __future__ import annotations

import asyncio
import json
import uuid
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .schemas import (
    SessionResponse,
    IntakeRequest,
    IntakeResponse,
    ScenariosRequest,
    ScenariosResponse,
    AnalysisRequest,
    AnalysisResponse,
    WhatIfRequest,
    WhatIfResponse,
    BriefRequest,
    BriefResponse,
    RankedScenario,
    RankedScenariosResponse,
)
from .state import store, SessionState
from .agents.intake import IntakeAgent
from .agents.scenario_generator import ScenarioGeneratorAgent
from .agents.research import ResearchAgent
from .agents.market_outlook import MarketOutlookAgent
from .agents.tradeoff_analyzer import TradeoffAnalyzerAgent
from .agents.what_if import WhatIfSimulatorAgent
from .agents.orchestrator import OrchestratorAgent
from .simulation import simulate_all
from .tools import progress as progress_tracker
from typing import Optional

_SCORE_MAP = {"strong": 3, "mixed": 2, "weak": 1, "unclear": 0}
_MC_RISK_BONUS = {"low": 3, "medium": 1, "high": 0}


def _rank_scenarios(state: SessionState) -> list[RankedScenario]:
    if not state.tradeoff_matrix:
        return []
    research_by_id = {r.scenario_id: r for r in state.research_results}
    quant_by_id    = {q.scenario_id: q for q in state.quant_results}
    mc_by_id       = {m.scenario_id: m for m in state.monte_carlo_results}
    outlook_by_id  = {o.scenario_id: o for o in state.market_outlooks}

    scored = []
    for scenario in state.scenarios:
        sid = scenario.id
        entries = [e for e in state.tradeoff_matrix.entries if e.scenario_id == sid]
        tradeoff_score = sum(_SCORE_MAP.get(e.score, 0) for e in entries)
        mc = mc_by_id.get(sid)
        mc_bonus = (mc.prob_positive * 10 + _MC_RISK_BONUS.get(mc.risk_label, 0)) if mc else 0.0
        scored.append((tradeoff_score + mc_bonus, scenario, entries))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        RankedScenario(
            rank=i + 1,
            score=round(score, 2),
            scenario=scenario,
            tradeoff_entries=entries,
            research=research_by_id.get(scenario.id),
            quant=quant_by_id.get(scenario.id),
            monte_carlo=mc_by_id.get(scenario.id),
            market_outlook=outlook_by_id.get(scenario.id),
        )
        for i, (score, scenario, entries) in enumerate(scored)
    ]

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="Second Brain API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent singletons
_intake = IntakeAgent()
_scenario_gen = ScenarioGeneratorAgent()
_research = ResearchAgent()
_market_outlook = MarketOutlookAgent()
_tradeoff = TradeoffAnalyzerAgent()
_whatif = WhatIfSimulatorAgent()
_orchestrator = OrchestratorAgent()


def _get_state(session_id: str) -> SessionState:
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@app.get("/")
@app.get("/api/health")
async def root():
    return {"status": "ok"}


# ── Session ───────────────────────────────────────────────────────────────────

@app.post("/api/session", response_model=SessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    state = SessionState(session_id=session_id)
    store.set(session_id, state)
    return SessionResponse(session_id=session_id)


@app.get("/api/session/{session_id}/state")
async def get_state(session_id: str):
    state = _get_state(session_id)
    return state.model_dump()


# ── Intake ────────────────────────────────────────────────────────────────────

@app.post("/api/intake", response_model=IntakeResponse)
async def intake(req: IntakeRequest):
    state = _get_state(req.session_id)

    user_content = req.message
    if req.form_data:
        user_content = (
            f"{req.message}\n\n"
            f"[Form data submitted: {req.form_data.model_dump_json()}]"
        )
    state.chat_history.append({"role": "user", "content": user_content})

    output = await _intake.run(state)

    state.chat_history.append({"role": "assistant", "content": output.reply})
    if output.profile_complete and output.profile:
        state.profile = output.profile
        state.phase = "scenarios"

    store.set(req.session_id, state)

    return IntakeResponse(
        reply=output.reply,
        profile_complete=output.profile_complete,
        profile=output.profile,
    )


# ── Scenarios + Analysis ──────────────────────────────────────────────────────

@app.post("/api/scenarios/generate", response_model=ScenariosResponse)
async def generate_scenarios(req: ScenariosRequest):
    state = _get_state(req.session_id)
    if not state.profile:
        raise HTTPException(status_code=400, detail="Complete intake before generating scenarios")

    output = await _scenario_gen.run(state)
    state.scenarios = output.scenarios
    state.phase = "analysis"
    store.set(req.session_id, state)

    return ScenariosResponse(scenarios=output.scenarios)


@app.get("/api/analysis/stream/{session_id}")
async def analysis_stream(session_id: str):
    """SSE endpoint — frontend connects here to receive live progress messages."""
    async def event_generator():
        q = progress_tracker.create_queue(session_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=600.0)
                except asyncio.TimeoutError:
                    yield "data: {\"message\": \"Still working…\", \"step\": null}\n\n"
                    continue

                if msg is None:   # sentinel — analysis finished
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    break
                yield f"data: {json.dumps(msg)}\n\n"
        finally:
            progress_tracker.remove_queue(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/analysis/run", response_model=AnalysisResponse)
async def run_analysis(req: AnalysisRequest):
    state = _get_state(req.session_id)
    if not state.scenarios:
        raise HTTPException(status_code=400, detail="Generate scenarios before running analysis")

    sid = req.session_id
    n = len(state.scenarios)

    await progress_tracker.emit(sid, f"Starting research across {n} scenarios…")

    research_output, outlook_output = await asyncio.gather(
        _research.run(state),
        _market_outlook.run(state),
    )

    state.quant_results = research_output.quant_results
    state.research_results = research_output.research_results
    state.market_outlooks = outlook_output.results

    await progress_tracker.emit(sid, "Running Monte Carlo simulations…")
    time_horizon = state.profile.time_horizon_years if state.profile else 5
    state.monte_carlo_results = simulate_all(
        state.quant_results,
        state.market_outlooks,
        time_horizon,
    )

    await progress_tracker.emit(sid, "Analyzing tradeoffs across all scenarios…")
    tradeoff_output = await _tradeoff.run(state)
    state.tradeoff_matrix = tradeoff_output.matrix
    state.phase = "exploration"
    store.set(req.session_id, state)

    await progress_tracker.done(sid)

    return AnalysisResponse(
        quant=research_output.quant_results,
        research=research_output.research_results,
        market_outlooks=outlook_output.results,
        monte_carlo=state.monte_carlo_results,
        tradeoffs=tradeoff_output.matrix,
    )


# ── Brief ─────────────────────────────────────────────────────────────────────

@app.post("/api/brief", response_model=BriefResponse)
async def get_brief(req: BriefRequest):
    state = _get_state(req.session_id)
    if not state.tradeoff_matrix:
        raise HTTPException(status_code=400, detail="Run analysis before generating brief")

    output = await _orchestrator.run(state)
    state.brief = output.brief
    state.phase = "brief"
    store.set(req.session_id, state)

    return BriefResponse(brief=output.brief)


# ── Ranked Scenarios ─────────────────────────────────────────────────────────

@app.get("/api/scenarios/ranked/{session_id}", response_model=RankedScenariosResponse)
async def get_ranked_scenarios(session_id: str, limit: int = 5):
    state = _get_state(session_id)
    if not state.tradeoff_matrix:
        raise HTTPException(status_code=400, detail="Run analysis before fetching ranked scenarios")
    ranked = _rank_scenarios(state)
    return RankedScenariosResponse(ranked=ranked[:limit], total=len(ranked))


# ── What-If ───────────────────────────────────────────────────────────────────

@app.post("/api/whatif", response_model=WhatIfResponse)
async def whatif(req: WhatIfRequest):
    state = _get_state(req.session_id)
    if not state.tradeoff_matrix:
        raise HTTPException(status_code=400, detail="Run analysis before using what-if")

    state.perturbation = req.perturbation
    output = await _whatif.run(state)
    state.perturbation = None  # clear after use
    store.set(req.session_id, state)

    return WhatIfResponse(diff=output.diff)
