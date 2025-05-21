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
            rs = await client.execute("SELECT 1")
            if rs.rows and rs.rows[0][0] == 1:
                typer.secho("Database connection successful.", fg=typer.colors.GREEN)
            else:
                typer.secho(
                    "Database connection test failed to return expected result.",
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
    step: int = typer.Option(None, help="Number of migrations to apply"),
    db_url_override: str = typer.Option(
        None, "--db-url", help="Override DATABASE_URL from environment/dotenv"
    ),
):
    """Apply all (or N) pending migrations."""
    actual_db_url = get_db_url(db_url_override)
    # client = create_db_client(actual_db_url)
    # ... rest of the implementation ...
    # client.close()
    if step:
        typer.echo(f"Up: Not implemented yet (step={step}) using DB: {actual_db_url}")
    else:
        typer.echo(f"Up: Not implemented yet (all) using DB: {actual_db_url}")


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
BEGIN;

-- Your SQL statements for applying the migration go here

COMMIT;

-- DOWN script
BEGIN;

-- Your SQL statements for rolling back the migration go here

COMMIT;
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
