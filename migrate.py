import typer
import os
from datetime import datetime
import libsql_client
from dotenv import load_dotenv
import asyncio

app = typer.Typer(help="Custom migration tool for libSQL.")
MIGRATIONS_DIR = "migrations"


# --- Configuration and DB Connection ---
def get_db_url(db_url_override: str = None) -> str:
    if db_url_override:
        return db_url_override
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        typer.secho(
            "Error: DATABASE_URL not found in environment or .env file. "
            "Please set it or use the --db-url option.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    return db_url


def create_db_client(db_url: str):
    try:
        adapted_db_url = db_url
        if db_url.startswith("sqlite+libsql://"):
            adapted_db_url = db_url.replace("sqlite+libsql://", "http://", 1)
        elif db_url.startswith("libsql://"):
            pass
        elif db_url.startswith("sqlite+http://"):
            adapted_db_url = db_url.replace("sqlite+http://", "http://", 1)
        elif db_url.startswith("sqlite+ws://"):
            adapted_db_url = db_url.replace("sqlite+ws://", "ws://", 1)

        typer.echo(f"Attempting to connect with adapted URL: {adapted_db_url}")
        client = libsql_client.create_client(url=adapted_db_url)
        # typer.echo("Successfully created DB client.") # Optional
        return client
    except Exception as e:
        typer.secho(f"Error creating database client: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def get_migration_files() -> list[str]:
    """Returns a sorted list of .sql migration filenames from the MIGRATIONS_DIR."""
    if not os.path.isdir(MIGRATIONS_DIR):
        typer.echo(f"Migrations directory '{MIGRATIONS_DIR}' not found.")
        return []
    files = [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")]
    files.sort()
    return files


def parse_migration_sql(filepath: str) -> list[str]:
    """
    Parses a migration SQL file and extracts the UP script.
    Returns the SQL commands for the UP migration as a list of statements.
    """
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except IOError:
        typer.secho(f"Error reading migration file: {filepath}", fg=typer.colors.RED)
        return []  # Return empty list on error

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
    # Split by semicolon and filter out empty/comment-only statements
    statements = []
    for stmt in full_up_script.split(";"):
        stripped_stmt = stmt.strip()
        if stripped_stmt and not stripped_stmt.startswith("--"):
            statements.append(stripped_stmt)
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
    try:
        await client.execute(create_table_sql)
        typer.echo("Migrations table checked/ensured.")
    except Exception as e:
        typer.secho(f"Error ensuring migrations table: {e}", fg=typer.colors.RED)
        raise


# --- End Configuration and DB Connection ---


@app.command()
def status(
    db_url_override: str = typer.Option(
        None, "--db-url", help="Override DATABASE_URL from environment/dotenv"
    )
):
    """Show current migration state."""
    actual_db_url = get_db_url(db_url_override)
    typer.echo(f"Using database URL: {actual_db_url}")

    async def _run_db_operations():
        nonlocal actual_db_url
        client = None
        try:
            client = create_db_client(actual_db_url)
            await ensure_migrations_table_exists(client)

            rs = await client.execute("SELECT 1")
            if rs.rows and rs.rows[0][0] == 1:
                typer.secho(
                    "Database connection successful (test query).",
                    fg=typer.colors.GREEN,
                )
            else:
                typer.secho(
                    "Database connection test query failed.",
                    fg=typer.colors.YELLOW,
                )
            typer.echo("Status: Not implemented yet (beyond connection test)")
        finally:
            if client:
                await client.close()

    try:
        asyncio.run(_run_db_operations())
    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED)


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
    actual_db_url = get_db_url(db_url_override)
    typer.echo(f"Attempting to apply migrations using DB: {actual_db_url}")

    async def _apply_migrations_up():
        nonlocal step  # Capture 'step' from outer scope
        nonlocal actual_db_url  # Ensure access if create_db_client is called within this scope
        client = None
        try:
            client = create_db_client(actual_db_url)
            await ensure_migrations_table_exists(client)

            all_disk_migrations = get_migration_files()
            if not all_disk_migrations:
                typer.secho("No migration files found.", fg=typer.colors.YELLOW)
                return

            # Get applied migrations from DB
            rs_applied = await client.execute(
                "SELECT version FROM migrations ORDER BY version ASC"
            )
            applied_versions = {row[0] for row in rs_applied.rows}

            pending_migrations = [
                m for m in all_disk_migrations if m not in applied_versions
            ]

            if not pending_migrations:
                typer.secho("Database is already up to date.", fg=typer.colors.GREEN)
                return

            typer.echo(f"Found {len(pending_migrations)} pending migration(s):")
            for mig in pending_migrations:
                typer.echo(f"  - {mig}")

            migrations_to_apply = pending_migrations
            if step is not None:
                if step <= 0:
                    typer.secho("Step count must be positive.", fg=typer.colors.RED)
                    return
                migrations_to_apply = pending_migrations[:step]
                if not migrations_to_apply:
                    typer.secho(
                        "No migrations to apply for the given step count (or all pending already applied).",
                        fg=typer.colors.YELLOW,
                    )
                    return

            # For now, just print what would be applied
            typer.echo(f"Identified {len(migrations_to_apply)} migration(s) to apply:")
            for mig_file in migrations_to_apply:
                typer.echo(f"  - Would apply: {mig_file}")

            applied_count = 0
            for mig_filename in migrations_to_apply:
                typer.echo(f"Applying migration: {mig_filename}...")
                filepath = os.path.join(MIGRATIONS_DIR, mig_filename)

                list_of_sql_statements = parse_migration_sql(filepath)
                if not list_of_sql_statements:
                    typer.secho(
                        f"  No executable UP statements found in: {mig_filename}",
                        fg=typer.colors.RED,
                    )
                    raise Exception(
                        f"Failed to parse UP script or script is empty for {mig_filename}"
                    )

                try:
                    # Use client.batch() for a list of SQL statements
                    await client.batch(list_of_sql_statements)

                    insert_sql = "INSERT INTO migrations (version) VALUES (?)"
                    await client.execute(insert_sql, (mig_filename,))

                    typer.secho(
                        f"  Successfully applied and recorded: {mig_filename}",
                        fg=typer.colors.GREEN,
                    )
                    applied_count += 1
                except Exception as e:
                    typer.secho(
                        f"  Error applying migration {mig_filename}: {e}",
                        fg=typer.colors.RED,
                    )
                    raise Exception(
                        f"Failed to apply migration {mig_filename}. Error: {e}"
                    )

            if applied_count > 0:
                typer.secho(
                    f"\nSuccessfully applied {applied_count} migration(s).",
                    fg=typer.colors.CYAN,
                )
            elif not migrations_to_apply and pending_migrations:
                pass
            elif not pending_migrations:
                pass
            else:
                typer.secho(
                    "No migrations were applied in this run.", fg=typer.colors.YELLOW
                )

        finally:
            if client:
                await client.close()

    try:
        asyncio.run(_apply_migrations_up())
    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"An error occurred during 'up' command: {e}", fg=typer.colors.RED)


@app.command()
def down(
    step: int = typer.Option(None, help="Number of migrations to roll back"),
    db_url_override: str = typer.Option(
        None, "--db-url", help="Override DATABASE_URL from environment/dotenv"
    ),
):
    """Rollback the most recent (or N) migrations."""
    actual_db_url = get_db_url(db_url_override)
    # client = create_db_client(actual_db_url)
    # ... rest of the implementation ...
    # client.close()
    if step:
        typer.echo(f"Down: Not implemented yet (step={step}) using DB: {actual_db_url}")
    else:
        typer.echo(f"Down: Not implemented yet (1) using DB: {actual_db_url}")


@app.command()
def create(name: str = typer.Argument(..., help="Name for the new migration")):
    """Create a new migration file."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{name}.sql"
    filepath = os.path.join(MIGRATIONS_DIR, filename)

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
        typer.echo(f"Created migration: {filepath}")
    except IOError as e:
        typer.secho(f"Error creating migration file: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
