"""
Shared pytest fixtures for testing the chiropractic app.

This module provides fixtures for:
- Database sessions with in-memory SQLite
- Sample data for users and roles
- Authentication helpers
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from typing import List

from api.database.session import Base, get_db
from api.models.base import User, Role, UserRole
from api.core.config import RoleType
from api.core.security import get_password_hash


# Create test database engine
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test function"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# Override the get_db dependency
def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


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


@pytest.fixture
def authenticated_user_data(sample_users, sample_roles):
    """Create test data for authenticated user scenarios"""
    return {
        "admin_user": sample_users[0],
        "manager_user": sample_users[1],
        "provider_user": sample_users[2],
        "admin_role": sample_roles[0],
        "manager_role": sample_roles[1],
        "provider_role": sample_roles[2],
    }
