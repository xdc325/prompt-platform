import uuid
from datetime import datetime

from arq import Worker
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import get_logger
from app.models.base import async_session_factory
from app.models.test_run import TestRun
from app.repositories.test_run_repo import TestRunRepository
from app.repositories.test_suite_repo import TestSuiteRepository
from app.repositories.version_repo import VersionRepository
from app.providers import get_provider

logger = get_logger(__name__)


async def run_regression_test(ctx: dict, test_run_id: str, model: str = "deepseek-chat") -> dict:
    """Background task: run all test cases for a test suite against a prompt version.

    Renders each test case's input variables into the version content template,
    calls the LLM, compares output with expected, and updates the TestRun record.
    """
    logger.info("test_run_started", test_run_id=test_run_id, model=model)

    async with async_session_factory() as session:
        test_run_repo = TestRunRepository(session)
        test_suite_repo = TestSuiteRepository(session)
        version_repo = VersionRepository(session)

        test_run = await test_run_repo.find_by_id(uuid.UUID(test_run_id))
        if not test_run:
            return {"error": "test run not found"}

        test_suite = await test_suite_repo.find_by_id(test_run.test_suite_id)
        version = await version_repo.find_by_id(test_run.version_id)
        if not test_suite or not version:
            test_run.status = "failed"
            await session.commit()
            return {"error": "test suite or version not found"}

        test_cases = test_suite.test_cases
        results = []
        passed = 0
        total = len(test_cases)

        provider = get_provider(model)

        for idx, case in enumerate(test_cases):
            try:
                case_input = case.get("input", "")
                rendered = version.content.replace("{input}", str(case_input))
                result = await provider.chat(
                    model=model,
                    prompt=rendered,
                    params={"temperature": 0},
                    use_cache=False,
                )
                output = result.content
                expected = case.get("expected", "")
                case_passed = expected in output if expected else True

                if case_passed:
                    passed += 1

                results.append({
                    "case_index": idx,
                    "passed": case_passed,
                    "input": case_input,
                    "output": output,
                    "expected": expected,
                })
            except Exception as e:
                results.append({
                    "case_index": idx,
                    "passed": False,
                    "input": case.get("input", ""),
                    "output": None,
                    "expected": case.get("expected", ""),
                    "error": str(e),
                })

        test_run.results = results
        test_run.pass_rate = passed / total if total > 0 else 0
        test_run.status = "completed"
        test_run.finished_at = datetime.utcnow()

        await session.commit()

        logger.info("test_run_completed", test_run_id=test_run_id, pass_rate=test_run.pass_rate)
        return {"test_run_id": test_run_id, "pass_rate": test_run.pass_rate, "passed": passed, "total": total}


async def create_worker():
    return Worker(
        redis_settings=RedisSettings(host="redis", port=6379, database=0),
        functions=[run_regression_test],
    )


class WorkerSettings:
    """arq WorkerSettings — discovered by the arq CLI."""
    functions = [run_regression_test]
    redis_settings = RedisSettings(host="redis", port=6379, database=0)
    allow_abort_jobs = True
