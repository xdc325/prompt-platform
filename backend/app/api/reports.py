import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id, get_db
from app.core.exceptions import ForbiddenError
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.prompt_repo import PromptRepository
from app.repositories.project_member_repo import ProjectMemberRepository
from app.repositories.test_run_repo import TestRunRepository
from app.repositories.version_repo import VersionRepository
from app.services.prompt_service import PromptService

router = APIRouter(prefix=f"{settings.api_prefix}", tags=["reports"])


@router.get("/prompts/{prompt_id}/metrics")
async def get_metrics(
    prompt_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregate metrics for a prompt: version counts, current version, latest test pass rate."""
    svc = PromptService(db)
    prompt = await svc.get(prompt_id, uuid.UUID(user_id))

    version_repo = VersionRepository(db)
    versions, total = await version_repo.find_by_prompt(prompt_id, page=1, page_size=100)

    test_run_repo = TestRunRepository(db)
    version_ids = [v.id for v in versions]
    recent_run = await test_run_repo.find_latest_by_version_ids(version_ids)

    return {
        "success": True,
        "data": {
            "total_versions": total,
            "published_versions": sum(1 for v in versions if v.status == "published"),
            "has_current_version": prompt.current_version_id is not None,
            "latest_pass_rate": recent_run.pass_rate if recent_run else None,
        },
        "error": None,
    }


@router.get("/prompts/{prompt_id}/metrics/history")
async def get_metrics_history(
    prompt_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = PromptService(db)
    await svc.get(prompt_id, uuid.UUID(user_id))

    version_repo = VersionRepository(db)
    versions, _ = await version_repo.find_by_prompt(prompt_id, page=1, page_size=100)

    history = [
        {"version_number": v.version_number, "status": v.status, "created_at": v.created_at}
        for v in versions
    ]

    return {"success": True, "data": {"history": history}, "error": None}


@router.get("/projects/{project_id}/dashboard")
async def project_dashboard(
    project_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return project-level dashboard: total prompts, total experiments."""
    member_repo = ProjectMemberRepository(db)
    member = await member_repo.find_member(project_id, uuid.UUID(user_id))
    if not member:
        raise ForbiddenError("Access denied")

    prompt_repo = PromptRepository(db)
    prompts, prompt_total = await prompt_repo.find_by_project(project_id, page=1, page_size=100)

    total_experiments = 0
    for p in prompts:
        exp_repo = ExperimentRepository(db)
        exps, _ = await exp_repo.find_by_prompt(p.id, page=1, page_size=1)
        total_experiments += len(exps)

    return {
        "success": True,
        "data": {
            "total_prompts": prompt_total,
            "total_experiments": total_experiments,
        },
        "error": None,
    }
