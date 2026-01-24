"""Tests for auditly REST API Tier 1 endpoints (evidence CRUD, validation, control status)."""

from fastapi.testclient import TestClient

from auditly.api.app import app

client = TestClient(app)


def test_evidence_crud():
    # Create evidence
    payload = {"environment": "testenv", "provider": "test", "data": {"foo": "bar"}}
    resp = client.post("/evidence", json=payload)
    assert resp.status_code == 200
    evidence = resp.json()
    eid = evidence["id"]
    assert evidence["environment"] == "testenv"
    # Get evidence
    resp = client.get(f"/evidence/{eid}")
    assert resp.status_code == 200
    # Update evidence
    resp = client.put(f"/evidence/{eid}", json={"data": {"foo": "baz"}})
    assert resp.status_code == 200
    assert resp.json()["data"]["foo"] == "baz"
    # List evidence
    resp = client.get("/evidence?environment=testenv")
    assert resp.status_code == 200
    assert any(ev["id"] == eid for ev in resp.json())
    # Delete evidence
    resp = client.delete(f"/evidence/{eid}")
    assert resp.status_code == 200
    # Should not find after delete
    resp = client.get(f"/evidence/{eid}")
    assert resp.status_code == 404


def test_control_status():
    # Add evidence for environment
    payload = {"environment": "env2", "provider": "prov", "data": {"x": 1}}
    resp = client.post("/evidence", json=payload)
    eid = resp.json()["id"]
    # Query control status
    resp = client.get("/evidence/control-status?environment=env2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["environment"] == "env2"
    assert data["status_summary"]["total"] >= 1
    # Cleanup
    client.delete(f"/evidence/{eid}")
