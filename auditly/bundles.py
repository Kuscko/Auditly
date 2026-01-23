"""Bundle creation, verification, and key management for auditly."""

from __future__ import annotations

import base64
import json
import tarfile
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

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
    """Represents a single item in a bundle."""

    key: str
    size: int
    sha256: str


@dataclass
class BundleManifest:
    """Manifest describing the contents and metadata of a bundle."""

    version: str
    environment: str
    created_at: float
    items: list[BundleItem]
    note: str | None = None

    def to_json_bytes(self) -> bytes:
        """Serialize the manifest to JSON bytes."""
        data = asdict(self)
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Generate a new Ed25519 keypair and return private and public key bytes."""
    sk = signing.SigningKey.generate()
    pk = sk.verify_key
    return bytes(sk), bytes(pk)


def save_keypair(
    private_bytes: bytes, public_bytes: bytes, priv_path: Path, pub_path: Path
) -> None:
    """Save private and public key bytes to the specified file paths."""
    priv_path.write_bytes(private_bytes)
    pub_path.write_bytes(public_bytes)


def load_private_key(path: Path) -> signing.SigningKey:
    """Load a private Ed25519 key from a file."""
    return signing.SigningKey(path.read_bytes())


def load_public_key(path: Path) -> signing.VerifyKey:
    """Load a public Ed25519 key from a file."""
    return signing.VerifyKey(path.read_bytes())


def create_bundle(
    environment: str,
    files: list[tuple[Path, str]],
    out_path: Path,
    private_key: signing.SigningKey,
    note: str | None = None,
) -> Path:
    """Create a signed evidence bundle tar.gz from files and a private key."""
    items: list[BundleItem] = []
    for src, key in files:
        items.append(BundleItem(key=key, size=src.stat().st_size, sha256=_sha256_file(src)))

    manifest = BundleManifest(
        version="0.1", environment=environment, created_at=time.time(), items=items, note=note
    )
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
    """Verify a bundle's signature and hashes, returning the manifest if valid."""
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
            if f is None:
                raise ValueError(f"missing file in bundle: {it.key}")
            h = sha256()

            # Defensive: type checker and runtime safe
            def _read_chunk():
                assert f is not None
                return f.read(8192)

            for chunk in iter(_read_chunk, b""):
                h.update(chunk)
            if h.hexdigest() != it.sha256:
                raise ValueError(f"hash mismatch for {it.key}")
        return manifest
