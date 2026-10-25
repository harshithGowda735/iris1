"""
IRIS — FastAPI application factory & root configuration.

Wires together:
- Lifespan handler that performs startup connectivity check and clean shutdown pool disposal
- v1 API routers
- CORS middleware
- Global IRISError exception handler
- Operations health-check endpoints (/health and /api/health/db)
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import engine, get_db
from app.core.exceptions import IRISError

logger = logging.getLogger("iris.database")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Performs a lightweight startup query (`SELECT 1`) to verify database
    connectivity before serving requests, and cleanly disposes of the connection
    pool on shutdown.
    """
    logger.info("Verifying database connectivity on startup...")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except Exception as exc:  # noqa: BLE001
        logger.critical("Database startup connection probe failed: %s", exc)
    yield
    logger.info("Disposing database connection pool...")
    await engine.dispose()
    logger.info("Database connection pool disposed cleanly.")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title="IRIS",
        summary="Privacy-first hierarchical academic communication platform",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handler ────────────────────────────────
    @app.exception_handler(IRISError)
    async def _iris_error_handler(_req: Request, exc: IRISError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # ── Routers ──────────────────────────────────────────
    app.include_router(v1_router)

    # ── Health-Check Endpoints ───────────────────────────
    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health() -> dict[str, str]:
        """Simple liveness probe."""
        return {"status": "ok"}

    @app.get("/api/health/db", tags=["ops"], response_model=None)
    async def db_health(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> dict[str, Any] | JSONResponse:
        """Database readiness and latency health-check endpoint.

        Executes a test query against the database using the production get_db
        session dependency and returns connection status, round-trip latency,
        and database server version.
        """
        start_time = time.perf_counter()
        try:
            # Query version according to database engine dialect
            version_stmt = (
                text("SELECT sqlite_version();")
                if db.bind and db.bind.dialect.name == "sqlite"
                else text("SELECT version();")
            )
            result = await db.execute(version_stmt)
            db_version = result.scalar()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "connected",
                "latency_ms": latency_ms,
                "database_version": db_version,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("Database health check probe failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "disconnected",
                    "error": str(exc),
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

    return app


app = create_app()
