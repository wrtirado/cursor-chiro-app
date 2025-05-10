import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text

from alembic import context

# Add the project root to the Python path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# Import the Base from your models - Keep this for general access if needed
# from api.database.session import Base

# Explicitly import models to ensure they are registered with Base.metadata
# This should make Base.metadata available globally in this script if models are loaded.
import api.models.base
from api.database.session import Base  # Import Base directly

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# Set target_metadata using the imported Base
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# Function to prevent Alembic from managing sqlite_sequence table
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name == "sqlite_sequence":
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable not set for Alembic offline mode"
        )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable not set for Alembic online mode"
        )

    # Create a configuration dictionary for the engine
    # The poolclass=pool.NullPool is important for Alembic's online mode.
    engine_config = {
        "sqlalchemy.url": db_url,
        "poolclass": pool.NullPool,  # Ensure NullPool is correctly passed if not part of prefix handling
    }

    connectable = engine_from_config(
        engine_config,  # Use our constructed config
        prefix="sqlalchemy.",  # Keep prefix if 'sqlalchemy.url' is used, or adjust if not.
        # If prefix is kept, ensure your key is 'sqlalchemy.url'.
        # If not using prefix or key is just 'url', adjust accordingly.
        # For simplicity and directness with os.environ:
        # from sqlalchemy import create_engine
        # connectable = create_engine(db_url, poolclass=pool.NullPool)
        # This bypasses engine_from_config if simpler.
        # Let's stick to engine_from_config but ensure it gets the URL.
    )

    with connectable.connect() as connection:
        # Ensure foreign keys are enabled for SQLite when in online mode
        if connection.dialect.name == "sqlite":
            connection.execute(text("PRAGMA foreign_keys=ON"))
            # app_log.info(
            #     "SQLite PRAGMA foreign_keys=ON executed."
            # )  # Optional: for logging - app_log needs to be defined/imported

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
