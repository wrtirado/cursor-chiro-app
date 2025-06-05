-- MIGRATION: 20250605001659_copy_users_data.sql
-- CREATED_AT: 2025-06-05T00:16:59.946997
-- DESCRIPTION: Copy user data from users to users_new table (excluding role_id)

-- UP script
INSERT INTO users_new (
    user_id, email, password_hash, name, join_code, office_id,
    created_at, updated_at, activated_at, deactivated_at, last_billed_cycle
)
SELECT 
    user_id, email, password_hash, name, join_code, office_id,
    created_at, updated_at, activated_at, deactivated_at, last_billed_cycle
FROM users;

-- DOWN script
DELETE FROM users_new;

