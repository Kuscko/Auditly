"""GitHub Actions collectors for evidence and artifact retrieval."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# type: ignore[import-untyped]
import requests

from ..evidence import ArtifactRecord, EvidenceManifest, sha256_file


@dataclass
class GitHubRun:
    """Represents a GitHub Actions workflow run."""

    id: int
    head_branch: str | None
    status: str
    conclusion: str | None
    created_at: str
    name: str | None


def _gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_latest_run(repo: str, token: str, branch: str | None = None) -> GitHubRun:
    """Get the latest workflow run for a repository and optional branch."""
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    params = {"per_page": 10}
    if branch:
        params["branch"] = branch
    r = requests.get(url, headers=_gh_headers(token), params=params, timeout=30)
    r.raise_for_status()
    runs = r.json().get("workflow_runs", [])
    if not runs:
        raise RuntimeError("No workflow runs found")
    run = runs[0]
    return GitHubRun(
        id=run["id"],
        head_branch=run.get("head_branch"),
        status=run.get("status"),
        conclusion=run.get("conclusion"),
        created_at=run.get("created_at"),
        name=run.get("name"),
    )


def get_run(repo: str, token: str, run_id: int) -> GitHubRun:
    """Get a specific workflow run by run ID."""
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
    r = requests.get(url, headers=_gh_headers(token), timeout=30)
    r.raise_for_status()
    run = r.json()
    return GitHubRun(
        id=run["id"],
        head_branch=run.get("head_branch"),
        status=run.get("status"),
        conclusion=run.get("conclusion"),
        created_at=run.get("created_at"),
        name=run.get("name"),
    )


def download_run_logs(repo: str, token: str, run_id: int, out_dir: Path) -> Path:
    """Download logs for a workflow run as a zip file."""
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/logs"
    # Logs return as a zip stream
    r = requests.get(url, headers=_gh_headers(token), timeout=60)
    r.raise_for_status()
    zip_path = out_dir / f"run-{run_id}-logs.zip"
    zip_path.write_bytes(r.content)
    return zip_path


def list_artifacts(repo: str, token: str, run_id: int) -> list[dict[str, Any]]:
    """List artifacts for a workflow run."""
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts"
    r = requests.get(url, headers=_gh_headers(token), timeout=30)
    r.raise_for_status()
    return r.json().get("artifacts", [])


def download_artifact_zip(repo: str, token: str, artifact_id: int, out_dir: Path) -> Path:
    """Download a workflow run artifact as a zip file."""
    url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    r = requests.get(url, headers=_gh_headers(token), timeout=60)
    r.raise_for_status()
    zip_path = out_dir / f"artifact-{artifact_id}.zip"
    zip_path.write_bytes(r.content)
    return zip_path


def collect_github_actions(
    environment: str,
    repo: str,
    token: str,
    run_id: int | None = None,
    branch: str | None = None,
    key_prefix: str = "github-actions",
) -> tuple[list[ArtifactRecord], EvidenceManifest, GitHubRun]:
    """Collect logs and artifacts for a GitHub Actions run and build evidence records and manifest."""
    run = get_run(repo, token, run_id) if run_id else get_latest_run(repo, token, branch)
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        logs_zip = download_run_logs(repo, token, run.id, tdir)
        artifacts_meta = list_artifacts(repo, token, run.id)
        artifact_zips: list[Path] = []
        for art in artifacts_meta:
            artifact_zips.append(download_artifact_zip(repo, token, art["id"], tdir))

        records: list[ArtifactRecord] = []
        # Logs record
        records.append(
            ArtifactRecord(
                key=f"{key_prefix}/runs/{run.id}/logs/{logs_zip.name}",
                filename=logs_zip.name,
                sha256=sha256_file(logs_zip),
                size=logs_zip.stat().st_size,
                metadata={"kind": "github-run-logs", "repo": repo, "run_id": str(run.id)},
            )
        )
        # Artifact zips
        for p in artifact_zips:
            records.append(
                ArtifactRecord(
                    key=f"{key_prefix}/runs/{run.id}/artifacts/{p.name}",
                    filename=p.name,
                    sha256=sha256_file(p),
                    size=p.stat().st_size,
                    metadata={"kind": "github-run-artifact", "repo": repo, "run_id": str(run.id)},
                )
            )

        manifest = EvidenceManifest.create(
            environment=environment, artifacts=records, notes=f"github actions run {run.id}"
        )
        # Copy files to a stable temp dir for caller to upload
        # Return paths via metadata (we keep Path local, upload handled by CLI)
        for r in records:
            # Store temp local path hint
            r.metadata["_local_path"] = str(tdir / r.filename)

        return records, manifest, run
