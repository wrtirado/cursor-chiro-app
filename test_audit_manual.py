#!/usr/bin/env python3
"""
Manual test script to verify audit logging functions
"""

import asyncio
import libsql_client
from api.core.audit_logger import log_audit_event, log_role_event
from api.database.session import get_db, SessionLocal
from api.models.base import User
from datetime import datetime


def test_database_audit_logging():
    """Test database audit logging by creating sample entries"""

    print("🔍 Testing database audit logging...")

    # Get database session
    db = SessionLocal()

    try:
        # Test 1: Basic audit event
        print("📝 Creating basic audit event...")
        log_audit_event(
            event_type="TEST_EVENT",
            outcome="SUCCESS",
            resource_type="test",
            resource_id="123",
            details={"test": "manual_audit_test"},
            db_session=db,
        )

        # Test 2: Role event
        print("📝 Creating role audit event...")
        log_role_event(
            action="role_assigned",
            user_id=1,
            target_user_id=1,
            role_id=1,
            role_name="admin",
            assigned_by_id=1,
            details={"test": "manual_role_test"},
            outcome="SUCCESS",
            db_session=db,
        )

        print("✅ Audit events created successfully")

    except Exception as e:
        print(f"❌ Error creating audit events: {e}")
        db.rollback()
    finally:
        db.close()


async def check_audit_logs():
    """Check if audit logs were created"""
    print("🔍 Checking audit logs in database...")

    client = libsql_client.create_client(url="http://localhost:8080")

    try:
        # Check total count
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

    except Exception as e:
        print(f"❌ Error checking audit logs: {e}")


if __name__ == "__main__":
    print("🚀 Manual Audit Logging Test")
    print("=" * 40)

    # Test database logging
    test_database_audit_logging()

    print("\n" + "=" * 40)

    # Check results
    asyncio.run(check_audit_logs())
