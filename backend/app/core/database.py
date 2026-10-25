"""
Async SQLAlchemy 2.0 engine & session wiring.

Connects to Supabase PostgreSQL using the asynchronous ``asyncpg`` driver.
Engine and session configuration include:
- Connection pool recycling and pre-ping for resilient cloud connections
- Prepared statement cache disabling for Supabase Transaction Pooler (port 6543)
- Clean session lifecycle management with guaranteed commit/rollback/close
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Detect dialect to allow in-memory sqlite during testing without pool errors
is_sqlite = "sqlite" in settings.database_url

engine_kwargs: dict[str, Any] = {
    "echo": settings.debug and not settings.is_production,
}

if not is_sqlite:
    engine_kwargs.update(
        {
            # Verify connection liveness before handing out of pool (handles drops cleanly)
            "pool_pre_ping": True,
            # Number of persistent connections in the pool
            "pool_size": 10,
            # Number of extra connections that can be opened beyond pool_size under surge
            "max_overflow": 20,
            # Recycle connections every 30 minutes to prevent stale idle TCP drops from NAT/firewalls
            "pool_recycle": 1800,
            # Fail fast if pool is completely exhausted after waiting 30 seconds
            "pool_timeout": 30.0,
            # Required for Supabase Transaction Pooler (PgBouncer/Supavisor mode on port 6543)
            # Disables asyncpg client-side prepared statement cache across reused pooled connections
            "connect_args": {
                "statement_cache_size": 0,
            },
        }
    )

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a scoped async database session.

    Session Lifecycle:
    1. Opens session via context manager
    2. Yields session to endpoint / dependency consumer
    3. On clean completion, commits changes automatically
    4. On any unhandled exception, rolls back transaction and re-raises
    5. Always closes session context, returning connection back to pool
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
