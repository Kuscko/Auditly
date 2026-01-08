from __future__ import annotations

import base64
import json
import tarfile
import time
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import List, Optional, Tuple

from nacl import signing
from nacl.encoding import RawEncoder


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class BundleItem:
    key: str
    size: int
    sha256: str


@dataclass
class BundleManifest:
    version: str
    environment: str
    created_at: float
    items: List[BundleItem]
    note: Optional[str] = None

    def to_json_bytes(self) -> bytes:
        data = asdict(self)
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def generate_ed25519_keypair() -> Tuple[bytes, bytes]:
    sk = signing.SigningKey.generate()
    pk = sk.verify_key
    return bytes(sk), bytes(pk)


def save_keypair(private_bytes: bytes, public_bytes: bytes, priv_path: Path, pub_path: Path) -> None:
    priv_path.write_bytes(private_bytes)
    pub_path.write_bytes(public_bytes)


def load_private_key(path: Path) -> signing.SigningKey:
    return signing.SigningKey(path.read_bytes())


def load_public_key(path: Path) -> signing.VerifyKey:
    return signing.VerifyKey(path.read_bytes())


def create_bundle(
    environment: str,
    files: List[Tuple[Path, str]],
    out_path: Path,
    private_key: signing.SigningKey,
    note: Optional[str] = None,
) -> Path:
    items: List[BundleItem] = []
    for src, key in files:
        items.append(BundleItem(key=key, size=src.stat().st_size, sha256=_sha256_file(src)))

    manifest = BundleManifest(version="0.1", environment=environment, created_at=time.time(), items=items, note=note)
    manifest_bytes = manifest.to_json_bytes()
    sig = private_key.sign(manifest_bytes, encoder=RawEncoder).signature

    with tarfile.open(out_path, "w:gz", format=tarfile.PAX_FORMAT, compresslevel=9) as tar:
        # Add files with deterministic metadata
        for src, key in sorted(files, key=lambda x: x[1]):
            ti = tarfile.TarInfo(name=key)
            ti.size = src.stat().st_size
            ti.mtime = 0
            ti.uid = 0
            ti.gid = 0
            ti.uname = ""
            ti.gname = ""
            with src.open("rb") as f:
                tar.addfile(ti, fileobj=f)

        # Add manifest and signature
        man_info = tarfile.TarInfo(name="bundle/bundle.json")
        man_info.size = len(manifest_bytes)
        man_info.mtime = 0
        man_info.uid = 0
        man_info.gid = 0
        man_info.uname = ""
        man_info.gname = ""
        tar.addfile(man_info, fileobj=BytesIO(manifest_bytes))

        sig_b64 = base64.b64encode(sig)
        sig_info = tarfile.TarInfo(name="bundle/bundle.sig")
        sig_info.size = len(sig_b64)
        sig_info.mtime = 0
        sig_info.uid = 0
        sig_info.gid = 0
        tar.addfile(sig_info, fileobj=BytesIO(sig_b64))

    return out_path


def verify_bundle(bundle_path: Path, public_key: signing.VerifyKey) -> BundleManifest:
    with tarfile.open(bundle_path, "r:gz") as tar:
        man = tar.extractfile("bundle/bundle.json")
        sig = tar.extractfile("bundle/bundle.sig")
        if not man or not sig:
            raise ValueError("bundle missing manifest or signature")
        manifest_bytes = man.read()
        sig_bytes = base64.b64decode(sig.read())
        public_key.verify(manifest_bytes, sig_bytes, encoder=RawEncoder)
        data = json.loads(manifest_bytes)
        manifest = BundleManifest(
            version=data["version"],
            environment=data["environment"],
            created_at=data["created_at"],
            items=[BundleItem(**it) for it in data["items"]],
            note=data.get("note"),
        )
        # Verify each item hash
        for it in manifest.items:
            f = tar.extractfile(it.key)
            if not f:
                raise ValueError(f"missing file in bundle: {it.key}")
            h = sha256()
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            if h.hexdigest() != it.sha256:
                raise ValueError(f"hash mismatch for {it.key}")
        return manifest


from io import BytesIO
