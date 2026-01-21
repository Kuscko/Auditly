"""Tests for performance optimization: caching, parallel collection, incremental validation."""

import asyncio

import pytest

from rapidrmf.performance import (
    EvidenceDependencyGraph,
    IncrementalValidator,
    ParallelCollector,
    PerformanceMetrics,
    ValidationResultCache,
    incremental_validator,
    parallel_collector,
    performance_metrics,
    validation_cache,
)


class TestValidationResultCache:
    """Test validation result caching."""

    def test_cache_set_get(self):
        """Test basic cache set and get."""
        cache = ValidationResultCache()

        cache.set("control-ac-2", {"passed": True})
        result = cache.get("control-ac-2")

        assert result is not None
        assert result["passed"] is True

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = ValidationResultCache()

        result = cache.get("nonexistent-key")
        assert result is None

    def test_cache_expiration(self):
        """Test cache expiration by TTL."""
        cache = ValidationResultCache()

        # Set with 0 second TTL (immediate expiration)
        cache.set("control-ac-3", {"passed": True}, ttl=0)

        # Get immediately (should be expired)
        result = cache.get("control-ac-3")
        assert result is None

    def test_cache_invalidation_pattern(self):
        """Test invalidating cache by pattern."""
        cache = ValidationResultCache()

        cache.set("control-ac-2", {"data": 1})
        cache.set("control-ac-3", {"data": 2})
        cache.set("control-au-2", {"data": 3})

        # Invalidate AC controls
        cache.invalidate("control-ac-*")

        assert cache.get("control-ac-2") is None
        assert cache.get("control-ac-3") is None
        assert cache.get("control-au-2") is not None

    def test_cache_invalidate_control(self):
        """Test invalidating cache for specific control."""
        cache = ValidationResultCache()

        cache.set("system-123-control-ac-2", {"data": 1})
        cache.set("system-123-control-ac-3", {"data": 2})

        cache.invalidate_control("AC-2")

        assert cache.get("system-123-control-ac-2") is None
        assert cache.get("system-123-control-ac-3") is not None

    def test_cache_invalidate_system(self):
        """Test invalidating cache for specific system."""
        cache = ValidationResultCache()

        cache.set("system-123-control-ac-2", {"data": 1})
        cache.set("system-456-control-ac-2", {"data": 2})

        cache.invalidate_system(123)

        assert cache.get("system-123-control-ac-2") is None
        assert cache.get("system-456-control-ac-2") is not None

    def test_cache_key_generation(self):
        """Test cache key generation from parts."""
        cache = ValidationResultCache()

        key = cache.make_key("system", "123", "control", "AC-2")
        assert key == "system-123-control-ac-2"

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = ValidationResultCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2", ttl=0)  # Will be expired

        stats = cache.stats()
        assert stats["entries"] == 2
        assert stats["active"] >= 1

    def test_cache_clear_all(self):
        """Test clearing all cache entries."""
        cache = ValidationResultCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate(None)  # None pattern = clear all

        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestEvidenceDependencyGraph:
    """Test evidence dependency tracking."""

    def test_add_control_evidence_dependency(self):
        """Test registering evidence types for controls."""
        graph = EvidenceDependencyGraph()

        graph.add_dependency("AC-2", ["aws_iam_users", "aws_iam_policies"])

        evidence = graph.get_evidence_for_control("AC-2")
        assert "aws_iam_users" in evidence
        assert "aws_iam_policies" in evidence

    def test_get_affected_controls(self):
        """Test finding controls affected by evidence changes."""
        graph = EvidenceDependencyGraph()

        graph.add_dependency("AC-2", ["aws_iam_users", "aws_iam_policies"])
        graph.add_dependency("AC-3", ["aws_iam_policies"])
        graph.add_dependency("AU-2", ["aws_cloudtrail"])

        # If AWS IAM users change, only AC-2 is affected
        affected = graph.get_affected_controls(["aws_iam_users"])
        assert "AC-2" in affected
        assert "AU-2" not in affected

        # If IAM policies change, AC-2 and AC-3 are affected
        affected = graph.get_affected_controls(["aws_iam_policies"])
        assert "AC-2" in affected
        assert "AC-3" in affected

    def test_no_evidence_no_affected(self):
        """Test that unknown evidence returns no affected controls."""
        graph = EvidenceDependencyGraph()

        graph.add_dependency("AC-2", ["aws_iam_users"])

        affected = graph.get_affected_controls(["unknown_evidence"])
        assert len(affected) == 0

    def test_multiple_evidence_multiple_affected(self):
        """Test multiple evidence types affecting multiple controls."""
        graph = EvidenceDependencyGraph()

        graph.add_dependency("AC-1", ["a", "b"])
        graph.add_dependency("AC-2", ["b", "c"])
        graph.add_dependency("AC-3", ["c", "d"])

        affected = graph.get_affected_controls(["b", "c"])
        assert "AC-1" in affected
        assert "AC-2" in affected
        assert "AC-3" in affected


class TestIncrementalValidator:
    """Test incremental validation."""

    def test_all_controls_on_first_run(self):
        """Test that all controls need validation on first run."""
        validator = IncrementalValidator()

        all_controls = ["AC-1", "AC-2", "AU-2"]
        to_validate = validator.get_controls_needing_validation(
            all_controls, current_evidence={}, previous_evidence=None
        )

        assert set(to_validate) == set(all_controls)

    def test_no_controls_on_no_changes(self):
        """Test no validation needed when evidence unchanged."""
        validator = IncrementalValidator()

        evidence = {"aws_iam": {"users": ["admin"]}}

        to_validate = validator.get_controls_needing_validation(
            ["AC-1", "AC-2"], current_evidence=evidence, previous_evidence=evidence
        )

        assert len(to_validate) == 0

    def test_affected_controls_on_new_evidence(self):
        """Test validation of affected controls when new evidence added."""
        validator = IncrementalValidator()
        validator.register_evidence_types("AC-2", ["aws_iam_users"])
        validator.register_evidence_types("AU-2", ["aws_cloudtrail"])

        previous = {"aws_iam_users": []}
        current = {"aws_iam_users": ["new_user"]}

        to_validate = validator.get_controls_needing_validation(
            ["AC-2", "AU-2"], current_evidence=current, previous_evidence=previous
        )

        # AC-2 should be affected (depends on aws_iam_users)
        assert "AC-2" in to_validate

    def test_snapshot_evidence(self):
        """Test capturing evidence snapshot."""
        validator = IncrementalValidator()

        evidence = {"aws": {"users": 5}}
        validator.snapshot_evidence(evidence)

        assert validator.evidence_snapshots["last"] is not None


class TestParallelCollector:
    """Test parallel evidence collection."""

    @pytest.mark.asyncio
    async def test_parallel_collection_basic(self):
        """Test basic parallel collection."""
        collector = ParallelCollector(max_concurrent=2)

        async def mock_collector_1():
            await asyncio.sleep(0.01)
            return {"service": "aws", "data": "evidence1"}

        async def mock_collector_2():
            await asyncio.sleep(0.01)
            return {"service": "gcp", "data": "evidence2"}

        collectors = {
            "aws": mock_collector_1(),
            "gcp": mock_collector_2(),
        }

        result = await collector.collect_parallel(collectors)

        assert result["success"] == 2
        assert result["failed"] == 0
        assert "aws" in result["results"]
        assert "gcp" in result["results"]

    @pytest.mark.asyncio
    async def test_parallel_collection_with_failure(self):
        """Test parallel collection with service failure."""
        collector = ParallelCollector(max_concurrent=2)

        async def good_collector():
            return {"data": "success"}

        async def bad_collector():
            raise Exception("Service failed")

        collectors = {
            "good": good_collector(),
            "bad": bad_collector(),
        }

        result = await collector.collect_parallel(collectors)

        assert result["success"] == 1
        assert result["failed"] == 1
        assert "good" in result["results"]
        assert "bad" in result["errors"]

    @pytest.mark.asyncio
    async def test_empty_collectors(self):
        """Test parallel collection with no collectors."""
        collector = ParallelCollector(max_concurrent=2)

        result = await collector.collect_parallel({})

        assert result["success"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Test that concurrency limit is respected."""
        collector = ParallelCollector(max_concurrent=2)
        concurrent_count = 0
        max_concurrent_observed = 0

        async def counting_collector():
            nonlocal concurrent_count, max_concurrent_observed
            concurrent_count += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return {"data": "done"}

        collectors = {f"service_{i}": counting_collector() for i in range(5)}

        result = await collector.collect_parallel(collectors)

        assert result["success"] == 5
        assert max_concurrent_observed <= 2


class TestPerformanceMetrics:
    """Test performance metrics tracking."""

    def test_record_validation(self):
        """Test recording validation metrics."""
        metrics = PerformanceMetrics()

        metrics.record_validation(duration=0.5, cached=False)
        metrics.record_validation(duration=0.05, cached=True)

        assert metrics.metrics["total_validations"] == 2
        assert metrics.metrics["cached_validations"] == 1
        assert metrics.metrics["cache_hit_rate"] == 0.5

    def test_cache_hit_rate_zero(self):
        """Test cache hit rate when no cached validations."""
        metrics = PerformanceMetrics()

        metrics.record_validation(0.5, cached=False)
        metrics.record_validation(0.3, cached=False)

        assert metrics.metrics["cache_hit_rate"] == 0.0

    def test_cache_hit_rate_hundred(self):
        """Test cache hit rate when all validations cached."""
        metrics = PerformanceMetrics()

        metrics.record_validation(0.5, cached=True)
        metrics.record_validation(0.3, cached=True)

        assert metrics.metrics["cache_hit_rate"] == 1.0

    def test_record_collection(self):
        """Test recording collection timings."""
        metrics = PerformanceMetrics()

        metrics.record_collection("aws", 0.5)
        metrics.record_collection("aws", 0.6)
        metrics.record_collection("gcp", 0.3)

        report = metrics.get_report()

        assert "aws" in report["avg_collection_times"]
        assert abs(report["avg_collection_times"]["aws"] - 0.55) < 0.01

    def test_metrics_report(self):
        """Test generating metrics report."""
        metrics = PerformanceMetrics()

        metrics.record_validation(0.5)
        metrics.record_validation(0.3, cached=True)
        metrics.record_parallel_collection()
        metrics.record_incremental_validation()

        report = metrics.get_report()

        assert report["total_validations"] == 2
        assert report["cached_validations"] == 1
        assert report["parallel_collections"] == 1
        assert report["incremental_validations"] == 1
        assert "avg_collection_times" in report


class TestGlobalInstances:
    """Test global module instances."""

    def test_global_validation_cache(self):
        """Test global validation_cache instance."""
        assert validation_cache is not None
        assert isinstance(validation_cache, ValidationResultCache)

    def test_global_incremental_validator(self):
        """Test global incremental_validator instance."""
        assert incremental_validator is not None
        assert isinstance(incremental_validator, IncrementalValidator)

    def test_global_parallel_collector(self):
        """Test global parallel_collector instance."""
        assert parallel_collector is not None
        assert isinstance(parallel_collector, ParallelCollector)

    def test_global_performance_metrics(self):
        """Test global performance_metrics instance."""
        assert performance_metrics is not None
        assert isinstance(performance_metrics, PerformanceMetrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
