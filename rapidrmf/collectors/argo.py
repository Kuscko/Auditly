from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..evidence import ArtifactRecord, EvidenceManifest, sha256_file


@dataclass
class ArgoWorkflow:
    uid: str
    name: str
    namespace: str
    status: Optional[str]
    created_at: Optional[str]


def _argo_headers(token: Optional[str] = None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def list_workflows(
    base_url: str, namespace: str, token: Optional[str] = None, limit: int = 10
) -> List[Dict[str, Any]]:
    url = f"{base_url}/api/v1/workflows/{namespace}"
    params = {"listOptions.limit": limit}
    r = requests.get(url, headers=_argo_headers(token), params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("items", [])


def get_workflow(base_url: str, namespace: str, name: str, token: Optional[str] = None) -> Dict[str, Any]:
    url = f"{base_url}/api/v1/workflows/{namespace}/{name}"
    r = requests.get(url, headers=_argo_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def get_workflow_logs(
    base_url: str, namespace: str, name: str, token: Optional[str] = None
) -> str:
    url = f"{base_url}/api/v1/workflows/{namespace}/{name}/log"
    r = requests.get(url, headers=_argo_headers(token), timeout=60)
    r.raise_for_status()
    return r.text


def list_artifacts(
    base_url: str, namespace: str, name: str, token: Optional[str] = None
) -> List[Dict[str, Any]]:
    # Argo artifacts are per-node; we'll list nodes and check for outputArtifacts
    wf = get_workflow(base_url, namespace, name, token)
    artifacts = []
    for node_id, node in wf.get("status", {}).get("nodes", {}).items():
        if "outputs" in node and "artifacts" in node["outputs"]:
            for art in node["outputs"]["artifacts"]:
                artifacts.append({"node": node.get("displayName", node_id), "artifact": art})
    return artifacts


def download_artifact(
    base_url: str,
    namespace: str,
    name: str,
    node_id: str,
    artifact_name: str,
    out_dir: Path,
    token: Optional[str] = None,
) -> Optional[Path]:
    # Argo artifact download endpoint
    url = f"{base_url}/artifacts/{namespace}/{name}/{node_id}/{artifact_name}"
    try:
        r = requests.get(url, headers=_argo_headers(token), timeout=60)
        r.raise_for_status()
        art_path = out_dir / f"{node_id}-{artifact_name}"
        art_path.write_bytes(r.content)
        return art_path
    except Exception:
        return None


def collect_argo(
    environment: str,
    base_url: str,
    namespace: str,
    workflow_name: Optional[str] = None,
    token: Optional[str] = None,
    key_prefix: str = "argo",
) -> Tuple[List[ArtifactRecord], EvidenceManifest, ArgoWorkflow]:
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
        records: List[ArtifactRecord] = []

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
            # Argo artifacts can be in S3/GCS/etc; we'll try the HTTP endpoint
            # This is a simplified approach; production may need S3 direct access
            try:
                node_id = art_meta.get("node", "unknown")
                art_path = download_artifact(base_url, namespace, wf.name, node_id, art_name, tdir, token)
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

        manifest = EvidenceManifest.create(
            environment=environment,
            artifacts=records,
            notes=f"argo workflow {wf.name}",
        )
        return records, manifest, wf
