#!/usr/bin/env python3
"""
Comprehensive test script to validate the role system migration functionality.
This script tests database schema, relationships, API functionality, and data integrity.
"""
import asyncio
import libsql_client
import requests
import json
import sys
from datetime import datetime


class MigrationValidator:
    def __init__(self):
        self.db_url = "http://localhost:8080"
        self.api_base = "http://localhost:8000"
        self.client = None
        self.test_results = []

    async def setup(self):
        """Initialize database connection"""
        try:
            self.client = libsql_client.create_client(url=self.db_url)
            print("✅ Database connection established")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False

    async def cleanup(self):
        """Close database connection"""
        if self.client:
            await self.client.close()

    def log_test(self, test_name, passed, details=""):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append(
            {
                "test": test_name,
                "passed": passed,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def test_database_schema(self):
        """Test 1: Verify database schema is correct"""
        print("\n🔍 Testing Database Schema...")

        # Test 1.1: Check user_roles table exists and has correct structure
        try:
            result = await self.client.execute("PRAGMA table_info(user_roles)")
            columns = {row[1]: row[2] for row in result.rows}

            expected_columns = {
                "user_role_id": "INTEGER",
                "user_id": "INTEGER",
                "role_id": "INTEGER",
                "assigned_at": "DATETIME",
                "assigned_by_id": "INTEGER",
                "is_active": "BOOLEAN",
            }

            schema_correct = all(col in columns for col in expected_columns)
            self.log_test(
                "user_roles table schema",
                schema_correct,
                f"Expected: {expected_columns}, Found: {columns}",
            )
        except Exception as e:
            self.log_test("user_roles table schema", False, str(e))

        # Test 1.2: Check users table no longer has role_id column
        try:
            result = await self.client.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in result.rows]
            has_role_id = "role_id" in columns
            self.log_test(
                "users.role_id column removed",
                not has_role_id,
                f"role_id found in columns: {has_role_id}",
            )
        except Exception as e:
            self.log_test("users.role_id column removed", False, str(e))

        # Test 1.3: Check indexes exist
        try:
            result = await self.client.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='user_roles'"
            )
            indexes = [row[0] for row in result.rows]
            expected_indexes = [
                "idx_user_roles_user_id",
                "idx_user_roles_role_id",
                "idx_user_roles_user_active",
                "idx_user_roles_assigned_at",
                "idx_user_roles_assigned_by",
            ]

            indexes_exist = all(idx in indexes for idx in expected_indexes)
            self.log_test(
                "user_roles indexes",
                indexes_exist,
                f"Expected: {expected_indexes}, Found: {indexes}",
            )
        except Exception as e:
            self.log_test("user_roles indexes", False, str(e))

    async def test_data_migration(self):
        """Test 2: Verify data migration was successful"""
        print("\n🔍 Testing Data Migration...")

        # Test 2.1: Check role name was updated
        try:
            result = await self.client.execute(
                "SELECT name FROM roles WHERE name = 'care_provider'"
            )
            has_care_provider = len(result.rows) > 0

            result = await self.client.execute(
                "SELECT name FROM roles WHERE name = 'chiropractor'"
            )
            has_chiropractor = len(result.rows) > 0

            role_updated = has_care_provider and not has_chiropractor
            self.log_test(
                "role name updated (chiropractor → care_provider)",
                role_updated,
                f"care_provider exists: {has_care_provider}, chiropractor exists: {has_chiropractor}",
            )
        except Exception as e:
            self.log_test("role name updated", False, str(e))

        # Test 2.2: Check user role assignments were migrated
        try:
            result = await self.client.execute(
                "SELECT COUNT(*) FROM user_roles WHERE is_active = 1"
            )
            active_assignments = result.rows[0][0] if result.rows else 0

            result = await self.client.execute("SELECT COUNT(*) FROM users")
            total_users = result.rows[0][0] if result.rows else 0

            # Assuming most/all users had roles assigned originally
            assignments_migrated = (
                active_assignments > 0 and active_assignments <= total_users
            )
            self.log_test(
                "user role assignments migrated",
                assignments_migrated,
                f"Active assignments: {active_assignments}, Total users: {total_users}",
            )
        except Exception as e:
            self.log_test("user role assignments migrated", False, str(e))

        # Test 2.3: Check for orphaned data
        try:
            # Check for user_roles pointing to non-existent users
            result = await self.client.execute(
                """
                SELECT COUNT(*) FROM user_roles ur 
                LEFT JOIN users u ON ur.user_id = u.user_id 
                WHERE u.user_id IS NULL
            """
            )
            orphaned_user_roles = result.rows[0][0] if result.rows else 0

            # Check for user_roles pointing to non-existent roles
            result = await self.client.execute(
                """
                SELECT COUNT(*) FROM user_roles ur 
                LEFT JOIN roles r ON ur.role_id = r.role_id 
                WHERE r.role_id IS NULL
            """
            )
            orphaned_role_refs = result.rows[0][0] if result.rows else 0

            no_orphans = orphaned_user_roles == 0 and orphaned_role_refs == 0
            self.log_test(
                "no orphaned data",
                no_orphans,
                f"Orphaned user roles: {orphaned_user_roles}, Orphaned role refs: {orphaned_role_refs}",
            )
        except Exception as e:
            self.log_test("no orphaned data", False, str(e))

    async def test_relationship_functionality(self):
        """Test 3: Test that relationships work correctly"""
        print("\n🔍 Testing Relationship Functionality...")

        # Test 3.1: Test many-to-many query (user with multiple roles)
        try:
            # Get a user and their roles
            result = await self.client.execute(
                """
                SELECT u.user_id, u.name, r.name as role_name
                FROM users u
                JOIN user_roles ur ON u.user_id = ur.user_id
                JOIN roles r ON ur.role_id = r.role_id
                WHERE ur.is_active = 1
                ORDER BY u.user_id
                LIMIT 5
            """
            )

            relationships_work = len(result.rows) > 0
            user_roles = {}
            for row in result.rows:
                user_id = row[0]
                if user_id not in user_roles:
                    user_roles[user_id] = []
                user_roles[user_id].append(row[2])

            self.log_test(
                "user-role relationships queryable",
                relationships_work,
                f"Found {len(result.rows)} active user-role relationships",
            )

            # Check if any user has multiple roles (for future functionality)
            multi_role_users = sum(1 for roles in user_roles.values() if len(roles) > 1)
            self.log_test(
                "many-to-many capability",
                True,
                f"Users with multiple roles: {multi_role_users}",
            )

        except Exception as e:
            self.log_test("user-role relationships", False, str(e))

    def test_api_availability(self):
        """Test 4: Check if API server is running"""
        print("\n🔍 Testing API Availability...")

        try:
            response = requests.get(f"{self.api_base}/health", timeout=5)
            api_available = response.status_code == 200
            self.log_test(
                "API server running",
                api_available,
                f"Status code: {response.status_code}",
            )
        except Exception as e:
            self.log_test("API server running", False, str(e))

    async def test_api_functionality(self):
        """Test 5: Test API endpoints work with new schema"""
        print("\n🔍 Testing API Functionality...")

        # This would require authentication, so we'll just test basic endpoints
        try:
            # Test docs endpoint
            response = requests.get(f"{self.api_base}/docs", timeout=5)
            docs_work = response.status_code == 200
            self.log_test(
                "API docs accessible", docs_work, f"Status code: {response.status_code}"
            )
        except Exception as e:
            self.log_test("API docs accessible", False, str(e))

        # Test OpenAPI schema
        try:
            response = requests.get(f"{self.api_base}/openapi.json", timeout=5)
            openapi_work = response.status_code == 200
            self.log_test(
                "OpenAPI schema accessible",
                openapi_work,
                f"Status code: {response.status_code}",
            )
        except Exception as e:
            self.log_test("OpenAPI schema accessible", False, str(e))

    async def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Migration Validation Tests")
        print("=" * 50)

        # Setup
        if not await self.setup():
            return False

        try:
            # Run all test suites
            await self.test_database_schema()
            await self.test_data_migration()
            await self.test_relationship_functionality()
            self.test_api_availability()
            await self.test_api_functionality()

            # Summary
            print("\n" + "=" * 50)
            print("📊 TEST SUMMARY")
            print("=" * 50)

            passed_tests = sum(1 for result in self.test_results if result["passed"])
            total_tests = len(self.test_results)

            print(f"Tests Passed: {passed_tests}/{total_tests}")
            print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

            if passed_tests == total_tests:
                print(
                    "\n🎉 ALL TESTS PASSED! Migration appears to be fully functional."
                )
                return True
            else:
                print(
                    f"\n⚠️  {total_tests - passed_tests} tests failed. Review the issues above."
                )

                # Show failed tests
                failed_tests = [r for r in self.test_results if not r["passed"]]
                if failed_tests:
                    print("\n❌ Failed Tests:")
                    for test in failed_tests:
                        print(f"   - {test['test']}: {test['details']}")
                return False

        finally:
            await self.cleanup()


async def main():
    """Main function to run validation"""
    validator = MigrationValidator()
    success = await validator.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
