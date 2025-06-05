-- MIGRATION: 20250605001640_create_users_new_table.sql
-- CREATED_AT: 2025-06-05T00:16:40.247997
-- DESCRIPTION: Create new users table without role_id column

-- UP script
CREATE TABLE users_new (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    join_code TEXT UNIQUE,
    office_id INTEGER,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),
    is_active_for_billing BOOLEAN DEFAULT 0,
    activated_at DATETIME,
    deactivated_at DATETIME,
    last_billed_cycle DATETIME,
    FOREIGN KEY (office_id) REFERENCES offices(office_id) ON DELETE SET NULL
);

-- DOWN script
DROP TABLE IF EXISTS users_new;

