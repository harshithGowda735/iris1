"""
Tests for system and database health check endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_health(client: AsyncClient) -> None:
    """Verify /health returns 200 OK."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_db_health(client: AsyncClient) -> None:
    """Verify /api/health/db returns connected status and DB version."""
    response = await client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert "latency_ms" in data
    assert "database_version" in data
    assert "timestamp" in data
