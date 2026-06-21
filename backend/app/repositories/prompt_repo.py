import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt import Prompt
from app.repositories.base import BaseRepository


class PromptRepository(BaseRepository):
    model = Prompt

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_project(
        self, project_id: uuid.UUID, page: int = 1, page_size: int = 20, search: str | None = None
    ) -> tuple[list[Prompt], int]:
        q = select(Prompt).where(Prompt.project_id == project_id)
        count_q = select(func.count()).select_from(Prompt).where(Prompt.project_id == project_id)

        if search:
            q = q.where(Prompt.name.ilike(f"%{search}%"))
            count_q = count_q.where(Prompt.name.ilike(f"%{search}%"))

        total = (await self.session.execute(count_q)).scalar_one()

        q = q.order_by(Prompt.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(q)
        return list(result.scalars().all()), total
