import pytest

from auditly.api import operations


def test_get_evidence_not_found():
    with pytest.raises(ValueError):
        operations.get_evidence("missing-id")


def test_update_evidence_not_found():
    with pytest.raises(ValueError):
        operations.update_evidence("missing-id", type("E", (), {"data": {}})())


def test_delete_evidence_not_found():
    with pytest.raises(ValueError):
        operations.delete_evidence("missing-id")


def test_list_evidence_with_and_without_env():
    e1 = operations.create_evidence(
        type("E", (), {"environment": "env1", "provider": "p", "data": {}})()
    )
    e2 = operations.create_evidence(
        type("E", (), {"environment": "env2", "provider": "p", "data": {}})()
    )
    all_evs = operations.list_evidence()
    assert e1 in all_evs and e2 in all_evs
    env1_evs = operations.list_evidence("env1")
    assert e1 in env1_evs and e2 not in env1_evs


def test_get_control_status_empty_and_nonempty():
    resp = operations.get_control_status("env3")
    assert resp.environment == "env3"
    operations.create_evidence(
        type("E", (), {"environment": "env4", "provider": "p", "data": {}})()
    )
    resp2 = operations.get_control_status("env4")
    assert resp2.environment == "env4"
    assert resp2.status_summary["total"] == 1


def test_collect_evidence_unsupported_provider():
    with pytest.raises(ValueError):
        operations.collect_evidence("config.yaml", "env", "notreal")


def test_collect_evidence_missing_params(monkeypatch):
    class DummyEnvCfg:
        storage = None

    class DummyCfg:
        environments = {"env": DummyEnvCfg()}

    monkeypatch.setattr("auditly.api.operations.AppConfig.load", lambda x: DummyCfg())
    with pytest.raises(ValueError):
        operations.collect_evidence("config.yaml", "env", "terraform")


def test_validate_evidence_dedup(monkeypatch):
    class DummyCatalog:
        def control_ids(self):
            return ["A", "A", "B"]

    class DummyCfg:
        environments = {"env": type("E", (), {})()}
        catalogs = type("C", (), {"get_all_catalogs": lambda self: {"c": "dummy"}})()

    monkeypatch.setattr("auditly.api.operations.AppConfig.load", lambda x: DummyCfg())
    monkeypatch.setattr("auditly.api.operations.load_oscal", lambda x: DummyCatalog())
    results, summary = operations.validate_evidence("dummy", "env")
    assert isinstance(results, dict)
    assert isinstance(summary, dict)


def test_generate_report_unsupported_type(monkeypatch):
    class DummyCfg:
        pass

    monkeypatch.setattr("auditly.api.operations.AppConfig.load", lambda x: DummyCfg())
    with pytest.raises(ValueError):
        operations.generate_report("dummy", "env", report_type="notreal")


def test__generate_readiness_report_error(monkeypatch, tmp_path):
    import json

    class DummyCfg:
        catalogs = type("C", (), {"get_all_catalogs": lambda self: {"c": "dummy"}})()

    monkeypatch.setattr("auditly.api.operations.OscalCatalog", object)
    monkeypatch.setattr("auditly.api.operations.OscalProfile", object)

    def raise_fail(*args, **kwargs):
        # Directly raise the exception for test error simulation
        raise RuntimeError("fail")

    monkeypatch.setattr("auditly.api.operations.load_oscal", raise_fail)

    def dummy_create(environment, artifacts):
        return type("M", (), {"to_json": lambda self: "{}", "artifacts": []})()

    monkeypatch.setattr("auditly.api.operations.EvidenceManifest.create", dummy_create)
    # Write the manifest file with required keys to .auditly_manifests
    import os

    manifest_dir = ".auditly_manifests"
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "env-dummy.json")
    with open(manifest_path, "w") as f:
        json.dump({"version": "1.0", "environment": "env", "created_at": 0, "artifacts": []}, f)
    _, _, summary = operations._generate_readiness_report(
        DummyCfg(), "env", str(tmp_path / "out.html")
    )
    assert "error" in summary["controls"]
