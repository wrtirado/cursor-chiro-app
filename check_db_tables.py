#!/usr/bin/env python3

import asyncio
import libsql_client


async def check_tables():
    client = libsql_client.create_client(url="http://localhost:8080")
    result = await client.execute('SELECT name FROM sqlite_master WHERE type="table"')
    print("Available tables:")
    for row in result.rows:
        print(f"  - {row[0]}")

    # Check if audit_logs exists
    try:
        result = await client.execute("SELECT COUNT(*) FROM audit_logs")
        print(f"\nAudit logs count: {result.rows[0][0]}")
    except Exception as e:
        print(f"\nAudit logs table error: {e}")


if __name__ == "__main__":
    asyncio.run(check_tables())
