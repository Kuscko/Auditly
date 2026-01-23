"""Configuration models and utilities for auditly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

# type: ignore[import-untyped]
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class MinioStorageConfig(BaseModel):
    """Configuration for Minio storage backend."""

    type: Literal["minio"]
    endpoint: str
    bucket: str
    access_key: str | None = None
    secret_key: str | None = None
    secure: bool = True


class S3StorageConfig(BaseModel):
    """Configuration for S3 storage backend."""

    type: Literal["s3"]
    region: str
    bucket: str
    profile: str | None = None


StorageConfig = MinioStorageConfig | S3StorageConfig


class EnvironmentConfig(BaseModel):
    """Configuration for an environment, including storage and database."""

    description: str | None = None
    storage: StorageConfig
    database_url: str | None = None  # e.g., postgresql+asyncpg://user:pass@host:5432/dbname


class PolicyConfig(BaseModel):
    """Configuration for policy bundles (rego/wasm)."""

    rego_bundles: list[str] = Field(default_factory=list)
    wasm_bundles: list[str] = Field(default_factory=list)


class CIConfig(BaseModel):
    """Configuration for CI provider preferences."""

    preferred: Literal["github", "gitlab", "argo"] = "github"
    fallback: Literal["github", "gitlab", "argo"] | None = None
    optional: Literal["github", "gitlab", "argo"] | None = None


class CatalogsConfig(BaseModel):
    """Configuration for catalog file locations."""

    nist_800_53_rev5: str | None = None
    nist_800_53b_low: str | None = None
    nist_800_53b_moderate: str | None = None
    nist_800_53b_high: str | None = None
    fedramp_low: str | None = None
    fedramp_moderate: str | None = None
    fedramp_high: str | None = None
    fedramp_li_saas: str | None = None
    nist_800_207_zero_trust: str | None = None
    stig_baseline: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def validate_catalog_path(cls, v: str | None) -> str | None:
        """Validate that catalog file exists if path is provided."""
        if v is None:
            return v

        path = Path(v)
        if not path.exists():
            raise ValueError(f"Catalog file not found: {v}")

        if not path.is_file():
            raise ValueError(f"Catalog path is not a file: {v}")

        if path.suffix.lower() not in [".json", ".xml", ".yaml", ".yml"]:
            raise ValueError(f"Catalog file must be JSON, XML, or YAML: {v}")

        return str(path.resolve())

    @model_validator(mode="after")
    def validate_oscal_structure(self) -> CatalogsConfig:
        """Validate that provided catalog files contain valid OSCAL structure."""
        for file_path in self.model_dump().values():
            if file_path is None:
                continue

            path = Path(file_path)
            if not path.exists():
                continue

            try:
                if path.suffix.lower() == ".json":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    # Check for basic OSCAL structure
                    if "catalog" not in data and "profile" not in data:
                        raise ValueError(
                            f"Invalid OSCAL file '{file_path}': must contain 'catalog' or 'profile' root element"
                        )
                # XML/YAML validation could be added here
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in catalog file '{file_path}': {e}") from e
            except Exception as e:
                raise ValueError(f"Error validating catalog '{file_path}': {e}") from e

        return self

    def get_all_catalogs(self) -> dict[str, Path]:
        """Return all configured catalog paths."""
        catalogs = {}
        for field_name, file_path in self.model_dump().items():
            if file_path:
                catalogs[field_name] = Path(file_path)
        return catalogs

    def get_catalog(self, name: str) -> Path | None:
        """Get a specific catalog path by name."""
        file_path = getattr(self, name, None)
        return Path(file_path) if file_path else None


class AppConfig(BaseModel):
    """Application configuration settings."""

    version: str = "0.1"
    organization: str | None = None
    catalogs: CatalogsConfig = Field(default_factory=CatalogsConfig)
    environments: dict[str, EnvironmentConfig] = Field(default_factory=dict)
    ci: CIConfig = Field(default_factory=CIConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    staging_dir: str | None = None

    @staticmethod
    def load(path: Path | str) -> AppConfig:
        """Load configuration from a file."""
        p = Path(path)
        data = yaml.safe_load(p.read_text())
        return AppConfig.model_validate(data)

    def save(self, path: Path | str) -> None:
        """Save configuration to a file."""
        p = Path(path)
        p.write_text(yaml.safe_dump(self.model_dump(mode="python"), sort_keys=False))
