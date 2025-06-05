-- MIGRATION: 20250605002000_create_audit_logs_table.sql
-- CREATED_AT: 2025-06-05T00:20:00.000000
-- DESCRIPTION: Create audit_logs table for HIPAA-compliant database audit logging

-- UP script
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER,
    event_type TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    outcome TEXT NOT NULL DEFAULT 'SUCCESS',
    source_ip TEXT,
    user_agent TEXT,
    request_path TEXT,
    request_method TEXT,
    message TEXT NOT NULL,
    props TEXT, -- JSON string for additional structured data
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
);

-- Create indexes for performance and common audit queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_outcome ON audit_logs(outcome);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_event ON audit_logs(user_id, event_type);

-- DOWN script
-- Remove indexes first
DROP INDEX IF EXISTS idx_audit_logs_user_event;
DROP INDEX IF EXISTS idx_audit_logs_outcome;
DROP INDEX IF EXISTS idx_audit_logs_resource_type;
DROP INDEX IF EXISTS idx_audit_logs_event_type;
DROP INDEX IF EXISTS idx_audit_logs_user_id;
DROP INDEX IF EXISTS idx_audit_logs_timestamp;

-- Remove the table
DROP TABLE IF EXISTS audit_logs; 