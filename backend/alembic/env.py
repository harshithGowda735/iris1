"""
Alembic environment configuration for async migrations.

Reads the database URL from ``app.core.config.settings`` so there is a
single source of truth.  Supports both offline (SQL script generation)
and online (live database) migration modes via asyncpg.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings

# Import Base and ALL models so Alembic's autogenerate can see them.
from app.models.base import Base
from app.models.membership import NodeMembership  # noqa: F401
from app.models.node import Node  # noqa: F401
from app.models.post import Post  # noqa: F401
from app.models.profile import UserProfile  # noqa: F401
from app.models.resource import Resource  # noqa: F401

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Set the SQLAlchemy URL from our settings (overrides alembic.ini).
# Escape '%' to '%%' so configparser does not treat percent-encoded characters as interpolation.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData target for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry-point for online migrations — delegates to async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
