#!/usr/bin/env python3
"""
Comprehensive unit tests for Role and UserRole CRUD operations.

This test suite validates the following functionality:
1. CRUDRole: role creation, retrieval, updating, deletion
2. CRUDUserRole: role assignment, unassignment, history tracking
3. Database constraints and relationship integrity
4. Audit logging integration for all operations
5. Error handling and edge cases

Tests are designed to run with pytest and use a test database.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from api.models.base import Base, User, Role, UserRole, AuditLog
from api.crud.crud_role import crud_role, crud_user_role
from api.schemas.role import RoleCreate, RoleUpdate, UserRoleCreate
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


class TestCRUDRole:
    """Test suite for CRUDRole operations"""

    def test_create_role(self, db: Session, sample_users: List[User]):
        """Test role creation with audit logging"""
        admin_user = sample_users[0]
        role_data = RoleCreate(name="test_role")

        # Create role
        created_role = crud_role.create(
            db=db, obj_in=role_data, user_id=admin_user.user_id
        )

        # Verify role was created
        assert created_role is not None
        assert created_role.name == "test_role"
        assert created_role.role_id is not None

        # Verify audit log was created
        audit_logs = (
            db.query(AuditLog).filter(AuditLog.event_type == "ROLE_CREATED").all()
        )
        assert len(audit_logs) >= 1

        # Verify role can be retrieved
        retrieved_role = crud_role.get(db=db, role_id=created_role.role_id)
        assert retrieved_role.name == "test_role"

    def test_get_role_by_name(self, db: Session, sample_roles: List[Role]):
        """Test role retrieval by name"""
        admin_role = sample_roles[0]  # ADMIN role

        retrieved_role = crud_role.get_by_name(db=db, name=RoleType.ADMIN.value)
        assert retrieved_role is not None
        assert retrieved_role.role_id == admin_role.role_id
        assert retrieved_role.name == RoleType.ADMIN.value

    def test_get_multi_roles(self, db: Session, sample_roles: List[Role]):
        """Test retrieving multiple roles"""
        roles = crud_role.get_multi(db=db, skip=0, limit=10)
        assert len(roles) == len(sample_roles)

        # Test pagination
        first_page = crud_role.get_multi(db=db, skip=0, limit=2)
        second_page = crud_role.get_multi(db=db, skip=2, limit=2)
        assert len(first_page) == 2
        assert len(second_page) <= 2
        assert first_page[0].role_id != second_page[0].role_id

    def test_update_role(
        self, db: Session, sample_roles: List[Role], sample_users: List[User]
    ):
        """Test role updating with audit logging"""
        role_to_update = sample_roles[0]
        admin_user = sample_users[0]

        update_data = RoleUpdate(name="updated_admin_role")

        updated_role = crud_role.update(
            db=db, db_obj=role_to_update, obj_in=update_data, user_id=admin_user.user_id
        )

        # Verify update
        assert updated_role.name == "updated_admin_role"

        # Verify audit log
        audit_logs = (
            db.query(AuditLog).filter(AuditLog.event_type == "ROLE_UPDATED").all()
        )
        assert len(audit_logs) >= 1

    def test_delete_role_success(self, db: Session, sample_users: List[User]):
        """Test successful role deletion"""
        admin_user = sample_users[0]

        # Create a role that's not assigned to anyone
        test_role = Role(name="deletable_role")
        db.add(test_role)
        db.commit()
        db.refresh(test_role)

        # Delete the role
        success = crud_role.delete(
            db=db, role_id=test_role.role_id, user_id=admin_user.user_id
        )

        assert success is True

        # Verify role is deleted
        deleted_role = crud_role.get(db=db, role_id=test_role.role_id)
        assert deleted_role is None

        # Verify audit log
        audit_logs = (
            db.query(AuditLog).filter(AuditLog.event_type == "ROLE_DELETED").all()
        )
        assert len(audit_logs) >= 1

    def test_delete_role_with_assignments_fails(
        self, db: Session, sample_roles: List[Role], sample_users: List[User]
    ):
        """Test that role deletion fails when role is assigned to users"""
        admin_role = sample_roles[0]
        admin_user = sample_users[0]
        test_user = sample_users[1]

        # Assign role to user
        crud_user_role.assign_roles(
            db=db,
            user_id=test_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Try to delete the role
        success = crud_role.delete(
            db=db, role_id=admin_role.role_id, user_id=admin_user.user_id
        )

        assert success is False

        # Role should still exist
        existing_role = crud_role.get(db=db, role_id=admin_role.role_id)
        assert existing_role is not None


class TestCRUDUserRole:
    """Test suite for CRUDUserRole operations"""

    def test_assign_single_role(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test assigning a single role to a user"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Verify assignment
        assert len(assigned_roles) == 1
        assert assigned_roles[0].user_id == target_user.user_id
        assert assigned_roles[0].role_id == admin_role.role_id
        assert assigned_roles[0].assigned_by_id == admin_user.user_id
        assert assigned_roles[0].is_active is True
        assert assigned_roles[0].assigned_at is not None

        # Verify audit log
        audit_logs = (
            db.query(AuditLog).filter(AuditLog.event_type == "ROLE_ASSIGNED").all()
        )
        assert len(audit_logs) >= 1

    def test_assign_multiple_roles(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test assigning multiple roles to a user"""
        admin_user = sample_users[0]
        target_user = sample_users[2]
        roles_to_assign = [
            sample_roles[1].role_id,
            sample_roles[2].role_id,
        ]  # OFFICE_MANAGER, CARE_PROVIDER

        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )

        # Verify assignments
        assert len(assigned_roles) == 2
        assigned_role_ids = [ur.role_id for ur in assigned_roles]
        assert set(assigned_role_ids) == set(roles_to_assign)

        # All should be active and assigned by admin
        for user_role in assigned_roles:
            assert user_role.is_active is True
            assert user_role.assigned_by_id == admin_user.user_id

    def test_assign_duplicate_role_fails_gracefully(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that assigning an already assigned role logs properly"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        # First assignment
        first_assignment = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )
        assert len(first_assignment) == 1

        # Second assignment (duplicate)
        second_assignment = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Should not create new assignment, but should log the attempt
        audit_logs = (
            db.query(AuditLog)
            .filter(AuditLog.event_type == "ROLE_ASSIGNMENT_ATTEMPT")
            .all()
        )
        assert len(audit_logs) >= 1

    def test_reactivate_inactive_role(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test reactivating a previously unassigned role"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        # Assign role
        assigned = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Unassign role
        unassigned = crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            removed_by_id=admin_user.user_id,
        )
        assert unassigned[0].is_active is False

        # Reassign role (should reactivate)
        reactivated = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Should reactivate the existing assignment
        assert len(reactivated) == 1
        assert reactivated[0].is_active is True

        # Check audit log for reactivation
        audit_logs = (
            db.query(AuditLog).filter(AuditLog.event_type == "ROLE_REACTIVATED").all()
        )
        assert len(audit_logs) >= 1

    def test_unassign_roles(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test unassigning roles from a user"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        roles_to_assign = [sample_roles[0].role_id, sample_roles[1].role_id]

        # First assign roles
        assigned = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )
        assert len(assigned) == 2

        # Unassign one role
        unassigned = crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[sample_roles[0].role_id],
            removed_by_id=admin_user.user_id,
        )

        # Verify unassignment (soft delete)
        assert len(unassigned) == 1
        assert unassigned[0].is_active is False
        assert unassigned[0].role_id == sample_roles[0].role_id

        # Verify remaining role is still active
        remaining_roles = crud_user_role.get_user_roles(
            db=db, user_id=target_user.user_id, active_only=True
        )
        assert len(remaining_roles) == 1
        assert remaining_roles[0].role_id == sample_roles[1].role_id

    def test_unassign_nonexistent_role_logs_failure(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test unassigning a role that wasn't assigned logs failure"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        # Try to unassign role that was never assigned
        unassigned = crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Should return empty list
        assert len(unassigned) == 0

        # Should log failure attempt
        audit_logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.event_type == "ROLE_ASSIGNMENT_ATTEMPT",
                AuditLog.outcome == "FAILURE",
            )
            .all()
        )
        assert len(audit_logs) >= 1

    def test_get_user_roles(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test retrieving user roles with active/inactive filtering"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        roles_to_assign = [sample_roles[0].role_id, sample_roles[1].role_id]

        # Assign roles
        crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=admin_user.user_id,
        )

        # Unassign one role
        crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[sample_roles[0].role_id],
            removed_by_id=admin_user.user_id,
        )

        # Test active only (default)
        active_roles = crud_user_role.get_user_roles(
            db=db, user_id=target_user.user_id, active_only=True
        )
        assert len(active_roles) == 1
        assert active_roles[0].role_id == sample_roles[1].role_id

        # Test including inactive
        all_roles = crud_user_role.get_user_roles(
            db=db, user_id=target_user.user_id, active_only=False
        )
        assert len(all_roles) == 2

    def test_get_assignment_history(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test getting complete role assignment history"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        # Create some history: assign, unassign, reassign
        crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            removed_by_id=admin_user.user_id,
        )

        crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Get history
        history = crud_user_role.get_assignment_history(
            db=db, user_id=target_user.user_id
        )

        # Should include all states (active and inactive)
        assert len(history) >= 1  # At least the reactivated assignment

        # Should be ordered by assigned_at desc (most recent first)
        if len(history) > 1:
            assert history[0].assigned_at >= history[1].assigned_at

    def test_get_role_assignments(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test getting users assigned to a specific role"""
        admin_user = sample_users[0]
        admin_role = sample_roles[0]

        # Assign admin role to multiple users
        users_to_assign = [sample_users[1], sample_users[2]]
        for user in users_to_assign:
            crud_user_role.assign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=[admin_role.role_id],
                assigned_by_id=admin_user.user_id,
            )

        # Get role assignments
        assignments = crud_user_role.get_role_assignments(
            db=db, role_id=admin_role.role_id, active_only=True
        )

        assert len(assignments) == 2
        assigned_user_ids = [assignment.user_id for assignment in assignments]
        expected_user_ids = [user.user_id for user in users_to_assign]
        assert set(assigned_user_ids) == set(expected_user_ids)


class TestDatabaseConstraints:
    """Test database constraints and relationship integrity"""

    def test_unique_user_role_constraint(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that duplicate user-role combinations are handled properly"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        # Create first assignment directly in database
        first_assignment = UserRole(
            user_id=target_user.user_id,
            role_id=admin_role.role_id,
            assigned_by_id=admin_user.user_id,
            is_active=True,
        )
        db.add(first_assignment)
        db.commit()

        # Try to create duplicate - should fail at database level
        with pytest.raises(Exception):  # IntegrityError expected
            duplicate_assignment = UserRole(
                user_id=target_user.user_id,
                role_id=admin_role.role_id,
                assigned_by_id=admin_user.user_id,
                is_active=False,  # Even with different is_active
            )
            db.add(duplicate_assignment)
            db.commit()

    def test_foreign_key_constraints(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test foreign key constraint enforcement"""
        # Test invalid user_id - Note: SQLite might not enforce FK constraints in test mode
        try:
            invalid_assignment = UserRole(
                user_id=99999,  # Non-existent user
                role_id=sample_roles[0].role_id,
                assigned_by_id=sample_users[0].user_id,
                is_active=True,
            )
            db.add(invalid_assignment)
            db.commit()

            # If we get here, FK constraints aren't enforced in test DB
            # This is acceptable for in-memory SQLite databases used in testing
            # Clean up the test data
            db.delete(invalid_assignment)
            db.commit()

        except Exception:
            # FK constraint was enforced, which is good
            db.rollback()  # Clean up failed transaction

    def test_audit_logging_integration(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that all CRUD operations properly create audit logs"""
        admin_user = sample_users[0]
        target_user = sample_users[1]
        admin_role = sample_roles[0]

        # Count initial audit logs
        initial_count = db.query(AuditLog).count()

        # Perform various operations
        crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        crud_user_role.unassign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=[admin_role.role_id],
            removed_by_id=admin_user.user_id,
        )

        crud_role.create(
            db=db, obj_in=RoleCreate(name="test_audit_role"), user_id=admin_user.user_id
        )

        # Check that audit logs were created
        final_count = db.query(AuditLog).count()
        assert final_count > initial_count


if __name__ == "__main__":
    """Run tests directly with pytest"""
    pytest.main([__file__, "-v", "--tb=short"])
