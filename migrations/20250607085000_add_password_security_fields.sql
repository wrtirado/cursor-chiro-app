-- Migration: Add HIPAA-compliant password security fields to users table
-- Date: 2025-06-07 08:50:00
-- Description: Adds password history, failed login tracking, and account lockout fields

-- UP script

-- Add password security fields to users table
ALTER TABLE users ADD COLUMN password_history TEXT; -- JSON array of password hashes
ALTER TABLE users ADD COLUMN password_changed_at DATETIME;
ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN last_failed_login DATETIME;
ALTER TABLE users ADD COLUMN account_locked_until DATETIME;
ALTER TABLE users ADD COLUMN last_successful_login DATETIME;

-- Add indexes for performance on security queries
CREATE INDEX idx_users_failed_login_attempts ON users(failed_login_attempts);
CREATE INDEX idx_users_account_locked_until ON users(account_locked_until);
CREATE INDEX idx_users_last_failed_login ON users(last_failed_login);

-- Set initial password_changed_at for existing users (assume password was set at creation)
UPDATE users SET password_changed_at = created_at WHERE password_changed_at IS NULL; 