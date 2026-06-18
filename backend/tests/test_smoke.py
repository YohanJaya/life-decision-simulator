"""API smoke tests — health, session lifecycle, and endpoint guardrails.

No LLM, web search, or Qdrant required: every endpoint here is exercised only up to
its prerequisite check, so the agent pipeline is never invoked.
"""
from fastapi.testclient import TestClient


# ── Health ──────────────────────────────────────────────────────────────────

def test_root_ok(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ok(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Session lifecycle ─────────────────────────────────────────────────────────

def test_create_session(client: TestClient):
    r = client.post("/api/session")
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 10


def test_get_session_state(client: TestClient, session_id: str):
    r = client.get(f"/api/session/{session_id}/state")
    assert r.status_code == 200
    state = r.json()
    assert state["session_id"] == session_id
    assert state["phase"] == "intake"
    assert state["profile"] is None
    assert state["scenarios"] == []


def test_session_not_found(client: TestClient):
    assert client.get("/api/session/does-not-exist/state").status_code == 404


# ── Endpoint guardrails (prerequisite checks return 400) ───────────────────────

def test_generate_scenarios_requires_profile(client: TestClient, session_id: str):
    r = client.post("/api/scenarios/generate", json={"session_id": session_id})
    assert r.status_code == 400
    assert "intake" in r.json()["detail"].lower()


def test_run_analysis_requires_scenarios(client: TestClient, session_id: str):
    r = client.post("/api/analysis/run", json={"session_id": session_id})
    assert r.status_code == 400
    assert "scenario" in r.json()["detail"].lower()


def test_brief_requires_analysis(client: TestClient, session_id: str):
    r = client.post("/api/brief", json={"session_id": session_id})
    assert r.status_code == 400
    assert "analysis" in r.json()["detail"].lower()


def test_whatif_requires_analysis(client: TestClient, session_id: str):
    r = client.post("/api/whatif", json={"session_id": session_id, "perturbation": "salary -20%"})
    assert r.status_code == 400
    assert "analysis" in r.json()["detail"].lower()


def test_ranked_requires_analysis(client: TestClient, session_id: str):
    r = client.get(f"/api/scenarios/ranked/{session_id}")
    assert r.status_code == 400
    assert "analysis" in r.json()["detail"].lower()


# ── Unknown-session handling (404 before any prerequisite check) ───────────────

def test_generate_scenarios_unknown_session(client: TestClient):
    r = client.post("/api/scenarios/generate", json={"session_id": "nope"})
    assert r.status_code == 404


def test_ranked_unknown_session(client: TestClient):
    assert client.get("/api/scenarios/ranked/nope").status_code == 404


# ── Request validation ─────────────────────────────────────────────────────────

def test_whatif_missing_perturbation_is_422(client: TestClient, session_id: str):
    # perturbation is a required field — FastAPI/Pydantic rejects the body before routing.
    r = client.post("/api/whatif", json={"session_id": session_id})
    assert r.status_code == 422
