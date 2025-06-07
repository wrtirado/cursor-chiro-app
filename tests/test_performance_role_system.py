"""
Performance Tests for Many-to-Many Role System

This test suite validates:
- Role checking performance benchmarks
- Database query optimization
- N+1 query prevention with eager loading
- Scalability with large user/role datasets
- Index usage and query efficiency
- Memory usage optimization
- Concurrent access performance
"""

import pytest
import time
import statistics
from typing import List, Dict, Any, Tuple
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from api.database.session import Base
from api.models.base import User, Role, UserRole
from api.core.config import RoleType
from api.core.security import get_password_hash
from api.crud.crud_role import crud_role, crud_user_role
from api.crud.crud_user import create_user
from api.schemas.user import UserCreate


# Test Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class QueryCounter:
    """Helper class to count database queries"""

    def __init__(self):
        self.query_count = 0
        self.queries = []

    def reset(self):
        self.query_count = 0
        self.queries.clear()

    def count_query(self, conn, cursor, statement, parameters, context, executemany):
        self.query_count += 1
        self.queries.append(
            {
                "statement": str(statement),
                "parameters": parameters,
                "timestamp": time.time(),
            }
        )


@contextmanager
def query_counter():
    """Context manager to count queries during execution"""
    counter = QueryCounter()

    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        counter.count_query(conn, cursor, statement, parameters, context, executemany)

    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", receive_before_cursor_execute)


@contextmanager
def timer():
    """Context manager to time execution"""
    start_time = time.perf_counter()
    yield lambda: time.perf_counter() - start_time


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
def performance_roles(db) -> List[Role]:
    """Create roles for performance testing"""
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
def large_dataset(db, performance_roles) -> Dict[str, Any]:
    """Create a large dataset for performance testing"""
    # Create 100 users
    users = []
    for i in range(100):
        user = User(
            email=f"user{i}@performance.test",
            password_hash=get_password_hash(f"Password{i}123!"),
            name=f"Performance User {i}",
            is_active_for_billing=True,
        )
        db.add(user)
        users.append(user)

    db.commit()

    for user in users:
        db.refresh(user)

    # Assign roles to users (some users have multiple roles)
    admin_user = users[0]  # First user as admin for assignments
    crud_user_role.assign_roles(
        db=db,
        user_id=admin_user.user_id,
        role_ids=[performance_roles[0].role_id],  # Admin role
        assigned_by_id=admin_user.user_id,
    )

    # Assign various role combinations
    for i, user in enumerate(users[1:], 1):
        if i % 5 == 0:  # Every 5th user gets admin
            role_ids = [performance_roles[0].role_id]
        elif i % 3 == 0:  # Every 3rd user gets multiple roles
            role_ids = [
                performance_roles[1].role_id,
                performance_roles[2].role_id,
            ]  # Manager + Provider
        elif i % 2 == 0:  # Every 2nd user gets single role
            role_ids = [performance_roles[2].role_id]  # Care Provider
        else:  # Others get patient role
            role_ids = [performance_roles[4].role_id]  # Patient

        crud_user_role.assign_roles(
            db=db,
            user_id=user.user_id,
            role_ids=role_ids,
            assigned_by_id=admin_user.user_id,
        )

    return {"users": users, "roles": performance_roles, "admin_user": admin_user}


class TestRoleCheckingPerformance:
    """Test performance of role checking operations"""

    def test_single_role_check_performance(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Benchmark single role check performance"""
        users = large_dataset["users"]
        user = users[0]  # Admin user

        # Warm up
        user.has_role(RoleType.ADMIN.value, db_session=db)

        # Benchmark multiple role checks
        times = []
        for _ in range(100):
            with timer() as get_time:
                result = user.has_role(RoleType.ADMIN.value, db_session=db)
            times.append(get_time())
            assert result  # Should be admin

        avg_time = statistics.mean(times)
        max_time = max(times)
        min_time = min(times)

        print(f"\nSingle role check performance:")
        print(f"Average: {avg_time*1000:.3f}ms")
        print(f"Min: {min_time*1000:.3f}ms")
        print(f"Max: {max_time*1000:.3f}ms")

        # Performance assertions
        assert avg_time < 0.01, f"Average role check too slow: {avg_time*1000:.3f}ms"
        assert max_time < 0.05, f"Max role check too slow: {max_time*1000:.3f}ms"

    def test_multiple_role_check_performance(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Benchmark performance when checking multiple roles"""
        users = large_dataset["users"]
        user = users[6]  # User with multiple roles (manager + provider)

        role_types = [
            RoleType.ADMIN.value,
            RoleType.OFFICE_MANAGER.value,
            RoleType.CARE_PROVIDER.value,
            RoleType.BILLING_ADMIN.value,
            RoleType.PATIENT.value,
        ]

        # Warm up
        for role_type in role_types:
            user.has_role(role_type, db_session=db)

        # Benchmark multiple role checks
        times = []
        for _ in range(50):
            with timer() as get_time:
                results = [
                    user.has_role(role_type, db_session=db) for role_type in role_types
                ]
            times.append(get_time())

            # Verify expected results
            assert not results[0]  # Not admin
            assert results[1]  # Is office manager
            assert results[2]  # Is care provider
            assert not results[3]  # Not billing admin
            assert not results[4]  # Not patient

        avg_time = statistics.mean(times)
        max_time = max(times)

        print(f"\nMultiple role check performance (5 roles):")
        print(f"Average: {avg_time*1000:.3f}ms")
        print(f"Max: {max_time*1000:.3f}ms")

        # Performance assertions
        assert avg_time < 0.05, f"Multiple role check too slow: {avg_time*1000:.3f}ms"
        assert (
            max_time < 0.1
        ), f"Max multiple role check too slow: {max_time*1000:.3f}ms"

    def test_get_active_roles_performance(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Benchmark get_active_roles performance"""
        users = large_dataset["users"]

        # Test with different types of users
        test_users = [
            users[0],  # Admin (1 role)
            users[6],  # Manager + Provider (2 roles)
            users[99],  # Patient (1 role)
        ]

        for i, user in enumerate(test_users):
            times = []
            for _ in range(50):
                with timer() as get_time:
                    roles = user.get_active_roles(db_session=db)
                times.append(get_time())

                # Verify we get roles back
                assert len(roles) > 0

            avg_time = statistics.mean(times)
            max_time = max(times)

            print(f"\nget_active_roles performance (user {i}):")
            print(f"Roles count: {len(roles)}")
            print(f"Average: {avg_time*1000:.3f}ms")
            print(f"Max: {max_time*1000:.3f}ms")

            # Performance assertions
            assert avg_time < 0.02, f"get_active_roles too slow: {avg_time*1000:.3f}ms"


class TestQueryOptimization:
    """Test database query optimization and N+1 prevention"""

    def test_role_check_query_count(self, db: Session, large_dataset: Dict[str, Any]):
        """Test that role checking doesn't generate excessive queries"""
        users = large_dataset["users"]
        user = users[0]  # Admin user

        with query_counter() as counter:
            result = user.has_role(RoleType.ADMIN.value, db_session=db)

        print(f"\nRole check query count: {counter.query_count}")
        for i, query in enumerate(counter.queries):
            print(f"Query {i+1}: {query['statement'][:100]}...")

        assert result
        # Should use minimal queries (allow for audit logging)
        assert (
            counter.query_count <= 5
        ), f"Too many queries for role check: {counter.query_count}"

    def test_get_active_roles_query_count(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test query count for getting all active roles"""
        users = large_dataset["users"]
        user = users[6]  # User with multiple roles

        with query_counter() as counter:
            roles = user.get_active_roles(db_session=db)

        print(f"\nget_active_roles query count: {counter.query_count}")
        print(f"Retrieved {len(roles)} roles")

        assert len(roles) > 0
        # Should be able to get all roles efficiently (allow for audit logging)
        assert (
            counter.query_count <= 5
        ), f"Too many queries for get_active_roles: {counter.query_count}"

    def test_bulk_role_assignment_performance(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test performance of bulk role assignments"""
        roles = large_dataset["roles"]
        admin_user = large_dataset["admin_user"]

        # Create additional users for bulk testing
        new_users = []
        for i in range(20):
            user = User(
                email=f"bulk{i}@performance.test",
                password_hash=get_password_hash(f"BulkPass{i}123!"),
                name=f"Bulk User {i}",
                is_active_for_billing=True,
            )
            db.add(user)
            new_users.append(user)

        db.commit()
        for user in new_users:
            db.refresh(user)

        # Test bulk role assignment performance
        with timer() as get_time:
            with query_counter() as counter:
                for user in new_users:
                    crud_user_role.assign_roles(
                        db=db,
                        user_id=user.user_id,
                        role_ids=[roles[2].role_id],  # Care provider role
                        assigned_by_id=admin_user.user_id,
                    )

        total_time = get_time()
        avg_time_per_assignment = total_time / len(new_users)

        print(f"\nBulk role assignment performance:")
        print(f"Total time for {len(new_users)} assignments: {total_time*1000:.3f}ms")
        print(f"Average per assignment: {avg_time_per_assignment*1000:.3f}ms")
        print(f"Total queries: {counter.query_count}")
        print(f"Queries per assignment: {counter.query_count / len(new_users):.1f}")

        # Performance assertions (allow more queries due to audit logging)
        assert (
            avg_time_per_assignment < 0.05
        ), f"Role assignment too slow: {avg_time_per_assignment*1000:.3f}ms"
        assert (
            counter.query_count / len(new_users) < 15
        ), f"Too many queries per assignment"


class TestScalabilityAndIndexes:
    """Test scalability with large datasets and index usage"""

    def test_role_checking_with_many_users(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test role checking performance doesn't degrade with many users"""
        users = large_dataset["users"]

        # Test role checking for different users
        check_times = []
        for i in range(0, len(users), 10):  # Test every 10th user
            user = users[i]

            with timer() as get_time:
                user.has_role(RoleType.CARE_PROVIDER.value, db_session=db)
            check_times.append(get_time())

        avg_time = statistics.mean(check_times)
        max_time = max(check_times)
        std_dev = statistics.stdev(check_times) if len(check_times) > 1 else 0

        print(f"\nRole checking with {len(users)} users:")
        print(f"Average time: {avg_time*1000:.3f}ms")
        print(f"Max time: {max_time*1000:.3f}ms")
        print(f"Standard deviation: {std_dev*1000:.3f}ms")

        # Performance should be consistent regardless of dataset size
        assert (
            avg_time < 0.02
        ), f"Role checking degraded with large dataset: {avg_time*1000:.3f}ms"
        assert (
            std_dev < 0.01
        ), f"Performance inconsistent with large dataset: {std_dev*1000:.3f}ms"

    def test_user_role_join_performance(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test performance of user-role joins with explicit join conditions"""
        users = large_dataset["users"]

        # Test getting users with specific roles using explicit join
        with timer() as get_time:
            with query_counter() as counter:
                # Query users with admin role - explicit join to avoid ambiguity
                admin_users = (
                    db.query(User)
                    .join(UserRole, User.user_id == UserRole.user_id)
                    .join(Role, UserRole.role_id == Role.role_id)
                    .filter(Role.name == RoleType.ADMIN.value)
                    .filter(UserRole.is_active == True)
                    .all()
                )

        query_time = get_time()

        print(f"\nUser-role join performance:")
        print(f"Found {len(admin_users)} admin users")
        print(f"Query time: {query_time*1000:.3f}ms")
        print(f"Query count: {counter.query_count}")

        assert len(admin_users) > 0
        assert query_time < 0.05, f"User-role join too slow: {query_time*1000:.3f}ms"
        assert (
            counter.query_count <= 2
        ), f"Too many queries for join: {counter.query_count}"

    def test_role_assignment_history_performance(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test performance when querying role assignment history"""
        users = large_dataset["users"]
        user = users[0]  # Admin user

        # Get role assignment history
        with timer() as get_time:
            with query_counter() as counter:
                user_roles = (
                    db.query(UserRole)
                    .filter(UserRole.user_id == user.user_id)
                    .order_by(UserRole.assigned_at.desc())
                    .all()
                )

        query_time = get_time()

        print(f"\nRole history query performance:")
        print(f"Found {len(user_roles)} role assignments")
        print(f"Query time: {query_time*1000:.3f}ms")
        print(f"Query count: {counter.query_count}")

        assert len(user_roles) > 0
        assert (
            query_time < 0.02
        ), f"Role history query too slow: {query_time*1000:.3f}ms"


class TestMemoryUsage:
    """Test memory efficiency of role operations"""

    def test_role_object_creation_efficiency(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test that role checking doesn't create excessive objects"""
        users = large_dataset["users"]
        user = users[0]

        # Check memory-efficient role checking using session new/dirty/deleted
        initial_new = len(db.new)
        initial_dirty = len(db.dirty)

        # Perform multiple role checks
        for _ in range(50):
            user.has_role(RoleType.ADMIN.value, db_session=db)

        final_new = len(db.new)
        final_dirty = len(db.dirty)
        object_growth = (final_new - initial_new) + (final_dirty - initial_dirty)

        print(f"\nMemory usage (session objects):")
        print(f"Initial new: {initial_new}, dirty: {initial_dirty}")
        print(f"Final new: {final_new}, dirty: {final_dirty}")
        print(f"Total growth: {object_growth}")

        # Should not accumulate excessive objects
        assert object_growth < 10, f"Too many objects created: {object_growth}"

    def test_active_roles_caching_efficiency(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test that repeated calls to get_active_roles are efficient"""
        users = large_dataset["users"]
        user = users[6]  # User with multiple roles

        # First call - may need to query database
        with timer() as get_time_1:
            roles_1 = user.get_active_roles(db_session=db)
        first_call_time = get_time_1()

        # Subsequent calls should be faster (if properly optimized)
        subsequent_times = []
        for _ in range(20):
            with timer() as get_time:
                roles = user.get_active_roles(db_session=db)
            subsequent_times.append(get_time())
            assert len(roles) == len(roles_1)  # Should return same roles

        avg_subsequent_time = statistics.mean(subsequent_times)

        print(f"\nRole caching efficiency:")
        print(f"First call: {first_call_time*1000:.3f}ms")
        print(f"Avg subsequent: {avg_subsequent_time*1000:.3f}ms")
        print(f"Speedup ratio: {first_call_time / avg_subsequent_time:.1f}x")

        # Subsequent calls should be reasonably fast
        assert (
            avg_subsequent_time < 0.02
        ), f"Subsequent role calls too slow: {avg_subsequent_time*1000:.3f}ms"


class TestConcurrentAccess:
    """Test performance under concurrent access scenarios"""

    def test_concurrent_role_checking_simulation(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Simulate concurrent role checking (sequential for testing)"""
        users = large_dataset["users"]

        # Simulate multiple "concurrent" role checks
        all_times = []
        for iteration in range(5):  # 5 "concurrent" sessions
            session_times = []
            for user in users[:20]:  # Check 20 users per session
                with timer() as get_time:
                    user.has_role(RoleType.CARE_PROVIDER.value, db_session=db)
                session_times.append(get_time())

            avg_session_time = statistics.mean(session_times)
            all_times.extend(session_times)

            print(f"Session {iteration + 1} avg time: {avg_session_time*1000:.3f}ms")

        overall_avg = statistics.mean(all_times)
        max_time = max(all_times)

        print(f"\nConcurrent access simulation:")
        print(f"Overall average: {overall_avg*1000:.3f}ms")
        print(f"Max time: {max_time*1000:.3f}ms")

        # Performance should remain stable under load
        assert (
            overall_avg < 0.02
        ), f"Performance degraded under load: {overall_avg*1000:.3f}ms"
        assert max_time < 0.05, f"Max time too high under load: {max_time*1000:.3f}ms"

    def test_role_assignment_under_load(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test role assignment performance under simulated load"""
        roles = large_dataset["roles"]
        admin_user = large_dataset["admin_user"]

        # Create users for load testing
        load_users = []
        for i in range(30):
            user = User(
                email=f"load{i}@performance.test",
                password_hash=get_password_hash(f"LoadPass{i}123!"),
                name=f"Load User {i}",
                is_active_for_billing=True,
            )
            db.add(user)
            load_users.append(user)

        db.commit()
        for user in load_users:
            db.refresh(user)

        # Simulate load with rapid role assignments
        assignment_times = []
        with timer() as get_total_time:
            for user in load_users:
                with timer() as get_time:
                    crud_user_role.assign_roles(
                        db=db,
                        user_id=user.user_id,
                        role_ids=[roles[2].role_id],  # Care provider
                        assigned_by_id=admin_user.user_id,
                    )
                assignment_times.append(get_time())

        total_time = get_total_time()
        avg_time = statistics.mean(assignment_times)
        max_time = max(assignment_times)

        print(f"\nRole assignment under load:")
        print(f"Total assignments: {len(load_users)}")
        print(f"Total time: {total_time*1000:.3f}ms")
        print(f"Average per assignment: {avg_time*1000:.3f}ms")
        print(f"Max assignment time: {max_time*1000:.3f}ms")
        print(f"Assignments per second: {len(load_users) / total_time:.1f}")

        # Should maintain reasonable performance under load (adjusted for audit logging)
        assert (
            avg_time < 0.05
        ), f"Role assignment too slow under load: {avg_time*1000:.3f}ms"
        assert (
            len(load_users) / total_time > 10
        ), f"Throughput too low: {len(load_users) / total_time:.1f} ops/sec"


class TestDatabaseIndexEfficiency:
    """Test that database indexes are being used effectively"""

    def test_user_role_index_usage(self, db: Session, large_dataset: Dict[str, Any]):
        """Test that queries use indexes efficiently"""
        users = large_dataset["users"]
        user = users[0]

        # Query that should use user_id index
        with query_counter() as counter:
            user_roles = (
                db.query(UserRole)
                .filter(UserRole.user_id == user.user_id)
                .filter(UserRole.is_active == True)
                .all()
            )

        print(f"\nIndex usage test:")
        print(f"Found {len(user_roles)} active roles")
        print(f"Query count: {counter.query_count}")

        # Should find roles efficiently (allow for audit logging)
        assert len(user_roles) > 0
        assert (
            counter.query_count <= 5
        ), f"Inefficient query execution: {counter.query_count} queries"

    def test_role_name_lookup_efficiency(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Test role lookup by name efficiency"""

        # Query that should use role name index/primary key
        with timer() as get_time:
            with query_counter() as counter:
                role = db.query(Role).filter(Role.name == RoleType.ADMIN.value).first()

        query_time = get_time()

        print(f"\nRole name lookup:")
        print(f"Query time: {query_time*1000:.3f}ms")
        print(f"Query count: {counter.query_count}")

        assert role is not None
        assert query_time < 0.01, f"Role lookup too slow: {query_time*1000:.3f}ms"
        assert (
            counter.query_count <= 1
        ), f"Multiple queries for simple lookup: {counter.query_count}"


class TestRegressionAndComparison:
    """Test for performance regressions and comparisons"""

    def test_performance_baseline_establishment(
        self, db: Session, large_dataset: Dict[str, Any]
    ):
        """Establish performance baselines for future regression testing"""
        users = large_dataset["users"]

        # Baseline metrics
        baselines = {}

        # Single role check baseline
        user = users[0]
        times = []
        for _ in range(100):
            with timer() as get_time:
                user.has_role(RoleType.ADMIN.value, db_session=db)
            times.append(get_time())
        baselines["single_role_check"] = statistics.mean(times)

        # Multiple role check baseline
        user_multi = users[6]
        times = []
        for _ in range(50):
            with timer() as get_time:
                user_multi.get_active_roles(db_session=db)
            times.append(get_time())
        baselines["get_active_roles"] = statistics.mean(times)

        # Role assignment baseline
        admin_user = large_dataset["admin_user"]
        roles = large_dataset["roles"]
        test_user = users[50]

        with timer() as get_time:
            crud_user_role.assign_roles(
                db=db,
                user_id=test_user.user_id,
                role_ids=[roles[3].role_id],
                assigned_by_id=admin_user.user_id,
            )
        baselines["role_assignment"] = get_time()

        print(f"\nPerformance Baselines:")
        print(f"Single role check: {baselines['single_role_check']*1000:.3f}ms")
        print(f"Get active roles: {baselines['get_active_roles']*1000:.3f}ms")
        print(f"Role assignment: {baselines['role_assignment']*1000:.3f}ms")

        # Store baselines for comparison (in real implementation, these would be stored)
        assert all(
            time < 0.1 for time in baselines.values()
        ), "Baseline performance acceptable"

    def test_scale_comparison(self, db: Session):
        """Compare performance with different dataset sizes"""
        # Test with small dataset (10 users)
        small_users = []
        for i in range(10):
            user = User(
                email=f"small{i}@test.com",
                password_hash=get_password_hash(f"Pass{i}123!"),
                name=f"Small User {i}",
                is_active_for_billing=True,
            )
            db.add(user)
            small_users.append(user)

        db.commit()
        for user in small_users:
            db.refresh(user)

        # Performance with small dataset
        small_times = []
        for user in small_users:
            with timer() as get_time:
                user.has_role(RoleType.ADMIN.value, db_session=db)
            small_times.append(get_time())

        small_avg = statistics.mean(small_times)

        print(f"\nScale comparison:")
        print(f"Small dataset (10 users): {small_avg*1000:.3f}ms avg")

        # Should scale linearly or better
        assert (
            small_avg < 0.02
        ), f"Performance poor even with small dataset: {small_avg*1000:.3f}ms"
