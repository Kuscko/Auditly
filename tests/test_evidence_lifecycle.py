"""Tests for evidence lifecycle management."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rapidrmf.db import Base
from rapidrmf.db.models import System, Evidence, EvidenceVersion, EvidenceAccessLog
from rapidrmf.evidence_lifecycle import EvidenceLifecycleManager


@pytest.fixture
def db_session():
    """Create in-memory test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_system(db_session):
    """Create test system."""
    system = System(
        name="test-system",
        environment="test",
        description="Test system for evidence lifecycle",
        attributes={},
    )
    db_session.add(system)
    db_session.flush()
    return system


@pytest.fixture
def test_evidence(db_session, test_system):
    """Create test evidence."""
    evidence = Evidence(
        system=test_system,
        evidence_type="terraform-plan",
        key="evidence/test/terraform.json",
        sha256="abc123",
        size=1024,
        collected_at=datetime.utcnow() - timedelta(days=45),  # 45 days old
        attributes={},
    )
    db_session.add(evidence)
    db_session.flush()
    return evidence


def test_detect_stale_evidence(db_session, test_system, test_evidence):
    """Test staleness detection."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Should detect stale evidence (45 days old, threshold 30)
    stale = mgr.detect_stale_evidence(test_system.id, staleness_threshold_days=30)
    assert len(stale) == 1
    assert stale[0].id == test_evidence.id
    
    # Should not detect with higher threshold
    stale = mgr.detect_stale_evidence(test_system.id, staleness_threshold_days=60)
    assert len(stale) == 0


def test_evidence_versioning(db_session, test_evidence):
    """Test evidence version tracking."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Add version manually (normally done by persistence layer)
    v1 = EvidenceVersion(
        evidence=test_evidence,
        version=1,
        data={"config": "old_value"},
        collected_at=datetime.utcnow() - timedelta(days=10),
        collector_version="1.0",
        attributes={},
    )
    db_session.add(v1)
    
    v2 = EvidenceVersion(
        evidence=test_evidence,
        version=2,
        data={"config": "new_value"},
        collected_at=datetime.utcnow(),
        collector_version="1.0",
        attributes={},
    )
    db_session.add(v2)
    db_session.flush()
    
    # Get versions
    versions = mgr.get_evidence_versions(test_evidence.id)
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2


def test_drift_detection(db_session, test_evidence):
    """Test configuration drift detection."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Create two versions with different data
    v1 = EvidenceVersion(
        evidence=test_evidence,
        version=1,
        data={"key1": "value1", "key2": "value2"},
        collected_at=datetime.utcnow() - timedelta(days=10),
        attributes={},
    )
    v2 = EvidenceVersion(
        evidence=test_evidence,
        version=2,
        data={"key1": "value1", "key2": "changed", "key3": "added"},
        collected_at=datetime.utcnow(),
        attributes={},
    )
    db_session.add_all([v1, v2])
    db_session.flush()
    
    # Detect drift
    drift = mgr.get_evidence_drift(test_evidence.id, version1=1, version2=2)
    
    assert drift["drift_detected"] is True
    assert "key2" in drift["changes"]
    assert drift["changes"]["key2"]["change_type"] == "modified"
    assert "key3" in drift["changes"]
    assert drift["changes"]["key3"]["change_type"] == "added"


def test_duplicate_detection(db_session, test_system):
    """Test duplicate evidence detection by hash."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Create two evidence records with same hash
    ev1 = Evidence(
        system=test_system,
        evidence_type="terraform-plan",
        key="evidence/v1/terraform.json",
        sha256="duplicate_hash",
        size=1024,
        attributes={},
    )
    ev2 = Evidence(
        system=test_system,
        evidence_type="terraform-plan",
        key="evidence/v2/terraform.json",
        sha256="duplicate_hash",
        size=1024,
        attributes={},
    )
    db_session.add_all([ev1, ev2])
    db_session.flush()
    
    # Detect duplicates
    duplicates = mgr.detect_duplicate_evidence(
        test_system.id,
        "duplicate_hash",
        exclude_evidence_id=ev1.id,
    )
    
    assert len(duplicates) == 1
    assert duplicates[0].id == ev2.id


def test_access_logging(db_session, test_evidence):
    """Test evidence access logging."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Log access
    log1 = mgr.log_evidence_access(
        evidence_id=test_evidence.id,
        user_id="user123",
        action="read",
        ip_address="192.168.1.1",
        attributes={"method": "api"},
    )
    
    log2 = mgr.log_evidence_access(
        evidence_id=test_evidence.id,
        user_id="validator",
        action="validate",
        attributes={"control_ids": ["AC-2"]},
    )
    
    db_session.flush()
    
    # Retrieve access log
    access_log = mgr.get_access_log(test_evidence.id)
    
    assert len(access_log) == 2
    # Logs are sorted by timestamp desc, but SQLite may not guarantee order without explicit timestamp
    actions = {log.action for log in access_log}
    assert "read" in actions
    assert "validate" in actions


def test_evidence_age_calculation(db_session, test_system):
    """Test evidence age calculation."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Create evidence 10 days old
    evidence = Evidence(
        system=test_system,
        evidence_type="test",
        key="test/key",
        sha256="hash",
        size=100,
        collected_at=datetime.utcnow() - timedelta(days=10),
        attributes={},
    )
    db_session.add(evidence)
    db_session.flush()
    
    age = mgr.get_evidence_age_days(evidence)
    assert age == 10


def test_recollection_needed(db_session, test_system):
    """Test recollection threshold detection."""
    mgr = EvidenceLifecycleManager(db_session)
    
    # Fresh evidence
    fresh = Evidence(
        system=test_system,
        evidence_type="test",
        key="fresh/key",
        sha256="fresh",
        size=100,
        collected_at=datetime.utcnow() - timedelta(days=5),
        attributes={},
    )
    
    # Stale evidence
    stale = Evidence(
        system=test_system,
        evidence_type="test",
        key="stale/key",
        sha256="stale",
        size=100,
        collected_at=datetime.utcnow() - timedelta(days=35),
        attributes={},
    )
    
    db_session.add_all([fresh, stale])
    db_session.flush()
    
    # Check recollection needed (30 day threshold)
    assert mgr.needs_recollection(fresh, recollection_threshold_days=30) is False
    assert mgr.needs_recollection(stale, recollection_threshold_days=30) is True


def test_mark_expired(db_session, test_evidence):
    """Test marking evidence as expired."""
    mgr = EvidenceLifecycleManager(db_session)
    
    expire_date = datetime.utcnow() + timedelta(days=90)
    updated = mgr.mark_evidence_expired(test_evidence.id, expire_date)
    
    assert updated.expires_at == expire_date
    
    # Verify in session
    evidence = db_session.get(Evidence, test_evidence.id)
    assert evidence.expires_at == expire_date


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
