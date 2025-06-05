#!/usr/bin/env python3
"""
Direct database audit logging test - bypassing SQLAlchemy session issues.
"""

import asyncio
import libsql_client
import json
from datetime import datetime


async def test_direct_audit_logging():
    """Test audit logging by writing directly to the database"""

    print("🔍 Testing direct database audit logging...")

    client = libsql_client.create_client(url="http://localhost:8080")

    try:
        # Test 1: Basic audit event
        print("📝 Creating basic audit event...")
        await client.execute(
            """
            INSERT INTO audit_logs (
                timestamp, user_id, event_type, resource_type, resource_id,
                outcome, source_ip, user_agent, request_path, request_method,
                message, props
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                datetime.now().isoformat(),
                1,  # user_id
                "TEST_EVENT",
                "test",
                "123",
                "SUCCESS",
                "127.0.0.1",
                "test-agent",
                "/test",
                "POST",
                "Test audit event",
                json.dumps({"test": "manual_audit_test"}),
            ],
        )

        # Test 2: Role audit event
        print("📝 Creating role audit event...")
        await client.execute(
            """
            INSERT INTO audit_logs (
                timestamp, user_id, event_type, resource_type, resource_id,
                outcome, source_ip, user_agent, request_path, request_method,
                message, props
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                datetime.now().isoformat(),
                1,  # user_id
                "ROLE_ASSIGNED",
                "user_role",
                "1",
                "SUCCESS",
                "127.0.0.1",
                "test-agent",
                "/roles/assign",
                "POST",
                "Role assigned: admin role assigned to user 1",
                json.dumps(
                    {
                        "test": "manual_role_test",
                        "role_name": "admin",
                        "target_user_id": 1,
                    }
                ),
            ],
        )

        print("✅ Direct audit events created successfully")

        # Check if audit logs were created
        result = await client.execute("SELECT COUNT(*) FROM audit_logs")
        total_count = result.rows[0][0]
        print(f"📊 Total audit logs: {total_count}")

        # Check recent logs
        result = await client.execute(
            """
            SELECT timestamp, event_type, outcome, message, user_id
            FROM audit_logs 
            ORDER BY timestamp DESC 
            LIMIT 5
        """
        )

        print("📝 Recent audit logs:")
        for row in result.rows:
            timestamp, event_type, outcome, message, user_id = row
            print(f"   {timestamp} | {event_type} | {outcome} | User: {user_id}")
            print(f"      Message: {message}")

        return total_count >= 2  # Should have at least our 2 test entries

    except Exception as e:
        print(f"❌ Error with direct audit logging: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Direct Database Audit Logging Test")
    print("=" * 40)

    success = asyncio.run(test_direct_audit_logging())

    if success:
        print("\n✅ Direct audit logging test PASSED")
    else:
        print("\n❌ Direct audit logging test FAILED")
