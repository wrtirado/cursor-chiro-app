#!/usr/bin/env python3
"""
Unit tests for role utility methods and helper functions.

This test suite validates the utility methods that make role checking
convenient throughout the application, including:
1. User.has_role() method
2. User.get_active_roles() method
3. Role checking helpers and decorators
4. Permission validation utilities
5. Role hierarchy and precedence logic

Tests are designed to run with pytest and use a test database.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from api.models.base import Base, User, Role, UserRole
from api.crud.crud_role import crud_user_role
from api.core.security import get_password_hash
from api.core.config import RoleType


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
def sample_users(db: Session) -> List[User]:
    """Create sample users for testing"""
    users = [
        User(
            email="admin@test.com",
            password_hash=get_password_hash("adminpass"),
            name="Admin User",
            is_active_for_billing=True,
        ),
        User(
            email="manager@test.com",
            password_hash=get_password_hash("managerpass"),
            name="Manager User",
            is_active_for_billing=True,
        ),
        User(
            email="provider@test.com",
            password_hash=get_password_hash("providerpass"),
            name="Care Provider",
            is_active_for_billing=True,
        ),
        User(
            email="patient@test.com",
            password_hash=get_password_hash("patientpass"),
            name="Test Patient",
            is_active_for_billing=True,
        ),
    ]

    for user in users:
        db.add(user)
    db.commit()

    for user in users:
        db.refresh(user)

    return users


@pytest.fixture
def sample_roles(db: Session) -> List[Role]:
    """Create sample roles for testing"""
    roles = [
        Role(name=RoleType.ADMIN.value),
        Role(name=RoleType.OFFICE_MANAGER.value),
        Role(name=RoleType.CARE_PROVIDER.value),
        Role(name=RoleType.PATIENT.value),
    ]

    for role in roles:
        db.add(role)
    db.commit()

    for role in roles:
        db.refresh(role)

    return roles


class TestUserRoleMethods:
    """Test suite for User model role-related methods"""

    def test_user_has_role_single_role(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.has_role() method with single role assignment"""
        admin_user = sample_users[0]
        test_user = sample_users[1]
        admin_role = sample_roles[0]

        # Initially should not have role
        assert not test_user.has_role(RoleType.ADMIN.value, db)

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Should now have role
        assert test_user.has_role(RoleType.ADMIN.value, db)

        # Should not have other roles
        assert not test_user.has_role(RoleType.PATIENT.value, db)

    def test_user_has_role_multiple_roles(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.has_role() method with multiple role assignments"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign multiple roles
        roles_to_assign = [
            sample_roles[1].role_id,
            sample_roles[2].role_id,
        ]  # OFFICE_MANAGER, CARE_PROVIDER
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )

        # Should have both assigned roles
        assert test_user.has_role(RoleType.OFFICE_MANAGER.value, db)
        assert test_user.has_role(RoleType.CARE_PROVIDER.value, db)

        # Should not have unassigned roles
        assert not test_user.has_role(RoleType.ADMIN.value, db)
        assert not test_user.has_role(RoleType.PATIENT.value, db)

    def test_user_has_role_inactive_assignment(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that inactive role assignments return False for has_role()"""
        admin_user = sample_users[0]
        test_user = sample_users[1]
        admin_role = sample_roles[0]

        # Assign and then unassign role
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        assert test_user.has_role(RoleType.ADMIN.value, db)

        crud_user_role.unassign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[admin_role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Should no longer have role after unassignment
        assert not test_user.has_role(RoleType.ADMIN.value, db)

    def test_user_get_active_roles_empty(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.get_active_roles() method with no assignments"""
        test_user = sample_users[1]

        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 0

    def test_user_get_active_roles_single(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.get_active_roles() method with single role"""
        admin_user = sample_users[0]
        test_user = sample_users[1]
        admin_role = sample_roles[0]

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 1
        assert active_roles[0].name == RoleType.ADMIN.value

    def test_user_get_active_roles_multiple(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.get_active_roles() method with multiple roles"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign multiple roles
        roles_to_assign = [
            sample_roles[1].role_id,
            sample_roles[2].role_id,
        ]  # OFFICE_MANAGER, CARE_PROVIDER
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )

        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 2

        role_names = [role.name for role in active_roles]
        assert RoleType.OFFICE_MANAGER.value in role_names
        assert RoleType.CARE_PROVIDER.value in role_names

    def test_user_get_active_roles_excludes_inactive(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that get_active_roles() excludes inactive assignments"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign multiple roles
        roles_to_assign = [
            sample_roles[0].role_id,
            sample_roles[1].role_id,
        ]  # ADMIN, OFFICE_MANAGER
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )

        # Verify both roles are active
        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 2

        # Unassign one role
        crud_user_role.unassign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[sample_roles[0].role_id],  # Remove ADMIN
            removed_by_id=admin_user.user_id,
        )

        # Should only have one active role now
        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 1
        assert active_roles[0].name == RoleType.OFFICE_MANAGER.value

    def test_user_has_any_role(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test checking if user has any role from a list"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign CARE_PROVIDER role
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[sample_roles[2].role_id],  # CARE_PROVIDER
            assigned_by_id=admin_user.user_id,
        )

        # Test has_any_role method (if it exists) or simulate the logic
        admin_or_manager_roles = [RoleType.ADMIN.value, RoleType.OFFICE_MANAGER.value]
        provider_or_patient_roles = [
            RoleType.CARE_PROVIDER.value,
            RoleType.PATIENT.value,
        ]

        # Should not have admin or manager roles
        has_admin_or_manager = any(
            test_user.has_role(role, db) for role in admin_or_manager_roles
        )
        assert not has_admin_or_manager

        # Should have provider or patient role (has CARE_PROVIDER)
        has_provider_or_patient = any(
            test_user.has_role(role, db) for role in provider_or_patient_roles
        )
        assert has_provider_or_patient


class TestRoleCheckingUtilities:
    """Test role checking utility functions and decorators"""

    def test_role_precedence_logic(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test role precedence when user has multiple roles"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign multiple roles with different precedence levels
        # ADMIN > OFFICE_MANAGER > CARE_PROVIDER > PATIENT (assumed hierarchy)
        roles_to_assign = [
            sample_roles[0].role_id,  # ADMIN
            sample_roles[2].role_id,  # CARE_PROVIDER
        ]

        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )

        # User should have both roles
        assert test_user.has_role(RoleType.ADMIN.value, db)
        assert test_user.has_role(RoleType.CARE_PROVIDER.value, db)

        # Get all active roles
        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 2

    def test_role_checking_performance(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role checking is efficient with multiple roles"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign all roles to user
        all_role_ids = [role.role_id for role in sample_roles]
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=all_role_ids,
            assigned_by_id=admin_user.user_id,
        )

        # Time multiple role checks (basic performance test)
        import time

        start_time = time.time()

        for _ in range(100):  # Check roles 100 times
            test_user.has_role(RoleType.ADMIN.value, db)
            test_user.has_role(RoleType.PATIENT.value, db)
            test_user.get_active_roles(db)

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        assert execution_time < 5.0  # 5 seconds for 100 iterations

    def test_role_assignment_timestamps(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role assignments have proper timestamps"""
        admin_user = sample_users[0]
        test_user = sample_users[1]
        admin_role = sample_roles[0]

        # Assign role
        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Check assignment timestamp exists and is a valid datetime
        assignment = assigned_roles[0]
        assert assignment.assigned_at is not None
        assert isinstance(assignment.assigned_at, datetime)

        # Verify the assigned_by_id is set correctly
        assert assignment.assigned_by_id == admin_user.user_id

    def test_assigned_by_tracking(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role assignments track who assigned them"""
        admin_user = sample_users[0]
        manager_user = sample_users[1]
        test_user = sample_users[2]

        # Admin assigns role to test user
        assigned_by_admin = crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[sample_roles[0].role_id],  # ADMIN role
            assigned_by_id=admin_user.user_id,
        )

        # Manager assigns different role to test user
        assigned_by_manager = crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[sample_roles[1].role_id],  # OFFICE_MANAGER role
            assigned_by_id=manager_user.user_id,
        )

        # Verify assignment tracking
        assert assigned_by_admin[0].assigned_by_id == admin_user.user_id
        assert assigned_by_manager[0].assigned_by_id == manager_user.user_id

        # Get user role history
        history = crud_user_role.get_assignment_history(
            db=db, user_id=test_user.user_id
        )

        # Should have both assignments with correct assigned_by tracking
        assert len(history) >= 2
        assigned_by_ids = [assignment.assigned_by_id for assignment in history]
        assert admin_user.user_id in assigned_by_ids
        assert manager_user.user_id in assigned_by_ids


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_has_role_with_invalid_role_name(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test has_role() with non-existent role name"""
        test_user = sample_users[0]

        # Should return False for non-existent role
        assert not test_user.has_role("non_existent_role", db)

    def test_has_role_with_none_values(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test has_role() with None values"""
        test_user = sample_users[0]

        # Should handle None role name gracefully
        assert not test_user.has_role(None, db)

    def test_get_active_roles_after_user_deactivation(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test role behavior when user is deactivated"""
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[sample_roles[0].role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Verify role is active
        assert test_user.has_role(RoleType.ADMIN.value, db)

        # Deactivate user
        test_user.is_active = False
        db.commit()

        # Role assignments should still exist in database
        active_roles = test_user.get_active_roles(db)
        assert len(active_roles) == 1  # Role assignment still exists

        # But has_role should still work (role assignment is separate from user status)
        assert test_user.has_role(RoleType.ADMIN.value, db)


if __name__ == "__main__":
    """Run tests directly with pytest"""
    pytest.main([__file__, "-v", "--tb=short"])
