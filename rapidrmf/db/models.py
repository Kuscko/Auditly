"""SQLAlchemy ORM models for RapidRMF v0.2."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Boolean,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from enum import Enum

from . import Base


class ValidationStatus(str, Enum):
    """Validation status enumeration."""
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNKNOWN = "unknown"


class System(Base):
    """A system registered for compliance monitoring."""
    __tablename__ = "systems"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    environment = Column(String(50), nullable=False, index=True)  # edge, IL2, IL4, IL5, IL6
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attributes = Column(JSON, default=dict, nullable=False)  # Custom fields, tags, etc.

    # Relationships
    evidence = relationship("Evidence", back_populates="system", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="system", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="system", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<System(id={self.id}, name={self.name}, env={self.environment})>"


class Evidence(Base):
    """Collected evidence for a system."""
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("systems.id"), nullable=False, index=True)
    evidence_type = Column(String(100), nullable=False, index=True)  # terraform-plan, azure-config, etc.
    key = Column(String(500), nullable=False)  # Storage key in vault
    vault_path = Column(String(500), nullable=True)  # MinIO/S3 path
    filename = Column(String(255), nullable=True)
    sha256 = Column(String(64), nullable=False, index=True)  # SHA256 hash
    size = Column(Integer, nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)  # Evidence staleness threshold
    attributes = Column(JSON, default=dict, nullable=False)  # Source, version, etc.

    # Relationships
    system = relationship("System", back_populates="evidence")
    manifest_entries = relationship("EvidenceManifestEntry", back_populates="evidence", cascade="all, delete-orphan")
    versions = relationship("EvidenceVersion", back_populates="evidence", cascade="all, delete-orphan")
    access_logs = relationship("EvidenceAccessLog", back_populates="evidence", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Evidence(id={self.id}, type={self.evidence_type}, system_id={self.system_id})>"


class Catalog(Base):
    """Compliance framework catalogs (NIST, FedRAMP, STIG, etc.)."""
    __tablename__ = "catalogs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # nist-800-53-rev5, fedramp-moderate, etc.
    title = Column(String(255), nullable=False)
    version = Column(String(50), nullable=True)
    framework = Column(String(100), nullable=False, index=True)  # NIST, FedRAMP, STIG, HIPAA, PCI, ISO, etc.
    baseline = Column(String(50), nullable=True)  # Low, Moderate, High, etc.
    oscal_path = Column(String(500), nullable=True)  # Path to OSCAL JSON file
    loaded_at = Column(DateTime, default=datetime.utcnow)
    attributes = Column(JSON, default=dict, nullable=False)

    # Relationships
    controls = relationship("Control", back_populates="catalog", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Catalog(name={self.name}, framework={self.framework})>"


class Control(Base):
    """Individual control within a catalog."""
    __tablename__ = "controls"

    id = Column(Integer, primary_key=True)
    catalog_id = Column(Integer, ForeignKey("catalogs.id"), nullable=False, index=True)
    control_id = Column(String(50), nullable=False, index=True)  # AC-1, IA-2, etc.
    title = Column(String(255), nullable=False)
    family = Column(String(10), nullable=False, index=True)  # AC, AU, AT, etc.
    description = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    baseline_required = Column(Boolean, default=False)  # Required in Low/Moderate/High
    attributes = Column(JSON, default=dict, nullable=False)

    # Relationships
    catalog = relationship("Catalog", back_populates="controls")
    requirements = relationship("ControlRequirement", back_populates="control", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="control", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Control(control_id={self.control_id}, family={self.family})>"


class ControlRequirement(Base):
    """Evidence requirements for a control."""
    __tablename__ = "control_requirements"

    id = Column(Integer, primary_key=True)
    control_id = Column(Integer, ForeignKey("controls.id"), nullable=False, index=True)
    required_any = Column(JSON, default=list, nullable=False)  # Any one of these evidence types
    required_all = Column(JSON, default=list, nullable=False)  # All of these evidence types
    description = Column(Text, nullable=True)

    # Relationships
    control = relationship("Control", back_populates="requirements")

    def __repr__(self):
        return f"<ControlRequirement(control_id={self.control_id})>"


class ValidationResult(Base):
    """Result of a single control validation."""
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("systems.id"), nullable=False, index=True)
    control_id = Column(Integer, ForeignKey("controls.id"), nullable=False, index=True)
    status = Column(SQLEnum(ValidationStatus), nullable=False, index=True)
    message = Column(Text, nullable=True)
    evidence_keys = Column(JSON, default=list, nullable=False)
    remediation = Column(Text, nullable=True)
    validated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    attributes = Column(JSON, default=dict, nullable=False)

    # Relationships
    system = relationship("System", back_populates="validation_results")
    control = relationship("Control", back_populates="validation_results")

    def __repr__(self):
        return f"<ValidationResult(system={self.system_id}, control={self.control_id}, status={self.status})>"


class Finding(Base):
    """A discovered compliance gap or issue."""
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("systems.id"), nullable=False, index=True)
    control_id = Column(Integer, ForeignKey("controls.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical
    status = Column(String(50), default="open", nullable=False, index=True)  # open, investigating, remediating, closed
    found_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    closed_at = Column(DateTime, nullable=True)
    attributes = Column(JSON, default=dict, nullable=False)

    # Relationships
    system = relationship("System", back_populates="findings")
    control = relationship("Control")

    def __repr__(self):
        return f"<Finding(id={self.id}, system={self.system_id}, severity={self.severity})>"


class EvidenceManifest(Base):
    """Manifest for grouped evidence (tamper-evident bundles)."""
    __tablename__ = "evidence_manifests"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("systems.id"), nullable=True, index=True)
    environment = Column(String(50), nullable=False)  # edge, IL2, IL4, IL5, IL6
    version = Column(String(10), default="1.0", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    overall_hash = Column(String(64), nullable=False)  # Merkle-tree or overall SHA256
    signed_by = Column(String(255), nullable=True)  # Ed25519 key ID
    signature = Column(Text, nullable=True)  # Ed25519 signature
    notes = Column(Text, nullable=True)
    attributes = Column(JSON, default=dict, nullable=False)

    # Relationships
    entries = relationship("EvidenceManifestEntry", back_populates="manifest", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EvidenceManifest(id={self.id}, env={self.environment})>"


class EvidenceManifestEntry(Base):
    """Entry in an evidence manifest (artifact record)."""
    __tablename__ = "evidence_manifest_entries"

    id = Column(Integer, primary_key=True)
    manifest_id = Column(Integer, ForeignKey("evidence_manifests.id"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)
    key = Column(String(500), nullable=False)  # Storage key
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    size = Column(Integer, nullable=True)

    # Relationships
    manifest = relationship("EvidenceManifest", back_populates="entries")
    evidence = relationship("Evidence", back_populates="manifest_entries")

    def __repr__(self):
        return f"<EvidenceManifestEntry(manifest={self.manifest_id}, key={self.key})>"


class EvidenceVersion(Base):
    """Historical versions of evidence for chain-of-custody and drift analysis."""

    __tablename__ = "evidence_versions"

    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    collector_version = Column(String(50), nullable=True)
    signature = Column(Text, nullable=True)
    attributes = Column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("evidence_id", "version", name="uq_evidence_version"),)

    evidence = relationship("Evidence", back_populates="versions")

    def __repr__(self):
        return f"<EvidenceVersion(evidence_id={self.evidence_id}, version={self.version})>"


class EvidenceAccessLog(Base):
    """Audit trail for evidence access."""

    __tablename__ = "evidence_access_log"

    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)  # read, write, delete
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    attributes = Column(JSON, default=dict, nullable=False)

    evidence = relationship("Evidence", back_populates="access_logs")

    def __repr__(self):
        return f"<EvidenceAccessLog(evidence_id={self.evidence_id}, action={self.action})>"


class JobRun(Base):
    """Scheduler job run state for persistence and metrics."""
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True)
    job_type = Column(String(100), nullable=False, index=True)  # validation, collection, report
    environment = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True, default="pending")  # pending, running, success, failed
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)
    error = Column(Text, nullable=True)
    metrics = Column(JSON, default=dict, nullable=False)
    attributes = Column(JSON, default=dict, nullable=False)

    def __repr__(self):
        return f"<JobRun(id={self.id}, type={self.job_type}, env={self.environment}, status={self.status})>"
