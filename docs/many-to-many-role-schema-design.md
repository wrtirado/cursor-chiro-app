# Many-to-Many User-Role Schema Design

## Task 34.2: Design Many-to-Many User-Role Schema

**Date**: June 1, 2025  
**Status**: Complete  
**Dependencies**: Task 34.1 (Audit Complete)

## Design Overview

This document outlines the new database schema design to transition from the current one-to-one User-Role relationship to a flexible many-to-many relationship, allowing users to have multiple roles simultaneously.

## Current Schema Analysis

### Existing Tables

- **Users Table**: Contains `role_id` foreign key (NOT NULL) → **TO BE REMOVED**
- **Roles Table**: Contains `role_id` primary key and role names → **TO BE UPDATED**

### Current Limitations

- Users can only have one role at a time
- No flexibility for users who need multiple access levels
- Business logic assumes single role throughout system

## New Schema Design

### 1. New Junction Table: `user_roles`

```sql
-- UserRoles Table: Junction table for many-to-many User-Role relationship
CREATE TABLE user_roles (
    user_role_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES Roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    assigned_by_id INT REFERENCES Users(user_id) ON DELETE SET NULL, -- Who assigned this role
    is_active BOOLEAN DEFAULT TRUE, -- Allow for role deactivation without deletion
    UNIQUE (user_id, role_id) -- Prevent duplicate role assignments
);
```

### 2. Updated Roles Table

```sql
-- Update role names: chiropractor → care_provider
UPDATE Roles SET name = 'care_provider' WHERE name = 'chiropractor';
```

### 3. Modified Users Table

```sql
-- Remove the single role_id foreign key
ALTER TABLE Users DROP COLUMN role_id;
```

### 4. Indexes for Performance

```sql
-- Primary lookup indexes
CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX idx_user_roles_active ON user_roles(user_id, is_active) WHERE is_active = TRUE;

-- Composite index for common queries
CREATE INDEX idx_user_roles_lookup ON user_roles(user_id, role_id, is_active);
```

## Schema Relationships

### Many-to-Many Relationship Structure

```
Users (1) ←→ (M) user_roles (M) ←→ (1) Roles
```

### Relationship Benefits

1. **Flexibility**: Users can have multiple roles (e.g., admin + care_provider)
2. **Audit Trail**: Track when roles were assigned and by whom
3. **Soft Deletion**: Deactivate roles without losing history
4. **Granular Control**: Fine-grained permission management

## Business Logic Implications

### Role Checking Logic (New)

```python
# Old logic (single role)
user.role.name in required_roles

# New logic (multiple roles)
any(role.name in required_roles for role in user.roles if role.is_active)
```

### Common Use Cases

1. **Admin + Care Provider**: Office manager who also provides treatment
2. **Billing Admin + Office Manager**: Shared administrative responsibilities
3. **Care Provider + Patient**: Staff member receiving treatment
4. **Temporary Roles**: Grant temporary admin access without losing base role

## Data Migration Strategy

### Phase 1: Create New Structure

1. Create `user_roles` junction table
2. Add necessary indexes
3. Update Roles table (chiropractor → care_provider)

### Phase 2: Migrate Existing Data

```sql
-- Migrate all existing user role assignments
INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by_id, is_active)
SELECT
    user_id,
    CASE
        WHEN role_id = (SELECT role_id FROM Roles WHERE name = 'chiropractor')
        THEN (SELECT role_id FROM Roles WHERE name = 'care_provider')
        ELSE role_id
    END as role_id,
    created_at as assigned_at,
    NULL as assigned_by_id, -- System migration
    TRUE as is_active
FROM Users;
```

### Phase 3: Remove Old Structure

```sql
-- Remove single role foreign key
ALTER TABLE Users DROP COLUMN role_id;
```

## SQLAlchemy Model Changes

### User Model (New Relationship)

```python
class User(Base):
    # ... existing fields ...

    # NEW: Many-to-many relationship
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin"  # Eager loading for performance
    )

    # Helper methods
    def has_role(self, role_name: str) -> bool:
        return any(role.name == role_name for role in self.roles)

    def get_active_roles(self):
        # Note: This would need to be implemented with proper query
        # since we can't directly access user_roles.is_active here
        return self.roles
```

### Role Model (Updated Relationship)

```python
class Role(Base):
    # ... existing fields ...

    # UPDATED: Many-to-many relationship
    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles"
    )
```

### New UserRole Association Model

```python
class UserRole(Base):
    __tablename__ = "user_roles"

    user_role_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), default=func.now())
    assigned_by_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='unique_user_role'),
    )
```

## Performance Considerations

### Query Optimization

1. **Eager Loading**: Use `selectin` loading for roles to avoid N+1 queries
2. **Index Usage**: Composite indexes for common lookup patterns
3. **Active Roles Filter**: Index on active roles for performance

### Expected Query Patterns

```sql
-- Get all active roles for a user
SELECT r.name FROM user_roles ur
JOIN roles r ON ur.role_id = r.role_id
WHERE ur.user_id = ? AND ur.is_active = TRUE;

-- Check if user has specific role
SELECT EXISTS(
    SELECT 1 FROM user_roles ur
    JOIN roles r ON ur.role_id = r.role_id
    WHERE ur.user_id = ? AND r.name = ? AND ur.is_active = TRUE
);

-- Get all users with specific role
SELECT u.* FROM users u
JOIN user_roles ur ON u.user_id = ur.user_id
JOIN roles r ON ur.role_id = r.role_id
WHERE r.name = ? AND ur.is_active = TRUE;
```

## Security & HIPAA Considerations

### Audit Trail Requirements

- Track all role assignments/removals
- Record who made the changes
- Maintain historical data for compliance
- Log access attempts with multiple roles

### Access Control

- Role deactivation instead of deletion preserves audit trail
- Granular permission checking with multiple roles
- Clear role hierarchy and precedence rules

### Data Minimization

- Users only get roles they need
- Temporary role assignments possible
- Clear role expiration mechanisms

## libSQL/SQLite Compatibility

### Supported Features

- ✅ Foreign key constraints
- ✅ Unique constraints
- ✅ Indexes
- ✅ Triggers
- ✅ Transactions

### Schema Adjustments for libSQL

- Use `INTEGER` instead of `SERIAL` for auto-increment
- Ensure proper foreign key pragma enabled
- Use compatible timestamp functions

### Final Schema (libSQL Compatible)

```sql
-- UserRoles Table: Junction table for many-to-many User-Role relationship
CREATE TABLE user_roles (
    user_role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    assigned_at DATETIME DEFAULT (datetime('now')),
    assigned_by_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES Roles(role_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by_id) REFERENCES Users(user_id) ON DELETE SET NULL,
    UNIQUE (user_id, role_id)
);
```

## Validation & Testing

### Data Integrity Checks

1. Verify all existing users maintain their roles after migration
2. Ensure no orphaned role assignments
3. Validate foreign key constraints
4. Test role assignment/removal operations

### Performance Testing

1. Benchmark role checking queries
2. Test with multiple roles per user
3. Validate index usage
4. Monitor query execution plans

## Next Steps

1. **Review and Approval**: Get stakeholder sign-off on design
2. **Implementation**: Update SQLAlchemy models (Task 34.3)
3. **RBAC Update**: Modify role checking logic (Task 34.4)
4. **Migration Script**: Create data migration (Task 34.7)
5. **Testing**: Comprehensive validation (Task 34.9)

## Risk Mitigation

### Rollback Plan

- Maintain backup before migration
- Implement reverse migration script
- Test rollback procedures
- Monitor for issues post-deployment

### Performance Monitoring

- Set up query performance alerts
- Monitor role checking latency
- Track database query patterns
- Optimize indexes as needed

## Conclusion

This many-to-many schema design provides the flexibility needed for complex role requirements while maintaining HIPAA compliance and system performance. The design accounts for libSQL/SQLite compatibility and includes comprehensive audit trails for regulatory compliance.
