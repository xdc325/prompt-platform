import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import Experiment
from app.repositories.base import BaseRepository


class ExperimentRepository(BaseRepository):
    model = Experiment

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_prompt(
        self, prompt_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[Experiment], int]:
        count_q = select(func.count()).select_from(Experiment).where(Experiment.prompt_id == prompt_id)
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(Experiment)
            .where(Experiment.prompt_id == prompt_id)
            .order_by(Experiment.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def find_running_by_prompt(self, prompt_id: uuid.UUID) -> Experiment | None:
        q = select(Experiment).where(
            Experiment.prompt_id == prompt_id, Experiment.status == "running"
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()
