from __future__ import annotations

import uuid
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
)
from .state import store, SessionState

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="Second Brain API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
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
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state.model_dump()


# ── Intake (Milestone 2) ──────────────────────────────────────────────────────

@app.post("/api/intake", response_model=IntakeResponse)
async def intake(req: IntakeRequest):
    raise HTTPException(status_code=501, detail="Implemented in Milestone 2")


# ── Scenarios + Analysis (Milestone 3) ───────────────────────────────────────

@app.post("/api/scenarios/generate", response_model=ScenariosResponse)
async def generate_scenarios(req: ScenariosRequest):
    raise HTTPException(status_code=501, detail="Implemented in Milestone 3")


@app.post("/api/analysis/run", response_model=AnalysisResponse)
async def run_analysis(req: AnalysisRequest):
    raise HTTPException(status_code=501, detail="Implemented in Milestone 3")


# ── Brief (Milestone 4) ───────────────────────────────────────────────────────

@app.post("/api/brief", response_model=BriefResponse)
async def get_brief(req: BriefRequest):
    raise HTTPException(status_code=501, detail="Implemented in Milestone 4")


# ── What-If (Milestone 5) ─────────────────────────────────────────────────────

@app.post("/api/whatif", response_model=WhatIfResponse)
async def whatif(req: WhatIfRequest):
    raise HTTPException(status_code=501, detail="Implemented in Milestone 5")
