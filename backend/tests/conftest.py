"""Tests run against a real Postgres (HANDOFF §2). DATABASE_URL must point at a disposable DB:
the schema is dropped and rebuilt with Alembic at session start."""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ignis:ignis@localhost:5432/ignis")
import tempfile  # noqa: E402

os.environ["MEDIA_ROOT"] = tempfile.mkdtemp(prefix="ignis-media-")

import asyncio  # noqa: E402
import uuid  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.engine import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Station, User  # noqa: E402
from app.services.settings import ensure_defaults  # noqa: E402

PASSWORD = "Passw0rd-test"
_PW_HASH = hash_password(PASSWORD)  # hash once; argon2 is deliberately slow
ROLES = ("admin", "incident_commander", "field_responder", "trainee", "training_staff")


async def _reset_schema() -> None:
    eng = create_async_engine(os.environ["DATABASE_URL"])
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    asyncio.run(_reset_schema())
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    async with SessionLocal() as db:
        tables = (
            await db.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        await db.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        await ensure_defaults(db)
        await db.commit()
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # https so the Secure refresh cookie is stored and sent back.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        yield c


@pytest.fixture
async def station() -> Station:
    async with SessionLocal() as db:
        s = Station(name="Test Station", city="Lahore", region="Punjab")
        db.add(s)
        await db.commit()
        return s


@pytest.fixture
def make_user(station):
    async def _make(role: str = "incident_commander", **kw) -> User:
        async with SessionLocal() as db:
            u = User(
                username=kw.pop("username", f"{role[:6]}_{uuid.uuid4().hex[:6]}"),
                full_name=kw.pop("full_name", f"Test {role}"),
                role=role,
                station_id=station.id,
                password_hash=kw.pop("password_hash", _PW_HASH),
                **kw,
            )
            db.add(u)
            await db.commit()
            await db.refresh(u)
            return u

    return _make


@pytest.fixture
def login(client):
    async def _login(user: User, password: str = PASSWORD) -> dict:
        r = await client.post(
            "/api/v1/auth/login", json={"username": user.username, "password": password}
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture
def as_role(make_user, login):
    async def _as(role: str) -> tuple[User, dict]:
        u = await make_user(role)
        return u, await login(u)

    return _as


@pytest.fixture
def create_incident(client):
    async def _create(headers: dict, responders: list[User] = (), **overrides) -> dict:
        body = {
            "address": "Gul Plaza, M.A Jinnah Road",
            "city": "Lahore",
            "structure_type": "commercial",
            "incident_type": "structural",
            "reported_by": "Control room",
            "floors": 2,
            "zones_per_floor": 4,
            "zone_labels": {"F1-Z1": "Lobby"},
            "assignments": [
                {"user_id": str(u.id), "zone_code": f"F1-Z{i + 1}", "device_label": f"Rig {i + 1}"}
                for i, u in enumerate(responders)
            ],
            **overrides,
        }
        r = await client.post("/api/v1/incidents", json=body, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()

    return _create
