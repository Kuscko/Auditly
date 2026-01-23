"""GitLab CI pipeline and artifact collection utilities."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# type: ignore[import-untyped]
import requests

from ..evidence import ArtifactRecord, EvidenceManifest, sha256_file


@dataclass
class GitLabPipeline:
    """Represents a GitLab pipeline with basic metadata."""

    id: int
    ref: str | None
    status: str
    created_at: str
    web_url: str | None


def _gitlab_headers(token: str) -> dict[str, str]:
    """Return headers for GitLab API requests."""
    return {
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json",
    }


def get_latest_pipeline(
    base_url: str, project_id: str, token: str, ref: str | None = None
) -> GitLabPipeline:
    """Get the latest pipeline for a project, optionally filtered by ref."""
    url = f"{base_url}/api/v4/projects/{project_id}/pipelines"
    params = {"per_page": 10, "order_by": "id", "sort": "desc"}
    if ref:
        params["ref"] = ref
    r = requests.get(url, headers=_gitlab_headers(token), params=params, timeout=30)
    r.raise_for_status()
    pipelines = r.json()
    if not pipelines:
        raise RuntimeError("No pipelines found")
    p = pipelines[0]
    return GitLabPipeline(
        id=p["id"],
        ref=p.get("ref"),
        status=p.get("status"),
        created_at=p.get("created_at"),
        web_url=p.get("web_url"),
    )


def get_pipeline(base_url: str, project_id: str, token: str, pipeline_id: int) -> GitLabPipeline:
    """Get a specific pipeline by ID."""
    url = f"{base_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
    r = requests.get(url, headers=_gitlab_headers(token), timeout=30)
    r.raise_for_status()
    p = r.json()
    return GitLabPipeline(
        id=p["id"],
        ref=p.get("ref"),
        status=p.get("status"),
        created_at=p.get("created_at"),
        web_url=p.get("web_url"),
    )


def list_pipeline_jobs(
    base_url: str, project_id: str, token: str, pipeline_id: int
) -> list[dict[str, Any]]:
    """List jobs for a given pipeline."""
    url = f"{base_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    r = requests.get(url, headers=_gitlab_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def download_job_trace(
    base_url: str, project_id: str, token: str, job_id: int, out_dir: Path
) -> Path:
    """Download the trace log for a job and save it to out_dir."""
    url = f"{base_url}/api/v4/projects/{project_id}/jobs/{job_id}/trace"
    r = requests.get(url, headers=_gitlab_headers(token), timeout=60)
    r.raise_for_status()
    log_path = out_dir / f"job-{job_id}.log"
    log_path.write_text(r.text)
    return log_path


def list_job_artifacts(base_url: str, project_id: str, token: str, job_id: int) -> bool:
    """Check if job artifacts exist for a given job."""
    url = f"{base_url}/api/v4/projects/{project_id}/jobs/{job_id}/artifacts"
    r = requests.head(url, headers=_gitlab_headers(token), timeout=10)
    return r.status_code == 200


def download_job_artifacts(
    base_url: str, project_id: str, token: str, job_id: int, out_dir: Path
) -> Path | None:
    """Download job artifacts as a zip file if present."""
    url = f"{base_url}/api/v4/projects/{project_id}/jobs/{job_id}/artifacts"
    r = requests.get(url, headers=_gitlab_headers(token), timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    zip_path = out_dir / f"job-{job_id}-artifacts.zip"
    zip_path.write_bytes(r.content)
    return zip_path


def collect_gitlab(
    environment: str,
    base_url: str,
    project_id: str,
    token: str,
    pipeline_id: int | None = None,
    ref: str | None = None,
    key_prefix: str = "gitlab",
) -> tuple[list[ArtifactRecord], EvidenceManifest, GitLabPipeline]:
    """Collect logs and artifacts from a GitLab pipeline and return records, manifest, and pipeline info."""
    pipeline = (
        get_pipeline(base_url, project_id, token, pipeline_id)
        if pipeline_id
        else get_latest_pipeline(base_url, project_id, token, ref)
    )
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        jobs = list_pipeline_jobs(base_url, project_id, token, pipeline.id)
        records: list[ArtifactRecord] = []

        for job in jobs:
            job_id = job["id"]
            job_name = job.get("name", "unknown")

            # Download job trace/log
            try:
                log_path = download_job_trace(base_url, project_id, token, job_id, tdir)
                records.append(
                    ArtifactRecord(
                        key=f"{key_prefix}/pipelines/{pipeline.id}/jobs/{job_id}/{log_path.name}",
                        filename=log_path.name,
                        sha256=sha256_file(log_path),
                        size=log_path.stat().st_size,
                        metadata={
                            "kind": "gitlab-job-log",
                            "project_id": project_id,
                            "pipeline_id": str(pipeline.id),
                            "job_id": str(job_id),
                            "job_name": job_name,
                            "_local_path": str(log_path),
                        },
                    )
                )
            except Exception:
                pass

            # Download job artifacts if present
            if list_job_artifacts(base_url, project_id, token, job_id):
                try:
                    art_path = download_job_artifacts(base_url, project_id, token, job_id, tdir)
                    if art_path:
                        records.append(
                            ArtifactRecord(
                                key=f"{key_prefix}/pipelines/{pipeline.id}/jobs/{job_id}/{art_path.name}",
                                filename=art_path.name,
                                sha256=sha256_file(art_path),
                                size=art_path.stat().st_size,
                                metadata={
                                    "kind": "gitlab-job-artifacts",
                                    "project_id": project_id,
                                    "pipeline_id": str(pipeline.id),
                                    "job_id": str(job_id),
                                    "job_name": job_name,
                                    "_local_path": str(art_path),
                                },
                            )
                        )
                except Exception:
                    pass

        manifest = EvidenceManifest.create(
            environment=environment,
            artifacts=records,
            notes=f"gitlab pipeline {pipeline.id}",
        )
        return records, manifest, pipeline
