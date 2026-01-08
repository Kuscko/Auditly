from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class MinioStorageConfig(BaseModel):
    type: Literal["minio"]
    endpoint: str
    bucket: str
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    secure: bool = True


class S3StorageConfig(BaseModel):
    type: Literal["s3"]
    region: str
    bucket: str
    profile: Optional[str] = None


StorageConfig = MinioStorageConfig | S3StorageConfig


class EnvironmentConfig(BaseModel):
    description: Optional[str] = None
    storage: StorageConfig
    database_url: Optional[str] = None  # e.g., postgresql+asyncpg://user:pass@host:5432/dbname


class PolicyConfig(BaseModel):
    rego_bundles: list[str] = Field(default_factory=list)
    wasm_bundles: list[str] = Field(default_factory=list)


class CIConfig(BaseModel):
    preferred: Literal["github", "gitlab", "argo"] = "github"
    fallback: Optional[Literal["github", "gitlab", "argo"]] = None
    optional: Optional[Literal["github", "gitlab", "argo"]] = None


class CatalogsConfig(BaseModel):
    nist_800_53_rev5: Optional[str] = None
    nist_800_53b_low: Optional[str] = None
    nist_800_53b_moderate: Optional[str] = None
    nist_800_53b_high: Optional[str] = None
    fedramp_low: Optional[str] = None
    fedramp_moderate: Optional[str] = None
    fedramp_high: Optional[str] = None
    fedramp_li_saas: Optional[str] = None
    nist_800_207_zero_trust: Optional[str] = None
    stig_baseline: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def validate_catalog_path(cls, v: Optional[str]) -> Optional[str]:
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
    def validate_oscal_structure(self) -> "CatalogsConfig":
        """Validate that provided catalog files contain valid OSCAL structure."""
        for field_name, file_path in self.model_dump().items():
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
                raise ValueError(f"Invalid JSON in catalog file '{file_path}': {e}")
            except Exception as e:
                raise ValueError(f"Error validating catalog '{file_path}': {e}")
        
        return self

    def get_all_catalogs(self) -> Dict[str, Path]:
        """Return all configured catalog paths."""
        catalogs = {}
        for field_name, file_path in self.model_dump().items():
            if file_path:
                catalogs[field_name] = Path(file_path)
        return catalogs

    def get_catalog(self, name: str) -> Optional[Path]:
        """Get a specific catalog path by name."""
        file_path = getattr(self, name, None)
        return Path(file_path) if file_path else None


class AppConfig(BaseModel):
    version: str = "0.1"
    organization: Optional[str] = None
    catalogs: CatalogsConfig = Field(default_factory=CatalogsConfig)
    environments: Dict[str, EnvironmentConfig] = Field(default_factory=dict)
    ci: CIConfig = Field(default_factory=CIConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    staging_dir: Optional[str] = None

    @staticmethod
    def load(path: Path | str) -> "AppConfig":
        p = Path(path)
        data = yaml.safe_load(p.read_text())
        return AppConfig.model_validate(data)

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.write_text(yaml.safe_dump(self.model_dump(mode="python"), sort_keys=False))
