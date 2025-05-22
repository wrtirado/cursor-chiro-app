import typer
import os
from datetime import datetime
import libsql_client
from dotenv import load_dotenv
import asyncio
import logging
import re

# --- Logging Configuration ---
# Create a file handler
file_handler = logging.FileHandler("logs/migration.log")
file_handler.setLevel(logging.DEBUG)  # Set file handler to DEBUG
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Console can remain INFO
console_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
)

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(
    logging.DEBUG
)  # Set root logger to DEBUG to allow DEBUG messages through
root_logger.handlers = []  # Clear existing handlers if any (e.g., from basicConfig)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
# --- End Logging Configuration ---


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


def parse_migration_sql(filepath: str) -> str:
    """
    Parses a migration SQL file and extracts the UP script content as a single string.
    """
    logger.info(f"Reading UP script content from migration file: {filepath}")
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except IOError as e:
        logger.error(f"IOError reading migration file {filepath}: {e}", exc_info=True)
        typer.secho(
            f"Error reading migration file: {filepath}. Check file existence and permissions.",
            fg=typer.colors.RED,
        )
        raise MigrationFileError(
            f"Could not read migration file {filepath}: {e}"
        ) from e

    up_script_marker = "-- UP script"
    down_script_marker = "-- DOWN script"

    up_start_index = content.lower().find(up_script_marker.lower())
    if up_start_index == -1:
        logger.warning(f"No '{up_script_marker}' found in {filepath}")
        return ""

    up_start_index += len(up_script_marker)

    down_start_index = content.lower().find(down_script_marker.lower(), up_start_index)
    if down_start_index == -1:
        up_script_content = content[up_start_index:]
    else:
        up_script_content = content[up_start_index:down_start_index]

    final_content = up_script_content.strip()
    if not final_content:
        logger.warning(
            f"No UP script content found in {filepath} between '{up_script_marker}' and '{down_script_marker}' markers."
        )
    return final_content


def parse_migration_sql_down(filepath: str) -> str:
    """
    Parses a migration SQL file and extracts the DOWN script content as a single string.
    """
    logger.info(f"Reading DOWN script content from migration file: {filepath}")
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except IOError as e:
        logger.error(f"IOError reading migration file {filepath}: {e}", exc_info=True)
        typer.secho(
            f"Error reading migration file: {filepath}. Check file existence and permissions.",
            fg=typer.colors.RED,
        )
        raise MigrationFileError(
            f"Could not read migration file {filepath}: {e}"
        ) from e

    down_script_marker = "-- DOWN script"
    up_script_marker_for_end = (
        "-- UP script"  # To stop reading if UP script starts again
    )

    down_start_index = content.lower().find(down_script_marker.lower())
    if down_start_index == -1:
        logger.warning(f"No '{down_script_marker}' found in {filepath}")
        return ""

    down_start_index += len(down_script_marker)

    # Find where the DOWN script might end (start of UP script or end of file)
    up_again_start_index = content.lower().find(
        up_script_marker_for_end.lower(), down_start_index
    )
    if up_again_start_index != -1:
        down_script_content = content[down_start_index:up_again_start_index]
    else:
        down_script_content = content[down_start_index:]

    final_content = down_script_content.strip()
    if not final_content:
        logger.warning(
            f"No DOWN script content found in {filepath} after '{down_script_marker}' marker."
        )
    return final_content


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
                    full_up_script = parse_migration_sql(filepath)
                    if not full_up_script:
                        logger.error(
                            f"No executable UP statements found in {mig_filename} or parsing failed."
                        )
                        typer.secho(
                            f"  Error: No executable UP statements found in: {mig_filename}. Migration script might be empty or malformed.",
                            fg=typer.colors.RED,
                        )
                        raise MigrationFileError(
                            f"No UP statements in {mig_filename} or parsing error."
                        )

                    logger.debug(f"--- Full UP Script for {mig_filename} ---")
                    logger.debug(full_up_script)
                    logger.debug("--- End Full UP Script ---")

                    script_to_process = str(full_up_script)
                    processed_parts_for_batch = []

                    logger.info(
                        "Starting DDL processing: searching for CREATE TRIGGER statements."
                    )
                    while True:
                        script_lower = script_to_process.lower()
                        trigger_start_keyword = "create trigger"
                        end_trigger_keyword = "end;"
                        trigger_start_idx = script_lower.find(trigger_start_keyword)

                        if trigger_start_idx == -1:
                            logger.debug("No more 'CREATE TRIGGER' keywords found.")
                            break

                        # Add the part of the script before this trigger to processed_parts_for_batch
                        # This part should contain simple statements to be batched.
                        pre_trigger_script = script_to_process[
                            :trigger_start_idx
                        ].strip()
                        if pre_trigger_script:
                            processed_parts_for_batch.append(pre_trigger_script)

                        # Find the end of this trigger statement (looking for 'END;')
                        # This assumes triggers are not nested and 'END;' is the terminator.
                        # A more robust parser would handle nested BEGIN/END or different terminators.
                        # For now, let's try a simple approach assuming our triggers are straightforward.
                        # This will find the *next* "end;"
                        # A proper SQL parser would be better here.

                        # To make it slightly more robust for simple BEGIN...END; blocks:
                        # Find 'BEGIN' for this trigger
                        begin_idx_abs = -1
                        temp_search_script = script_to_process[trigger_start_idx:]
                        temp_begin_idx_rel = temp_search_script.lower().find("begin")
                        if temp_begin_idx_rel != -1:
                            begin_idx_abs = (
                                trigger_start_idx + temp_begin_idx_rel + len("begin")
                            )

                        end_trigger_idx_marker_start = -1
                        if begin_idx_abs != -1:
                            # Search for 'END;' after 'BEGIN'
                            end_trigger_idx_marker_start = script_lower.find(
                                end_trigger_keyword, begin_idx_abs
                            )
                        else:  # No explicit BEGIN found after CREATE TRIGGER NAME ..., try finding END; anyway
                            logger.warning(
                                f"No 'BEGIN' found for trigger starting at index {trigger_start_idx}. Searching for 'END;' from {trigger_start_idx}"
                            )
                            end_trigger_idx_marker_start = script_lower.find(
                                end_trigger_keyword, trigger_start_idx
                            )

                        if end_trigger_idx_marker_start != -1:
                            trigger_end_idx = end_trigger_idx_marker_start + len(
                                end_trigger_keyword
                            )
                            extracted_trigger_sql = script_to_process[
                                trigger_start_idx:trigger_end_idx
                            ].strip()

                            logger.info(
                                f"Extracted TRIGGER DDL (heuristic):\\n{extracted_trigger_sql}"
                            )
                            try:
                                await client.execute(extracted_trigger_sql)
                                logger.info(
                                    "Successfully executed extracted TRIGGER DDL."
                                )
                            except Exception as e_trigger:
                                logger.error(
                                    f"Error executing TRIGGER DDL: {extracted_trigger_sql}\\nError: {e_trigger}",
                                    exc_info=True,
                                )
                                raise MigrationSQLError(
                                    f"Failed to execute trigger DDL: {e_trigger}"
                                ) from e_trigger

                            script_to_process = script_to_process[trigger_end_idx:]
                        else:
                            logger.error(
                                f"Found 'CREATE TRIGGER' at index {trigger_start_idx} but could not find a corresponding 'END;'. Halting processing of this migration."
                            )
                            # Add remaining script to ensure it's not lost if error occurs after some triggers
                            if script_to_process[trigger_start_idx:].strip():
                                processed_parts_for_batch.append(
                                    script_to_process[trigger_start_idx:].strip()
                                )
                            raise MigrationFileError(
                                f"Malformed TRIGGER statement in {mig_filename}: No 'END;' found after 'CREATE TRIGGER'."
                            )

                    # Add any remaining script after the last trigger (or if no triggers were found)
                    if script_to_process.strip():
                        processed_parts_for_batch.append(script_to_process.strip())

                    logger.info("Finished searching for TRIGGER DDLs.")

                    # Process remaining script: separate INSERTs for Roles, batch the rest
                    statements_for_main_batch = []
                    insert_roles_statements = []

                    if script_to_process.strip():
                        logger.debug(
                            "Processing remaining script part for main batch and Role INSERTs."
                        )
                        potential_statements = [
                            stmt.strip()
                            for stmt in script_to_process.strip().split(";")
                            if stmt.strip() and not stmt.strip().startswith("--")
                        ]
                        for stmt in potential_statements:
                            if stmt.lower().startswith("insert into roles"):
                                insert_roles_statements.append(stmt)
                            else:
                                statements_for_main_batch.append(stmt)

                    # Batch execute DDL (CREATE TABLE, CREATE INDEX, etc.)
                    if statements_for_main_batch:
                        logger.debug(
                            f"Executing main batch of {len(statements_for_main_batch)} statements (DDL, non-Role INSERTs)."
                        )
                        logger.debug(
                            f"Main batch statements: {statements_for_main_batch}"
                        )
                        await client.batch(statements_for_main_batch)
                        logger.info(
                            "Successfully executed main batch of DDL statements."
                        )
                    else:
                        logger.info(
                            "No DDL statements (CREATE TABLE, etc.) to execute in main batch."
                        )

                    # Execute INSERT INTO Roles statements individually
                    if insert_roles_statements:
                        logger.info(
                            f"Executing {len(insert_roles_statements)} INSERT INTO Roles statements individually."
                        )
                        for insert_sql in insert_roles_statements:
                            logger.debug(f"Executing: {insert_sql}")
                            await client.execute(
                                insert_sql
                            )  # No parameters needed as values are in the string
                        logger.info(
                            "Successfully executed INSERT INTO Roles statements."
                        )
                    else:
                        logger.info("No INSERT INTO Roles statements found to execute.")

                    logger.info(
                        f"Successfully processed UP statements for {mig_filename}"
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
                    full_down_script = parse_migration_sql_down(filepath)
                    if not full_down_script:
                        logger.warning(
                            f"No executable DOWN statements found in {mig_filename}. Proceeding to unmark only."
                        )
                        typer.secho(
                            f"  Warning: No executable DOWN statements found in: {mig_filename}. Will only unmark as applied.",
                            fg=typer.colors.YELLOW,
                        )
                        # No actual SQL to execute, so skip to unmarking
                    else:
                        logger.debug(f"--- Full DOWN Script for {mig_filename} ---")
                        logger.debug(full_down_script)
                        logger.debug("--- End Full DOWN Script ---")

                        # Simplified: Batch all DOWN statements
                        simple_down_statements = [
                            stmt.strip()
                            for stmt in full_down_script.split(";")
                            if stmt.strip() and not stmt.strip().startswith("--")
                        ]

                        if simple_down_statements:
                            logger.debug(
                                f"Executing batch of {len(simple_down_statements)} DOWN statements."
                            )
                            logger.debug(
                                f"DOWN statements to batch: {simple_down_statements}"
                            )
                            await client.batch(simple_down_statements)
                            logger.info(
                                f"Successfully processed DOWN script for {mig_filename}"
                            )
                            typer.secho(
                                f"  Successfully executed DOWN script for: {mig_filename}",
                                fg=typer.colors.GREEN,
                            )
                        else:
                            logger.warning(
                                f"The DOWN script for {mig_filename} contained no executable statements after splitting."
                            )
                            typer.secho(
                                f"  Warning: No executable DOWN statements in {mig_filename} to run.",
                                fg=typer.colors.YELLOW,
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
