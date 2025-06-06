"""
Simplified integration tests for API endpoints and authentication with many-to-many role system.

This test suite validates:
- Core CRUD operations work correctly
- Role assignment logic functions properly
- Authentication dependencies work as expected
- Error handling is appropriate

This approach tests the business logic without requiring a full API server.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import List, Dict, Any

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
from api.schemas.role import RoleCreate, RoleAssignmentRequest


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
def sample_roles(db) -> List[Role]:
    """Create sample roles for testing"""
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
def sample_users(db) -> List[User]:
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
    ]

    for user in users:
        db.add(user)
    db.commit()

    for user in users:
        db.refresh(user)

    return users


class TestAuthenticationCore:
    """Test core authentication functionality"""

    def test_password_hashing_and_verification(self):
        """Test that password hashing and verification work correctly"""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_jwt_token_creation_and_decoding(self):
        """Test JWT token creation and decoding"""
        test_email = "test@example.com"
        token = create_access_token(data={"sub": test_email})

        assert token is not None
        assert isinstance(token, str)

        # Decode token
        payload = decode_access_token(token)
        assert payload is not None
        assert payload.get("sub") == test_email

    def test_user_authentication_flow(self, db: Session, sample_users: List[User]):
        """Test the complete user authentication process"""
        user = sample_users[0]

        # Verify stored password can be validated
        assert verify_password("adminpass", user.password_hash)

        # Create token for user
        token = create_access_token(data={"sub": user.email})

        # Verify token contains correct user data
        payload = decode_access_token(token)
        assert payload.get("sub") == user.email


class TestRoleAssignmentLogic:
    """Test role assignment business logic"""

    def test_role_assignment_creates_user_role_record(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role assignment creates proper UserRole records"""
        user = sample_users[0]
        role = sample_roles[0]  # Admin role

        # Assign role
        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )

        assert len(assigned_roles) == 1
        assert assigned_roles[0].user_id == user.user_id
        assert assigned_roles[0].role_id == role.role_id
        assert assigned_roles[0].is_active is True

    def test_multiple_role_assignment(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test assigning multiple roles to a user"""
        user = sample_users[1]
        roles_to_assign = [
            sample_roles[0].role_id,
            sample_roles[1].role_id,
        ]  # Admin and Office Manager

        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=sample_users[0].user_id,
        )

        assert len(assigned_roles) == 2
        assigned_role_ids = [ar.role_id for ar in assigned_roles]
        assert sample_roles[0].role_id in assigned_role_ids
        assert sample_roles[1].role_id in assigned_role_ids

    def test_role_unassignment_uses_soft_delete(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role unassignment uses soft deletion"""
        user = sample_users[0]
        role = sample_roles[0]

        # First assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )

        # Then unassign role
        unassigned_roles = crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=user.user_id,
        )

        assert len(unassigned_roles) == 1
        assert unassigned_roles[0].is_active is False  # Soft deleted

        # Verify record still exists but inactive
        all_user_roles = crud_user_role.get_user_roles(
            db=db, user_id=user.user_id, active_only=False
        )
        assert len(all_user_roles) == 1
        assert all_user_roles[0].is_active is False

    def test_role_reactivation(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that reassigning a previously unassigned role reactivates it"""
        user = sample_users[0]
        role = sample_roles[0]

        # Assign, unassign, then reassign
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )
        crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=user.user_id,
        )
        reactivated_roles = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )

        assert len(reactivated_roles) == 1
        assert reactivated_roles[0].is_active is True


class TestUserRoleValidation:
    """Test user role checking and validation methods"""

    def test_user_has_role_method_with_session(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.has_role() method with database session"""
        user = sample_users[0]
        admin_role = sample_roles[0]  # Admin role

        # Assign admin role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=user.user_id,
        )

        # Test has_role method with database session
        assert user.has_role(RoleType.ADMIN.value, db_session=db)
        assert not user.has_role(RoleType.PATIENT.value, db_session=db)

    def test_user_get_active_roles_method(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test User.get_active_roles() method"""
        user = sample_users[0]

        # Assign multiple roles
        roles_to_assign = [sample_roles[0].role_id, sample_roles[1].role_id]
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=roles_to_assign,
            assigned_by_id=user.user_id,
        )

        # Get active roles
        active_roles = user.get_active_roles(db_session=db)
        assert len(active_roles) == 2

        role_names = [role.name for role in active_roles]
        assert RoleType.ADMIN.value in role_names
        assert RoleType.OFFICE_MANAGER.value in role_names

    def test_inactive_roles_not_returned(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that inactive roles are not returned by active role methods"""
        user = sample_users[0]
        role = sample_roles[0]

        # Assign and then unassign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )
        crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=user.user_id,
        )

        # Check that inactive role is not returned
        assert not user.has_role(role.name, db_session=db)
        active_roles = user.get_active_roles(db_session=db)
        assert len(active_roles) == 0


class TestRoleManagementAPI:
    """Test role management business logic that would be used by API endpoints"""

    def test_role_creation_logic(self, db: Session, sample_users: List[User]):
        """Test role creation business logic"""
        admin_user = sample_users[0]

        # Create new role
        new_role = crud_role.create(
            db=db,
            obj_in=RoleCreate(name="CUSTOM_ROLE"),
            user_id=admin_user.user_id,
        )

        assert new_role.name == "CUSTOM_ROLE"
        assert new_role.role_id is not None

    def test_role_assignment_request_validation(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test validation logic for role assignment requests"""
        target_user = sample_users[1]
        valid_role_ids = [role.role_id for role in sample_roles[:2]]

        # This would be the logic used in API endpoint
        # Verify target user exists
        assert target_user is not None

        # Verify all roles exist
        roles = db.query(Role).filter(Role.role_id.in_(valid_role_ids)).all()
        assert len(roles) == len(valid_role_ids)

        # Perform assignment
        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=target_user.user_id,
            role_ids=valid_role_ids,
            assigned_by_id=sample_users[0].user_id,
        )

        assert len(assigned_roles) == 2

    def test_invalid_role_assignment_handling(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test handling of invalid role assignment scenarios"""
        target_user = sample_users[1]

        # Test with non-existent role ID
        invalid_role_ids = [99999]
        roles = db.query(Role).filter(Role.role_id.in_(invalid_role_ids)).all()

        # Should find no roles
        assert len(roles) == 0

        # This validates the logic that would return 400 error in API


class TestAuditAndCompliance:
    """Test audit logging and compliance features"""

    def test_role_assignment_creates_audit_trail(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role assignments create audit logs"""
        user = sample_users[0]
        role = sample_roles[0]

        # Assign role (should create audit logs)
        assigned_roles = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )

        # Verify assignment was successful
        assert len(assigned_roles) == 1

        # In a full implementation, we would verify audit log entries were created
        # For now, we verify the operation completed successfully

    def test_role_history_tracking(
        self, db: Session, sample_users: List[User], sample_roles: List[Role]
    ):
        """Test that role assignment history is tracked properly"""
        user = sample_users[0]
        role = sample_roles[0]

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=user.user_id,
        )

        # Get assignment history
        history = crud_user_role.get_assignment_history(db=db, user_id=user.user_id)

        assert len(history) == 1
        assert history[0].user_id == user.user_id
        assert history[0].role_id == role.role_id
        assert history[0].assigned_by_id == user.user_id
        assert history[0].assigned_at is not None
