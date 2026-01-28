"""Tests for /validate and /report endpoints (minimal, smoke tests)."""

from fastapi.testclient import TestClient

from auditly.api.app import app

client = TestClient(app)


def test_validate_smoke():
    # Should return 200 and a summary, even if no evidence
    payload = {"environment": "testenv"}
    resp = client.post("/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "controls_validated" in data


def test_report_smoke():
    payload = {"environment": "testenv", "report_type": "readiness"}
    resp = client.post("/report", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["report_type"] == "readiness"
    assert "report_html" in data
