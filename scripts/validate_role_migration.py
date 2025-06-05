#!/usr/bin/env python3
"""
Role Migration Validation Script

This script validates that the role system migration from single role_id
to many-to-many user_roles was successful and maintains data integrity.

Usage:
    python scripts/validate_role_migration.py

The script performs the following checks:
1. Verifies user_roles table exists and has proper structure
2. Checks that all users from the old system have corresponding entries
3. Validates role name changes (chiropractor -> care_provider)
4. Ensures no data loss during migration
5. Verifies foreign key constraints and indexes
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
import libsql_client
from typing import Dict, List, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def get_db_client():
    """Create and return a database client"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not found in environment")

    # Adapt URL for libsql_client
    adapted_url = db_url
    if db_url.startswith("sqlite+libsql://"):
        adapted_url = db_url.replace("sqlite+libsql://", "http://", 1)
    elif db_url.startswith("sqlite+http://"):
        adapted_url = db_url.replace("sqlite+http://", "http://", 1)
    elif db_url.startswith("sqlite:///"):
        path = db_url[len("sqlite:///") :]
        adapted_url = "file:" + path

    return libsql_client.create_client(url=adapted_url)


async def check_table_exists(client, table_name: str) -> bool:
    """Check if a table exists in the database"""
    result = await client.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    return len(result.rows) > 0


async def check_user_roles_structure(client) -> Dict[str, Any]:
    """Validate the user_roles table structure"""
    logger.info("🔍 Checking user_roles table structure...")

    checks = {
        "table_exists": False,
        "correct_columns": False,
        "indexes_exist": False,
        "foreign_keys": False,
    }

    # Check if table exists
    checks["table_exists"] = await check_table_exists(client, "user_roles")
    if not checks["table_exists"]:
        logger.error("❌ user_roles table does not exist!")
        return checks

    # Check column structure
    result = await client.execute("PRAGMA table_info(user_roles)")
    columns = {row[1]: row[2] for row in result.rows}  # column_name: data_type

    expected_columns = {
        "user_role_id": "INTEGER",
        "user_id": "INTEGER",
        "role_id": "INTEGER",
        "assigned_at": "DATETIME",
        "assigned_by_id": "INTEGER",
        "is_active": "BOOLEAN",
    }

    checks["correct_columns"] = all(
        col in columns and columns[col] == expected_columns[col]
        for col in expected_columns
    )

    if checks["correct_columns"]:
        logger.info("✅ user_roles table has correct column structure")
    else:
        logger.error(f"❌ user_roles table structure mismatch. Found: {columns}")

    # Check indexes
    result = await client.execute(
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

    checks["indexes_exist"] = all(idx in indexes for idx in expected_indexes)

    if checks["indexes_exist"]:
        logger.info("✅ All required indexes exist on user_roles table")
    else:
        missing = [idx for idx in expected_indexes if idx not in indexes]
        logger.error(f"❌ Missing indexes: {missing}")

    # Check foreign keys
    result = await client.execute("PRAGMA foreign_key_list(user_roles)")
    fk_tables = {row[2] for row in result.rows}  # referenced table names

    expected_fk_tables = {"Users", "Roles"}
    checks["foreign_keys"] = expected_fk_tables.issubset(fk_tables)

    if checks["foreign_keys"]:
        logger.info("✅ Foreign key constraints are properly configured")
    else:
        logger.error(f"❌ Foreign key constraints missing. Found: {fk_tables}")

    return checks


async def check_role_name_migration(client) -> bool:
    """Check that role names were properly updated"""
    logger.info("🔍 Checking role name migration (chiropractor -> care_provider)...")

    # Check if 'care_provider' role exists
    result = await client.execute(
        "SELECT COUNT(*) FROM Roles WHERE name = 'care_provider'"
    )
    care_provider_count = result.rows[0][0]

    # Check if 'chiropractor' role still exists (should not)
    result = await client.execute(
        "SELECT COUNT(*) FROM Roles WHERE name = 'chiropractor'"
    )
    chiropractor_count = result.rows[0][0]

    success = care_provider_count > 0 and chiropractor_count == 0

    if success:
        logger.info(
            "✅ Role name migration successful: 'chiropractor' -> 'care_provider'"
        )
    else:
        logger.error(
            f"❌ Role name migration failed. care_provider: {care_provider_count}, chiropractor: {chiropractor_count}"
        )

    return success


async def check_users_table_migration(client) -> bool:
    """Check that Users table no longer has role_id column"""
    logger.info("🔍 Checking Users table migration (role_id column removal)...")

    result = await client.execute("PRAGMA table_info(Users)")
    columns = [row[1] for row in result.rows]  # column names

    role_id_exists = "role_id" in columns

    if not role_id_exists:
        logger.info("✅ Users table migration successful: role_id column removed")
        return True
    else:
        logger.error("❌ Users table still contains role_id column")
        return False


async def check_data_integrity(client) -> Dict[str, Any]:
    """Validate data integrity after migration"""
    logger.info("🔍 Checking data integrity...")

    checks = {
        "all_users_have_roles": False,
        "no_orphaned_user_roles": False,
        "role_assignments_valid": False,
        "user_count_consistent": False,
    }

    # Check that all users have at least one role
    result = await client.execute(
        """
        SELECT COUNT(*) FROM Users u
        WHERE NOT EXISTS (
            SELECT 1 FROM user_roles ur 
            WHERE ur.user_id = u.user_id AND ur.is_active = 1
        )
    """
    )
    users_without_roles = result.rows[0][0]

    checks["all_users_have_roles"] = users_without_roles == 0

    if checks["all_users_have_roles"]:
        logger.info("✅ All users have at least one active role")
    else:
        logger.error(f"❌ {users_without_roles} users have no active roles")

    # Check for orphaned user_roles (references to non-existent users/roles)
    result = await client.execute(
        """
        SELECT COUNT(*) FROM user_roles ur
        WHERE NOT EXISTS (SELECT 1 FROM Users u WHERE u.user_id = ur.user_id)
           OR NOT EXISTS (SELECT 1 FROM Roles r WHERE r.role_id = ur.role_id)
    """
    )
    orphaned_roles = result.rows[0][0]

    checks["no_orphaned_user_roles"] = orphaned_roles == 0

    if checks["no_orphaned_user_roles"]:
        logger.info("✅ No orphaned user role assignments found")
    else:
        logger.error(f"❌ {orphaned_roles} orphaned user role assignments found")

    # Check that all role assignments are valid
    result = await client.execute(
        """
        SELECT COUNT(*) FROM user_roles 
        WHERE is_active NOT IN (0, 1) 
           OR assigned_at IS NULL
           OR user_id IS NULL 
           OR role_id IS NULL
    """
    )
    invalid_assignments = result.rows[0][0]

    checks["role_assignments_valid"] = invalid_assignments == 0

    if checks["role_assignments_valid"]:
        logger.info("✅ All role assignments have valid data")
    else:
        logger.error(f"❌ {invalid_assignments} invalid role assignments found")

    # Check user count consistency
    result = await client.execute("SELECT COUNT(*) FROM Users")
    total_users = result.rows[0][0]

    result = await client.execute(
        """
        SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE is_active = 1
    """
    )
    users_with_roles = result.rows[0][0]

    checks["user_count_consistent"] = total_users == users_with_roles

    if checks["user_count_consistent"]:
        logger.info(f"✅ User count consistent: {total_users} users, all have roles")
    else:
        logger.warning(
            f"⚠️  User count mismatch: {total_users} total users, {users_with_roles} with roles"
        )

    return checks


async def generate_migration_report(client) -> None:
    """Generate a detailed migration report"""
    logger.info("📊 Generating migration report...")

    # Count users by role
    result = await client.execute(
        """
        SELECT r.name, COUNT(DISTINCT ur.user_id) as user_count
        FROM Roles r
        LEFT JOIN user_roles ur ON r.role_id = ur.role_id AND ur.is_active = 1
        GROUP BY r.role_id, r.name
        ORDER BY user_count DESC
    """
    )

    print("\n" + "=" * 50)
    print("           MIGRATION REPORT")
    print("=" * 50)

    print("\n📈 Users by Role:")
    for row in result.rows:
        role_name, user_count = row
        print(f"  • {role_name}: {user_count} users")

    # Total role assignments
    result = await client.execute(
        """
        SELECT COUNT(*) FROM user_roles WHERE is_active = 1
    """
    )
    total_assignments = result.rows[0][0]

    result = await client.execute("SELECT COUNT(*) FROM Users")
    total_users = result.rows[0][0]

    print(f"\n📊 Summary:")
    print(f"  • Total users: {total_users}")
    print(f"  • Total active role assignments: {total_assignments}")
    print(
        f"  • Average roles per user: {total_assignments/total_users:.1f}"
        if total_users > 0
        else "  • Average roles per user: 0"
    )

    # Check for users with multiple roles
    result = await client.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT user_id
            FROM user_roles 
            WHERE is_active = 1
            GROUP BY user_id
            HAVING COUNT(*) > 1
        )
    """
    )
    multi_role_users = result.rows[0][0]

    print(f"  • Users with multiple roles: {multi_role_users}")

    print("\n" + "=" * 50)


async def main():
    """Main validation function"""
    print("🚀 Starting Role Migration Validation")
    print("=" * 50)

    client = None
    all_checks_passed = True

    try:
        client = await get_db_client()
        logger.info("✅ Database connection established")

        # Run all validation checks
        structure_checks = await check_user_roles_structure(client)
        role_name_check = await check_role_name_migration(client)
        users_migration_check = await check_users_table_migration(client)
        integrity_checks = await check_data_integrity(client)

        # Generate report
        await generate_migration_report(client)

        # Determine overall success
        all_structure_good = all(structure_checks.values())
        all_integrity_good = all(integrity_checks.values())

        all_checks_passed = (
            all_structure_good
            and role_name_check
            and users_migration_check
            and all_integrity_good
        )

        print("\n🏁 VALIDATION SUMMARY")
        print("=" * 30)

        if all_checks_passed:
            print("✅ ALL CHECKS PASSED!")
            print("🎉 Role migration was successful!")
            logger.info("Migration validation completed successfully")
        else:
            print("❌ SOME CHECKS FAILED!")
            print("⚠️  Please review the errors above and fix before proceeding")
            logger.error("Migration validation found issues")

            # Show failed checks
            failed_checks = []
            for check, passed in structure_checks.items():
                if not passed:
                    failed_checks.append(f"Structure: {check}")

            if not role_name_check:
                failed_checks.append("Role name migration")

            if not users_migration_check:
                failed_checks.append("Users table migration")

            for check, passed in integrity_checks.items():
                if not passed:
                    failed_checks.append(f"Integrity: {check}")

            print(f"\n❌ Failed checks: {', '.join(failed_checks)}")

    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        print(f"❌ Validation failed: {e}")
        all_checks_passed = False

    finally:
        if client:
            await client.close()
            logger.info("Database connection closed")

    # Exit with appropriate code
    sys.exit(0 if all_checks_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
