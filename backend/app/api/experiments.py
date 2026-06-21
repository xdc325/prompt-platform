import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id, get_db
from app.schemas.experiment import (
    CompareRequest,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentResultResponse,
    PlaygroundRequest,
)
from app.services.experiment_service import ExperimentService

router = APIRouter(prefix=f"{settings.api_prefix}", tags=["experiments"])


def _exp_response(exp) -> dict:
    """Serialize an Experiment ORM instance to the API response dict."""
    return ExperimentResponse.model_validate(exp).model_dump(mode="json")


@router.post("/prompts/{prompt_id}/experiments")
async def create_experiment(
    prompt_id: uuid.UUID,
    body: ExperimentCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new A/B experiment comparing two versions."""
    svc = ExperimentService(db)
    exp = await svc.create_experiment(
        prompt_id, uuid.UUID(body.version_a_id), uuid.UUID(body.version_b_id),
        body.traffic_split, uuid.UUID(user_id),
    )
    return {"success": True, "data": _exp_response(exp), "error": None}


@router.get("/prompts/{prompt_id}/experiments")
async def list_experiments(
    prompt_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List experiments for a prompt."""
    svc = ExperimentService(db)
    items, total = await svc.list_experiments(prompt_id, uuid.UUID(user_id), page, page_size)
    return {
        "success": True,
        "data": {
            "items": [_exp_response(e) for e in items],
            "total": total, "page": page, "page_size": page_size,
        },
        "error": None,
    }


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get experiment details with aggregated result summary."""
    svc = ExperimentService(db)
    exp = await svc.get_experiment(experiment_id, uuid.UUID(user_id))
    return {"success": True, "data": exp, "error": None}  # get_experiment returns a pre-built dict with summary


@router.post("/experiments/{experiment_id}/stop")
async def stop_experiment(
    experiment_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Stop a running experiment."""
    svc = ExperimentService(db)
    exp = await svc.stop_experiment(experiment_id, uuid.UUID(user_id))
    return {"success": True, "data": _exp_response(exp), "error": None}


@router.delete("/prompts/{prompt_id}/experiments/{experiment_id}")
async def delete_experiment(
    prompt_id: uuid.UUID,
    experiment_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete an experiment."""
    svc = ExperimentService(db)
    await svc.delete_experiment(experiment_id, uuid.UUID(user_id))
    return {"success": True, "data": None, "error": None}


@router.get("/experiments/{experiment_id}/results")
async def list_experiment_results(
    experiment_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List individual results for an experiment."""
    svc = ExperimentService(db)
    items, total = await svc.list_results(experiment_id, uuid.UUID(user_id), page, page_size)
    return {
        "success": True,
        "data": {
            "items": [ExperimentResultResponse.model_validate(r).model_dump(mode="json") for r in items],
            "total": total, "page": page, "page_size": page_size,
        },
        "error": None,
    }


@router.post("/prompts/{prompt_id}/playground")
async def playground(
    prompt_id: uuid.UUID,
    body: PlaygroundRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Run a prompt version against an LLM and return the output."""
    svc = ExperimentService(db)
    result = await svc.playground(prompt_id, uuid.UUID(body.version_id), body.input, body.model, uuid.UUID(user_id))
    return {"success": True, "data": result, "error": None}


@router.post("/prompts/{prompt_id}/compare")
async def compare_versions(
    prompt_id: uuid.UUID,
    body: CompareRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Run the same input through two versions and diff their outputs."""
    svc = ExperimentService(db)
    result = await svc.compare(
        prompt_id, uuid.UUID(body.version_a_id), uuid.UUID(body.version_b_id),
        body.input, body.model, uuid.UUID(user_id),
    )
    return {"success": True, "data": result, "error": None}
