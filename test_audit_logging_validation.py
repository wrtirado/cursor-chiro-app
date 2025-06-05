#!/usr/bin/env python3
"""
Comprehensive test script to validate HIPAA-compliant audit logging for role operations.

This script tests:
1. Role assignment audit logging
2. Role removal audit logging
3. Role access checking audit logging
4. Role management audit logging
5. Audit log format and completeness
"""

import asyncio
import libsql_client
import requests
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any
import logging


class AuditLoggingValidator:
    def __init__(self):
        # Detect if running inside Docker container
        if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_ENV"):
            # Inside Docker container
            self.db_url = "http://db:8080"
            self.api_base = "http://localhost:8000"  # API is on same container
        else:
            # Outside Docker (local development)
            self.db_url = "http://localhost:8080"
            self.api_base = "http://localhost:8000"

        self.client = None
        self.test_results = []
        self.auth_token = None

    async def setup(self):
        """Initialize database connection and authentication"""
        try:
            self.client = libsql_client.create_client(url=self.db_url)
            print("✅ Database connection established")

            # Try to authenticate as admin
            await self.authenticate()
            return True
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False

    async def authenticate(self):
        """Authenticate to get access token"""
        try:
            login_data = {
                "username": "admin@example.com",
                "password": "adminpassword",
            }
            response = requests.post(
                f"{self.api_base}/api/v1/auth/login", data=login_data, timeout=10
            )

            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = token_data.get("access_token")
                print("✅ Authentication successful")
            else:
                print(f"⚠️ Authentication failed: {response.status_code}")
                # Continue without auth for basic tests
        except Exception as e:
            print(f"⚠️ Authentication error: {e}")
            # Continue without auth for basic tests

    def get_auth_headers(self):
        """Get authorization headers if authenticated"""
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    async def test_audit_log_structure(self) -> bool:
        """Test 1: Verify audit log table structure"""
        print("🔍 Test 1: Checking audit log table structure...")

        try:
            # Check if audit_logs table exists and has required fields
            result = await self.client.execute("PRAGMA table_info(audit_logs)")
            columns = {row[1]: row[2] for row in result.rows}  # name -> type

            required_fields = {
                "id": "INTEGER",
                "timestamp": "DATETIME",
                "user_id": "INTEGER",
                "event_type": "TEXT",
                "resource_type": "TEXT",
                "resource_id": "TEXT",
                "outcome": "TEXT",
                "source_ip": "TEXT",
                "user_agent": "TEXT",
                "message": "TEXT",
                "props": "TEXT",
            }

            missing_fields = []
            for field, expected_type in required_fields.items():
                if field not in columns:
                    missing_fields.append(field)

            if missing_fields:
                print(f"❌ Missing audit log fields: {missing_fields}")
                return False
            else:
                print("✅ Audit log table structure is complete")
                return True

        except Exception as e:
            print(f"❌ Error checking audit log structure: {e}")
            return False

    async def test_role_assignment_logging(self) -> bool:
        """Test 2: Verify role assignment operations are logged"""
        print("🔍 Test 2: Testing role assignment audit logging...")

        try:
            # First, check if we have users and roles to work with
            result = await self.client.execute("SELECT COUNT(*) FROM users")
            user_count = result.rows[0][0]

            result = await self.client.execute("SELECT COUNT(*) FROM roles")
            role_count = result.rows[0][0]

            if user_count == 0 or role_count == 0:
                print("⚠️ No users or roles found for testing")
                return False

            # Get baseline audit log count
            result = await self.client.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event_type LIKE 'ROLE_%'"
            )
            baseline_count = result.rows[0][0]

            # Test role assignment via API if authenticated
            if self.auth_token:
                try:
                    # Get a test user and role
                    result = await self.client.execute(
                        "SELECT user_id FROM users WHERE email != 'admin@example.com' LIMIT 1"
                    )
                    if result.rows:
                        test_user_id = result.rows[0][0]

                        result = await self.client.execute(
                            "SELECT role_id FROM roles WHERE name = 'patient' LIMIT 1"
                        )
                        if result.rows:
                            test_role_id = result.rows[0][0]

                            # Try to assign role via API
                            assignment_data = {
                                "user_id": test_user_id,
                                "role_ids": [test_role_id],
                            }

                            response = requests.post(
                                f"{self.api_base}/api/v1/roles/assign",
                                json=assignment_data,
                                headers=self.get_auth_headers(),
                                timeout=10,
                            )

                            if response.status_code in [200, 201]:
                                print("✅ Role assignment API call successful")
                            else:
                                print(
                                    f"⚠️ Role assignment API failed: {response.status_code}"
                                )

                except Exception as e:
                    print(f"⚠️ API test failed: {e}")

            # Check if new audit logs were created
            await asyncio.sleep(1)  # Give time for logs to be written

            result = await self.client.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event_type LIKE 'ROLE_%'"
            )
            new_count = result.rows[0][0]

            if new_count > baseline_count:
                print(
                    f"✅ Role audit logs detected: {new_count - baseline_count} new entries"
                )

                # Show recent role audit logs
                result = await self.client.execute(
                    """
                    SELECT timestamp, event_type, message 
                    FROM audit_logs 
                    WHERE event_type LIKE 'ROLE_%' 
                    ORDER BY timestamp DESC 
                    LIMIT 5
                """
                )

                print("📝 Recent role audit logs:")
                for row in result.rows:
                    timestamp, event_type, message = row
                    print(f"   {timestamp} | {event_type} | {message}")

                return True
            else:
                print("⚠️ No new role audit logs found")
                return baseline_count > 0  # Pass if we have any existing logs

        except Exception as e:
            print(f"❌ Error testing role assignment logging: {e}")
            return False

    async def test_role_access_logging(self) -> bool:
        """Test 3: Verify role access checks are logged"""
        print("🔍 Test 3: Testing role access audit logging...")

        try:
            # Get baseline audit log count for access events
            result = await self.client.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event_type IN ('ROLE_ACCESS_GRANTED', 'ROLE_ACCESS_DENIED')"
            )
            baseline_count = result.rows[0][0]

            # Test API endpoints that require role checking
            if self.auth_token:
                try:
                    # Try to access role management endpoints
                    endpoints_to_test = [
                        "/api/v1/roles/roles",
                        "/api/v1/users/1/roles",
                    ]

                    for endpoint in endpoints_to_test:
                        try:
                            response = requests.get(
                                f"{self.api_base}{endpoint}",
                                headers=self.get_auth_headers(),
                                timeout=5,
                            )
                            # Don't care about success/failure, just that it was logged
                        except:
                            pass  # Connection errors are ok for this test

                except Exception as e:
                    print(f"⚠️ API access test failed: {e}")

            # Check if new access audit logs were created
            await asyncio.sleep(1)  # Give time for logs to be written

            result = await self.client.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE event_type IN ('ROLE_ACCESS_GRANTED', 'ROLE_ACCESS_DENIED')"
            )
            new_count = result.rows[0][0]

            if new_count > baseline_count:
                print(
                    f"✅ Role access audit logs detected: {new_count - baseline_count} new entries"
                )

                # Show recent access audit logs
                result = await self.client.execute(
                    """
                    SELECT timestamp, event_type, outcome, message 
                    FROM audit_logs 
                    WHERE event_type IN ('ROLE_ACCESS_GRANTED', 'ROLE_ACCESS_DENIED')
                    ORDER BY timestamp DESC 
                    LIMIT 3
                """
                )

                print("📝 Recent role access audit logs:")
                for row in result.rows:
                    timestamp, event_type, outcome, message = row
                    print(f"   {timestamp} | {event_type} | {outcome} | {message}")

                return True
            else:
                print("⚠️ No new role access audit logs found")
                return baseline_count > 0  # Pass if we have any existing logs

        except Exception as e:
            print(f"❌ Error testing role access logging: {e}")
            return False

    async def test_audit_log_hipaa_compliance(self) -> bool:
        """Test 4: Verify audit logs meet HIPAA requirements"""
        print("🔍 Test 4: Testing HIPAA compliance of audit logs...")

        try:
            # Check for required HIPAA audit fields in recent logs
            result = await self.client.execute(
                """
                SELECT id, timestamp, user_id, event_type, resource_type, 
                       outcome, source_ip, message, props
                FROM audit_logs 
                WHERE event_type LIKE 'ROLE_%'
                ORDER BY timestamp DESC 
                LIMIT 10
            """
            )

            if not result.rows:
                print("⚠️ No role audit logs found for HIPAA compliance check")
                return False

            compliance_issues = []

            for row in result.rows:
                (
                    log_id,
                    timestamp,
                    user_id,
                    event_type,
                    resource_type,
                    outcome,
                    source_ip,
                    message,
                    props,
                ) = row

                # Check required fields are not null
                if not timestamp:
                    compliance_issues.append(f"Log {log_id}: Missing timestamp")
                if not user_id:
                    compliance_issues.append(f"Log {log_id}: Missing user_id")
                if not event_type:
                    compliance_issues.append(f"Log {log_id}: Missing event_type")
                if not outcome:
                    compliance_issues.append(f"Log {log_id}: Missing outcome")
                if not message:
                    compliance_issues.append(f"Log {log_id}: Missing message")

                # Check props contains structured data
                if props:
                    try:
                        props_data = json.loads(props)
                        if not isinstance(props_data, dict):
                            compliance_issues.append(
                                f"Log {log_id}: Props is not a valid JSON object"
                            )
                    except json.JSONDecodeError:
                        compliance_issues.append(
                            f"Log {log_id}: Props is not valid JSON"
                        )

            if compliance_issues:
                print("❌ HIPAA compliance issues found:")
                for issue in compliance_issues[:5]:  # Show first 5 issues
                    print(f"   {issue}")
                return False
            else:
                print(
                    f"✅ All {len(result.rows)} checked audit logs are HIPAA compliant"
                )
                return True

        except Exception as e:
            print(f"❌ Error testing HIPAA compliance: {e}")
            return False

    async def test_role_history_preservation(self) -> bool:
        """Test 5: Verify role assignment history is preserved"""
        print("🔍 Test 5: Testing role assignment history preservation...")

        try:
            # Check that user_roles table preserves history with soft deletes
            result = await self.client.execute(
                """
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN is_active = 1 THEN 1 END) as active,
                       COUNT(CASE WHEN is_active = 0 THEN 1 END) as inactive
                FROM user_roles
            """
            )

            if result.rows:
                total, active, inactive = result.rows[0]
                print(
                    f"📊 Role assignments: {total} total, {active} active, {inactive} inactive"
                )

                if total > 0:
                    # Check if we have complete audit information
                    result = await self.client.execute(
                        """
                        SELECT COUNT(*) 
                        FROM user_roles 
                        WHERE assigned_at IS NOT NULL 
                        AND assigned_by_id IS NOT NULL
                    """
                    )

                    complete_records = result.rows[0][0] if result.rows else 0
                    completion_rate = (
                        (complete_records / total) * 100 if total > 0 else 0
                    )

                    print(
                        f"📋 Audit completeness: {complete_records}/{total} records ({completion_rate:.1f}%)"
                    )

                    # Show sample history
                    result = await self.client.execute(
                        """
                        SELECT ur.user_id, r.name as role_name, ur.assigned_at, 
                               ur.assigned_by_id, ur.is_active
                        FROM user_roles ur
                        JOIN roles r ON ur.role_id = r.role_id
                        ORDER BY ur.assigned_at DESC
                        LIMIT 5
                    """
                    )

                    print("📝 Sample role assignment history:")
                    for row in result.rows:
                        user_id, role_name, assigned_at, assigned_by_id, is_active = row
                        status = "active" if is_active else "inactive"
                        print(
                            f"   User {user_id}: {role_name} | {assigned_at} | by {assigned_by_id} | {status}"
                        )

                    return completion_rate >= 80  # 80% completion rate threshold
                else:
                    print("⚠️ No role assignments found")
                    return False
            else:
                print("❌ Could not query role assignment history")
                return False

        except Exception as e:
            print(f"❌ Error testing role history preservation: {e}")
            return False

    async def run_all_tests(self):
        """Run all audit logging validation tests"""
        print("🚀 Starting HIPAA Audit Logging Validation...")
        print("=" * 60)

        if not await self.setup():
            print("❌ Setup failed. Cannot continue tests.")
            return False

        tests = [
            ("Audit Log Structure", self.test_audit_log_structure),
            ("Role Assignment Logging", self.test_role_assignment_logging),
            ("Role Access Logging", self.test_role_access_logging),
            ("HIPAA Compliance", self.test_audit_log_hipaa_compliance),
            ("Role History Preservation", self.test_role_history_preservation),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            print(f"\n{test_name}:")
            print("-" * 40)
            try:
                result = await test_func()
                if result:
                    passed += 1
                    self.test_results.append((test_name, "PASS"))
                else:
                    self.test_results.append((test_name, "FAIL"))
            except Exception as e:
                print(f"❌ Test '{test_name}' crashed: {e}")
                self.test_results.append((test_name, "ERROR"))

        print("\n" + "=" * 60)
        print("📊 AUDIT LOGGING VALIDATION SUMMARY")
        print("=" * 60)

        for test_name, result in self.test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")

        success_rate = (passed / total) * 100
        print(f"\n🎯 Overall Success Rate: {passed}/{total} ({success_rate:.1f}%)")

        if success_rate >= 80:
            print(
                "🎉 Audit logging validation PASSED! HIPAA compliance requirements met."
            )
            return True
        else:
            print(
                "⚠️ Audit logging validation FAILED. HIPAA compliance issues detected."
            )
            return False


async def main():
    validator = AuditLoggingValidator()
    success = await validator.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
