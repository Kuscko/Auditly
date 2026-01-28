"""Tests for the /webhook endpoint."""

from fastapi.testclient import TestClient

from auditly.api.app import app

client = TestClient(app)


def test_webhook_triggers_validation():
    payload = {
        "event_type": "evidence_changed",
        "environment": "testenv",
        "evidence_id": None,
        "payload": None,
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["success"] is True
    assert "summary" in data
    assert isinstance(data["summary"], dict)
