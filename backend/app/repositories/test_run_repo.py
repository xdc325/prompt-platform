import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_run import TestRun
from app.repositories.base import BaseRepository


class TestRunRepository(BaseRepository):
    model = TestRun

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def find_running_by_suite(self, test_suite_id: uuid.UUID) -> TestRun | None:
        q = select(TestRun).where(
            TestRun.test_suite_id == test_suite_id, TestRun.status == "running"
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def find_latest_by_version_ids(self, version_ids: list[uuid.UUID]) -> TestRun | None:
        """Return the most recent completed test run for any of the given version IDs."""
        if not version_ids:
            return None
        q = (
            select(TestRun)
            .where(TestRun.version_id.in_(version_ids), TestRun.status == "completed")
            .order_by(TestRun.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()
