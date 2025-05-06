# Areas of Impact & Changes Needed: PostgreSQL to libSQL Migration

Migrating the backend from PostgreSQL to libSQL/SQLite involves significant changes across multiple areas.

## 1. Database Server Setup (`docker-compose.yml`)

- **Current:** Uses the `postgres:15-alpine` image, standard Postgres environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`), and a specific volume (`postgres_data`).
- **Change Required:**
  - Replace the `db` service definition in `docker-compose.yml`.
  - Use a libSQL server image (e.g., `ghcr.io/tursodatabase/libsql-server`) or configure for a local file-based database (`.db`/`.sqlite`).
  - Update the `DATABASE_URL` environment variable in the `api` service configuration to use the SQLite/libSQL format (e.g., `sqlite+libsql://...` or `sqlite:///path/to/database.db`).
  - Adapt environment variables for database configuration as needed for libSQL.
  - Modify volume definitions for persistent storage.
- **Difficulty:** Moderate. Requires sourcing and correctly configuring the libSQL environment within Docker Compose.

## 2. SQLAlchemy Configuration & Dialect

- **Current:** Implicitly uses the `postgresql` dialect (likely via `psycopg2` driver) based on the `DATABASE_URL`.
- **Change Required:**
  - Ensure the `DATABASE_URL` uses the correct format for SQLite/libSQL.
  - Verify the necessary SQLAlchemy dialect driver is installed or available in the `api` container's Python environment (`sqlite3` is built-in; specific drivers like `libsql-experimental` might be needed for server features).
  - Potentially configure SQLAlchemy or the connection to explicitly enable foreign key support for SQLite (e.g., using `PRAGMA foreign_keys=ON;` or through SQLAlchemy event listeners).
- **Difficulty:** Low to Moderate. Primarily involves configuration adjustments and driver verification.

## 3. SQLAlchemy Models (`api/models/base.py`)

- **Current:** Utilizes PostgreSQL-specific or well-supported types like `TIMESTAMP(timezone=True)`, `JSON`, `String(length=...)`.
- **Change Required:** Adapt models to SQLite's more limited, affinity-based type system (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `NUMERIC`).
  - **Timestamps:** `TIMESTAMP(timezone=True)` needs review. SQLite doesn't natively store timezone info. Consider storing as UTC TEXT (ISO format) or INTEGER (Unix timestamp) and handling timezone conversions in the application. SQLAlchemy's handling needs verification.
  - **JSON:** Native `JSON` support in SQLite is limited. May need to store as `TEXT` and manage serialization/deserialization application-side, or rely on SQLAlchemy's `JSON` type adapter for SQLite, checking for behavioral differences.
  - **String Length:** `String(length=...)` constraints are generally not enforced by SQLite for `TEXT` columns. Validation should rely on Pydantic or application logic.
  - **Encryption (`EncryptedType`):** Should still work as it relies on `Text`, which maps cleanly to SQLite's `TEXT` affinity.
- **Difficulty:** Moderate. Requires careful review and potential modification of all data types used in models, with special attention to timestamps and JSON.

## 4. Alembic Migrations (`alembic/` directory)

- **Current:** Existing migration scripts (`*.py` files in `alembic/versions/`) contain PostgreSQL-specific SQL operations and type definitions.
- **Change Required:** Existing migration scripts are **largely incompatible** with SQLite due to differences in SQL syntax, type handling, and `ALTER TABLE` support.
  - **Option A (Hard):** Manually edit every existing migration file to use SQLite-compatible syntax and operations. Very complex and error-prone.
  - **Option B (Easier, Loses History):** Delete all files within `alembic/versions/`. Generate a single new "initial" migration based on the SQLite-adapted models (`alembic revision --autogenerate -m "Initial schema for SQLite/libSQL"`).
  - Alembic's autogenerate feature may behave differently with SQLite.
  - SQLite's limited `ALTER TABLE` often forces Alembic into "batch mode" for complex changes, which can be fragile.
- **Difficulty:** **Very High.** This is a major undertaking. Reworking existing migrations is difficult; starting fresh simplifies the process but erases the schema evolution history.

## 5. Raw SQL & Initialization (`database/init_schema.sql`, `scripts/seed_admin.py`)

- **Current:** `init_schema.sql` uses PostgreSQL-specific syntax (`SERIAL PRIMARY KEY`, `TIMESTAMP WITH TIME ZONE`, custom functions/triggers). `seed_admin.py` uses SQLAlchemy.
- **Change Required:**
  - **`init_schema.sql`:** Needs a **complete rewrite** using SQLite syntax (`INTEGER PRIMARY KEY AUTOINCREMENT`, different type names, standard SQL triggers if needed). The `INSERT INTO Roles` statement is likely portable.
  - **`seed_admin.py`:** Should require minimal changes _if_ the SQLAlchemy models (`api/models/base.py`) are correctly adapted for SQLite first. It primarily interacts with the ORM, not raw SQL.
- **Difficulty:** High (for rewriting `init_schema.sql`), Low (for `seed_admin.py` assuming models are correct).
