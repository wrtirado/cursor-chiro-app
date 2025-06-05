#!/usr/bin/env python3
import asyncio
import libsql_client


async def check_migration_status():
    client = libsql_client.create_client(url="http://localhost:8080")

    # Check migrations table
    result = await client.execute(
        "SELECT version, applied_at FROM migrations ORDER BY applied_at"
    )
    print("Applied migrations:")
    for row in result.rows:
        print(f"  - {row[0]} (applied: {row[1]})")
    print()

    # Check current Users table structure
    result = await client.execute("PRAGMA table_info(users)")
    print("Users table columns:")
    for row in result.rows:
        print(
            f"  - {row[1]}: {row[2]} (notnull: {row[3]}, default: {row[4]}, pk: {row[5]})"
        )
    print()

    # Check user_roles table structure
    result = await client.execute("PRAGMA table_info(user_roles)")
    print("user_roles table columns:")
    for row in result.rows:
        print(
            f"  - {row[1]}: {row[2]} (notnull: {row[3]}, default: {row[4]}, pk: {row[5]})"
        )
    print()

    # Check role names
    result = await client.execute("SELECT name FROM roles")
    print("Current role names:")
    for row in result.rows:
        print(f"  - {row[0]}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(check_migration_status())
