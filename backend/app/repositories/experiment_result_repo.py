import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment_result import ExperimentResult
from app.repositories.base import BaseRepository


class ExperimentResultRepository(BaseRepository):
    model = ExperimentResult

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_by_experiment(
        self, experiment_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ExperimentResult], int]:
        count_q = select(func.count()).select_from(ExperimentResult).where(
            ExperimentResult.experiment_id == experiment_id
        )
        total = (await self.session.execute(count_q)).scalar_one()

        q = (
            select(ExperimentResult)
            .where(ExperimentResult.experiment_id == experiment_id)
            .order_by(ExperimentResult.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def summary_by_experiment(self, experiment_id: uuid.UUID) -> dict:
        q = select(ExperimentResult).where(ExperimentResult.experiment_id == experiment_id)
        result = await self.session.execute(q)
        results = list(result.scalars().all())

        a_results = [r for r in results if r.version == "a"]
        b_results = [r for r in results if r.version == "b"]

        return {
            "version_a": {
                "avg_latency_ms": round(sum(r.latency_ms for r in a_results) / len(a_results)) if a_results else 0,
                "avg_quality": round(sum(r.quality_score for r in a_results if r.quality_score) / len([r for r in a_results if r.quality_score]), 1) if a_results else 0,
                "call_count": len(a_results),
            },
            "version_b": {
                "avg_latency_ms": round(sum(r.latency_ms for r in b_results) / len(b_results)) if b_results else 0,
                "avg_quality": round(sum(r.quality_score for r in b_results if r.quality_score) / len([r for r in b_results if r.quality_score]), 1) if b_results else 0,
                "call_count": len(b_results),
            },
        }
