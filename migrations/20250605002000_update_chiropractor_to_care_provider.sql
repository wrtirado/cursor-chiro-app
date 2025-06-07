-- MIGRATION: 20250605002000_update_chiropractor_to_care_provider.sql
-- CREATED_AT: 2025-06-05T00:20:00.000Z
-- DESCRIPTION: Update chiropractor terminology to care_provider in database schema

-- UP script

-- Step 1: Rename chiropractor_id column to care_provider_id in TherapyPlans table
ALTER TABLE TherapyPlans RENAME COLUMN chiropractor_id TO care_provider_id;

-- Step 2: Update role name from 'chiropractor' to 'care_provider'
UPDATE Roles SET name = 'care_provider' WHERE name = 'chiropractor';

-- Step 3: Add any missing indexes if needed (none required for this change)

-- DOWN script (rollback)

-- Step 1: Revert role name back to 'chiropractor'
-- UPDATE Roles SET name = 'chiropractor' WHERE name = 'care_provider';

-- Step 2: Revert column name back to chiropractor_id
-- ALTER TABLE TherapyPlans RENAME COLUMN care_provider_id TO chiropractor_id; 