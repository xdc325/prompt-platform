import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    model = Project

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_owner(self, owner_id: uuid.UUID, page: int = 1, page_size: int = 20) -> tuple[list[Project], int]:
        count_q = select(func.count()).select_from(Project).where(Project.owner_id == owner_id)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def find_by_ids(self, ids: list[uuid.UUID], page: int = 1, page_size: int = 20) -> tuple[list[Project], int]:
        """Find projects by a list of IDs with database-level pagination."""
        if not ids:
            return [], 0
        count_q = select(func.count()).select_from(Project).where(Project.id.in_(ids))
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(Project)
            .where(Project.id.in_(ids))
            .order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total
