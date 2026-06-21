import asyncio
import json
import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_arq, get_current_user_id, get_db
from app.models.base import async_session_factory
from app.repositories.test_run_repo import TestRunRepository
from app.schemas.test import TestSuiteCreate, TestSuiteResponse, TestSuiteUpdate, TestRunRequest, TestRunResponse
from app.services.test_service import TestService

router = APIRouter(prefix=f"{settings.api_prefix}", tags=["tests"])


def _suite_response(suite) -> dict:
    """Serialize a TestSuite ORM instance to the API response dict."""
    return TestSuiteResponse.model_validate(suite).model_dump(mode="json")


def _run_response(run) -> dict:
    """Serialize a TestRun ORM instance to the API response dict."""
    return TestRunResponse.model_validate(run).model_dump(mode="json")


@router.post("/prompts/{prompt_id}/test-suites")
async def create_test_suite(
    prompt_id: uuid.UUID,
    body: TestSuiteCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a test suite with test cases."""
    svc = TestService(db)
    cases = [c.model_dump() for c in body.test_cases]
    suite = await svc.create_suite(prompt_id, uuid.UUID(user_id), body.name, cases)
    return {"success": True, "data": _suite_response(suite), "error": None}


@router.get("/prompts/{prompt_id}/test-suites")
async def list_test_suites(
    prompt_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List test suites for a prompt."""
    svc = TestService(db)
    items, total = await svc.list_suites(prompt_id, uuid.UUID(user_id), page, page_size)
    return {
        "success": True,
        "data": {
            "items": [_suite_response(s) for s in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "error": None,
    }


@router.put("/prompts/{prompt_id}/test-suites/{suite_id}")
async def update_test_suite(
    prompt_id: uuid.UUID,
    suite_id: uuid.UUID,
    body: TestSuiteUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a test suite's name or test cases."""
    svc = TestService(db)
    cases = [c.model_dump() for c in body.test_cases] if body.test_cases is not None else None
    suite = await svc.update_suite(suite_id, uuid.UUID(user_id), body.name, cases)
    return {"success": True, "data": _suite_response(suite), "error": None}


@router.delete("/prompts/{prompt_id}/test-suites/{suite_id}")
async def delete_test_suite(
    prompt_id: uuid.UUID,
    suite_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a test suite."""
    svc = TestService(db)
    await svc.delete_suite(suite_id, uuid.UUID(user_id))
    return {"success": True, "data": None, "error": None}


@router.post("/prompts/{prompt_id}/test-suites/{suite_id}/run")
async def run_test(
    prompt_id: uuid.UUID,
    suite_id: uuid.UUID,
    body: TestRunRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    arq: ArqRedis = Depends(get_arq),
):
    """Enqueue a regression test run for a test suite and version."""
    svc = TestService(db, arq)
    test_run = await svc.run_test(suite_id, uuid.UUID(body.version_id), uuid.UUID(user_id), body.model)
    return {"success": True, "data": _run_response(test_run), "error": None}


@router.get("/test-runs/{run_id}")
async def get_test_run(
    run_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a test run by ID."""
    svc = TestService(db)
    test_run = await svc.get_run(run_id, uuid.UUID(user_id))
    return {"success": True, "data": _run_response(test_run), "error": None}


@router.get("/test-runs/{run_id}/stream")
async def stream_test_run(
    run_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Stream test run progress as SSE events (case_result → ... → complete)."""
    svc = TestService(db)
    await svc.get_run(run_id, uuid.UUID(user_id))

    async def event_generator():
        while True:
            async with async_session_factory() as session:
                repo = TestRunRepository(session)
                current = await repo.find_by_id(run_id)
                if not current or current.status in ("completed", "failed"):
                    data = {
                        "pass_rate": current.pass_rate if current else 0,
                        "total_cases": len(current.results) if current and current.results else 0,
                        "passed": sum(1 for r in (current.results or []) if r.get("passed")),
                        "failed": sum(1 for r in (current.results or []) if not r.get("passed")),
                    }
                    yield {"event": "complete", "data": json.dumps(data)}
                    break

                if current.results:
                    latest = current.results[-1]
                    yield {"event": "case_result", "data": json.dumps(latest)}

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
