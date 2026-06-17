"""Milestone 1 smoke tests — no LLM required."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_session():
    r = client.post("/api/session")
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 10


def test_get_session_state():
    session_id = client.post("/api/session").json()["session_id"]
    r = client.get(f"/api/session/{session_id}/state")
    assert r.status_code == 200
    state = r.json()
    assert state["session_id"] == session_id
    assert state["phase"] == "intake"
    assert state["profile"] is None


def test_session_not_found():
    r = client.get("/api/session/does-not-exist/state")
    assert r.status_code == 404


def test_unimplemented_endpoints_return_501():
    session_id = client.post("/api/session").json()["session_id"]
    assert client.post("/api/intake", json={"session_id": session_id, "message": "hi"}).status_code == 501
    assert client.post("/api/scenarios/generate", json={"session_id": session_id}).status_code == 501
    assert client.post("/api/analysis/run", json={"session_id": session_id}).status_code == 501
    assert client.post("/api/brief", json={"session_id": session_id}).status_code == 501
    assert client.post("/api/whatif", json={"session_id": session_id, "perturbation": "test"}).status_code == 501


def test_csv_lookup_salaries():
    from app.tools.csv_lookup import lookup_salary
    result = lookup_salary("software_engineer", "usa", "entry")
    assert result is not None
    assert result["p50"] > 0
    assert "row_id" in result


def test_csv_lookup_education():
    from app.tools.csv_lookup import lookup_education_cost
    result = lookup_education_cost("ms_cs", "germany")
    assert result is not None
    assert result["tuition_usd_yr"] < 2000  # Germany is cheap


def test_csv_lookup_col():
    from app.tools.csv_lookup import lookup_cost_of_living
    result = lookup_cost_of_living("munich", "germany")
    assert result is not None
    assert result["monthly_usd"] > 0
