# Role System Audit Report

## Task 34.1: Current User-Role Schema and References

**Date**: June 1, 2025  
**Status**: Complete

## Executive Summary

This audit identifies all locations in the codebase where the current single-role system is implemented and needs to be updated for the transition to a many-to-many role relationship system. The audit also identifies all references to the "chiropractor" role that need to be updated to "care_provider".

## Current System Architecture

### Database Schema

- **Current relationship**: One-to-one (User has one Role)
- **Users table**: Contains `role_id` foreign key (NOT NULL)
- **Roles table**: Contains `role_id` primary key and seeded roles

### Seeded Roles

1. `patient`
2. `chiropractor` ← **TO BE CHANGED TO `care_provider`**
3. `office_manager`
4. `billing_admin`
5. `admin`

## Detailed Findings

### 1. Database Schema References

#### Files to Update:

- `database/init_schema.sql` (Lines 23, 34)
- `migrations/20250522044259_initial_database_setup.sql` (Lines 27, 42)

#### Changes Required:

- Remove `role_id` column from Users table
- Create `user_roles` junction table
- Update role seeding to use "care_provider" instead of "chiropractor"

### 2. SQLAlchemy Models

#### File: `api/models/base.py`

- **Role model** (Line 74): `role_id` primary key
- **User model** (Line 83): `role_id` foreign key
- **Relationships**: Need to update to many-to-many with `secondary` table

#### Changes Required:

- Update User-Role relationship to many-to-many
- Create UserRole association table
- Update TherapyPlan.chiropractor_id references

### 3. Pydantic Schemas

#### Files to Update:

- `api/schemas/user.py` (Lines 9, 24): role_id fields
- `api/schemas/role.py` (Line 10): role_id field

#### Changes Required:

- Replace role_id with roles list
- Update UserCreate/UserUpdate schemas
- Add role assignment schemas

### 4. RoleType Enum

#### File: `api/core/config.py` (Lines 12-18)

```python
class RoleType(str, Enum):
    PATIENT = "patient"
    CHIROPRACTOR = "chiropractor"  # ← UPDATE TO CARE_PROVIDER
    OFFICE_MANAGER = "office_manager"
    BILLING_ADMIN = "billing_admin"
    ADMIN = "admin"
```

### 5. RBAC Implementation

#### File: `api/auth/dependencies.py`

- **require_role() function** (Line 49): Currently checks single role
- **Logic**: `RoleType(current_user.role.name) not in required_roles`

#### Changes Required:

- Update to check if ANY of user's roles match required roles
- Modify role validation logic for multiple roles

### 6. API Endpoints Using Role Checks

#### Files with RoleType.CHIROPRACTOR usage:

1. `api/media/router.py` (Lines 9, 15, 35)
2. `api/plans/router.py` (Lines 12, 17-19, 44, 46, 67, 70)
3. `api/progress/router.py` (Lines 9, 15)
4. `api/branding/router.py` (Lines 25, 33-34)
5. `api/companies/router.py` (Line 9)
6. `api/offices/router.py` (Line 8)
7. `api/users/router.py` (Line 8)

#### Changes Required:

- Update all `RoleType.CHIROPRACTOR` to `RoleType.CARE_PROVIDER`
- Ensure role checking logic works with multiple roles

### 7. CRUD Operations

#### Files with role-related logic:

1. `api/crud/crud_user.py` (Lines 47, 52-56): role_id usage and chiropractor checks
2. `api/crud/crud_plan.py` (Lines 10, 107): RoleType usage
3. `api/crud/crud_office.py` (Line 11, 173): Role validation
4. `api/crud/crud_progress.py` (Line 5): RoleType import

### 8. Authentication and Authorization

#### File: `api/auth/router.py`

- Line 55: role_id in registration endpoint docs
- Line 91: Hard-coded "chiropractor" string check
- Lines 62-65: role_id validation (commented)

### 9. Seed Scripts

#### Files to Update:

- `scripts/seed_admin.py` (Lines 13, 27-28, 34-43, 66)
- `scripts/seed_roles.py` (Lines 11, 19-20)

### 10. Business Logic with Role Names

#### TherapyPlan Model:

- `chiropractor_id` field name throughout system
- Business logic assuming plan creators are "chiropractors"

#### Plan Assignment Logic:

- Ownership checks based on chiropractor role
- Access control for plan management

## Impact Assessment

### High Impact Areas:

1. **Authentication & Authorization**: Core RBAC system
2. **API Endpoints**: 15+ endpoints with role checks
3. **Database Schema**: Fundamental relationship change
4. **Business Logic**: Plan ownership and assignment rules

### Medium Impact Areas:

1. **Frontend Integration**: Role selection and display
2. **Audit Logging**: Role change tracking
3. **Documentation**: API docs and system documentation

### Low Impact Areas:

1. **Test Files**: Update test data and assertions
2. **Configuration**: Environment-specific role mappings

## Migration Strategy Recommendations

### Phase 1: Database Schema

1. Create user_roles junction table
2. Migrate existing role_id data
3. Update role names (chiropractor → care_provider)
4. Remove role_id column

### Phase 2: Core Models and RBAC

1. Update SQLAlchemy models
2. Modify require_role() function
3. Update Pydantic schemas

### Phase 3: API Endpoints

1. Update all RoleType.CHIROPRACTOR references
2. Test role checking with multiple roles
3. Update business logic

### Phase 4: Integration and Testing

1. Update frontend components
2. Test complete user workflows
3. Validate HIPAA compliance

## Files Requiring Updates

### Critical Files (Must Update):

- `api/models/base.py`
- `api/core/config.py`
- `api/auth/dependencies.py`
- `database/init_schema.sql`
- Migration files

### API Router Files:

- `api/media/router.py`
- `api/plans/router.py`
- `api/progress/router.py`
- `api/branding/router.py`
- `api/auth/router.py`
- All other router files with role checks

### Schema Files:

- `api/schemas/user.py`
- `api/schemas/role.py`

### CRUD Files:

- `api/crud/crud_user.py`
- `api/crud/crud_plan.py`
- `api/crud/crud_office.py`

### Utility Files:

- `scripts/seed_admin.py`
- `scripts/seed_roles.py`

## Risk Mitigation

### Data Integrity:

- Implement comprehensive migration with rollback capability
- Validate all existing users maintain appropriate access
- Test edge cases with role combinations

### Security:

- Ensure no privilege escalation during transition
- Maintain audit logging throughout process
- Verify HIPAA compliance preserved

### Business Continuity:

- Plan for zero-downtime migration
- Implement feature flags for gradual rollout
- Prepare rollback procedures

## Conclusion

The current role system is deeply integrated throughout the application. The transition to many-to-many roles with the chiropractor→care_provider rename will require coordinated updates across database schema, models, RBAC logic, API endpoints, and business logic. Careful planning and testing will be essential to maintain system integrity and HIPAA compliance.
