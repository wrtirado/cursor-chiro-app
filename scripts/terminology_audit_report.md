# Comprehensive Terminology Audit Report

**Task 35.1: Complete analysis of 'chiropractor' → 'care_provider' terminology update**

Generated: $(date '+%Y-%m-%d %H:%M:%S')

## Executive Summary

Based on comprehensive search analysis, this audit identified **481+ instances** of 'chiropractor' terminology requiring updates:

- **182 direct 'chiropractor' references**
- **299+ compound references** (chiropractor_id, chiropractors, etc.)

## Audit Categories

### 1. Database Schema References (HIGH PRIORITY)

**Files requiring database field updates:**

#### Database Schema Files:

- `database/init_schema.sql` (Line 46): `chiropractor_id` field definition
- `migrations/20250522044259_initial_database_setup.sql` (Line 54): `chiropractor_id` field

#### SQLAlchemy Models:

- **TherapyPlan model**: Contains `chiropractor_id` field throughout codebase
- **Foreign key relationships**: References to `chiropractor_id` in business logic

### 2. API Layer Updates (HIGH PRIORITY)

**Core API components requiring updates:**

#### Enum Definitions:

- `api/core/config.py`: `CHIROPRACTOR = "chiropractor"` → `CARE_PROVIDER = "care_provider"`

#### API Router Files with Role Checks:

- `api/media/router.py` (Lines 14, 36): Documentation and role requirements
- `api/progress/router.py` (Lines 53-55, 64, 69): Comments and authorization logic
- `api/branding/router.py` (Lines 75, 128, 264): Role requirements in docs
- `api/plans/router.py` (Lines 34, 55, 83, 119, 144, 148, 172): Business logic using `chiropractor_id`

#### CRUD Operations:

- `api/crud/crud_plan.py`:

  - Line 22: `get_plans_by_chiropractor()` function name
  - Line 25: `.filter(TherapyPlan.chiropractor_id == chiropractor_id)`
  - Line 49: `create_plan()` parameter `chiropractor_id`
  - Line 53: Field assignment `chiropractor_id=chiropractor_id`

- `api/crud/crud_user.py`:
  - Line 51: Comment about "chiropractors"
  - Line 53: Comment assuming chiropractor role ID
  - Line 55: Variable `temp_chiro_role_id`
  - Line 117: Function `associate_user_with_chiro()`
  - Line 118: Comment about "chiropractor/office"
  - Line 121-123: Variable `chiro` and related logic

#### Authentication & Authorization:

- `api/auth/router.py` (Lines 103-104): `associate_user_with_chiro()` call
- `api/users/router.py` (Lines 75-76): Comments about chiropractor management

#### Schema Definitions:

- `api/schemas/plan.py` (Line 64): Comment referencing old field name

### 3. Business Logic & Comments (MEDIUM PRIORITY)

**Documentation and comments requiring updates:**

#### Function Names and Variables:

- `get_plans_by_chiropractor()` → `get_plans_by_care_provider()`
- `associate_user_with_chiro()` → `associate_user_with_care_provider()`
- `temp_chiro_role_id` → `temp_care_provider_role_id`
- `chiro` variable → `care_provider`

#### Comments and Documentation:

- 25+ inline comments referencing "chiropractor" or "chiropractors"
- API endpoint documentation strings
- Business logic explanations

### 4. Application Configuration (HIGH PRIORITY)

**Core application branding and configuration:**

#### Project Naming:

- `README.md`: "Tirado Chiro App" project title
- `api/main.py` (Line 143): "Tirado Chiropractic API" welcome message
- `api/core/config.py` (Line 22): `PROJECT_NAME = "Tirado Chiro API"`

### 5. Documentation Files (LOW PRIORITY)

**External documentation requiring terminology updates:**

#### Technical Documentation:

- `docs/sdp.md` (12 references): System design and API documentation
- `docs/healthcare-compliance.md` (20+ references): HIPAA compliance documentation
- `docs/prd.md` (8 references): Product requirements documentation
- `docs/payment-plan.md` (3 references): Business model documentation
- `docs/many-to-many-role-system-documentation.md`: Implementation notes
- `docs/role-system-audit-report.md`: Previous audit references

#### Migration Documentation:

- `migration_validation_summary.md`: References to terminology changes

### 6. Test Files (MEDIUM PRIORITY)

**Testing infrastructure referencing old terminology:**

- `test_migration_functionality.py` (Lines 125-133): Role name validation tests
- `debug_migration.py` (Line 34-36): Database role queries
- `scripts/validate_role_migration.py` (Lines 142-164): Migration validation logic

### 7. Task Management Files (LOW PRIORITY)

**Project management documentation:**

- `tasks/tasks.json`: 50+ references in task descriptions
- `tasks/*.txt` files: Individual task documentation
- Previous audit reports and implementation notes

### 8. Migration & Cleanup Scripts (HIGH PRIORITY)

**Database migration utilities:**

- `cleanup_partial_migration.py` (Line 33): Rollback logic
- `fix_migration_data.py` (Lines 15-18): Role name updates

## Risk Assessment

### HIGH RISK (Immediate Action Required):

1. **Database schema inconsistencies**: Field names not matching role terminology
2. **API endpoint functionality**: Business logic using outdated field names
3. **Authentication/authorization**: Role checks using outdated enum values

### MEDIUM RISK (Address Soon):

1. **Function naming**: Misleading function names for maintenance
2. **Test coverage**: Tests validating outdated terminology
3. **Comments/documentation**: Developer confusion during maintenance

### LOW RISK (Can Be Deferred):

1. **External documentation**: Non-functional but important for clarity
2. **Project branding**: Cosmetic changes for consistency

## Recommended Update Sequence

### Phase 1: Core Infrastructure (Subtasks 35.1-35.3)

1. **Database schema updates** (35.2)
2. **API layer enum and role updates** (35.3)

### Phase 2: Business Logic (Subtasks 35.4-35.6)

1. **Function names and CRUD operations** (35.4)
2. **Authentication and authorization logic** (35.5)
3. **Test updates and validation** (35.6)

### Phase 3: Documentation & Cleanup (Subtasks 35.7-35.8)

1. **Comments and inline documentation** (35.7)
2. **External documentation and branding** (35.8)

## Search Patterns Used

This audit used the following search patterns to ensure comprehensive coverage:

- `chiropractor` (case-insensitive): 182 direct matches
- `chiro` (case-insensitive): Additional abbreviated references
- `CHIROPRACTOR` (case-sensitive): Enum and constant definitions
- `chiropractor_id` (case-insensitive): Database field references
- `chiropractors` (case-insensitive): Plural form references

## Validation Checklist

After completing updates, verify:

- [ ] All database schema references updated
- [ ] API endpoints functional with new terminology
- [ ] Role-based access control working correctly
- [ ] Tests passing with updated terminology
- [ ] Documentation consistent throughout
- [ ] No broken function/variable references
- [ ] Migration scripts handle terminology correctly

## Impact Analysis

**Development Impact**: Medium

- Requires coordinated updates across multiple layers
- Testing required after each phase
- No external API breaking changes (internal refactoring)

**Business Impact**: Low

- Pure terminology update, no functional changes
- Improves consistency with healthcare industry standards
- Prepares system for broader healthcare provider support

---

**Total Files Requiring Updates**: 50+ files identified
**Estimated Lines of Code Affected**: 481+ instances
**Completion Priority**: Execute immediately (development environment)
