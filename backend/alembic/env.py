import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text
from sqlmodel import SQLModel

from backend.db import models  # noqa: F401 — registers models with SQLModel metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# Override sqlalchemy.url from environment variable
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Tables managed outside SQLModel (by Scrapy/Dagster raw SQL)
EXCLUDED_TABLES = {"raw_books_staging"}


def include_name(name, type_, parent_names):
    """Exclude tables not managed by SQLModel from autogenerate."""
    if type_ == "table" and name in EXCLUDED_TABLES:
        return False
    return True


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """Handle pgvector Vector type comparison.

    Alembic doesn't natively understand Vector columns. Without this,
    autogenerate would emit ALTER operations for vector columns every time.
    Return False to indicate no type change.
    """
    from pgvector.sqlalchemy import Vector

    if isinstance(metadata_type, Vector) or isinstance(inspected_type, Vector):
        return False
    return None  # Let Alembic use default comparison


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
        compare_type=compare_type,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure pgvector extension exists before any migration
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            compare_type=compare_type,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
