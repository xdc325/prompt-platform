import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id, get_db
from app.schemas.version import VersionCreate, VersionResponse
from app.services.version_service import VersionService

router = APIRouter(prefix=f"{settings.api_prefix}", tags=["versions"])


def _version_response(version) -> dict:
    """Serialize a PromptVersion ORM instance to the API response dict."""
    return VersionResponse.model_validate(version).model_dump(mode="json")


@router.get("/prompts/{prompt_id}/versions")
async def list_versions(
    prompt_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List versions for a prompt, newest first."""
    svc = VersionService(db)
    items, total = await svc.list_versions(prompt_id, uuid.UUID(user_id), page, page_size)
    return {
        "success": True,
        "data": {
            "items": [_version_response(v) for v in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "error": None,
    }


@router.get("/prompts/{prompt_id}/versions/{version_id}")
async def get_version(
    prompt_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a single version by ID."""
    svc = VersionService(db)
    version = await svc.get_version(version_id, uuid.UUID(user_id))
    return {"success": True, "data": _version_response(version), "error": None}


@router.post("/prompts/{prompt_id}/versions")
async def create_version(
    prompt_id: uuid.UUID,
    body: VersionCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new draft version with auto-incremented version number."""
    svc = VersionService(db)
    version = await svc.create_draft(prompt_id, uuid.UUID(user_id), body.content, body.variables, body.changelog)
    return {"success": True, "data": _version_response(version), "error": None}


@router.post("/prompts/{prompt_id}/versions/{version_id}/submit")
async def submit_review(
    prompt_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Submit a draft version for review (draft → pending_review)."""
    svc = VersionService(db)
    version = await svc.transition(version_id, uuid.UUID(user_id), "pending_review")
    return {"success": True, "data": _version_response(version), "error": None}


@router.post("/prompts/{prompt_id}/versions/{version_id}/publish")
async def publish_version(
    prompt_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Publish a version (pending_review → published). Archives previous published versions."""
    svc = VersionService(db)
    version = await svc.transition(version_id, uuid.UUID(user_id), "published")
    return {"success": True, "data": _version_response(version), "error": None}


@router.post("/prompts/{prompt_id}/rollback")
async def rollback(
    prompt_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Rollback the prompt's current version to a specified version."""
    svc = VersionService(db)
    version = await svc.rollback(prompt_id, version_id, uuid.UUID(user_id))
    return {"success": True, "data": _version_response(version), "error": None}


@router.delete("/prompts/{prompt_id}/versions/{version_id}")
async def delete_version(
    prompt_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a version."""
    svc = VersionService(db)
    await svc.delete(version_id, uuid.UUID(user_id))
    return {"success": True, "data": None, "error": None}


@router.get("/prompts/{prompt_id}/versions/{v1}/diff/{v2}")
async def diff_versions(
    prompt_id: uuid.UUID,
    v1: uuid.UUID,
    v2: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Compute a line-level diff between two prompt versions."""
    svc = VersionService(db)
    result = await svc.diff(v1, v2, uuid.UUID(user_id))
    return {"success": True, "data": result, "error": None}
