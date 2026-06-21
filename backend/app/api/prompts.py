import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id, get_db
from app.schemas.prompt import PromptCreate, PromptResponse, PromptUpdate
from app.services.prompt_service import PromptService

router = APIRouter(prefix=f"{settings.api_prefix}", tags=["prompts"])


def _prompt_response(prompt) -> dict:
    """Serialize a Prompt ORM instance to the API response dict."""
    return PromptResponse.model_validate(prompt).model_dump(mode="json")


@router.post("/projects/{project_id}/prompts")
async def create_prompt(
    project_id: uuid.UUID,
    body: PromptCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new prompt in a project."""
    svc = PromptService(db)
    prompt = await svc.create(project_id, body.name, body.description, uuid.UUID(user_id))
    return {"success": True, "data": _prompt_response(prompt), "error": None}


@router.get("/projects/{project_id}/prompts")
async def list_prompts(
    project_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List prompts in a project with optional name search and pagination."""
    svc = PromptService(db)
    items, total = await svc.list_by_project(project_id, uuid.UUID(user_id), page, page_size, search)
    return {
        "success": True,
        "data": {
            "items": [_prompt_response(p) for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "error": None,
    }


@router.get("/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a single prompt by ID."""
    svc = PromptService(db)
    prompt = await svc.get(prompt_id, uuid.UUID(user_id))
    return {"success": True, "data": _prompt_response(prompt), "error": None}


@router.patch("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a prompt's name or description."""
    svc = PromptService(db)
    prompt = await svc.update(prompt_id, uuid.UUID(user_id), body.name, body.description)
    return {"success": True, "data": _prompt_response(prompt), "error": None}


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a prompt."""
    svc = PromptService(db)
    await svc.delete(prompt_id, uuid.UUID(user_id))
    return {"success": True, "data": None, "error": None}
