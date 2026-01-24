"""Tests for /report API endpoints: HTML and JSON export."""

from fastapi.testclient import TestClient

from auditly.api.app import app

client = TestClient(app)


def test_report_html_endpoint():
    resp = client.get("/report/html?environment=testenv&report_type=readiness")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower() or "<!doctype html" in resp.text.lower()


def test_report_json_endpoint():
    resp = client.get("/report/json?environment=testenv&report_type=readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "artifact_count" in data or "score" in data or "environments" in data
