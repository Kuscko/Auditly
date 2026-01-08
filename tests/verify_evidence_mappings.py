#!/usr/bin/env python3
"""
Verify that test evidence mappings are correct and match validator requirements.
This ensures we're not creating false positives in our tests.
"""

import json
from pathlib import Path
from typing import Dict, Set
from rapidrmf.validators import FAMILY_PATTERNS, CONTROL_REQUIREMENTS


def load_test_evidence_data():
    """Load test evidence data with family mappings."""
    test_data_path = Path(__file__).parent / "test_evidence_data.json"
    with open(test_data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_evidence_types_for_family(family: str, test_data: Dict) -> Set[str]:
    """Get all evidence types that satisfy a given family."""
    evidence_types = set()
    
    for category, artifacts_dict in test_data['evidence_artifacts'].items():
        for evidence_type, evidence_info in artifacts_dict.items():
            satisfies_families = set(evidence_info.get('satisfies_families', []))
            if family in satisfies_families:
                evidence_types.add(evidence_type)
    
    return evidence_types


def verify_family_mappings():
    """Verify that test data provides evidence required by validators."""
    print("=" * 80)
    print("Evidence Mapping Verification")
    print("=" * 80)
    print()
    
    test_data = load_test_evidence_data()
    
    print("Checking each control family pattern against test evidence...")
    print()
    
    all_valid = True
    
    for family_code, pattern in FAMILY_PATTERNS.items():
        print(f"Family {family_code}: {pattern.description_template}")
        print(f"  Pattern requires:")
        
        # Get evidence types from test data for this family
        available_evidence = get_evidence_types_for_family(family_code, test_data)
        
        # Check required_any
        if pattern.required_any:
            print(f"    required_any: {pattern.required_any}")
            found_any = [e for e in pattern.required_any if e in available_evidence]
            if found_any:
                print(f"      ✅ Test data provides: {found_any}")
            else:
                print(f"      ❌ NO MATCH in test data!")
                all_valid = False
        
        # Check required_all
        if pattern.required_all:
            print(f"    required_all: {pattern.required_all}")
            found_all = [e for e in pattern.required_all if e in available_evidence]
            missing = [e for e in pattern.required_all if e not in available_evidence]
            if not missing:
                print(f"      ✅ Test data provides: {found_all}")
            else:
                print(f"      ❌ MISSING in test data: {missing}")
                all_valid = False
        
        print(f"  Total test evidence types for {family_code}: {len(available_evidence)}")
        print()
    
    # Check specific control overrides
    print("=" * 80)
    print("Checking specific control requirements...")
    print("(These inherit family evidence plus have specific requirements)")
    print()
    
    for control_id, requirement in CONTROL_REQUIREMENTS.items():
        family = control_id.split('-')[0].upper()  # Ensure uppercase
        available_evidence = get_evidence_types_for_family(family, test_data)
        
        print(f"{control_id}: {requirement.description}")
        print(f"  Family {family} provides {len(available_evidence)} evidence types")
        
        # Check required_any
        if requirement.required_any:
            found_any = [e for e in requirement.required_any if e in available_evidence]
            if found_any:
                print(f"  ✅ required_any matched: {found_any}")
            else:
                print(f"  ⚠️  required_any needs: {requirement.required_any}")
                print(f"      (Control will use family evidence: {list(available_evidence)[:3]}...)")
                # Not marking as invalid because family evidence will be used
        
        # Check required_all
        if requirement.required_all:
            missing = [e for e in requirement.required_all if e not in available_evidence]
            if not missing:
                print(f"  ✅ required_all satisfied: {requirement.required_all}")
            else:
                print(f"  ⚠️  required_all needs: {missing}")
                print(f"      (Control will use family evidence: {list(available_evidence)[:3]}...)")
                # Not marking as invalid because family evidence will be used
        
        print()
    
    # Summary
    print("=" * 80)
    if all_valid:
        print("✅ All evidence mappings are VALID")
        print("   Test evidence correctly satisfies validator requirements")
        print("   No false positives detected")
    else:
        print("❌ Some evidence mappings are INVALID")
        print("   Test data does not match validator requirements")
        print("   Results may include false positives or false negatives")
    print("=" * 80)
    
    return all_valid


def show_evidence_summary():
    """Show summary of all evidence types."""
    print("\n" + "=" * 80)
    print("Evidence Type Summary")
    print("=" * 80)
    print()
    
    test_data = load_test_evidence_data()
    
    # Count by family
    family_counts = {}
    all_evidence = {}
    
    for category, artifacts_dict in test_data['evidence_artifacts'].items():
        for evidence_type, evidence_info in artifacts_dict.items():
            all_evidence[evidence_type] = evidence_info
            for family in evidence_info.get('satisfies_families', []):
                if family not in family_counts:
                    family_counts[family] = []
                family_counts[family].append(evidence_type)
    
    print(f"Total evidence types: {len(all_evidence)}")
    print()
    print("Evidence types per family:")
    for family in sorted(family_counts.keys()):
        print(f"  {family}: {len(family_counts[family])} types")
    
    print()


if __name__ == "__main__":
    show_evidence_summary()
    valid = verify_family_mappings()
    exit(0 if valid else 1)
