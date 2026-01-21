from __future__ import annotations

from pathlib import Path

import typer
from rich import print

from .bundles import (
    create_bundle,
    generate_ed25519_keypair,
    load_private_key,
    load_public_key,
    save_keypair,
    verify_bundle,
)
from .cli_common import vault_from_envcfg
from .config import AppConfig

bundle_app = typer.Typer(help="Air-gap bundles (keygen, create, verify, import)")


@bundle_app.command("keygen", help="Generate Ed25519 keypair for bundles")
def bundle_keygen(
    out_dir: Path = typer.Option(Path(".keys"), help="Output directory for keys"),
    name: str = typer.Option("rapidrmf", help="Key name prefix"),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    sk, pk = generate_ed25519_keypair()
    priv_path = out_dir / f"{name}.ed25519"
    pub_path = out_dir / f"{name}.ed25519.pub"
    save_keypair(sk, pk, priv_path, pub_path)
    print(f"[green]Wrote keys: {priv_path}, {pub_path}")


@bundle_app.command("create", help="Create signed bundle from vault prefix")
def bundle_create(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Source environment key"),
    key_prefix: str = typer.Option("manifests/", help="Prefix to include from vault"),
    private_key_path: Path = typer.Option(..., exists=True, help="Path to Ed25519 private key"),
    out_path: Path = typer.Option(Path("evidence-bundle.tar.gz"), help="Output tar.gz path"),
    note: str = typer.Option("", help="Optional note"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)
    keys = vault.list(key_prefix)
    if not keys:
        raise typer.BadParameter(f"No objects under prefix '{key_prefix}' in environment '{env}'")

    staging = Path(cfg.staging_dir or ".rapidrmf_staging") / "bundle"
    staging.mkdir(parents=True, exist_ok=True)
    files = []
    for k in sorted(keys):
        out_file = staging / k
        vault.fetch(k, out_file)
        files.append((out_file, k))

    sk = load_private_key(private_key_path)
    create_bundle(
        environment=env, files=files, out_path=out_path, private_key=sk, note=note or None
    )
    print(f"[green]Created bundle at {out_path} with {len(files)} file(s)")


@bundle_app.command("verify", help="Verify bundle signature and manifest")
def bundle_verify_cmd(
    bundle_path: Path = typer.Option(..., exists=True, help="Path to evidence-bundle.tar.gz"),
    public_key_path: Path = typer.Option(..., exists=True, help="Path to Ed25519 public key"),
):
    vk = load_public_key(public_key_path)
    manifest = verify_bundle(bundle_path, vk)
    print(
        f"[green]Bundle OK for environment '{manifest.environment}', items: {len(manifest.items)}"
    )


@bundle_app.command("import", help="Verify bundle and import into vault")
def bundle_import(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Target environment key"),
    bundle_path: Path = typer.Option(..., exists=True, help="Path to evidence-bundle.tar.gz"),
    public_key_path: Path = typer.Option(..., exists=True, help="Path to Ed25519 public key"),
    dest_prefix: str = typer.Option("", help="Optional destination prefix to prepend"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)
    vk = load_public_key(public_key_path)
    manifest = verify_bundle(bundle_path, vk)

    import tarfile

    uploaded = 0
    with tarfile.open(bundle_path, "r:gz") as tar:
        for item in manifest.items:
            f = tar.extractfile(item.key)
            if not f:
                raise typer.BadParameter(f"missing file in bundle: {item.key}")
            tmp = Path(cfg.staging_dir or ".rapidrmf_staging") / "import" / item.key
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(f.read())
            dest_key = f"{dest_prefix}{item.key}" if dest_prefix else item.key
            vault.put_file(tmp, dest_key, metadata={"imported": "true"})
            uploaded += 1
    print(f"[green]Imported {uploaded} file(s) into environment '{env}'")
