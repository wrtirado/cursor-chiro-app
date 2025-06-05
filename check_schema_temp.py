#!/usr/bin/env python3
import asyncio
import libsql_client
import os


async def check_schema():
    client = libsql_client.create_client(url="http://localhost:8080")

    # Check if Users table exists and get its schema
    result = await client.execute(
        'SELECT sql FROM sqlite_master WHERE type="table" AND name="Users"'
    )
    if result.rows:
        print("Current Users table schema:")
        print(result.rows[0][0])
        print()

    # Check existing tables
    result = await client.execute(
        'SELECT name FROM sqlite_master WHERE type="table" ORDER BY name'
    )
    print("Existing tables:")
    for row in result.rows:
        print(f"  - {row[0]}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(check_schema())
