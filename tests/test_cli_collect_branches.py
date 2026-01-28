import types

from auditly.cli_collect import collect_github_cmd


def test_collect_github_cmd_invalid_local_path(monkeypatch, tmp_path):
    class DummyVault:
        def put_file(self, *a, **k):
            raise AssertionError("Should not be called")

        def put_json(self, *a, **k):
            # No-op for test: method intentionally left empty because put_json is not relevant for this test branch
            pass

    class DummyArtifact:
        def __init__(self):
            self.metadata = {"_local_path": 123}  # Not str or Path

        key = "key"

    class DummyManifest:
        def to_json(self):
            # Return minimal JSON for test; no-op content
            return "{}"

    def dummy_collect_github_actions(*a, **k):
        return [DummyArtifact()], DummyManifest(), types.SimpleNamespace(id=1)

    monkeypatch.setattr(
        "auditly.cli_collect.AppConfig.load",
        lambda x: types.SimpleNamespace(environments={"dev": {}}),
    )
    monkeypatch.setattr("auditly.cli_collect.vault_from_envcfg", lambda x: DummyVault())
    monkeypatch.setattr("auditly.cli_collect.collect_github_actions", dummy_collect_github_actions)
    # Should not raise, should skip put_file
    collect_github_cmd(tmp_path, "dev", "repo", "token")


def test_collect_gitlab_cmd_invalid_local_path(monkeypatch, tmp_path):
    from auditly.cli_collect import collect_gitlab_cmd

    class DummyVault:
        def put_file(self, *a, **k):
            raise AssertionError("Should not be called")

        def put_json(self, *a, **k):
            # No-op for test: method intentionally left empty because put_json is not relevant for this test branch
            pass

    class DummyArtifact:
        def __init__(self):
            self.metadata = {"_local_path": None}  # Not str or Path

        key = "key"

    class DummyManifest:
        def to_json(self):
            # Return minimal JSON for test; no-op content
            return "{}"

    def dummy_collect_gitlab(*a, **k):
        return [DummyArtifact()], DummyManifest(), types.SimpleNamespace(id=1)

    monkeypatch.setattr(
        "auditly.cli_collect.AppConfig.load",
        lambda x: types.SimpleNamespace(environments={"dev": {}}),
    )
    monkeypatch.setattr("auditly.cli_collect.vault_from_envcfg", lambda x: DummyVault())
    monkeypatch.setattr("auditly.cli_collect.collect_gitlab", dummy_collect_gitlab)
    collect_gitlab_cmd(tmp_path, "dev", "https://gitlab.com", "proj", "token")


def test_collect_argo_cmd_invalid_local_path(monkeypatch, tmp_path):
    from auditly.cli_collect import collect_argo_cmd

    class DummyVault:
        def put_file(self, *a, **k):
            raise AssertionError("Should not be called")

        def put_json(self, *a, **k):
            # No-op for test: method intentionally left empty because put_json is not relevant for this test branch
            pass

    class DummyArtifact:
        def __init__(self):
            self.metadata = {"_local_path": 0.0}  # Not str or Path

        key = "key"

    class DummyManifest:
        def to_json(self):
            # Return minimal JSON for test; no-op content
            return "{}"

    def dummy_collect_argo(*a, **k):
        return [DummyArtifact()], DummyManifest(), types.SimpleNamespace(name="wf")

    monkeypatch.setattr(
        "auditly.cli_collect.AppConfig.load",
        lambda x: types.SimpleNamespace(environments={"dev": {}}),
    )
    monkeypatch.setattr("auditly.cli_collect.vault_from_envcfg", lambda x: DummyVault())
    monkeypatch.setattr("auditly.cli_collect.collect_argo", dummy_collect_argo)
    collect_argo_cmd(tmp_path, "dev", "https://argo", "argo")
