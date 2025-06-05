-- MIGRATION: 20250605001518_add_user_roles_indexes.sql
-- CREATED_AT: 2025-06-05T00:15:18.759997
-- DESCRIPTION: Add performance indexes to user_roles table

-- UP script
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_active ON user_roles(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_roles_assigned_at ON user_roles(assigned_at);
CREATE INDEX IF NOT EXISTS idx_user_roles_assigned_by ON user_roles(assigned_by_id);

-- DOWN script
DROP INDEX IF EXISTS idx_user_roles_assigned_by;
DROP INDEX IF EXISTS idx_user_roles_assigned_at;
DROP INDEX IF EXISTS idx_user_roles_user_active;
DROP INDEX IF EXISTS idx_user_roles_role_id;
DROP INDEX IF EXISTS idx_user_roles_user_id;

