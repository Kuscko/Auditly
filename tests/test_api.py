"""Quick test/demo of auditly API endpoints."""

import json

import pytest
import requests

# API base URL
API_URL = "http://localhost:8000"


@pytest.mark.skip(reason="Requires running API server")
def test_health():
    """Test health check endpoint."""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{API_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_collect_terraform():
    """Test collect endpoint with Terraform (mock)."""
    print("\n=== Testing /collect (Terraform) ===")

    # This would need actual files in a real scenario
    request_data = {
        "environment": "production",
        "provider": "terraform",
        "terraform_plan_path": "/tmp/plan.json",  # Would need to exist
    }

    print(f"Request: {json.dumps(request_data, indent=2)}")
    print("Note: This will fail without actual Terraform plan file")

    try:
        response = requests.post(f"{API_URL}/collect", json=request_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Expected error (no plan file): {e}")


def test_validate():
    """Test validate endpoint."""
    print("\n=== Testing /validate ===")

    request_data = {
        "environment": "production",
        "control_ids": ["AC-2", "CM-2", "SC-7"],
        "evidence_dict": {
            "terraform-plan": True,
            "audit-log": True,
            "github-workflow": True,
            "change-request": True,
        },
    }

    print(f"Request: {json.dumps(request_data, indent=2)}")

    try:
        response = requests.post(f"{API_URL}/validate", json=request_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Success: {result.get('success')}")
        print(f"Controls Validated: {result.get('controls_validated')}")
        print(f"Summary: {json.dumps(result.get('summary'), indent=2)}")

        # Show one result detail
        if result.get("results"):
            first_control = list(result["results"].keys())[0]
            print(f"\nExample result for {first_control}:")
            print(json.dumps(result["results"][first_control], indent=2))
    except Exception as e:
        print(f"Error: {e}")


def test_report():
    """Test report endpoint."""
    print("\n=== Testing /report (Engineer Report) ===")

    request_data = {
        "environment": "production",
        "report_type": "engineer",
        "control_ids": ["AC-2", "CM-2"],
        "evidence_dict": {"terraform-plan": True, "audit-log": True},
    }

    print(f"Request: {json.dumps(request_data, indent=2)}")

    try:
        response = requests.post(f"{API_URL}/report", json=request_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Success: {result.get('success')}")
        print(f"Report Type: {result.get('report_type')}")
        print(f"Report Path: {result.get('report_path')}")
        print(f"Summary: {json.dumps(result.get('summary'), indent=2)}")

        if result.get("report_html"):
            html_len = len(result["report_html"])
            print(f"HTML Report Length: {html_len} characters")
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all tests."""
    print("auditly API Test Suite")
    print("=" * 50)
    print("\nMake sure the API server is running:")
    print("  python -m auditly.api")
    print("\nOr:")
    print("  uvicorn auditly.api.app:app --reload")
    print("\n" + "=" * 50)

    try:
        # Test health first
        if not test_health():
            print("\n❌ API server not responding. Start it first:")
            print("   python -m auditly.api")
            return

        print("\n✅ API server is running!")

        # Run other tests
        test_validate()
        test_report()
        # test_collect_terraform()  # Skip by default (needs files)

        print("\n" + "=" * 50)
        print("✅ API tests completed!")
        print("\nNext steps:")
        print("  - Visit http://localhost:8000/docs for Swagger UI")
        print("  - Visit http://localhost:8000/redoc for ReDoc")
        print("  - Try with real config.yaml and evidence files")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server.")
        print("Start the server with: python -m auditly.api")


if __name__ == "__main__":
    main()
