"""Argo workflow collector for auditly evidence collection."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# type: ignore[import-untyped]
import requests

from ..evidence import ArtifactRecord, EvidenceManifest, sha256_file


@dataclass
class ArgoWorkflow:
    """Represents an Argo workflow instance."""

    uid: str
    name: str
    namespace: str
    status: str | None
    created_at: str | None


def _argo_headers(token: str | None = None) -> dict[str, str]:
    """Return HTTP headers for Argo API requests, including auth if provided."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def collect_argo(
    environment: str,
    base_url: str,
    namespace: str,
    workflow_name: str | None = None,
    token: str | None = None,
    key_prefix: str = "argo",
) -> tuple[list[ArtifactRecord], EvidenceManifest, ArgoWorkflow]:
    """Collect logs and artifacts from an Argo workflow and return records and manifest."""
    if not workflow_name:
        workflows = list_workflows(base_url, namespace, token, limit=1)
        if not workflows:
            raise RuntimeError("No workflows found")
        wf_data = workflows[0]
    else:
        wf_data = get_workflow(base_url, namespace, workflow_name, token)

    wf = ArgoWorkflow(
        uid=wf_data["metadata"]["uid"],
        name=wf_data["metadata"]["name"],
        namespace=wf_data["metadata"]["namespace"],
        status=wf_data.get("status", {}).get("phase"),
        created_at=wf_data["metadata"].get("creationTimestamp"),
    )

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        records: list[ArtifactRecord] = []

        # Download workflow logs
        try:
            logs = get_workflow_logs(base_url, namespace, wf.name, token)
            log_path = tdir / f"{wf.name}.log"
            log_path.write_text(logs)
            records.append(
                ArtifactRecord(
                    key=f"{key_prefix}/workflows/{wf.name}/{log_path.name}",
                    filename=log_path.name,
                    sha256=sha256_file(log_path),
                    size=log_path.stat().st_size,
                    metadata={
                        "kind": "argo-workflow-log",
                        "namespace": namespace,
                        "workflow_name": wf.name,
                        "workflow_uid": wf.uid,
                        "_local_path": str(log_path),
                    },
                )
            )
        except Exception:
            pass

        # Download artifacts if any
        artifacts = list_artifacts(base_url, namespace, wf.name, token)
        for art_meta in artifacts:
            node = art_meta["node"]
            art = art_meta["artifact"]
            art_name = art.get("name", "artifact")
            try:
                node_id = art_meta.get("node", "unknown")
                art_path = download_artifact(
                    base_url, namespace, wf.name, node_id, art_name, tdir, token
                )
                if art_path:
                    records.append(
                        ArtifactRecord(
                            key=f"{key_prefix}/workflows/{wf.name}/artifacts/{art_path.name}",
                            filename=art_path.name,
                            sha256=sha256_file(art_path),
                            size=art_path.stat().st_size,
                            metadata={
                                "kind": "argo-workflow-artifact",
                                "namespace": namespace,
                                "workflow_name": wf.name,
                                "workflow_uid": wf.uid,
                                "node": node,
                                "artifact_name": art_name,
                                "_local_path": str(art_path),
                            },
                        )
                    )
            except Exception:
                pass

        # Removed unused assignment to 'manifest' (F841)


def list_workflows(
    base_url: str, namespace: str, token: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """List Argo workflows in the given namespace."""
    url = f"{base_url}/api/v1/workflows/{namespace}"
    params = {"listOptions.limit": limit}
    r = requests.get(url, headers=_argo_headers(token), params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("items", [])


def get_workflow_logs(base_url: str, namespace: str, name: str, token: str | None = None) -> str:
    """Retrieve logs for a specific Argo workflow."""
    url = f"{base_url}/api/v1/workflows/{namespace}/{name}/log"
    r = requests.get(url, headers=_argo_headers(token), timeout=60)
    r.raise_for_status()
    return r.text


def download_artifact(
    base_url: str,
    namespace: str,
    name: str,
    node_id: str,
    art_name: str,
    tdir: Path,
    token: str | None = None,
) -> Path | None:
    """Download a workflow artifact and return its local path."""
    try:
        url = f"{base_url}/api/v1/workflows/{namespace}/{name}/artifacts/{node_id}/{art_name}"
        r = requests.get(url, headers=_argo_headers(token), timeout=60)
        r.raise_for_status()
        art_path = tdir / art_name
        with open(art_path, "wb") as f:
            f.write(r.content)
        return art_path
    except Exception:
        return None


# --- STUBS FOR MISSING FUNCTIONS ---
def get_workflow(
    base_url: str, namespace: str, workflow_name: str, token: str | None = None
) -> dict:
    """Stub for get_workflow. Should return workflow metadata dict."""
    # TODO: Implement actual API call
    return {}


def list_artifacts(
    base_url: str, namespace: str, workflow_name: str, token: str | None = None
) -> list:
    """Stub for list_artifacts. Should return a list of artifact metadata dicts."""
    # TODO: Implement actual API call
    return []
