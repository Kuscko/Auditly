#!/usr/bin/env python3
"""Test the DRY refactor of common finalize_evidence."""

from auditly.collectors.common import finalize_evidence

# Test the shared finalize_evidence helper
test_data = {"users": [{"name": "alice"}, {"name": "bob"}]}
evidence = finalize_evidence(
    test_data, collector="test-collector", account_id="123456789", region="us-east-1"
)

print("✓ finalize_evidence works:")
print(f'  - metadata keys: {list(evidence["metadata"].keys())}')
print(f'  - sha256: {evidence["metadata"]["sha256"][:16]}...')
print(f'  - collector: {evidence["metadata"]["collector"]}')
print(f'  - account_id: {evidence["metadata"]["account_id"]}')
print(f'  - region: {evidence["metadata"]["region"]}')

# Verify data is preserved
assert evidence["users"] == test_data["users"]
print("✓ Data preserved correctly")
