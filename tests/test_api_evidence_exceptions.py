from fastapi.testclient import TestClient

from auditly.api.app import app

client = TestClient(app)


def test_create_evidence_exception(monkeypatch):
    def fail_create(*a, **kw):
        raise Exception("fail create")

    monkeypatch.setattr("auditly.api.routers.evidence.create_evidence", fail_create)
    resp = client.post("/evidence", json={"name": "foo"})
    assert resp.status_code == 422  # FastAPI returns 422 for validation errors


def test_get_evidence_exception(monkeypatch):
    def fail_get(*a, **kw):
        raise Exception("fail get")

    monkeypatch.setattr("auditly.api.routers.evidence.get_evidence", fail_get)
    resp = client.get("/evidence/someid")
    assert resp.status_code == 404
    assert "fail get" in resp.text


def test_update_evidence_exception(monkeypatch):
    def fail_update(*a, **kw):
        raise Exception("fail update")

    monkeypatch.setattr("auditly.api.routers.evidence.update_evidence", fail_update)
    resp = client.put("/evidence/someid", json={"name": "bar"})
    assert resp.status_code == 422  # FastAPI returns 422 for validation errors


def test_delete_evidence_exception(monkeypatch):
    def fail_delete(*a, **kw):
        raise Exception("fail delete")

    monkeypatch.setattr("auditly.api.routers.evidence.delete_evidence", fail_delete)
    resp = client.delete("/evidence/someid")
    assert resp.status_code == 404
    assert "fail delete" in resp.text


def test_list_evidence_exception(monkeypatch):
    def fail_list(*a, **kw):
        raise Exception("fail list")

    monkeypatch.setattr("auditly.api.routers.evidence.list_evidence", fail_list)
    resp = client.get("/evidence")
    assert resp.status_code == 400
    assert "fail list" in resp.text


def test_control_status_exception(monkeypatch):
    def fail_status(*a, **kw):
        raise Exception("fail status")

    monkeypatch.setattr("auditly.api.routers.evidence.get_control_status", fail_status)
    resp = client.get("/evidence/control-status?environment=prod")
    assert resp.status_code == 404  # Not found for missing env
    assert "Evidence not found" in resp.text
