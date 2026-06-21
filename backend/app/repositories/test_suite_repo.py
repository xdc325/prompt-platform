import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_suite import TestSuite
from app.repositories.base import BaseRepository


class TestSuiteRepository(BaseRepository):
    model = TestSuite

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_prompt(
        self, prompt_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[TestSuite], int]:
        count_q = select(func.count()).select_from(TestSuite).where(TestSuite.prompt_id == prompt_id)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(TestSuite)
            .where(TestSuite.prompt_id == prompt_id)
            .order_by(TestSuite.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total
