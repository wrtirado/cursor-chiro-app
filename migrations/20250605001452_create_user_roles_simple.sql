-- MIGRATION: 20250605001452_create_user_roles_simple.sql
-- CREATED_AT: 2025-06-05T00:14:52.727997
-- DESCRIPTION: Create user_roles junction table (simple version for testing)

-- UP script
CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    assigned_at DATETIME DEFAULT (datetime('now')),
    assigned_by_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES Roles(role_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by_id) REFERENCES Users(user_id) ON DELETE SET NULL,
    UNIQUE (user_id, role_id)
);

-- DOWN script
DROP TABLE IF EXISTS user_roles;

