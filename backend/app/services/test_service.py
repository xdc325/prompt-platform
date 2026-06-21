import uuid

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.test_run import TestRun
from app.models.test_suite import TestSuite
from app.repositories.project_member_repo import ProjectMemberRepository
from app.repositories.prompt_repo import PromptRepository
from app.repositories.test_run_repo import TestRunRepository
from app.repositories.test_suite_repo import TestSuiteRepository
from app.services.mixins import PromptAccessMixin


class TestService(PromptAccessMixin):
    """Manages test suites and regression test runs for prompt versions."""

    def __init__(self, session: AsyncSession, arq: ArqRedis | None = None):
        self.session = session
        self.arq = arq
        self.suite_repo = TestSuiteRepository(session)
        self.run_repo = TestRunRepository(session)
        self.prompt_repo = PromptRepository(session)
        self.member_repo = ProjectMemberRepository(session)

    async def create_suite(self, prompt_id: uuid.UUID, user_id: uuid.UUID, name: str, test_cases: list[dict]) -> TestSuite:
        """Create a test suite with the given test cases."""
        await self._check_prompt_access(prompt_id, user_id)
        suite = TestSuite(prompt_id=prompt_id, name=name, test_cases=test_cases)
        return await self.suite_repo.create(suite)

    async def list_suites(self, prompt_id: uuid.UUID, user_id: uuid.UUID, page: int, page_size: int):
        """List test suites for a prompt with pagination."""
        await self._check_prompt_access(prompt_id, user_id)
        return await self.suite_repo.find_by_prompt(prompt_id, page, page_size)

    async def update_suite(self, suite_id: uuid.UUID, user_id: uuid.UUID, name: str | None, test_cases: list[dict] | None) -> TestSuite:
        """Update a test suite's name and/or test cases."""
        suite = await self.suite_repo.find_by_id(suite_id)
        if not suite:
            raise NotFoundError("TestSuite", str(suite_id))
        await self._check_prompt_access(suite.prompt_id, user_id)
        if name is not None:
            suite.name = name
        if test_cases is not None:
            suite.test_cases = test_cases
        return await self.suite_repo.update(suite)

    async def delete_suite(self, suite_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a test suite and its associated test runs."""
        suite = await self.suite_repo.find_by_id(suite_id)
        if not suite:
            raise NotFoundError("TestSuite", str(suite_id))
        await self._check_prompt_access(suite.prompt_id, user_id)

        from sqlalchemy import delete, text
        await self.session.execute(
            text("DELETE FROM test_runs WHERE test_suite_id = :sid"), {"sid": suite_id}
        )
        await self.suite_repo.delete(suite)

    async def run_test(self, suite_id: uuid.UUID, version_id: uuid.UUID, user_id: uuid.UUID, model: str = "deepseek-chat") -> TestRun:
        """Enqueue a regression test run for the given suite and version."""
        suite = await self.suite_repo.find_by_id(suite_id)
        if not suite:
            raise NotFoundError("TestSuite", str(suite_id))
        await self._check_prompt_access(suite.prompt_id, user_id)

        running = await self.run_repo.find_running_by_suite(suite_id)
        if running:
            raise ConflictError("A test is already running for this suite")

        if not suite.test_cases:
            raise ConflictError("Test suite has no test cases")

        test_run = TestRun(test_suite_id=suite_id, version_id=version_id, status="running")
        test_run = await self.run_repo.create(test_run)

        if self.arq:
            await self.arq.enqueue_job("run_regression_test", str(test_run.id), model)

        return test_run

    async def get_run(self, run_id: uuid.UUID, user_id: uuid.UUID) -> TestRun:
        """Get a test run by ID, verifying prompt access."""
        run = await self.run_repo.find_by_id(run_id)
        if not run:
            raise NotFoundError("TestRun", str(run_id))
        suite = await self.suite_repo.find_by_id(run.test_suite_id)
        if suite:
            await self._check_prompt_access(suite.prompt_id, user_id)
        return run
