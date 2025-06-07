#!/usr/bin/env python3
"""
Test Script for Business Logic and Domain Models - Task 35.6
Validates that all business logic, domain models, and related service layers
use 'care_provider' terminology throughout.
"""

import sys
import os
import re
import json
from typing import Dict, List, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../")

print("🏗️  Testing Business Logic and Domain Models for Task 35.6")
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


def test_domain_model_relationships():
    """Test domain model relationships use correct terminology"""
    print("\n🏗️  Test 1: Domain Model Relationships")

    # Test TherapyPlan model uses care_provider_id
    model_results = check_file_content(
        "api/models/base.py",
        "TherapyPlan domain model",
        expected_content=[r"care_provider_id = Column"],
        forbidden_content=[r"chiropractor_id = Column", r"chiropractor", r"chiro"],
    )

    if model_results["passed"]:
        print("✅ PASS: base.py - TherapyPlan uses care_provider_id correctly")
    else:
        print(f"❌ FAIL: base.py - {model_results['issues']}")

    return model_results["passed"]


def test_business_logic_validation():
    """Test business validation logic uses correct terminology"""
    print("\n⚖️  Test 2: Business Logic Validation")

    # Check core validation files
    validation_files = [
        "api/core/security_validator.py",
        "api/core/data_minimization.py",
        "api/core/audit_logger.py",
        "api/core/middleware.py",
    ]

    all_passed = True
    for val_file in validation_files:
        if os.path.exists(val_file):
            val_results = check_file_content(
                val_file,
                f"Business validation in {val_file}",
                forbidden_content=[
                    r"chiropractor",
                    r"chiro(?!p)",  # Allow chiropractic if needed
                ],
            )

            if val_results["passed"]:
                print(f"✅ PASS: {val_file} - Business validation logic is clean")
            else:
                print(f"❌ FAIL: {val_file} - {val_results['issues']}")
                all_passed = False

    return all_passed


def test_service_layer_logic():
    """Test service layer business logic"""
    print("\n🔧 Test 3: Service Layer Business Logic")

    service_files = [
        "api/services/billing_service.py",
        "api/services/media_service.py",
    ]

    all_passed = True
    for service_file in service_files:
        if os.path.exists(service_file):
            service_results = check_file_content(
                service_file,
                f"Service layer logic in {service_file}",
                forbidden_content=[r"chiropractor", r"chiro(?!p)"],
            )

            if service_results["passed"]:
                print(f"✅ PASS: {service_file} - Service logic is clean")
            else:
                print(f"❌ FAIL: {service_file} - {service_results['issues']}")
                all_passed = False

    return all_passed


def test_role_enum_configuration():
    """Test role enum is correctly configured in business logic"""
    print("\n🔐 Test 4: Role Enum Configuration")

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


def test_user_model_methods():
    """Test User model helper methods work with new role names"""
    print("\n👤 Test 5: User Model Helper Methods")

    try:
        # Import User model and check role methods
        from api.models.base import User
        from api.core.config import RoleType

        # Verify that has_role method exists
        user = User()
        if hasattr(user, "has_role"):
            print("✅ PASS: User.has_role method exists")

            # Check if we can reference the new role type
            role_name = RoleType.CARE_PROVIDER.value
            print(f"✅ PASS: Can reference CARE_PROVIDER role: '{role_name}'")
            return True
        else:
            print("❌ FAIL: User.has_role method missing")
            return False

    except Exception as e:
        print(f"❌ FAIL: Error testing User model methods: {e}")
        return False


def test_crud_operation_names():
    """Test CRUD operations use correct function names"""
    print("\n🗃️  Test 6: CRUD Operation Names")

    # Test plan CRUD operations
    plan_crud_results = check_file_content(
        "api/crud/crud_plan.py",
        "Plan CRUD operations",
        expected_content=[r"def get_plans_by_care_provider"],
        forbidden_content=[r"def get_plans_by_chiropractor", r"chiropractor_id"],
    )

    if plan_crud_results["passed"]:
        print("✅ PASS: crud_plan.py - Uses get_plans_by_care_provider")
    else:
        print(f"❌ FAIL: crud_plan.py - {plan_crud_results['issues']}")

    # Test user CRUD operations
    user_crud_results = check_file_content(
        "api/crud/crud_user.py",
        "User CRUD operations",
        expected_content=[r"def associate_user_with_care_provider"],
        forbidden_content=[
            r"def associate_user_with_chiro",
            r"temp_chiro_role_id",
            r"chiropractor",
        ],
    )

    if user_crud_results["passed"]:
        print("✅ PASS: crud_user.py - Uses associate_user_with_care_provider")
    else:
        print(f"❌ FAIL: crud_user.py - {user_crud_results['issues']}")

    return plan_crud_results["passed"] and user_crud_results["passed"]


def test_test_fixture_documentation():
    """Test that test fixtures have updated documentation"""
    print("\n🧪 Test 7: Test Fixture Documentation")

    conftest_results = check_file_content(
        "tests/conftest.py",
        "Test configuration and fixtures",
        expected_content=[r"care provider app"],
        forbidden_content=[r"chiropractic app", r"chiropractor"],
    )

    if conftest_results["passed"]:
        print("✅ PASS: conftest.py - Test documentation updated")
    else:
        print(f"❌ FAIL: conftest.py - {conftest_results['issues']}")

    return conftest_results["passed"]


def test_database_relationship_integrity():
    """Test database relationships use correct field names"""
    print("\n🔗 Test 8: Database Relationship Integrity")

    try:
        # Import models and check relationship integrity
        from api.models.base import TherapyPlan, User

        # Check TherapyPlan has care_provider_id field reference
        plan_fields = TherapyPlan.__table__.columns.keys()
        if "care_provider_id" in plan_fields:
            print("✅ PASS: TherapyPlan has care_provider_id field")

            # Check if old field is gone
            if "chiropractor_id" not in plan_fields:
                print("✅ PASS: TherapyPlan no longer has chiropractor_id field")
                return True
            else:
                print("❌ FAIL: TherapyPlan still has chiropractor_id field")
                return False
        else:
            print("❌ FAIL: TherapyPlan missing care_provider_id field")
            return False

    except Exception as e:
        print(f"❌ FAIL: Error checking relationship integrity: {e}")
        return False


def main():
    """Run all business logic and domain model tests"""

    print("📊 Running comprehensive business logic and domain model validation...")

    test_results = []
    test_results.append(
        ("Domain Model Relationships", test_domain_model_relationships())
    )
    test_results.append(("Business Logic Validation", test_business_logic_validation()))
    test_results.append(("Service Layer Logic", test_service_layer_logic()))
    test_results.append(("Role Enum Configuration", test_role_enum_configuration()))
    test_results.append(("User Model Helper Methods", test_user_model_methods()))
    test_results.append(("CRUD Operation Names", test_crud_operation_names()))
    test_results.append(
        ("Test Fixture Documentation", test_test_fixture_documentation())
    )
    test_results.append(
        ("Database Relationship Integrity", test_database_relationship_integrity())
    )

    print("\n" + "=" * 60)
    print("📊 Business Logic and Domain Models Test Summary:")

    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   - {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎯 Task 35.6 Business Logic and Domain Models: COMPLETED")
        print("🏗️  All domain models using care_provider terminology")
        print("⚖️  All business validation logic updated")
        print("🔧 All service layer logic consistent")
        print("🔐 Role enums correctly configured")
        print("🗃️  All CRUD operations using correct names")
        print("🔗 Database relationships use proper field names")
        print("🧪 Test fixtures and documentation updated")
    else:
        print("\n⚠️  Task 35.6: Some issues found that need attention")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
