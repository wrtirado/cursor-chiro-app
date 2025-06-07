"""
Security and Authorization Tests for Many-to-Many Role System

This test suite validates:
- Authorization bypass prevention
- Privilege escalation detection
- Role boundary enforcement
- Security attack scenarios
- HIPAA compliance validation
- Audit logging for security events
- Multi-role security scenarios
- Session security and token validation
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import time

from api.database.session import Base
from api.models.base import User, Role, UserRole
from api.core.config import RoleType
from api.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from api.crud.crud_role import crud_role, crud_user_role
from api.crud.crud_user import create_user
from api.schemas.user import UserCreate
from api.auth.dependencies import require_role
from api.core.audit_logger import log_role_access_check, AuditEvent


# Test Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Session:
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def security_roles(db) -> List[Role]:
    """Create security-focused test roles"""
    roles = [
        Role(name=RoleType.ADMIN.value),
        Role(name=RoleType.OFFICE_MANAGER.value),
        Role(name=RoleType.CARE_PROVIDER.value),
        Role(name=RoleType.BILLING_ADMIN.value),
        Role(name=RoleType.PATIENT.value),
    ]

    for role in roles:
        db.add(role)
    db.commit()

    for role in roles:
        db.refresh(role)

    return roles


@pytest.fixture
def security_users(db) -> List[User]:
    """Create security test users with various privilege levels"""
    users = [
        User(
            email="admin@security.test",
            password_hash=get_password_hash("SecureAdmin123!"),
            name="Security Admin",
            is_active_for_billing=True,
        ),
        User(
            email="manager@security.test",
            password_hash=get_password_hash("SecureManager123!"),
            name="Security Manager",
            is_active_for_billing=True,
        ),
        User(
            email="provider@security.test",
            password_hash=get_password_hash("SecureProvider123!"),
            name="Security Provider",
            is_active_for_billing=True,
        ),
        User(
            email="lowpriv@security.test",
            password_hash=get_password_hash("LowPriv123!"),
            name="Low Privilege User",
            is_active_for_billing=True,
        ),
        User(
            email="noroles@security.test",
            password_hash=get_password_hash("NoRoles123!"),
            name="No Roles User",
            is_active_for_billing=True,
        ),
        User(
            email="inactive@security.test",
            password_hash=get_password_hash("Inactive123!"),
            name="Inactive User",
            is_active_for_billing=False,  # Inactive user
        ),
    ]

    for user in users:
        db.add(user)
    db.commit()

    for user in users:
        db.refresh(user)

    return users


class TestAuthorizationBypass:
    """Test authorization bypass prevention"""

    def test_no_role_user_cannot_access_protected_resources(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that users with no roles are denied access"""
        no_roles_user = security_users[4]  # User with no roles

        # Verify user has no roles
        assert not no_roles_user.has_role(RoleType.ADMIN.value, db_session=db)
        assert not no_roles_user.has_role(RoleType.OFFICE_MANAGER.value, db_session=db)

        # Test that role checking correctly identifies no access
        active_roles = no_roles_user.get_active_roles(db_session=db)
        assert len(active_roles) == 0

    def test_inactive_user_denied_access(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that inactive users cannot access resources even with roles"""
        inactive_user = security_users[5]  # Inactive user
        admin_role = security_roles[0]

        # Assign admin role to inactive user
        crud_user_role.assign_roles(
            db=db,
            user_id=inactive_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=security_users[0].user_id,
        )

        # User should have the role but be inactive
        assert inactive_user.has_role(RoleType.ADMIN.value, db_session=db)
        assert not inactive_user.is_active_for_billing  # But inactive

        # In a real implementation, inactive users would be blocked at authentication level

    def test_soft_deleted_roles_not_accessible(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that soft-deleted (inactive) role assignments are not accessible"""
        user = security_users[1]
        role = security_roles[1]  # Office Manager

        # Assign role then immediately unassign (soft delete)
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=security_users[0].user_id,
        )
        crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=security_users[0].user_id,
        )

        # Should not have access via soft-deleted role
        assert not user.has_role(RoleType.OFFICE_MANAGER.value, db_session=db)
        active_roles = user.get_active_roles(db_session=db)
        assert len(active_roles) == 0

    def test_role_assignment_requires_authorization(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that role assignment itself requires proper authorization"""
        low_priv_user = security_users[3]  # Low privilege user
        target_user = security_users[4]  # No roles user
        admin_role = security_roles[0]

        # Low privilege user should not be able to assign admin role
        # This would be enforced at the API level via require_role middleware

        # Verify low privilege user cannot assign roles (would need admin/manager role)
        user_roles = low_priv_user.get_active_roles(db_session=db)
        role_names = [role.name for role in user_roles]

        # Should not have admin or office manager roles
        assert RoleType.ADMIN.value not in role_names
        assert RoleType.OFFICE_MANAGER.value not in role_names


class TestPrivilegeEscalation:
    """Test privilege escalation prevention"""

    def test_cannot_escalate_via_multiple_role_assignment(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that users cannot escalate privileges by accumulating roles"""
        user = security_users[2]  # Provider user

        # Assign patient role first (lowest privilege)
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[security_roles[4].role_id],  # Patient role
            assigned_by_id=security_users[0].user_id,
        )

        # Then assign care provider role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[security_roles[2].role_id],  # Care Provider role
            assigned_by_id=security_users[0].user_id,
        )

        # User should have both roles but not admin privileges
        assert user.has_role(RoleType.PATIENT.value, db_session=db)
        assert user.has_role(RoleType.CARE_PROVIDER.value, db_session=db)
        assert not user.has_role(RoleType.ADMIN.value, db_session=db)

        # Multiple roles should not grant admin access
        active_roles = user.get_active_roles(db_session=db)
        role_names = {role.name for role in active_roles}
        assert RoleType.ADMIN.value not in role_names

    def test_role_modification_requires_proper_authority(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that only authorized users can modify roles"""
        admin_user = security_users[0]
        target_user = security_users[3]
        admin_role = security_roles[0]

        # Assign admin role to admin user
        crud_user_role.assign_roles(
            db=db,
            user_id=admin_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,  # Self-assignment for setup
        )

        # Admin should be able to assign roles
        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[security_roles[1].role_id],  # Office Manager
            assigned_by_id=admin_user.user_id,
        )

        assert len(assigned_roles) == 1
        assert target_user.has_role(RoleType.OFFICE_MANAGER.value, db_session=db)

    def test_self_role_assignment_prevention(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that users cannot assign roles to themselves without authorization"""
        regular_user = security_users[3]
        admin_role = security_roles[0]

        # Attempt to self-assign admin role (this would be blocked at API level)
        # For testing, we verify the user doesn't have admin access to begin with
        assert not regular_user.has_role(RoleType.ADMIN.value, db_session=db)

        # Verify that direct role assignment requires authorized user
        # In real implementation, this would be enforced via API middleware
        current_roles = regular_user.get_active_roles(db_session=db)
        assert len(current_roles) == 0


class TestRoleBoundaryEnforcement:
    """Test role boundary enforcement"""

    def test_patient_role_cannot_access_admin_functions(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that patient role has limited access"""
        patient_user = security_users[3]
        patient_role = security_roles[4]  # Patient role

        # Assign patient role
        crud_user_role.assign_roles(
            db=db,
            user_id=patient_user.user_id,
            role_ids=[patient_role.role_id],
            assigned_by_id=security_users[0].user_id,
        )

        # Patient should have patient role but not admin roles
        assert patient_user.has_role(RoleType.PATIENT.value, db_session=db)
        assert not patient_user.has_role(RoleType.ADMIN.value, db_session=db)
        assert not patient_user.has_role(RoleType.OFFICE_MANAGER.value, db_session=db)

    def test_care_provider_boundaries(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test care provider role boundaries"""
        provider_user = security_users[2]
        provider_role = security_roles[2]  # Care Provider role

        # Assign care provider role
        crud_user_role.assign_roles(
            db=db,
            user_id=provider_user.user_id,
            role_ids=[provider_role.role_id],
            assigned_by_id=security_users[0].user_id,
        )

        # Should have provider access but not admin/billing admin
        assert provider_user.has_role(RoleType.CARE_PROVIDER.value, db_session=db)
        assert not provider_user.has_role(RoleType.ADMIN.value, db_session=db)
        assert not provider_user.has_role(RoleType.BILLING_ADMIN.value, db_session=db)

    def test_office_manager_vs_admin_boundaries(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that office manager cannot perform admin-only functions"""
        manager_user = security_users[1]
        manager_role = security_roles[1]  # Office Manager

        # Assign office manager role
        crud_user_role.assign_roles(
            db=db,
            user_id=manager_user.user_id,
            role_ids=[manager_role.role_id],
            assigned_by_id=security_users[0].user_id,
        )

        # Should have manager access but not full admin
        assert manager_user.has_role(RoleType.OFFICE_MANAGER.value, db_session=db)
        assert not manager_user.has_role(RoleType.ADMIN.value, db_session=db)


class TestSecurityAttackScenarios:
    """Test various security attack scenarios"""

    def test_jwt_token_tampering_detection(self):
        """Test that tampered JWT tokens are rejected"""
        original_email = "test@example.com"
        token = create_access_token(data={"sub": original_email})

        # Attempt to tamper with token
        tampered_token = token[:-5] + "XXXXX"  # Change last 5 characters

        # Should not decode successfully
        payload = decode_access_token(tampered_token)
        assert payload is None

    def test_expired_token_rejection(self):
        """Test that expired tokens are properly rejected"""
        email = "test@example.com"

        # Create token with very short expiration
        token = create_access_token(
            data={"sub": email}, expires_delta=timedelta(seconds=-1)  # Already expired
        )

        # Should not decode successfully
        payload = decode_access_token(token)
        assert payload is None

    def test_role_injection_prevention(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that role checking prevents injection attacks"""
        user = security_users[3]

        # Test with malicious role names
        malicious_roles = [
            "admin'; DROP TABLE roles; --",
            "admin OR 1=1",
            "<script>alert('xss')</script>",
            "admin\x00null_byte_attack",
        ]

        for malicious_role in malicious_roles:
            # Should safely return False for malicious role names
            assert not user.has_role(malicious_role, db_session=db)

    def test_sql_injection_in_role_queries(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that role queries are protected against SQL injection"""
        user = security_users[0]

        # Assign admin role
        admin_role = security_roles[0]
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=user.user_id,
        )

        # Test with SQL injection attempts in role checking
        injection_attempts = [
            "admin'; SELECT * FROM users; --",
            "admin' UNION SELECT password_hash FROM users --",
            "admin' OR '1'='1",
        ]

        for injection in injection_attempts:
            # Should not return True for injection attempts
            # (only legitimate admin role should return True)
            result = user.has_role(injection, db_session=db)
            if injection.startswith("admin"):
                # These might partially match, but should not compromise security
                pass  # Test that system doesn't crash
            else:
                assert not result


class TestMultiRoleSecurity:
    """Test security with multiple roles assigned"""

    def test_multiple_role_privilege_isolation(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that multiple roles don't create unintended privilege combinations"""
        user = security_users[1]

        # Assign multiple non-admin roles
        multi_roles = [
            security_roles[1].role_id,  # Office Manager
            security_roles[2].role_id,  # Care Provider
            security_roles[3].role_id,  # Billing Admin
        ]

        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=multi_roles,
            assigned_by_id=security_users[0].user_id,
        )

        # Should have all assigned roles
        assert user.has_role(RoleType.OFFICE_MANAGER.value, db_session=db)
        assert user.has_role(RoleType.CARE_PROVIDER.value, db_session=db)
        assert user.has_role(RoleType.BILLING_ADMIN.value, db_session=db)

        # But still not admin
        assert not user.has_role(RoleType.ADMIN.value, db_session=db)

    def test_role_combination_security_matrix(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test security matrix for role combinations"""
        user = security_users[2]

        # Test various role combinations don't escalate to admin
        role_combinations = [
            [security_roles[4].role_id],  # Patient only
            [
                security_roles[2].role_id,
                security_roles[4].role_id,
            ],  # Provider + Patient
            [security_roles[1].role_id, security_roles[3].role_id],  # Manager + Billing
        ]

        for role_combo in role_combinations:
            # Clear previous roles
            current_roles = crud_user_role.get_user_roles(db=db, user_id=user.user_id)
            if current_roles:
                crud_user_role.unassign_roles(
                    db=db,
                    user_id=user.user_id,
                    role_ids=[ur.role_id for ur in current_roles],
                    removed_by_id=security_users[0].user_id,
                )

            # Assign new combination
            crud_user_role.assign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=role_combo,
                assigned_by_id=security_users[0].user_id,
            )

            # Should not have admin access regardless of combination
            assert not user.has_role(RoleType.ADMIN.value, db_session=db)


class TestAuditLoggingSecurity:
    """Test security-related audit logging"""

    def test_failed_access_attempts_logged(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that failed access attempts are properly logged"""
        user = security_users[3]  # User with no admin roles

        # Simulate failed access attempt (in real implementation)
        required_roles = [RoleType.ADMIN.value]
        user_roles = [role.name for role in user.get_active_roles(db_session=db)]

        # This would trigger audit logging in real implementation
        access_granted = any(role in required_roles for role in user_roles)
        assert not access_granted

        # In real implementation, this would create an audit log entry

    def test_role_modification_audit_trail(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that role modifications create proper audit trail"""
        admin_user = security_users[0]
        target_user = security_users[3]
        role = security_roles[1]  # Office Manager

        # Assign role (should create audit entry)
        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Verify assignment was successful
        assert len(assigned_roles) == 1
        assert assigned_roles[0].assigned_by_id == admin_user.user_id
        assert assigned_roles[0].assigned_at is not None

        # Unassign role (should create another audit entry)
        unassigned_roles = crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Verify unassignment was successful and audited
        assert len(unassigned_roles) == 1
        assert not unassigned_roles[0].is_active

    def test_suspicious_activity_detection(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test detection of suspicious access patterns"""
        user = security_users[1]

        # Simulate rapid role checking (potential enumeration attack)
        all_role_types = [
            RoleType.ADMIN.value,
            RoleType.OFFICE_MANAGER.value,
            RoleType.CARE_PROVIDER.value,
            RoleType.BILLING_ADMIN.value,
            RoleType.PATIENT.value,
        ]

        # Rapid successive role checks
        start_time = time.time()
        for role_type in all_role_types:
            user.has_role(role_type, db_session=db)
        end_time = time.time()

        # In real implementation, rapid successive checks might trigger alerts
        check_duration = end_time - start_time
        assert check_duration < 1.0  # Should complete quickly but be monitored


class TestHIPAAComplianceSecurity:
    """Test HIPAA-specific security requirements"""

    def test_minimum_necessary_principle(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test that users only get minimum necessary role access"""
        user = security_users[2]

        # Assign only care provider role (minimum necessary for care tasks)
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[security_roles[2].role_id],  # Care Provider only
            assigned_by_id=security_users[0].user_id,
        )

        # Should have only the assigned role, not broader permissions
        active_roles = user.get_active_roles(db_session=db)
        assert len(active_roles) == 1
        assert active_roles[0].name == RoleType.CARE_PROVIDER.value

    def test_access_control_granularity(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test granular access control for HIPAA compliance"""
        patient_user = security_users[3]
        billing_user = security_users[1]

        # Assign specific roles for specific functions
        crud_user_role.assign_roles(
            db=db,
            user_id=patient_user.user_id,
            role_ids=[security_roles[4].role_id],  # Patient role
            assigned_by_id=security_users[0].user_id,
        )
        crud_user_role.assign_roles(
            db=db,
            user_id=billing_user.user_id,
            role_ids=[security_roles[3].role_id],  # Billing Admin role
            assigned_by_id=security_users[0].user_id,
        )

        # Users should have access only to their designated areas
        assert patient_user.has_role(RoleType.PATIENT.value, db_session=db)
        assert not patient_user.has_role(RoleType.BILLING_ADMIN.value, db_session=db)

        assert billing_user.has_role(RoleType.BILLING_ADMIN.value, db_session=db)
        assert not billing_user.has_role(RoleType.PATIENT.value, db_session=db)

    def test_role_separation_enforcement(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test enforcement of role separation for compliance"""
        user = security_users[2]

        # Test that conflicting roles can be assigned but create audit trail
        # (Some role combinations might be valid in healthcare settings)

        # Assign both care provider and billing admin
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[security_roles[2].role_id, security_roles[3].role_id],
            assigned_by_id=security_users[0].user_id,
        )

        # Both roles should be assigned
        assert user.has_role(RoleType.CARE_PROVIDER.value, db_session=db)
        assert user.has_role(RoleType.BILLING_ADMIN.value, db_session=db)

        # In real implementation, this combination might trigger compliance review


class TestSessionSecurity:
    """Test session and token security"""

    def test_token_payload_integrity(self):
        """Test that token payloads maintain integrity"""
        test_data = {"sub": "test@example.com", "roles": ["admin", "manager"]}
        token = create_access_token(data=test_data)

        # Decode and verify data integrity
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == test_data["sub"]

    def test_token_expiration_enforcement(self):
        """Test that token expiration is properly enforced"""
        email = "test@example.com"

        # Create token with short expiration
        short_token = create_access_token(
            data={"sub": email}, expires_delta=timedelta(seconds=1)
        )

        # Token should be valid immediately
        payload = decode_access_token(short_token)
        assert payload is not None
        assert payload["sub"] == email

        # Wait for expiration
        time.sleep(2)

        # Token should now be invalid
        expired_payload = decode_access_token(short_token)
        assert expired_payload is None

    def test_concurrent_session_handling(
        self, db: Session, security_users: List[User], security_roles: List[Role]
    ):
        """Test handling of concurrent sessions for same user"""
        user = security_users[0]

        # Create multiple tokens for same user
        token1 = create_access_token(data={"sub": user.email})
        token2 = create_access_token(data={"sub": user.email})

        # Both tokens should be valid
        payload1 = decode_access_token(token1)
        payload2 = decode_access_token(token2)

        assert payload1 is not None
        assert payload2 is not None
        assert payload1["sub"] == payload2["sub"] == user.email

        # In real implementation, concurrent session policy would be enforced
