-- MIGRATION: 20250605001743_finalize_users_table_migration.sql
-- CREATED_AT: 2025-06-05T00:17:43.060997
-- DESCRIPTION: Drop old users table and rename users_new to users

-- UP script
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

-- DOWN script
-- Recreate users table with role_id column
CREATE TABLE users_old (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role_id INTEGER,
    join_code TEXT UNIQUE,
    office_id INTEGER,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    activated_at DATETIME,
    deactivated_at DATETIME,
    last_billed_cycle DATETIME,
    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE SET NULL,
    FOREIGN KEY (office_id) REFERENCES offices(office_id) ON DELETE SET NULL
);

-- Copy data back and restore first role assignment for each user
INSERT INTO users_old (
    user_id, email, password_hash, name, role_id, join_code, office_id,
    created_at, updated_at, activated_at, deactivated_at, last_billed_cycle
)
SELECT 
    u.user_id, u.email, u.password_hash, u.name, 
    (SELECT ur.role_id FROM user_roles ur WHERE ur.user_id = u.user_id AND ur.is_active = 1 LIMIT 1) as role_id,
    u.join_code, u.office_id, u.created_at, u.updated_at,
    u.activated_at, u.deactivated_at, u.last_billed_cycle
FROM users u;

-- Drop current table and rename old table back
DROP TABLE users;
ALTER TABLE users_old RENAME TO users;

