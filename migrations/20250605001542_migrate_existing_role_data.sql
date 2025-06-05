-- MIGRATION: 20250605001542_migrate_existing_role_data.sql
-- CREATED_AT: 2025-06-05T00:15:42.709997
-- DESCRIPTION: Update role names and migrate existing user role assignments to user_roles table

-- UP script
-- Update role name from "chiropractor" to "care_provider"
UPDATE Roles 
SET name = 'care_provider' 
WHERE name = 'chiropractor';

-- Migrate existing role assignments from Users.role_id to user_roles table
INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by_id, is_active)
SELECT 
    user_id,
    role_id,
    created_at,  -- Use user creation time as assignment time
    NULL,        -- No assigned_by_id for existing data
    1            -- Mark all existing assignments as active
FROM Users 
WHERE role_id IS NOT NULL;

-- DOWN script
-- Remove migrated role assignments
DELETE FROM user_roles;

-- Revert role name from "care_provider" back to "chiropractor"
UPDATE Roles 
SET name = 'chiropractor' 
WHERE name = 'care_provider';

