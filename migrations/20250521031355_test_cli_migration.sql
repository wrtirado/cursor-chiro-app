-- MIGRATION: 20250521031355_test_cli_migration.sql
-- CREATED_AT: 2025-05-21T03:13:55.210780

-- UP script
CREATE TABLE IF NOT EXISTS test_from_migration (id INTEGER PRIMARY KEY);

-- DOWN script
DROP TABLE IF EXISTS test_from_migration;
