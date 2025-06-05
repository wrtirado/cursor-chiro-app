#!/usr/bin/env python3
import asyncio
import libsql_client


async def cleanup_partial_migration():
    client = libsql_client.create_client(url="http://localhost:8080")

    print("🔄 Cleaning up partial migration...")

    try:
        # Drop the user_roles table that was partially created
        await client.execute("DROP TABLE IF EXISTS user_roles")
        print("✅ Dropped user_roles table")

        # Drop any indexes that might have been created
        indexes_to_drop = [
            "idx_user_roles_user_id",
            "idx_user_roles_role_id",
            "idx_user_roles_user_active",
            "idx_user_roles_assigned_at",
            "idx_user_roles_assigned_by",
        ]

        for index in indexes_to_drop:
            try:
                await client.execute(f"DROP INDEX IF EXISTS {index}")
                print(f"✅ Dropped index {index}")
            except Exception as e:
                print(f"⚠️  Index {index} may not exist: {e}")

        # Revert any role name changes
        await client.execute(
            "UPDATE roles SET name = 'chiropractor' WHERE name = 'care_provider'"
        )
        print("✅ Reverted any role name changes")

        print("🎉 Cleanup completed successfully!")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(cleanup_partial_migration())
