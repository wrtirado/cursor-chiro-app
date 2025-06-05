-- MIGRATION: 20250526204905_add_user_billing_status_fields.sql
-- CREATED_AT: 2025-05-26T20:49:05.527858

-- UP script
-- Note: This migration originally added billing status fields to the users table
-- However, these fields are now handled by the later users_new migration sequence
-- (migrations 20250605001640_create_users_new_table.sql and related)
-- 
-- To avoid conflicts, this migration is now a no-op
-- The billing fields (is_active_for_billing, activated_at, deactivated_at, last_billed_cycle)
-- are included in the users_new table definition and related indexes

-- No operations needed - handled by later migrations

-- DOWN script  
-- No operations needed - this migration is now a no-op

