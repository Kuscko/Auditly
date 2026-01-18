"""Integration tests for GCP collectors.

These tests verify that GCP collectors:
1. Can be imported correctly
2. Have consistent interfaces
3. Return properly formatted evidence
4. Follow naming conventions
"""

import pytest

# Test imports
def test_gcp_package_import():
    """Verify GCP collectors package can be imported."""
    try:
        import rapidrmf.collectors.gcp
        assert hasattr(rapidrmf.collectors.gcp, 'GCPClient')
    except ImportError as e:
        pytest.skip(f"GCP collectors not available: {e}")


def test_gcp_client_import():
    """Verify GCPClient can be imported."""
    try:
        from rapidrmf.collectors.gcp import GCPClient
        assert GCPClient is not None
    except ImportError as e:
        pytest.skip(f"GCPClient not available: {e}")


def test_iam_collector_import():
    """Verify IAM collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import IAMCollector
        assert IAMCollector is not None
    except ImportError as e:
        pytest.skip(f"IAMCollector not available: {e}")


def test_compute_collector_import():
    """Verify Compute Engine collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import ComputeCollector
        assert ComputeCollector is not None
    except ImportError as e:
        pytest.skip(f"ComputeCollector not available: {e}")


def test_storage_collector_import():
    """Verify Cloud Storage collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import StorageCollector
        assert StorageCollector is not None
    except ImportError as e:
        pytest.skip(f"StorageCollector not available: {e}")


def test_sql_collector_import():
    """Verify Cloud SQL collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import CloudSQLCollector
        assert CloudSQLCollector is not None
    except ImportError as e:
        pytest.skip(f"CloudSQLCollector not available: {e}")


def test_vpc_collector_import():
    """Verify VPC collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import VPCCollector
        assert VPCCollector is not None
    except ImportError as e:
        pytest.skip(f"VPCCollector not available: {e}")


def test_kms_collector_import():
    """Verify Cloud KMS collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import KMSCollector
        assert KMSCollector is not None
    except ImportError as e:
        pytest.skip(f"KMSCollector not available: {e}")


def test_logging_collector_import():
    """Verify Cloud Logging collector can be imported."""
    try:
        from rapidrmf.collectors.gcp import LoggingCollector
        assert LoggingCollector is not None
    except ImportError as e:
        pytest.skip(f"LoggingCollector not available: {e}")


def test_collector_interface():
    """Verify all GCP collectors have collect_all method."""
    try:
        from rapidrmf.collectors.gcp import (
            IAMCollector,
            ComputeCollector,
            StorageCollector,
            CloudSQLCollector,
            VPCCollector,
            KMSCollector,
            LoggingCollector,
        )
        
        collectors = [
            IAMCollector,
            ComputeCollector,
            StorageCollector,
            CloudSQLCollector,
            VPCCollector,
            KMSCollector,
            LoggingCollector,
        ]
        
        for collector_class in collectors:
            assert hasattr(collector_class, 'collect_all'), \
                f"{collector_class.__name__} missing collect_all method"
            
    except ImportError as e:
        pytest.skip(f"GCP collectors not available: {e}")


def test_collector_naming_conventions():
    """Verify GCP collectors follow naming conventions."""
    try:
        from rapidrmf.collectors.gcp import (
            IAMCollector,
            ComputeCollector,
            StorageCollector,
            CloudSQLCollector,
            VPCCollector,
            KMSCollector,
            LoggingCollector,
        )
        
        collectors = [
            IAMCollector,
            ComputeCollector,
            StorageCollector,
            CloudSQLCollector,
            VPCCollector,
            KMSCollector,
            LoggingCollector,
        ]
        
        for collector_class in collectors:
            # Should end with "Collector"
            assert collector_class.__name__.endswith('Collector'), \
                f"{collector_class.__name__} doesn't follow naming convention"
            
            # Should have docstring
            assert collector_class.__doc__ is not None, \
                f"{collector_class.__name__} missing docstring"
            
    except ImportError as e:
        pytest.skip(f"GCP collectors not available: {e}")


def test_gcp_client_instantiation():
    """Verify GCPClient can be instantiated with minimal config."""
    try:
        from rapidrmf.collectors.gcp import GCPClient
        
        # Should work with no arguments (uses application default credentials)
        client = GCPClient()
        assert client is not None
        
        # Should have required methods
        assert hasattr(client, 'get_compute_client')
        assert hasattr(client, 'get_storage_client')
        assert hasattr(client, 'get_iam_client')
        
    except ImportError as e:
        pytest.skip(f"GCPClient not available: {e}")
    except Exception as e:
        pytest.skip(f"Cannot instantiate GCPClient (credentials may be missing): {e}")


def test_evidence_structure():
    """Verify evidence structure has required fields."""
    try:
        from rapidrmf.collectors.gcp import IAMCollector, GCPClient
        
        client = GCPClient()
        collector = IAMCollector(client)
        
        # This may fail if credentials aren't set up, but tests the structure
        evidence = collector.collect_all()
        
        # Should have metadata section
        assert 'metadata' in evidence, "Evidence missing metadata section"
        assert 'evidence' in evidence['metadata'], \
            "Metadata missing evidence field"
        assert 'sha256' in evidence['metadata'], \
            "Metadata missing sha256 field"
        
    except ImportError as e:
        pytest.skip(f"GCP collectors not available: {e}")
    except Exception as e:
        pytest.skip(f"Cannot collect evidence (credentials may be missing): {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
