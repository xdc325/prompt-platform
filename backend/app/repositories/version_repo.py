import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_version import PromptVersion
from app.repositories.base import BaseRepository


class VersionRepository(BaseRepository):
    model = PromptVersion

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_prompt(
        self, prompt_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[PromptVersion], int]:
        count_q = select(func.count()).select_from(PromptVersion).where(PromptVersion.prompt_id == prompt_id)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.version_number.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def find_by_prompt_and_number(self, prompt_id: uuid.UUID, version_number: int) -> PromptVersion | None:
        q = select(PromptVersion).where(
            and_(PromptVersion.prompt_id == prompt_id, PromptVersion.version_number == version_number)
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_next_version_number(self, prompt_id: uuid.UUID) -> int:
        q = select(func.coalesce(func.max(PromptVersion.version_number), 0)).where(
            PromptVersion.prompt_id == prompt_id
        )
        result = await self.session.execute(q)
        return result.scalar_one() + 1

    async def find_published_by_prompt(self, prompt_id: uuid.UUID) -> list[PromptVersion]:
        q = (
            select(PromptVersion)
            .where(and_(PromptVersion.prompt_id == prompt_id, PromptVersion.status == "published"))
            .order_by(PromptVersion.version_number.desc())
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def find_by_parent_id(self, parent_id: uuid.UUID) -> list[PromptVersion]:
        q = select(PromptVersion).where(PromptVersion.parent_version_id == parent_id)
        result = await self.session.execute(q)
        return list(result.scalars().all())
