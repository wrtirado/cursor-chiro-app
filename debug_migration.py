#!/usr/bin/env python3
import asyncio
import libsql_client


async def debug_migration():
    client = libsql_client.create_client(url="http://localhost:8080")

    print("🔍 Debugging Migration Issues...")

    # Check if there are any user_roles at all (including inactive)
    result = await client.execute(
        "SELECT COUNT(*) as total, COUNT(CASE WHEN is_active = 1 THEN 1 END) as active FROM user_roles"
    )
    print(f"User roles - Total: {result.rows[0][0]}, Active: {result.rows[0][1]}")

    # Check actual data in user_roles
    result = await client.execute("SELECT * FROM user_roles LIMIT 10")
    print(f"Sample user_roles data: {result.rows}")

    # Check total users
    result = await client.execute("SELECT COUNT(*) FROM users")
    print(f"Total users: {result.rows[0][0]}")

    # Check user details
    result = await client.execute("SELECT user_id, name, email FROM users")
    print(f"Users: {result.rows}")

    # Check roles table
    result = await client.execute("SELECT * FROM roles")
    print(f"Roles: {result.rows}")

    # Check if roles have IDs that match what we expect
    result = await client.execute(
        'SELECT role_id, name FROM roles WHERE name IN ("chiropractor", "care_provider")'
    )
    print(f"Chiropractor/Care Provider roles: {result.rows}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(debug_migration())
