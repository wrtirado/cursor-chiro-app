#!/usr/bin/env python3

import asyncio
import libsql_client


async def check_audit_table():
    client = libsql_client.create_client(url="http://localhost:8080")

    # Check if table exists and get structure
    try:
        result = await client.execute("PRAGMA table_info(audit_logs)")
        print("Audit logs table structure:")
        for row in result.rows:
            print(f"  {row[1]} {row[2]} (nullable: {row[3] == 0})")

        # Check if there are any audit log entries
        result = await client.execute("SELECT COUNT(*) FROM audit_logs")
        print(f"\nAudit logs count: {result.rows[0][0]}")

        # Check indexes
        result = await client.execute(
            'SELECT name FROM sqlite_master WHERE type="index" AND tbl_name="audit_logs"'
        )
        print(f"\nIndexes on audit_logs:")
        for row in result.rows:
            print(f"  - {row[0]}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(check_audit_table())
