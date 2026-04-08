"""Integration tests — GET /api/v1/health"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_healthy_status(async_client):
    response = await async_client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "healthy"
