#!/usr/bin/env python3
"""
Test Script for API Endpoints and Contracts - Task 35.5
Validates that all API endpoint paths, request/response payloads, and documentation
use 'care_provider' instead of 'chiropractor'
"""

import sys
import os
import re
import json
from typing import Dict, List, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../")

print("🔍 Testing API Endpoints and Contracts for Task 35.5")
print("=" * 60)


def check_file_content(
    filepath, description, expected_content=None, forbidden_content=None
):
    """Check a file for expected and forbidden content"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        results = {
            "file": filepath,
            "description": description,
            "passed": True,
            "issues": [],
        }

        if expected_content:
            for pattern in expected_content:
                if not re.search(pattern, content, re.IGNORECASE):
                    results["passed"] = False
                    results["issues"].append(f"Missing expected: {pattern}")

        if forbidden_content:
            for pattern in forbidden_content:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    results["passed"] = False
                    results["issues"].append(f"Found forbidden: {matches}")

        return results
    except Exception as e:
        return {
            "file": filepath,
            "description": description,
            "passed": False,
            "issues": [str(e)],
        }


def test_openapi_configuration():
    """Test OpenAPI configuration and documentation"""
    print("\n📖 Test 1: OpenAPI Configuration")

    # Test that the main app uses the updated PROJECT_NAME
    main_results = check_file_content(
        "api/main.py",
        "FastAPI app configuration",
        expected_content=[r"title=settings\.PROJECT_NAME"],
        forbidden_content=[r"chiropractor", r"chiropractic"],
    )

    if main_results["passed"]:
        print(
            "✅ PASS: main.py - FastAPI app correctly configured with updated PROJECT_NAME"
        )
    else:
        print(f"❌ FAIL: main.py - {main_results['issues']}")

    # Test that config has the correct PROJECT_NAME
    config_results = check_file_content(
        "api/core/config.py",
        "Project configuration",
        expected_content=[r"Tirado Care Provider API"],
        forbidden_content=[r"chiropractor", r"chiropractic"],
    )

    if config_results["passed"]:
        print(
            "✅ PASS: config.py - PROJECT_NAME correctly set to 'Tirado Care Provider API'"
        )
    else:
        print(f"❌ FAIL: config.py - {config_results['issues']}")

    return main_results["passed"] and config_results["passed"]


def test_schema_definitions():
    """Test API schema definitions"""
    print("\n📋 Test 2: API Schema Definitions")

    schema_files = [
        "api/schemas/plan.py",
        "api/schemas/user.py",
        "api/schemas/media.py",
        "api/schemas/role.py",
        "api/schemas/branding.py",
        "api/schemas/office.py",
        "api/schemas/company.py",
    ]

    all_passed = True
    for schema_file in schema_files:
        if os.path.exists(schema_file):
            schema_results = check_file_content(
                schema_file,
                f"Schema definitions in {schema_file}",
                expected_content=(
                    [r"care_provider_id"] if "plan.py" in schema_file else None
                ),
                forbidden_content=[
                    r"chiropractor_id",
                    r"chiropractor",
                    r"chiropractic care application",
                ],
            )

            if schema_results["passed"]:
                print(f"✅ PASS: {schema_file} - Schema definitions are clean")
            else:
                print(f"❌ FAIL: {schema_file} - {schema_results['issues']}")
                all_passed = False

    return all_passed


def test_api_router_endpoints():
    """Test API router endpoint definitions"""
    print("\n🛣️  Test 3: API Router Endpoints")

    router_files = [
        "api/auth/router.py",
        "api/plans/router.py",
        "api/users/router.py",
        "api/media/router.py",
        "api/progress/router.py",
        "api/branding/router.py",
        "api/companies/router.py",
        "api/offices/router.py",
        "api/roles/router.py",
    ]

    all_passed = True
    for router_file in router_files:
        if os.path.exists(router_file):
            router_results = check_file_content(
                router_file,
                f"Router endpoints in {router_file}",
                forbidden_content=[
                    r"chiropractor_id",
                    r"get_plans_by_chiropractor",
                    r"associate_user_with_chiro",
                    r"chiropractor",
                    r"CHIROPRACTOR",
                ],
            )

            if router_results["passed"]:
                print(f"✅ PASS: {router_file} - Router endpoints are clean")
            else:
                print(f"❌ FAIL: {router_file} - {router_results['issues']}")
                all_passed = False

    return all_passed


def test_crud_operations():
    """Test CRUD operation definitions"""
    print("\n🔧 Test 4: CRUD Operation Definitions")

    crud_files = ["api/crud/crud_plan.py", "api/crud/crud_user.py"]

    all_passed = True
    for crud_file in crud_files:
        if os.path.exists(crud_file):
            crud_results = check_file_content(
                crud_file,
                f"CRUD operations in {crud_file}",
                expected_content=(
                    [r"get_plans_by_care_provider"]
                    if "crud_plan.py" in crud_file
                    else None
                ),
                forbidden_content=[
                    r"get_plans_by_chiropractor",
                    r"associate_user_with_chiro",
                    r"chiropractor_id",
                    r"temp_chiro_role_id",
                ],
            )

            if crud_results["passed"]:
                print(f"✅ PASS: {crud_file} - CRUD operations updated correctly")
            else:
                print(f"❌ FAIL: {crud_file} - {crud_results['issues']}")
                all_passed = False

    return all_passed


def test_response_models():
    """Test that response models use correct field names"""
    print("\n📄 Test 5: Response Model Field Names")

    # Test key files that define response models
    model_files = ["api/schemas/plan.py"]

    all_passed = True
    for model_file in model_files:
        if os.path.exists(model_file):
            model_results = check_file_content(
                model_file,
                f"Response model fields in {model_file}",
                expected_content=[r"care_provider_id: int"],
                forbidden_content=[r"chiropractor_id: int"],
            )

            if model_results["passed"]:
                print(
                    f"✅ PASS: {model_file} - Response model fields correctly updated"
                )
            else:
                print(f"❌ FAIL: {model_file} - {model_results['issues']}")
                all_passed = False

    return all_passed


def test_api_documentation():
    """Test API documentation and docstrings"""
    print("\n📚 Test 6: API Documentation")

    # Check for any remaining documentation references
    doc_files = [
        "api/main.py",
        "api/auth/router.py",
        "api/plans/router.py",
        "api/media/router.py",
    ]

    all_passed = True
    for doc_file in doc_files:
        if os.path.exists(doc_file):
            doc_results = check_file_content(
                doc_file,
                f"API documentation in {doc_file}",
                forbidden_content=[
                    r"chiropractor",
                    r"Chiropractor",
                    r"chiropractic.*api",
                    r"Chiropractic.*API",
                ],
            )

            if doc_results["passed"]:
                print(f"✅ PASS: {doc_file} - API documentation is clean")
            else:
                print(f"❌ FAIL: {doc_file} - {doc_results['issues']}")
                all_passed = False

    return all_passed


def test_role_enums_and_constants():
    """Test role enums and constants used in API"""
    print("\n🔐 Test 7: Role Enums and Constants")

    try:
        # Import and verify role configuration
        from api.core.config import RoleType

        # Verify CARE_PROVIDER exists and is used correctly
        has_care_provider = hasattr(RoleType, "CARE_PROVIDER")
        has_chiropractor = hasattr(RoleType, "CHIROPRACTOR")

        if has_care_provider and not has_chiropractor:
            print("✅ PASS: RoleType enum - CARE_PROVIDER exists, CHIROPRACTOR removed")

            # Check that the value is correct
            if RoleType.CARE_PROVIDER.value == "care_provider":
                print("✅ PASS: RoleType.CARE_PROVIDER value is 'care_provider'")
                return True
            else:
                print(
                    f"❌ FAIL: RoleType.CARE_PROVIDER value is '{RoleType.CARE_PROVIDER.value}', expected 'care_provider'"
                )
                return False
        else:
            print(
                f"❌ FAIL: RoleType enum - care_provider: {has_care_provider}, chiropractor: {has_chiropractor}"
            )
            return False

    except Exception as e:
        print(f"❌ FAIL: Could not validate RoleType enum: {e}")
        return False


def test_endpoint_tags():
    """Test that endpoint tags are appropriate"""
    print("\n🏷️  Test 8: Endpoint Tags")

    # Check main.py for router inclusions with tags
    main_results = check_file_content(
        "api/main.py",
        "Router tag configuration",
        expected_content=[
            r'tags=\["auth"\]',
            r'tags=\["plans"\]',
            r'tags=\["users"\]',
            r'tags=\["media"\]',
        ],
        forbidden_content=[r'tags=\["chiropractor.*"\]', r'tags=\["chiro.*"\]'],
    )

    if main_results["passed"]:
        print("✅ PASS: main.py - Router tags are appropriate and clean")
    else:
        print(f"❌ FAIL: main.py - {main_results['issues']}")

    return main_results["passed"]


def main():
    """Run all API endpoint and contract tests"""

    print("📊 Running comprehensive API endpoints and contracts validation...")

    test_results = []
    test_results.append(("OpenAPI Configuration", test_openapi_configuration()))
    test_results.append(("Schema Definitions", test_schema_definitions()))
    test_results.append(("API Router Endpoints", test_api_router_endpoints()))
    test_results.append(("CRUD Operations", test_crud_operations()))
    test_results.append(("Response Models", test_response_models()))
    test_results.append(("API Documentation", test_api_documentation()))
    test_results.append(("Role Enums", test_role_enums_and_constants()))
    test_results.append(("Endpoint Tags", test_endpoint_tags()))

    print("\n" + "=" * 60)
    print("📊 API Endpoints and Contracts Test Summary:")

    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   - {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎯 Task 35.5 API Endpoints and Contracts: COMPLETED")
        print("📝 All API endpoints using care_provider terminology")
        print("🔧 All CRUD operations updated correctly")
        print("📋 All schema definitions are consistent")
        print("📖 OpenAPI documentation reflects new terminology")
        print("🔐 Role enums correctly configured")
    else:
        print("\n⚠️  Task 35.5: Some issues found that need attention")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
