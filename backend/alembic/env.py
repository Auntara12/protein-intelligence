import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Alembic Config object
config = context.config

# Setup loggers
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect them
from app.db.database import Base  # noqa
from app.models.protein import Protein  # noqa
from app.models.mutation import Mutation  # noqa
from app.models.structure import Structure, Embedding, ClinVar  # noqa

target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable if set
# This allows docker/CI to inject the URL without editing alembic.ini
db_url = os.getenv("DATABASE_URL", "").replace(
    "postgresql+asyncpg://", "postgresql://"  # alembic needs sync driver for migrations
)
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,       # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Override with asyncpg URL
        url=os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url", "")),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
