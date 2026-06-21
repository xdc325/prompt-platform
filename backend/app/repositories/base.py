import uuid
from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository:
    model: type[Base]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, id: uuid.UUID) -> Base | None:
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[Base], int]:
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        total = (await self.session.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def create(self, instance: Base) -> Base:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: Base) -> Base:
        await self.session.flush()
        return instance

    async def delete(self, instance: Base) -> None:
        await self.session.delete(instance)
        await self.session.flush()
