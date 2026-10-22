from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_s = get_settings()
# Tests run each case on its own event loop; pooled asyncpg connections can't cross loops.
engine: AsyncEngine = create_async_engine(
    _s.database_url,
    pool_pre_ping=True,
    **({"poolclass": NullPool} if _s.environment == "test" else {}),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
