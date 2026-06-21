from collections.abc import AsyncGenerator

from arq import ArqRedis
from arq.connections import create_pool, RedisSettings
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.models.base import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload["sub"]
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_arq() -> AsyncGenerator[ArqRedis, None]:
    """Create arq Redis connection for enqueuing background jobs."""
    redis = await create_pool(RedisSettings(host="redis", port=6379, database=0))
    try:
        yield redis
    finally:
        await redis.close()
