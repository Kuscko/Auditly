"""Integration tests for AWS collectors.

Simple tests to verify collector structure, instantiation, and interfaces.
Full collector behavior testing would require live AWS or complex moto mocking.
"""

import pytest
from unittest.mock import Mock

from rapidrmf.collectors.aws import (
    AWSClient,
    IAMCollector,
    EC2Collector,
    S3Collector,
    CloudTrailCollector,
    VPCCollector,
    RDSCollector,
    KMSCollector,
)


class TestCollectorStructure:
    """Test that all AWS collectors have proper structure and interfaces."""

    def test_all_collectors_can_be_imported(self):
        """Verify all expected collectors can be imported."""
        assert IAMCollector is not None
        assert EC2Collector is not None
        assert S3Collector is not None
        assert CloudTrailCollector is not None
        assert VPCCollector is not None
        assert RDSCollector is not None
        assert KMSCollector is not None

    def test_all_collectors_have_collect_all_method(self):
        """Verify all collectors implement collect_all() method."""
        collectors = [
            IAMCollector,
            EC2Collector,
            S3Collector,
            CloudTrailCollector,
            VPCCollector,
            RDSCollector,
            KMSCollector,
        ]
        
        for CollectorClass in collectors:
            mock_client = Mock(spec=AWSClient)
            collector = CollectorClass(mock_client)
            
            assert hasattr(collector, "collect_all"), (
                f"{CollectorClass.__name__} missing collect_all() method"
            )
            assert callable(getattr(collector, "collect_all"))

    def test_aws_client_has_required_methods(self):
        """Verify AWSClient has required interface methods."""
        required_methods = ["get_client", "get_account_id"]
        
        for method in required_methods:
            assert hasattr(AWSClient, method), f"AWSClient missing {method}() method"

    def test_collectors_accept_client_parameter(self):
        """Verify all collectors can be instantiated with a client."""
        collectors = [
            IAMCollector,
            EC2Collector,
            S3Collector,
            CloudTrailCollector,
            VPCCollector,
            RDSCollector,
            KMSCollector,
        ]
        
        mock_client = Mock(spec=AWSClient)
        
        for CollectorClass in collectors:
            try:
                collector = CollectorClass(mock_client)
                assert collector is not None
            except Exception as e:
                pytest.fail(
                    f"{CollectorClass.__name__} failed instantiation with client: {e}"
                )


class TestCollectorNaming:
    """Test that collectors follow expected naming conventions."""

    def test_collector_class_names(self):
        """Verify collectors have proper naming (ServiceCollector pattern)."""
        expected_collectors = [
            ("IAMCollector", IAMCollector),
            ("EC2Collector", EC2Collector),
            ("S3Collector", S3Collector),
            ("CloudTrailCollector", CloudTrailCollector),
            ("VPCCollector", VPCCollector),
            ("RDSCollector", RDSCollector),
            ("KMSCollector", KMSCollector),
        ]
        
        for expected_name, collector_class in expected_collectors:
            assert collector_class.__name__ == expected_name, (
                f"Collector name mismatch: expected {expected_name}, "
                f"got {collector_class.__name__}"
            )

    def test_collector_docstrings_exist(self):
        """Verify all collectors have docstrings."""
        collectors = [
            IAMCollector,
            EC2Collector,
            S3Collector,
            CloudTrailCollector,
            VPCCollector,
            RDSCollector,
            KMSCollector,
        ]
        
        for CollectorClass in collectors:
            assert CollectorClass.__doc__ is not None, (
                f"{CollectorClass.__name__} missing docstring"
            )
            assert len(CollectorClass.__doc__.strip()) > 0


class TestCLIIntegration:
    """Test that collectors integrate with CLI expectations."""

    def test_cli_can_access_all_collectors(self):
        """Verify CLI can access all collector classes."""
        try:
            from rapidrmf.collectors.aws import (
                IAMCollector,
                EC2Collector,
                S3Collector,
                CloudTrailCollector,
                VPCCollector,
                RDSCollector,
                KMSCollector,
            )
            
            # Verify all imports work
            assert IAMCollector is not None
            assert EC2Collector is not None
            assert S3Collector is not None
            assert CloudTrailCollector is not None
            assert VPCCollector is not None
            assert RDSCollector is not None
            assert KMSCollector is not None
            
        except ImportError as e:
            pytest.fail(f"CLI cannot import collectors: {e}")


class TestEvidenceFormat:
    """Test that evidence format expectations are met."""

    def test_evidence_manifest_can_be_created(self):
        """Test that evidence manifests can be created with AWS evidence."""
        from rapidrmf.evidence import ArtifactRecord, EvidenceManifest
        
        # Create sample AWS artifacts
        artifacts = [
            ArtifactRecord(
                key="evidence/prod/aws-iam-123456789012.json",
                filename="aws-iam-123456789012.json",
                sha256="abc123",
                size=1024,
                metadata={"kind": "aws-iam", "service": "iam", "account_id": "123456789012"},
            ),
            ArtifactRecord(
                key="evidence/prod/aws-ec2-123456789012.json",
                filename="aws-ec2-123456789012.json",
                sha256="def456",
                size=2048,
                metadata={"kind": "aws-ec2", "service": "ec2", "account_id": "123456789012"},
            ),
        ]
        
        manifest = EvidenceManifest(
            version="1.0",
            environment="prod",
            created_at=1234567890.0,
            artifacts=artifacts,
            overall_hash=None,
            notes="AWS evidence collection",
        )
        
        manifest.compute_overall_hash()
        
        assert manifest.environment == "prod"
        assert len(manifest.artifacts) == 2
        assert manifest.overall_hash is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
