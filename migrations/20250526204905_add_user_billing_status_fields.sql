-- MIGRATION: 20250526204905_add_user_billing_status_fields.sql
-- CREATED_AT: 2025-05-26T20:49:05.527858

-- UP script
-- Add billing status fields to users table
ALTER TABLE users ADD COLUMN is_active_for_billing INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE users ADD COLUMN activated_at DATETIME;
ALTER TABLE users ADD COLUMN deactivated_at DATETIME;
ALTER TABLE users ADD COLUMN last_billed_cycle DATETIME;

-- Add indexes for billing queries
CREATE INDEX idx_users_is_active_for_billing ON users(is_active_for_billing);
CREATE INDEX idx_users_activated_at ON users(activated_at);
CREATE INDEX idx_users_last_billed_cycle ON users(last_billed_cycle);

-- DOWN script
-- Remove indexes first
DROP INDEX IF EXISTS idx_users_last_billed_cycle;
DROP INDEX IF EXISTS idx_users_activated_at;
DROP INDEX IF EXISTS idx_users_is_active_for_billing;

-- Remove billing status fields from users table
-- Note: SQLite doesn't support DROP COLUMN directly, so we document the fields for manual cleanup if needed
-- In production, consider using table recreation if rollback is essential
-- For now, the fields will remain but be unused after rollback
-- ALTER TABLE users DROP COLUMN last_billed_cycle;
-- ALTER TABLE users DROP COLUMN deactivated_at;
-- ALTER TABLE users DROP COLUMN activated_at;
-- ALTER TABLE users DROP COLUMN is_active_for_billing;

