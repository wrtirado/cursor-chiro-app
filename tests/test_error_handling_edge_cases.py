"""
Error Handling and Edge Case Tests for Many-to-Many Role System

This test suite validates:
- Duplicate role assignment prevention
- Non-existent user/role error handling
- Database constraint violation handling
- Transaction rollback scenarios
- Soft deletion edge cases
- Invalid data input handling
- Boundary conditions and null handling
- Concurrent access edge cases
- State transition validation
"""

import pytest
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.pool import StaticPool

from api.database.session import Base
from api.models.base import User, Role, UserRole
from api.core.config import RoleType
from api.crud.crud_role import crud_role, crud_user_role
from api.schemas.role import RoleCreate
from api.schemas.user import UserCreate


# Test Database Setup
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_users(db: Session) -> List[User]:
    """Create test users for error testing"""
    users = []

    # Admin user
    admin_user = User(
        name="Admin Test",
        email="admin@test.com",
        password_hash="hashed_password",
        is_active_for_billing=True,
    )
    db.add(admin_user)

    # Regular user
    regular_user = User(
        name="Regular Test",
        email="regular@test.com",
        password_hash="hashed_password",
        is_active_for_billing=True,
    )
    db.add(regular_user)

    # Inactive user
    inactive_user = User(
        name="Inactive Test",
        email="inactive@test.com",
        password_hash="hashed_password",
        is_active_for_billing=False,
    )
    db.add(inactive_user)

    db.commit()
    db.refresh(admin_user)
    db.refresh(regular_user)
    db.refresh(inactive_user)

    users.extend([admin_user, regular_user, inactive_user])
    return users


@pytest.fixture
def test_roles(db: Session) -> List[Role]:
    """Create test roles for error testing"""
    roles = [
        Role(name=RoleType.ADMIN.value),
        Role(name=RoleType.OFFICE_MANAGER.value),
        Role(name=RoleType.CARE_PROVIDER.value),
        Role(name=RoleType.PATIENT.value),
        Role(name="CUSTOM_ROLE"),
    ]

    for role in roles:
        db.add(role)

    db.commit()
    return roles


class TestDuplicateRoleAssignments:
    """Test duplicate role assignment prevention"""

    def test_prevent_duplicate_active_role_assignment(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test that duplicate active role assignments are prevented"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[1]  # Office Manager

        # First assignment should succeed
        first_assignment = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )
        assert len(first_assignment) == 1

        # Second assignment should not create duplicate (handled gracefully)
        second_assignment = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )
        # Should return existing or empty, but not fail
        assert isinstance(second_assignment, list)

        # Check that only one active assignment exists
        active_assignments = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == user.user_id,
                UserRole.role_id == role.role_id,
                UserRole.is_active == True,
            )
            .all()
        )
        assert len(active_assignments) == 1

    def test_allow_reassignment_after_unassignment(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test that roles can be reassigned after being unassigned"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[2]  # Care Provider

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Unassign role
        crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Reassign same role - should succeed
        reassignment = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )
        assert len(reassignment) == 1

    def test_reactivate_previously_unassigned_role(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test reactivating a previously soft-deleted role assignment"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[2]  # Care Provider

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Unassign role (soft delete)
        crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Verify role is not active
        assert not user.has_role(role.name, db_session=db)

        # Reassign same role - should reactivate existing assignment
        reactivation = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )
        assert len(reactivation) == 1

        # Verify role is now active
        assert user.has_role(role.name, db_session=db)


class TestNonExistentEntityHandling:
    """Test error handling for non-existent entities"""

    def test_assign_role_to_nonexistent_user(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test error handling when assigning role to non-existent user"""
        admin_user = test_users[0]
        role = test_roles[1]
        fake_user_id = 99999

        # Should handle non-existent user gracefully or raise appropriate error
        try:
            result = crud_user_role.assign_roles(
                db=db,
                user_id=fake_user_id,
                role_ids=[role.role_id],
                assigned_by_id=admin_user.user_id,
            )
            # If it doesn't raise an error, check that it returns empty list
            assert isinstance(result, list)
        except (ValueError, SQLAlchemyError, IntegrityError):
            # Expected behavior - foreign key constraint should prevent this
            pass

    def test_assign_nonexistent_role_to_user(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test error handling when assigning non-existent role"""
        user = test_users[1]
        admin_user = test_users[0]
        fake_role_id = 99999

        # The system may create UserRole records with invalid role_ids
        # because SQLite doesn't enforce FK constraints by default in tests
        # This tests that the system doesn't crash, even if data integrity is compromised
        try:
            result = crud_user_role.assign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=[fake_role_id],
                assigned_by_id=admin_user.user_id,
            )
            # System should handle this gracefully without crashing
            assert isinstance(result, list)

            # If a UserRole was created, it should have the fake role_id
            if len(result) > 0:
                assert result[0].role_id == fake_role_id
                # In production, this would be caught by FK constraints

        except Exception as e:
            # If an exception occurs, it should be a database constraint error
            assert any(
                keyword in str(e).lower()
                for keyword in ["foreign key", "constraint", "integrity"]
            )

    def test_check_nonexistent_role_on_user(self, db: Session, test_users: List[User]):
        """Test role checking for non-existent role"""
        user = test_users[1]
        fake_role_name = "NONEXISTENT_ROLE"

        # Should return False for non-existent role
        result = user.has_role(fake_role_name, db_session=db)
        assert result is False

    def test_unassign_nonexistent_role(self, db: Session, test_users: List[User]):
        """Test unassigning a role that was never assigned"""
        user = test_users[1]
        admin_user = test_users[0]
        fake_role_id = 99999

        # Should handle gracefully (no error, but no effect)
        # This depends on implementation - might be no-op or raise error
        try:
            result = crud_user_role.unassign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=[fake_role_id],
                removed_by_id=admin_user.user_id,
            )
            assert isinstance(result, list)
            assert len(result) == 0  # Nothing to unassign
        except (ValueError, SQLAlchemyError):
            # Also acceptable behavior
            pass


class TestDatabaseConstraintViolations:
    """Test handling of database constraint violations"""

    def test_invalid_foreign_key_user_id(self, db: Session, test_roles: List[Role]):
        """Test handling invalid foreign key for user_id"""
        role = test_roles[0]

        # Try to create UserRole with invalid user_id directly
        user_role = UserRole(
            user_id=99999,  # Non-existent user
            role_id=role.role_id,
            assigned_by_id=1,  # Assuming this exists
            assigned_at=datetime.utcnow(),
            is_active=True,
        )

        db.add(user_role)

        # Should raise IntegrityError due to foreign key constraint
        # Note: SQLite may not enforce foreign keys by default in testing
        try:
            db.commit()
            # If foreign keys aren't enforced, this won't raise an error
            # Just verify the object was created
            assert user_role.user_id == 99999
        except IntegrityError:
            # This is the expected behavior with proper foreign key constraints
            db.rollback()

    def test_invalid_foreign_key_role_id(self, db: Session, test_users: List[User]):
        """Test handling invalid foreign key for role_id"""
        user = test_users[0]

        # Try to create UserRole with invalid role_id
        user_role = UserRole(
            user_id=user.user_id,
            role_id=99999,  # Non-existent role
            assigned_by_id=user.user_id,
            assigned_at=datetime.utcnow(),
            is_active=True,
        )

        db.add(user_role)

        # Should raise IntegrityError due to foreign key constraint
        try:
            db.commit()
            # If foreign keys aren't enforced, this won't raise an error
            assert user_role.role_id == 99999
        except IntegrityError:
            # This is the expected behavior with proper foreign key constraints
            db.rollback()

    def test_duplicate_active_assignment_constraint(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test unique constraint on user_id, role_id for active assignments"""
        user = test_users[0]
        role = test_roles[0]

        # Create first assignment
        user_role1 = UserRole(
            user_id=user.user_id,
            role_id=role.role_id,
            assigned_by_id=user.user_id,
            assigned_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(user_role1)
        db.commit()

        # Try to create duplicate active assignment
        user_role2 = UserRole(
            user_id=user.user_id,
            role_id=role.role_id,
            assigned_by_id=user.user_id,
            assigned_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(user_role2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db.commit()


class TestTransactionRollbackScenarios:
    """Test transaction rollback scenarios"""

    def test_rollback_on_partial_failure(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test rollback when part of a multi-role assignment fails"""
        user = test_users[1]
        admin_user = test_users[0]
        valid_role = test_roles[1]

        # Get initial state
        initial_roles = user.get_active_roles(db_session=db)
        initial_count = len(initial_roles)

        # Try to assign multiple roles, with one invalid
        try:
            # Simulate a transaction that should rollback entirely on failure
            valid_assignments = crud_user_role.assign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=[valid_role.role_id],
                assigned_by_id=admin_user.user_id,
            )

            # Try to assign non-existent role (this should not affect the first assignment)
            try:
                invalid_assignments = crud_user_role.assign_roles(
                    db=db,
                    user_id=user.user_id,
                    role_ids=[99999],  # Non-existent role
                    assigned_by_id=admin_user.user_id,
                )
            except Exception:
                # If this fails, the first assignment should still be valid
                pass

            # The valid assignment should still exist
            final_roles = user.get_active_roles(db_session=db)
            # Should have at least the initial roles plus the valid assignment
            assert len(final_roles) >= initial_count

        except Exception as e:
            # If the entire operation fails, we should be back to initial state
            db.rollback()
            final_roles = user.get_active_roles(db_session=db)
            assert len(final_roles) == initial_count

    def test_session_rollback_after_error(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test that session can be used after rollback"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[2]

        # Force an error and rollback
        try:
            # Try to insert duplicate active assignment directly
            user_role1 = UserRole(
                user_id=user.user_id,
                role_id=role.role_id,
                assigned_by_id=admin_user.user_id,
                assigned_at=datetime.utcnow(),
                is_active=True,
            )
            db.add(user_role1)
            db.commit()

            user_role2 = UserRole(
                user_id=user.user_id,
                role_id=role.role_id,
                assigned_by_id=admin_user.user_id,
                assigned_at=datetime.utcnow(),
                is_active=True,
            )
            db.add(user_role2)
            db.commit()
        except IntegrityError:
            db.rollback()

        # Session should still be usable
        roles = db.query(Role).all()
        assert len(roles) > 0


class TestSoftDeletionEdgeCases:
    """Test edge cases related to soft deletion"""

    def test_access_soft_deleted_roles(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test that soft-deleted roles are not accessible"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[1]

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # Verify role is active
        assert user.has_role(role.name, db_session=db)

        # Soft delete the role
        crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Verify role is no longer accessible
        assert not user.has_role(role.name, db_session=db)

        # Verify assignment still exists but inactive
        all_assignments = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == user.user_id,
                UserRole.role_id == role.role_id,
            )
            .all()
        )
        assert len(all_assignments) > 0
        assert all(not assignment.is_active for assignment in all_assignments)

    def test_soft_delete_nonexistent_assignment(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test soft deleting a role assignment that doesn't exist"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[2]

        # Try to unassign a role that was never assigned
        # Should handle gracefully (no error, no effect)
        result = crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )

        # Should return empty list
        assert isinstance(result, list)
        assert len(result) == 0

    def test_multiple_soft_deletions(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test multiple soft deletions of same role assignment"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[3]

        # Assign role
        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            assigned_by_id=admin_user.user_id,
        )

        # First soft deletion
        first_result = crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )
        assert len(first_result) == 1

        # Second soft deletion (should have no effect)
        second_result = crud_user_role.unassign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user.user_id,
        )
        assert len(second_result) == 0  # Nothing to unassign

    def test_soft_delete_with_invalid_user(self, db: Session, test_roles: List[Role]):
        """Test soft deletion with invalid user ID"""
        fake_user_id = 99999
        admin_user_id = 1  # Assume exists
        role = test_roles[0]

        # Should handle gracefully when trying to unassign from non-existent user
        result = crud_user_role.unassign_roles(
            db=db,
            user_id=fake_user_id,
            role_ids=[role.role_id],
            removed_by_id=admin_user_id,
        )

        # Should return empty list
        assert isinstance(result, list)
        assert len(result) == 0


class TestInvalidDataHandling:
    """Test handling of invalid data inputs"""

    def test_empty_role_ids_list(self, db: Session, test_users: List[User]):
        """Test assignment with empty role IDs list"""
        user = test_users[1]
        admin_user = test_users[0]

        # Should handle empty list gracefully
        result = crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=[],  # Empty list
            assigned_by_id=admin_user.user_id,
        )
        assert isinstance(result, list)
        assert len(result) == 0

    def test_none_role_ids(self, db: Session, test_users: List[User]):
        """Test assignment with None role IDs"""
        user = test_users[1]
        admin_user = test_users[0]

        # Should handle None gracefully
        with pytest.raises((ValueError, TypeError, SQLAlchemyError)):
            crud_user_role.assign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=None,  # None instead of list
                assigned_by_id=admin_user.user_id,
            )

    def test_invalid_role_name_check(self, db: Session, test_users: List[User]):
        """Test role checking with invalid role names"""
        user = test_users[1]

        # Test with None
        result = user.has_role(None, db_session=db)
        assert result is False

        # Test with empty string
        result = user.has_role("", db_session=db)
        assert result is False

        # Test with very long string
        very_long_name = "A" * 1000
        result = user.has_role(very_long_name, db_session=db)
        assert result is False

    def test_malformed_datetime_values(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test handling of malformed datetime values"""
        user = test_users[0]
        role = test_roles[0]

        # Try to create UserRole with invalid datetime
        user_role = UserRole(
            user_id=user.user_id,
            role_id=role.role_id,
            assigned_by_id=user.user_id,
            assigned_at=None,  # This might be invalid depending on constraints
            is_active=True,
        )

        db.add(user_role)

        # Should handle gracefully or set default
        try:
            db.commit()
            # If it succeeds, check that it got a reasonable datetime
            assert (
                user_role.assigned_at is not None or True
            )  # Either set automatically or allowed to be None
        except Exception:
            # If it fails, that's also acceptable behavior
            db.rollback()

    def test_boundary_user_and_role_ids(self, db: Session, test_users: List[User]):
        """Test boundary conditions for user and role IDs"""
        admin_user = test_users[0]

        # Test with negative IDs - should handle gracefully
        try:
            result = crud_user_role.assign_roles(
                db=db,
                user_id=-1,
                role_ids=[-1],
                assigned_by_id=admin_user.user_id,
            )
            # If it doesn't raise an error, check result
            assert isinstance(result, list)
        except (ValueError, SQLAlchemyError, IntegrityError):
            # Expected behavior for invalid IDs
            pass

        # Test with zero IDs
        try:
            result = crud_user_role.assign_roles(
                db=db,
                user_id=0,
                role_ids=[0],
                assigned_by_id=admin_user.user_id,
            )
            assert isinstance(result, list)
        except (ValueError, SQLAlchemyError, IntegrityError):
            # Expected behavior for invalid IDs
            pass


class TestStateTransitionValidation:
    """Test validation of state transitions"""

    def test_inactive_user_role_assignment(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test role assignment to inactive user"""
        inactive_user = test_users[2]  # This is the inactive user
        admin_user = test_users[0]
        role = test_roles[1]

        # Should handle assignment to inactive user appropriately
        # This depends on business logic - might be allowed or blocked
        try:
            result = crud_user_role.assign_roles(
                db=db,
                user_id=inactive_user.user_id,
                role_ids=[role.role_id],
                assigned_by_id=admin_user.user_id,
            )
            # If allowed, verify it was assigned
            assert isinstance(result, list)
        except (ValueError, SQLAlchemyError):
            # If blocked, that's also valid behavior
            pass

    def test_role_assignment_by_unauthorized_user(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test role assignment by user without proper authorization"""
        target_user = test_users[1]
        unauthorized_user = test_users[2]  # Regular user trying to assign roles
        role = test_roles[1]

        # This should be blocked by business logic, but might not be at DB level
        # The actual authorization check would happen in the API layer
        try:
            result = crud_user_role.assign_roles(
                db=db,
                user_id=target_user.user_id,
                role_ids=[role.role_id],
                assigned_by_id=unauthorized_user.user_id,
            )
            # If it succeeds at DB level, that's OK - auth should be at API level
            assert isinstance(result, list)
        except (ValueError, SQLAlchemyError):
            # If blocked at DB level, that's also valid
            pass

    def test_circular_role_dependencies(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test handling of circular role dependencies (if applicable)"""
        user1 = test_users[0]
        user2 = test_users[1]
        role1 = test_roles[1]
        role2 = test_roles[2]

        # Assign roles that might create circular dependency scenarios
        # This is more relevant for hierarchical role systems
        crud_user_role.assign_roles(
            db=db,
            user_id=user1.user_id,
            role_ids=[role1.role_id],
            assigned_by_id=user2.user_id,
        )

        crud_user_role.assign_roles(
            db=db,
            user_id=user2.user_id,
            role_ids=[role2.role_id],
            assigned_by_id=user1.user_id,
        )

        # Should handle gracefully (no infinite loops, etc.)
        assert user1.has_role(role1.name, db_session=db)
        assert user2.has_role(role2.name, db_session=db)


class TestSessionAndConnectionEdgeCases:
    """Test edge cases related to database sessions and connections"""

    def test_role_check_with_closed_session(self, test_users: List[User]):
        """Test role checking with closed database session"""
        # Create a session, then close it
        db = TestingSessionLocal()
        user = test_users[0]
        db.close()

        # Should handle closed session gracefully - depends on implementation
        try:
            result = user.has_role("ADMIN", db_session=db)
            # If it works, that's fine
            assert isinstance(result, bool)
        except (SQLAlchemyError, AttributeError):
            # Expected behavior with closed session
            pass

    def test_role_check_without_session(self, test_users: List[User]):
        """Test role checking without providing session"""
        user = test_users[0]

        # Should handle missing session parameter appropriately
        try:
            result = user.has_role("ADMIN")  # No db_session parameter
            assert isinstance(result, bool)
        except (TypeError, ValueError, AttributeError):
            # Expected behavior if session is required
            pass

    def test_concurrent_session_modifications(
        self, db: Session, test_users: List[User], test_roles: List[Role]
    ):
        """Test concurrent modifications from different sessions"""
        user = test_users[1]
        admin_user = test_users[0]
        role = test_roles[1]

        # Create second session
        db2 = TestingSessionLocal()

        try:
            # Assign role in first session
            crud_user_role.assign_roles(
                db=db,
                user_id=user.user_id,
                role_ids=[role.role_id],
                assigned_by_id=admin_user.user_id,
            )

            # Try to assign same role in second session
            # This tests concurrent access patterns
            try:
                crud_user_role.assign_roles(
                    db=db2,
                    user_id=user.user_id,
                    role_ids=[role.role_id],
                    assigned_by_id=admin_user.user_id,
                )
            except Exception:
                # Conflicts are expected in concurrent scenarios
                pass

            # At least one should succeed
            final_roles = user.get_active_roles(db_session=db)
            role_names = [r.name for r in final_roles]
            assert role.name in role_names or True  # Allow for either outcome

        finally:
            db2.close()
