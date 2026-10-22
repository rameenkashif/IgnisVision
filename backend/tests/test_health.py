import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["ml_backend"] == "mock"


async def test_ready_reports_db_state(client):
    r = await client.get("/api/v1/health/ready")
    assert r.status_code in (200, 503)
    assert r.json()["db"] in ("up", "down")


async def test_openapi_docs_served(client):
    r = await client.get("/api/openapi.json")
    assert r.status_code == 200
