# Custom Database Migration Tool Documentation

This document provides comprehensive information on how to install, use, and extend the custom database migration tool for libSQL.

## Table of Contents

- [Installation Guide](#installation-guide)
- [Command Reference](#command-reference)
  - [migrate:status](#migratestatus)
  - [migrate:create NAME](#migratecreate-name)
  - [migrate:up](#migrateup)
  - [migrate:down](#migratedown)
- [Migration File Format](#migration-file-format)
- [Configuration](#configuration)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Developer Documentation](#developer-documentation)
- [Best Practices](#best-practices)

## Installation Guide

_(Details on how to install and set up the migration tool will go here. This should include any dependencies, environment setup, and initial configuration steps.)_

## Command Reference

This section details the available commands and their usage.

### migrate:status

**Description:** Shows the current status of all migrations. It lists which migrations have been applied, which are pending, and provides a summary.

**Usage:**

```bash
migrate:status
```

**Output Example:**

```
Migration Status:
--------------------------------------------------
Applied: 20230615120000_add_user_table.sql
Pending: 20230616100000_add_product_table.sql
--------------------------------------------------
Total Migrations: 2
Applied: 1
Pending: 1
```

### migrate:create NAME

**Description:** Generates a new migration file with a timestamp prefix and the provided name.

**Usage:**

```bash
migrate:create <NAME>
```

- `<NAME>`: A descriptive name for the migration (e.g., `add_order_table`).

**Example:**

```bash
migrate:create add_customer_address_column
```

This will create a file like `migrations/YYYYMMDDHHMMSS_add_customer_address_column.sql`.

### migrate:up

**Description:** Applies pending migrations to the database.

**Usage:**

```bash
migrate:up [--step=N]
```

- `--step=N` (optional): Apply the next `N` pending migrations. If not specified, all pending migrations are applied.

**Examples:**

```bash
# Apply all pending migrations
migrate:up

# Apply the next 2 pending migrations
migrate:up --step=2
```

### migrate:down

**Description:** Rolls back applied migrations.

**Usage:**

```bash
migrate:down [--step=N]
```

- `--step=N` (optional): Roll back the last `N` applied migrations. If not specified, only the most recent migration is rolled back.

**Examples:**

```bash
# Roll back the most recently applied migration
migrate:down

# Roll back the last 3 applied migrations
migrate:down --step=3
```

## Migration File Format

Each migration file is a standard SQL file containing "up" and "down" sections, clearly marked with comments.

**Structure:**

```sql
-- Up Migration
-- SQL statements to apply the migration (e.g., CREATE TABLE, ALTER TABLE ADD COLUMN)
-- Ensure this section is idempotent or handles existing schema gracefully if possible.
-- Example:
-- CREATE TABLE IF NOT EXISTS users (
--     id INTEGER PRIMARY KEY,
--     name TEXT NOT NULL
-- );

-- Down Migration
-- SQL statements to roll back the migration (e.g., DROP TABLE, ALTER TABLE DROP COLUMN)
-- Ensure this section correctly reverses the "Up Migration".
-- Example:
-- DROP TABLE IF EXISTS users;
```

**Naming Convention:**
Migration files are named with a timestamp prefix followed by a descriptive name, e.g., `YYYYMMDDHHMMSS_description.sql`. The tool uses the timestamp for ordering.

## Configuration

The migration tool requires database connection details. These can be configured through:

1.  **Environment Variables:**

    - `DB_URL`: The connection string for the libSQL database.
    - _(Add other relevant environment variables like `MIGRATIONS_DIR` if applicable)_

2.  **Configuration File (Optional):**
    - _(Specify if a config file like `config.json` or `.env` file is supported, and its format)_

_(Detailed instructions on setting up connection strings and other configurations will go here.)_

## Troubleshooting Guide

This section covers common issues and how to resolve them.

- **Issue: Connection Errors**

  - **Solution:** Verify `DB_URL` is correct. Check network connectivity to the database. Ensure database credentials are valid.

- **Issue: Migration Fails to Apply**

  - **Solution:** Check the SQL syntax in the migration file. Look at the tool's logs for specific error messages. Ensure the "up" script is valid and doesn't conflict with existing schema in an unexpected way.

- **Issue: Migration Fails to Rollback**
  - **Solution:** Check the SQL syntax in the "down" section of the migration file. Ensure the "down" script correctly reverses the changes made by the "up" script.

_(Add more common issues and solutions as they become apparent.)_

## Developer Documentation

This section is for developers who want to contribute to or extend the migration tool.

- **Project Structure:**

  - _(Brief overview of the codebase structure, key modules, and their responsibilities.)_

- **Adding New Commands:**

  - _(Guidelines on how to add new CLI commands.)_

- **Testing:**

  - _(Information on how to run existing tests and write new ones. Refer to the test strategy outlined in Task #33.)_

- **Contribution Guidelines:**
  - _(Coding standards, branching strategy, pull request process, etc.)_

## Best Practices

- **Keep Migrations Small and Focused:** Each migration should address a single, atomic change.
- **Test Migrations Thoroughly:** Especially the "down" migration, to ensure data integrity.
- **Never Edit Applied Migrations:** Once a migration is applied to a shared environment (staging, production), do not modify its "up" script. Create a new migration to make further changes.
- **Write Idempotent "Up" Scripts:** Where possible, write "up" scripts that can be run multiple times without causing errors (e.g., using `CREATE TABLE IF NOT EXISTS`).
- **Coordinate with Team:** Communicate with your team before running migrations that might impact others or shared databases.
- **Backup Data:** Before running significant migrations on production, always ensure you have a recent database backup.

_(Add any other project-specific best practices.)_
