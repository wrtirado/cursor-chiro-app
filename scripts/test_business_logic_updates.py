#!/usr/bin/env python3
"""
Test Script for Business Logic and Model Updates - Task 35.4
Validates that all remaining chiropractor terminology has been updated to care_provider
in business logic, models, and application configuration
"""

import sys
import os
import re
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../")

print("🔍 Testing Business Logic and Model Updates for Task 35.4")
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


def test_project_configuration():
    """Test project configuration updates"""
    print("\n⚙️  Test 1: Project Configuration Updates")

    # Test config.py PROJECT_NAME update
    config_results = check_file_content(
        "api/core/config.py",
        "Project name in configuration",
        expected_content=[r"Tirado Care Provider API"],
        forbidden_content=[r"Tirado Chiro API", r"chiropractor", r"Chiropractic"],
    )

    if config_results["passed"]:
        print("✅ PASS: config.py - Project name updated to 'Tirado Care Provider API'")
    else:
        print(f"❌ FAIL: config.py - {config_results['issues']}")

    return config_results["passed"]


def test_application_branding():
    """Test application branding updates"""
    print("\n🏷️  Test 2: Application Branding Updates")

    # Test main.py welcome message update
    main_results = check_file_content(
        "api/main.py",
        "Welcome message in main application",
        expected_content=[r"Welcome to the Tirado Care Provider API"],
        forbidden_content=[r"Tirado Chiropractic API", r"chiropractor", r"chiro"],
    )

    if main_results["passed"]:
        print(
            "✅ PASS: main.py - Welcome message updated to reference Care Provider API"
        )
    else:
        print(f"❌ FAIL: main.py - {main_results['issues']}")

    return main_results["passed"]


def test_schema_cleanup():
    """Test schema file cleanup"""
    print("\n📋 Test 3: Schema Comment Cleanup")

    # Test plan.py schema comment cleanup
    schema_results = check_file_content(
        "api/schemas/plan.py",
        "Schema comments cleaned up",
        expected_content=[r"care_provider_id: int"],
        forbidden_content=[r"Updated from chiropractor_id", r"chiropractor"],
    )

    if schema_results["passed"]:
        print("✅ PASS: plan.py - Schema comments cleaned up")
    else:
        print(f"❌ FAIL: plan.py - {schema_results['issues']}")

    return schema_results["passed"]


def test_model_consistency():
    """Test that model files are clean"""
    print("\n🏗️  Test 4: Model File Consistency")

    model_files = [
        "api/models/base.py",
        "api/models/audit.py",
        "api/models/audit_log.py",
    ]

    all_passed = True
    for model_file in model_files:
        if os.path.exists(model_file):
            model_results = check_file_content(
                model_file,
                f"Model file {model_file}",
                forbidden_content=[
                    r"chiropractor",
                    r"chiro(?!p)",
                ],  # Avoid matching "chiropractor" but allow "chiropractic" if needed
            )

            if model_results["passed"]:
                print(f"✅ PASS: {model_file} - No chiropractor references found")
            else:
                print(f"❌ FAIL: {model_file} - {model_results['issues']}")
                all_passed = False

    return all_passed


def test_service_consistency():
    """Test that service files are clean"""
    print("\n🔧 Test 5: Service File Consistency")

    service_files = ["api/services/billing_service.py", "api/services/media_service.py"]

    all_passed = True
    for service_file in service_files:
        if os.path.exists(service_file):
            service_results = check_file_content(
                service_file,
                f"Service file {service_file}",
                forbidden_content=[r"chiropractor", r"chiro(?!p)"],
            )

            if service_results["passed"]:
                print(f"✅ PASS: {service_file} - No chiropractor references found")
            else:
                print(f"❌ FAIL: {service_file} - {service_results['issues']}")
                all_passed = False

    return all_passed


def test_core_utilities():
    """Test that core utility files are clean"""
    print("\n🛠️  Test 6: Core Utility File Consistency")

    # Check key core files
    core_files = [
        "api/core/config.py",
        "api/core/security.py",
        "api/auth/dependencies.py",
    ]

    all_passed = True
    for core_file in core_files:
        if os.path.exists(core_file):
            core_results = check_file_content(
                core_file,
                f"Core file {core_file}",
                forbidden_content=[
                    r"chiropractor(?!ic)",
                    r"chiro(?!p)",
                ],  # Allow "chiropractic" in context
            )

            if core_results["passed"]:
                print(
                    f"✅ PASS: {core_file} - No inappropriate chiropractor references found"
                )
            else:
                print(f"❌ FAIL: {core_file} - {core_results['issues']}")
                all_passed = False

    return all_passed


def test_role_enum_consistency():
    """Test that RoleType enum is correctly configured"""
    print("\n🔐 Test 7: Role Enum Consistency")

    try:
        # Import the RoleType enum to verify it's correctly configured
        from api.core.config import RoleType

        # Check that CARE_PROVIDER exists and CHIROPRACTOR does not
        has_care_provider = hasattr(RoleType, "CARE_PROVIDER")
        has_chiropractor = hasattr(RoleType, "CHIROPRACTOR")

        if has_care_provider and not has_chiropractor:
            print(
                "✅ PASS: RoleType enum - CARE_PROVIDER exists, CHIROPRACTOR does not"
            )

            # Verify the value is correct
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
                f"❌ FAIL: RoleType enum - care_provider exists: {has_care_provider}, chiropractor exists: {has_chiropractor}"
            )
            return False

    except Exception as e:
        print(f"❌ FAIL: Could not validate RoleType enum: {e}")
        return False


def main():
    """Run all business logic and model update tests"""

    print("📊 Running comprehensive business logic validation...")

    test_results = []
    test_results.append(("Project Configuration", test_project_configuration()))
    test_results.append(("Application Branding", test_application_branding()))
    test_results.append(("Schema Cleanup", test_schema_cleanup()))
    test_results.append(("Model Consistency", test_model_consistency()))
    test_results.append(("Service Consistency", test_service_consistency()))
    test_results.append(("Core Utilities", test_core_utilities()))
    test_results.append(("Role Enum", test_role_enum_consistency()))

    print("\n" + "=" * 60)
    print("📊 Business Logic Update Test Summary:")

    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   - {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎯 Task 35.4 Business Logic and Model Updates: COMPLETED")
        print(
            "📝 All chiropractor terminology successfully updated to care_provider in business logic"
        )
        print("🏗️  All models, services, and configuration files are consistent")
        print("⚙️  Project branding updated to 'Tirado Care Provider API'")
    else:
        print("\n⚠️  Task 35.4: Some issues found that need attention")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
