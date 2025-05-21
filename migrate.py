import typer
import os
from datetime import datetime
import libsql_client
from dotenv import load_dotenv
import asyncio
import logging

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler("logs/migration.log"),  # Log to a file in logs/ directory
        logging.StreamHandler(),  # Log to console
    ],
)
logger = logging.getLogger(__name__)


# --- Custom Exceptions ---
class MigrationError(Exception):
    """Base exception for migration errors."""

    pass


class DatabaseConnectionError(MigrationError):
    """Error connecting to the database."""

    pass


class MigrationFileError(MigrationError):
    """Error related to migration files (e.g., not found, parsing error)."""

    pass


class MigrationSQLError(MigrationError):
    """Error executing SQL during migration."""

    pass


# --- End Custom Exceptions ---

app = typer.Typer(help="Custom migration tool for libSQL.")
MIGRATIONS_DIR = "migrations"


# --- Configuration and DB Connection ---
def get_db_url(db_url_override: str = None) -> str:
    if db_url_override:
        logger.info(f"Using provided DB URL override: {db_url_override}")
        return db_url_override
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not found in environment or .env file.")
        typer.secho(
            "Error: DATABASE_URL not found in environment or .env file. "
            "Please set it (e.g., in a .env file or as an environment variable) "
            "or use the --db-url option.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    logger.info(f"Retrieved DATABASE_URL from environment: {db_url}")
    return db_url


def create_db_client(db_url: str):
    logger.info(f"Attempting to create database client for URL: {db_url}")
    try:
        adapted_db_url = db_url
        if db_url.startswith("sqlite+libsql://"):
            adapted_db_url = db_url.replace("sqlite+libsql://", "http://", 1)
            logger.debug(f"Adapted URL from sqlite+libsql:// to {adapted_db_url}")
        elif db_url.startswith(
            "libsql://"
        ):  # For remote Turso or sqld with libsql scheme
            logger.debug(f"Using libsql:// URL as is: {adapted_db_url}")
            # No change needed, libsql_client supports this directly
            pass
        elif db_url.startswith("sqlite+http://"):  # For local sqld over http
            adapted_db_url = db_url.replace("sqlite+http://", "http://", 1)
            logger.debug(f"Adapted URL from sqlite+http:// to {adapted_db_url}")
        elif db_url.startswith("sqlite+ws://"):  # For local sqld over ws
            adapted_db_url = db_url.replace("sqlite+ws://", "ws://", 1)
            logger.debug(f"Adapted URL from sqlite+ws:// to {adapted_db_url}")
        elif db_url.startswith(
            "sqlite:////"
        ):  # Absolute path, e.g., sqlite:////path/to/file.db
            # Path part will be like "/path/to/file.db"
            path = db_url[len("sqlite:///") :]
            adapted_db_url = "file://" + path  # Results in "file:///path/to/file.db"
            logger.debug(
                f"Adapted URL from sqlite://// to {adapted_db_url} for absolute file access."
            )
        elif db_url.startswith(
            "sqlite:///"
        ):  # Relative path, e.g., sqlite:///file.db or :memory:
            path = db_url[len("sqlite:///") :]
            if path == ":memory:":
                # For :memory:, it's better to use the in_memory flag of create_client if available,
                # but adapting to "file::memory:" might work for some setups or if direct flag usage is complex here.
                # However, `libsql_client` prefers `in_memory=True` over a special URL for this.
                # For now, we'll adapt to a file string that might work, or let it be handled by `in_memory` if used.
                # The original error was not for :memory:, so focusing on file paths.
                # Let's assume `create_client` is called without `in_memory=True` for this path.
                # `file::memory:` is not standard. It's better to handle :memory: by passing `in_memory=True`
                # to `libsql_client.create_client()`. This adaptation is a fallback if not using that flag.
                # Given the context, it's more likely a file path.
                # If it's truly just "sqlite:///:memory:", this should ideally be caught earlier
                # and `in_memory=True` passed to `create_client`.
                # Sticking to file path adaptation:
                adapted_db_url = "file::memory:"  # This is a guess; actual :memory: handling is different
                logger.debug(
                    f"Adapted URL from sqlite:///:memory: to {adapted_db_url}. Consider using in_memory=True with create_client."
                )

            else:  # Relative file path like "file.db"
                adapted_db_url = "file:" + path  # Results in "file:file.db"
                logger.debug(
                    f"Adapted URL from sqlite:/// to {adapted_db_url} for relative file access."
                )
        else:
            logger.warning(
                f"URL {db_url} does not match known adaptation patterns. Using as is."
            )

        typer.echo(f"Attempting to connect with adapted URL: {adapted_db_url}")
        logger.info(f"Final adapted URL for client creation: {adapted_db_url}")
        # Special handling for :memory: with libsql_client
        if adapted_db_url == "file::memory:" or db_url == "sqlite:///:memory:":
            logger.info("Creating in-memory database client.")
            client = libsql_client.create_client(in_memory=True)
        else:
            client = libsql_client.create_client(url=adapted_db_url)
        logger.info("Successfully created DB client.")
        return client
    except Exception as e:
        logger.error(
            f"Error creating database client for URL {db_url}: {e}", exc_info=True
        )
        typer.secho(
            f"Error creating database client: {e}\n"
            f"URL used: {db_url} (adapted to: {adapted_db_url if 'adapted_db_url' in locals() else 'N/A'})\n"
            f"Please check your database URL, network connectivity, and ensure the database server is running.",
            fg=typer.colors.RED,
        )
        raise DatabaseConnectionError(f"Failed to create database client: {e}") from e


def get_migration_files() -> list[str]:
    """Returns a sorted list of .sql migration filenames from the MIGRATIONS_DIR."""
    logger.info(f"Looking for migration files in directory: {MIGRATIONS_DIR}")
    if not os.path.isdir(MIGRATIONS_DIR):
        logger.warning(f"Migrations directory '{MIGRATIONS_DIR}' not found.")
        typer.echo(
            f"Migrations directory '{MIGRATIONS_DIR}' not found. Please create it if you intend to use migrations."
        )
        return []
    try:
        files = [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")]
        files.sort()
        logger.info(f"Found {len(files)} migration files: {files}")
        return files
    except OSError as e:
        logger.error(
            f"Error reading migrations directory '{MIGRATIONS_DIR}': {e}", exc_info=True
        )
        typer.secho(
            f"Error accessing migrations directory '{MIGRATIONS_DIR}': {e}. Check permissions.",
            fg=typer.colors.RED,
        )
        raise MigrationFileError(f"Could not list migration files: {e}") from e


def parse_migration_sql(filepath: str) -> list[str]:
    """
    Parses a migration SQL file and extracts the UP script.
    Returns the SQL commands for the UP migration as a list of statements.
    """
    logger.info(f"Parsing UP script from migration file: {filepath}")
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except IOError as e:
        logger.error(f"IOError reading migration file {filepath}: {e}", exc_info=True)
        typer.secho(
            f"Error reading migration file: {filepath}. Check file existence and permissions.",
            fg=typer.colors.RED,
        )
        raise MigrationFileError(
            f"Could not read migration file {filepath}: {e}"
        ) from e

    up_script_lines = []
    in_up_script = False
    for line in lines:
        if line.strip().lower() == "-- up script":
            in_up_script = True
            continue
        if line.strip().lower() == "-- down script":
            in_up_script = False
            break

        if in_up_script:
            up_script_lines.append(line)

    full_up_script = "".join(up_script_lines).strip()
    if not full_up_script:
        logger.warning(
            f"No UP script content found in {filepath} between -- UP script and -- DOWN script markers."
        )
        # Return empty list, let caller decide if this is an error
        return []

    statements = []
    for stmt in full_up_script.split(";"):
        stripped_stmt = stmt.strip()
        if stripped_stmt and not stripped_stmt.startswith("--"):
            statements.append(stripped_stmt)
    logger.info(f"Parsed {len(statements)} UP statements from {filepath}")
    return statements


def parse_migration_sql_down(filepath: str) -> list[str]:
    """
    Parses a migration SQL file and extracts the DOWN script.
    Returns the SQL commands for the DOWN migration as a list of statements.
    """
    logger.info(f"Parsing DOWN script from migration file: {filepath}")
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except IOError as e:
        logger.error(f"IOError reading migration file {filepath}: {e}", exc_info=True)
        typer.secho(
            f"Error reading migration file: {filepath}. Check file existence and permissions.",
            fg=typer.colors.RED,
        )
        raise MigrationFileError(
            f"Could not read migration file {filepath}: {e}"
        ) from e

    down_script_lines = []
    in_down_script = False
    for line in lines:
        if line.strip().lower() == "-- down script":
            in_down_script = True
            continue
        if (
            in_down_script and line.strip().lower() == "-- up script"
        ):  # Stop if UP script section encountered
            break

        if in_down_script:
            down_script_lines.append(line)

    full_down_script = "".join(down_script_lines).strip()
    if not full_down_script:
        logger.warning(
            f"No DOWN script content found in {filepath} after -- DOWN script marker."
        )
        # Return empty list, let caller decide if this is an error
        return []

    statements = []
    for stmt in full_down_script.split(";"):
        stripped_stmt = stmt.strip()
        if stripped_stmt and not stripped_stmt.startswith("--"):
            statements.append(stripped_stmt)
    logger.info(f"Parsed {len(statements)} DOWN statements from {filepath}")
    return statements


async def ensure_migrations_table_exists(client: libsql_client.client.Client):
    """Ensures the migrations table exists in the database."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL UNIQUE,
        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    logger.info("Ensuring migrations table exists...")
    try:
        await client.execute(create_table_sql)
        logger.info("Migrations table checked/ensured successfully.")
        typer.echo("Migrations table checked/ensured.")
    except Exception as e:
        logger.error(f"Error ensuring migrations table exists: {e}", exc_info=True)
        typer.secho(
            f"Critical Error: Could not ensure '{MIGRATIONS_TABLE_NAME if 'MIGRATIONS_TABLE_NAME' in locals() else 'migrations'}' table exists: {e}. Check database permissions and connectivity.",
            fg=typer.colors.RED,
        )
        raise MigrationSQLError(f"Failed to ensure migrations table: {e}") from e


# --- End Configuration and DB Connection ---


@app.command()
def status(
    db_url_override: str = typer.Option(
        None, "--db-url", help="Override DATABASE_URL from environment/dotenv"
    )
):
    """Show current migration state."""
    logger.info("Executing 'status' command.")
    actual_db_url = get_db_url(db_url_override)
    typer.echo(f"Using database URL: {actual_db_url}")
    logger.info(f"Using database URL: {actual_db_url} for status command.")

    async def _run_db_operations():
        nonlocal actual_db_url
        client = None
        try:
            client = create_db_client(actual_db_url)
            await ensure_migrations_table_exists(client)

            logger.debug("Executing test query (SELECT 1)")
            rs = await client.execute("SELECT 1")
            if rs.rows and rs.rows[0][0] == 1:
                logger.info("Database connection test query successful.")
                typer.secho(
                    "Database connection successful (test query).",
                    fg=typer.colors.GREEN,
                )
            else:
                logger.warning(
                    "Database connection test query failed or returned unexpected result."
                )
                typer.secho(
                    "Database connection test query failed.",
                    fg=typer.colors.YELLOW,
                )
            logger.info("Fetching applied migration versions from database.")
            rs_applied = await client.execute(
                "SELECT version FROM migrations ORDER BY version ASC"
            )
            applied_versions = [row[0] for row in rs_applied.rows]
            logger.info(
                f"Found {len(applied_versions)} applied migrations: {applied_versions}"
            )

            if applied_versions:
                typer.secho("Applied migrations:", fg=typer.colors.BLUE)
                for version in applied_versions:
                    typer.echo(f"  - {version}")
            else:
                typer.secho("No migrations have been applied.", fg=typer.colors.YELLOW)

        except DatabaseConnectionError as e:
            # Error already logged and user notified by create_db_client
            raise typer.Exit(code=1)
        except MigrationSQLError as e:
            # Error logged and user notified by ensure_migrations_table_exists
            # or by specific SQL execution block
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in 'status' DB operations: {e}",
                exc_info=True,
            )
            typer.secho(
                f"An unexpected error occurred: {e}. Check logs for details.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        finally:
            if client:
                logger.debug("Closing database client in 'status' command.")
                try:
                    await client.close()
                    logger.info("Database client closed successfully.")
                except Exception as e:
                    logger.warning(f"Error closing database client: {e}", exc_info=True)
                    typer.secho(
                        f"Warning: Error closing database client: {e}",
                        fg=typer.colors.YELLOW,
                    )

    try:
        asyncio.run(_run_db_operations())
        logger.info("'status' command completed successfully.")
    except (
        typer.Exit
    ):  # Catch typer.Exit to prevent it from being logged as an unexpected error
        raise
    except Exception as e:  # Catch any other unexpected error from asyncio.run or setup
        logger.critical(
            f"A critical error occurred during the 'status' command execution: {e}",
            exc_info=True,
        )
        typer.secho(
            f"A critical error occurred: {e}. Please check migration.log for detailed information.",
            fg=typer.colors.RED,
        )


@app.command()
def up(
    step: int = typer.Option(
        None, help="Number of migrations to apply. If None, applies all pending."
    ),
    db_url_override: str = typer.Option(
        None, "--db-url", help="Override DATABASE_URL from environment/dotenv"
    ),
):
    """Apply all (or N) pending migrations."""
    logger.info(f"Executing 'up' command with step: {step}")
    actual_db_url = get_db_url(db_url_override)
    typer.echo(f"Attempting to apply migrations using DB: {actual_db_url}")
    logger.info(f"Using database URL: {actual_db_url} for 'up' command.")

    async def _apply_migrations_up():
        nonlocal step
        nonlocal actual_db_url
        client = None
        applied_count = 0
        try:
            client = create_db_client(actual_db_url)
            await ensure_migrations_table_exists(client)

            all_disk_migrations = get_migration_files()
            if not all_disk_migrations:
                logger.info("No migration files found on disk.")
                typer.secho("No migration files found.", fg=typer.colors.YELLOW)
                return

            logger.info("Fetching applied migration versions from database.")
            rs_applied = await client.execute(
                "SELECT version FROM migrations ORDER BY version ASC"
            )
            applied_versions = {row[0] for row in rs_applied.rows}
            logger.info(
                f"Found {len(applied_versions)} applied migrations in DB: {applied_versions}"
            )

            pending_migrations = [
                m for m in all_disk_migrations if m not in applied_versions
            ]

            if not pending_migrations:
                logger.info("Database is already up to date. No pending migrations.")
                typer.secho("Database is already up to date.", fg=typer.colors.GREEN)
                return

            logger.info(
                f"Found {len(pending_migrations)} pending migration(s): {pending_migrations}"
            )
            typer.echo(f"Found {len(pending_migrations)} pending migration(s):")
            for mig in pending_migrations:
                typer.echo(f"  - {mig}")

            migrations_to_apply = pending_migrations
            if step is not None:
                if step <= 0:
                    logger.warning(
                        f"Invalid step count provided: {step}. Must be positive."
                    )
                    typer.secho("Step count must be positive.", fg=typer.colors.RED)
                    return  # Or raise MigrationError("Step count must be positive")
                migrations_to_apply = pending_migrations[:step]
                logger.info(
                    f"Applying up to {step} migrations. Selected: {migrations_to_apply}"
                )
                if not migrations_to_apply:
                    logger.info(
                        "No migrations to apply for the given step count (or all pending already applied)."
                    )
                    typer.secho(
                        "No migrations to apply for the given step count (or all pending already applied).",
                        fg=typer.colors.YELLOW,
                    )
                    return
            else:
                logger.info(f"Applying all pending migrations: {migrations_to_apply}")

            typer.echo(f"Identified {len(migrations_to_apply)} migration(s) to apply:")
            # This loop for echoing is fine, actual application is below
            for mig_file in migrations_to_apply:
                typer.echo(f"  - Will attempt to apply: {mig_file}")

            for mig_filename in migrations_to_apply:
                logger.info(f"Starting application of migration: {mig_filename}")
                typer.echo(f"Applying migration: {mig_filename}...")
                filepath = os.path.join(MIGRATIONS_DIR, mig_filename)

                try:
                    list_of_sql_statements = parse_migration_sql(filepath)
                    if not list_of_sql_statements:
                        logger.error(
                            f"No executable UP statements found in {mig_filename} or parsing failed."
                        )
                        typer.secho(
                            f"  Error: No executable UP statements found in: {mig_filename}. Migration script might be empty or malformed.",
                            fg=typer.colors.RED,
                        )
                        # Consider this a failure for this specific migration
                        raise MigrationFileError(
                            f"No UP statements in {mig_filename} or parsing error."
                        )

                    logger.debug(
                        f"Executing {len(list_of_sql_statements)} UP statements for {mig_filename}: {list_of_sql_statements}"
                    )
                    await client.batch(list_of_sql_statements)
                    logger.info(
                        f"Successfully executed UP statements for {mig_filename}"
                    )

                    insert_sql = "INSERT INTO migrations (version) VALUES (?)"
                    logger.debug(
                        f"Recording application of {mig_filename} in migrations table."
                    )
                    await client.execute(insert_sql, (mig_filename,))
                    logger.info(
                        f"Successfully recorded {mig_filename} in migrations table."
                    )

                    typer.secho(
                        f"  Successfully applied and recorded: {mig_filename}",
                        fg=typer.colors.GREEN,
                    )
                    applied_count += 1
                except (
                    MigrationFileError
                ) as e:  # Catch parsing error from parse_migration_sql
                    logger.error(
                        f"File error during migration {mig_filename}: {e}",
                        exc_info=True,
                    )
                    typer.secho(
                        f"  File error for migration {mig_filename}: {e}",
                        fg=typer.colors.RED,
                    )
                    raise  # Re-raise to be caught by the main try-except block for this command
                except Exception as e:
                    logger.error(
                        f"Error applying migration {mig_filename}: {e}", exc_info=True
                    )
                    typer.secho(
                        f"  Error applying migration {mig_filename}: {e}. Check migration.log for details.",
                        fg=typer.colors.RED,
                    )
                    # This will stop further migrations if one fails
                    raise MigrationSQLError(
                        f"Failed to apply migration {mig_filename}. Error: {e}"
                    ) from e

            if applied_count > 0:
                logger.info(f"Successfully applied {applied_count} migration(s).")
                typer.secho(
                    f"\nSuccessfully applied {applied_count} migration(s).",
                    fg=typer.colors.CYAN,
                )
            elif not migrations_to_apply and pending_migrations:
                # This case means steps were specified but led to no migrations being selected, already handled
                pass
            elif not pending_migrations:
                # Already handled by the check at the beginning
                pass
            else:  # No migrations were applied, but some were identified
                logger.warning(
                    "No migrations were applied in this run, though some were identified."
                )
                typer.secho(
                    "No migrations were applied in this run.", fg=typer.colors.YELLOW
                )
        except DatabaseConnectionError as e:
            # Error already logged and user notified by create_db_client
            raise typer.Exit(code=1)
        except MigrationFileError as e:
            # Errors from get_migration_files or re-raised from parse_migration_sql loop
            logger.error(
                f"Migration file error during 'up' command: {e}", exc_info=True
            )
            # User message likely already shown, or will be generic here
            typer.secho(
                f"A migration file error occurred: {e}. Check logs.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        except MigrationSQLError as e:
            # Specific SQL error during migration application or ensure_migrations_table
            logger.error(f"SQL error during 'up' command: {e}", exc_info=True)
            # User message shown by the block that raised it
            typer.secho(
                f"A database error occurred during migration: {e}. Further migrations aborted. Check logs.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in 'up' command DB operations: {e}",
                exc_info=True,
            )
            typer.secho(
                f"An unexpected error occurred during 'up' command: {e}. Check logs.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        finally:
            if client:
                logger.debug("Closing database client in 'up' command.")
                try:
                    await client.close()
                    logger.info("Database client closed successfully.")
                except Exception as e:
                    logger.warning(
                        f"Error closing database client in 'up' command: {e}",
                        exc_info=True,
                    )
                    typer.secho(
                        f"Warning: Error closing database client: {e}",
                        fg=typer.colors.YELLOW,
                    )

    try:
        asyncio.run(_apply_migrations_up())
        logger.info("'up' command process completed.")
    except typer.Exit:
        raise
    except Exception as e:
        logger.critical(
            f"A critical error occurred during the 'up' command execution: {e}",
            exc_info=True,
        )
        typer.secho(
            f"A critical error occurred: {e}. Please check migration.log for detailed information.",
            fg=typer.colors.RED,
        )


@app.command()
def down(
    step: int = typer.Option(
        1, help="Number of migrations to roll back. Defaults to 1."
    ),
    db_url_override: str = typer.Option(
        None, "--db-url", help="Override DATABASE_URL from environment/dotenv"
    ),
):
    """Rollback the most recent (or N) migrations."""
    logger.info(f"Executing 'down' command with step: {step}")
    actual_db_url = get_db_url(db_url_override)
    typer.echo(f"Attempting to roll back migrations using DB: {actual_db_url}")
    logger.info(f"Using database URL: {actual_db_url} for 'down' command.")

    async def _rollback_migrations_down():
        nonlocal step
        nonlocal actual_db_url
        client = None
        rolled_back_count = 0
        try:
            client = create_db_client(actual_db_url)
            await ensure_migrations_table_exists(
                client
            )  # Good to ensure it exists, though we are deleting from it

            logger.info(
                "Fetching applied migration versions from database (newest first)."
            )
            rs_applied = await client.execute(
                "SELECT version FROM migrations ORDER BY version DESC"
            )
            applied_migrations = [row[0] for row in rs_applied.rows]
            logger.info(
                f"Found {len(applied_migrations)} applied migrations in DB: {applied_migrations}"
            )

            if not applied_migrations:
                logger.info("No migrations have been applied; nothing to roll back.")
                typer.secho(
                    "No migrations have been applied; nothing to roll back.",
                    fg=typer.colors.YELLOW,
                )
                return

            if step <= 0:
                logger.warning(
                    f"Invalid step count for rollback: {step}. Must be positive."
                )
                typer.secho("Step count must be positive.", fg=typer.colors.RED)
                return  # Or raise MigrationError("Step count must be positive")

            migrations_to_rollback = applied_migrations[:step]
            logger.info(
                f"Identified {len(migrations_to_rollback)} migration(s) to roll back: {migrations_to_rollback}"
            )

            if not migrations_to_rollback:
                logger.info(
                    "No migrations to roll back for the given criteria (e.g., step larger than applied count)."
                )
                typer.secho(
                    "No migrations to roll back for the given criteria.",
                    fg=typer.colors.YELLOW,
                )
                return

            typer.echo(
                f"Identified {len(migrations_to_rollback)} migration(s) to roll back (newest first):"
            )
            for mig_filename in migrations_to_rollback:
                typer.echo(f"  - Will attempt to roll back: {mig_filename}")

            for mig_filename in migrations_to_rollback:
                logger.info(f"Starting rollback of migration: {mig_filename}")
                typer.echo(f"Rolling back migration: {mig_filename}...")
                filepath = os.path.join(MIGRATIONS_DIR, mig_filename)

                if not os.path.exists(filepath):
                    logger.error(
                        f"Migration file not found: {filepath}. Cannot roll back."
                    )
                    typer.secho(
                        f"  Error: Migration file not found: {filepath}. Cannot roll back this specific migration. Consider manual intervention or restoring the file.",
                        fg=typer.colors.RED,
                    )
                    raise MigrationFileError(
                        f"Migration file {mig_filename} not found, cannot perform rollback."
                    )
                try:
                    list_of_sql_statements = parse_migration_sql_down(filepath)
                    if not list_of_sql_statements:
                        logger.warning(
                            f"No executable DOWN statements found in {mig_filename}. Proceeding to unmark only."
                        )
                        typer.secho(
                            f"  Warning: No executable DOWN statements found in: {mig_filename}. Will only unmark as applied.",
                            fg=typer.colors.YELLOW,
                        )
                    else:
                        logger.debug(
                            f"Executing {len(list_of_sql_statements)} DOWN statements for {mig_filename}: {list_of_sql_statements}"
                        )
                        await client.batch(list_of_sql_statements)
                        logger.info(
                            f"Successfully executed DOWN script for {mig_filename}"
                        )
                        typer.secho(
                            f"  Successfully executed DOWN script for: {mig_filename}",
                            fg=typer.colors.GREEN,
                        )

                    delete_sql = "DELETE FROM migrations WHERE version = ?"
                    logger.debug(
                        f"Unmarking migration {mig_filename} as applied in migrations table."
                    )
                    await client.execute(delete_sql, (mig_filename,))
                    logger.info(
                        f"Successfully unmarked {mig_filename} in migrations table."
                    )

                    typer.secho(
                        f"  Successfully unmarked migration as applied: {mig_filename}",
                        fg=typer.colors.GREEN,
                    )
                    rolled_back_count += 1
                except (
                    MigrationFileError
                ) as e:  # Catch parsing error from parse_migration_sql_down
                    logger.error(
                        f"File error during rollback of {mig_filename}: {e}",
                        exc_info=True,
                    )
                    typer.secho(
                        f"  File error for migration {mig_filename}: {e}",
                        fg=typer.colors.RED,
                    )
                    raise  # Re-raise to be caught by the main try-except block
                except Exception as e:
                    logger.error(
                        f"Error executing DOWN script or unmarking migration {mig_filename}: {e}",
                        exc_info=True,
                    )
                    typer.secho(
                        f"  Error during rollback of {mig_filename}: {e}. Check migration.log for details.",
                        fg=typer.colors.RED,
                    )
                    raise MigrationSQLError(
                        f"Failed during rollback of {mig_filename}. Error: {e}"
                    ) from e

            if rolled_back_count > 0:
                logger.info(
                    f"Successfully rolled back {rolled_back_count} migration(s)."
                )
                typer.secho(
                    f"\nSuccessfully rolled back {rolled_back_count} migration(s).",
                    fg=typer.colors.CYAN,
                )
            elif not migrations_to_rollback:  # Should have been caught earlier
                pass
            else:  # No migrations were actually rolled back
                logger.warning(
                    "No migrations were rolled back in this run, though some were identified for rollback."
                )
                typer.secho(
                    "No migrations were rolled back in this run.",
                    fg=typer.colors.YELLOW,
                )
        except DatabaseConnectionError as e:
            raise typer.Exit(code=1)
        except MigrationFileError as e:
            logger.error(
                f"Migration file error during 'down' command: {e}", exc_info=True
            )
            typer.secho(
                f"A migration file error occurred: {e}. Check logs.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        except MigrationSQLError as e:
            logger.error(f"SQL error during 'down' command: {e}", exc_info=True)
            typer.secho(
                f"A database error occurred during migration rollback: {e}. Further rollbacks aborted. Check logs.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in 'down' command DB operations: {e}",
                exc_info=True,
            )
            typer.secho(
                f"An unexpected error occurred during 'down' command: {e}. Check logs.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        finally:
            if client:
                logger.debug("Closing database client in 'down' command.")
                try:
                    await client.close()
                    logger.info("Database client closed successfully.")
                except Exception as e:
                    logger.warning(
                        f"Error closing database client in 'down' command: {e}",
                        exc_info=True,
                    )
                    typer.secho(
                        f"Warning: Error closing database client: {e}",
                        fg=typer.colors.YELLOW,
                    )

    try:
        asyncio.run(_rollback_migrations_down())
        logger.info("'down' command process completed.")
    except typer.Exit:
        raise
    except Exception as e:
        logger.critical(
            f"A critical error occurred during the 'down' command execution: {e}",
            exc_info=True,
        )
        typer.secho(
            f"A critical error occurred: {e}. Please check migration.log for detailed information.",
            fg=typer.colors.RED,
        )


@app.command()
def create(name: str = typer.Argument(..., help="Name for the new migration")):
    """Create a new migration file."""
    logger.info(f"Executing 'create' command for migration name: {name}")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{name}.sql"
    filepath = os.path.join(MIGRATIONS_DIR, filename)

    # Ensure MIGRATIONS_DIR exists
    if not os.path.isdir(MIGRATIONS_DIR):
        logger.info(f"Migrations directory '{MIGRATIONS_DIR}' not found, creating it.")
        try:
            os.makedirs(MIGRATIONS_DIR)
            logger.info(f"Successfully created migrations directory: {MIGRATIONS_DIR}")
            typer.echo(f"Created migrations directory: {MIGRATIONS_DIR}")
        except OSError as e:
            logger.error(
                f"Error creating migrations directory '{MIGRATIONS_DIR}': {e}",
                exc_info=True,
            )
            typer.secho(
                f"Error creating migrations directory '{MIGRATIONS_DIR}': {e}. Check permissions.",
                fg=typer.colors.RED,
            )
            raise MigrationFileError(
                f"Could not create migrations directory: {e}"
            ) from e

    template = """\
-- MIGRATION: %(filename)s
-- CREATED_AT: %(timestamp)s

-- UP script
-- Your SQL statements for applying the migration go here. 
-- Do NOT include BEGIN; or COMMIT; as the batch execution handles transactions.

-- DOWN script
-- Your SQL statements for rolling back the migration go here.
-- Do NOT include BEGIN; or COMMIT; as the batch execution handles transactions.

""" % {
        "filename": filename,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        with open(filepath, "w") as f:
            f.write(template)
        logger.info(f"Successfully created migration file: {filepath}")
        typer.echo(f"Created migration: {filepath}")
    except IOError as e:
        logger.error(f"IOError creating migration file {filepath}: {e}", exc_info=True)
        typer.secho(
            f"Error creating migration file: {filepath}. Check permissions and disk space.",
            fg=typer.colors.RED,
        )
        raise MigrationFileError(
            f"Could not create migration file {filepath}: {e}"
        ) from e


if __name__ == "__main__":
    app()
