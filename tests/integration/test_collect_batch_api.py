import pytest
from fastapi.testclient import TestClient

from rapidrmf.api.app import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_collect_batch_happy_path(client, monkeypatch):
    calls = []

    def fake_collect_evidence(**kwargs):
        calls.append(kwargs)
        provider = kwargs["provider"]
        env = kwargs["environment"]
        return (
            2,
            f"manifests/{env}/{provider}-manifest.json",
            f"Collected 2 artifacts from {provider}",
        )

    # Patch the operations.collect_evidence used by batch helper
    import rapidrmf.api.operations as ops

    monkeypatch.setattr(ops, "collect_evidence", fake_collect_evidence)

    payload = {
        "requests": [
            {
                "config_path": "config.yaml",
                "environment": "prod",
                "provider": "terraform",
                "terraform_plan_path": "plan.json",
            },
            {
                "config_path": "config.yaml",
                "environment": "prod",
                "provider": "github",
                "github_repo": "org/repo",
                "github_token": "token",
                "github_run_id": 123,
            },
        ],
        "timeout_seconds": 60,
    }

    resp = client.post("/collect/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["succeeded"] == 2
    assert data["failed"] == 0
    assert isinstance(data["results"], dict)
    assert "req-0-terraform" in data["results"]
    assert "req-1-github" in data["results"]
    assert data["errors"] == {}


def test_collect_batch_mixed_success(client, monkeypatch):
    def fake_collect_evidence(**kwargs):
        provider = kwargs["provider"]
        if provider == "github":
            raise Exception("github provider failed")
        return (1, f"manifests/x/{provider}-manifest.json", f"ok {provider}")

    import rapidrmf.api.operations as ops

    monkeypatch.setattr(ops, "collect_evidence", fake_collect_evidence)

    payload = {
        "requests": [
            {
                "config_path": "config.yaml",
                "environment": "x",
                "provider": "terraform",
                "terraform_plan_path": "plan.json",
            },
            {
                "config_path": "config.yaml",
                "environment": "x",
                "provider": "github",
                "github_repo": "org/repo",
                "github_token": "token",
                "github_run_id": 123,
            },
        ],
        "timeout_seconds": 30,
    }

    resp = client.post("/collect/batch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    # One result present for terraform, error present for github
    assert any(k.startswith("req-0-terraform") for k in data["results"].keys())
    assert any("github" in k for k in data["errors"].keys())
