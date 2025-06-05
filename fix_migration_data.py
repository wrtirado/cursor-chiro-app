#!/usr/bin/env python3
"""
Script to fix the migration data that didn't migrate properly.
This will complete the role system migration.
"""
import asyncio
import libsql_client


async def fix_migration_data():
    client = libsql_client.create_client(url="http://localhost:8080")

    print("🔧 Fixing Migration Data...")

    try:
        # Step 1: Update role name from "chiropractor" to "care_provider"
        print("1. Updating role name: chiropractor → care_provider")
        result = await client.execute(
            "UPDATE roles SET name = 'care_provider' WHERE name = 'chiropractor'"
        )
        print(f"   ✅ Updated {result.rows_affected} role(s)")

        # Step 2: Check what role the admin user should have
        # Let's assign admin role to the admin user
        print("2. Assigning appropriate role to admin user")

        # Get admin user ID
        result = await client.execute(
            "SELECT user_id FROM users WHERE email = 'admin@example.com'"
        )
        if result.rows:
            user_id = result.rows[0][0]
            print(f"   Found admin user with ID: {user_id}")

            # Get admin role ID
            result = await client.execute(
                "SELECT role_id FROM roles WHERE name = 'admin'"
            )
            if result.rows:
                role_id = result.rows[0][0]
                print(f"   Found admin role with ID: {role_id}")

                # Insert user role assignment
                result = await client.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by_id, is_active)
                    VALUES (?, ?, datetime('now'), NULL, 1)
                """,
                    [user_id, role_id],
                )
                print(
                    f"   ✅ Assigned admin role to user (affected rows: {result.rows_affected})"
                )
            else:
                print("   ❌ Admin role not found")
        else:
            print("   ❌ Admin user not found")

        # Step 3: Verify the fixes
        print("3. Verifying fixes...")

        # Check role name
        result = await client.execute(
            "SELECT name FROM roles WHERE name = 'care_provider'"
        )
        has_care_provider = len(result.rows) > 0
        print(f"   care_provider role exists: {has_care_provider}")

        # Check user role assignments
        result = await client.execute(
            "SELECT COUNT(*) FROM user_roles WHERE is_active = 1"
        )
        active_assignments = result.rows[0][0] if result.rows else 0
        print(f"   Active user role assignments: {active_assignments}")

        # Show user roles
        result = await client.execute(
            """
            SELECT u.name, r.name as role_name, ur.assigned_at
            FROM users u
            JOIN user_roles ur ON u.user_id = ur.user_id
            JOIN roles r ON ur.role_id = r.role_id
            WHERE ur.is_active = 1
        """
        )
        print(f"   User role assignments:")
        for row in result.rows:
            print(f"     - {row[0]}: {row[1]} (assigned: {row[2]})")

        print("\n🎉 Migration data fixes completed!")

    except Exception as e:
        print(f"❌ Error fixing migration data: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(fix_migration_data())
