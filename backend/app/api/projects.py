import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id, get_db
from app.schemas.project import (
    MemberAdd,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix=f"{settings.api_prefix}/projects", tags=["projects"])


@router.post("")
async def create_project(
    body: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project. The creator becomes the owner."""
    svc = ProjectService(db)
    project = await svc.create(body.name, body.description, uuid.UUID(user_id))
    return {
        "success": True,
        "data": ProjectResponse.model_validate(project).model_dump(mode="json"),
        "error": None,
    }


@router.get("")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all projects the current user is a member of."""
    svc = ProjectService(db)
    items, total = await svc.list_my_projects(uuid.UUID(user_id), page, page_size)
    return {
        "success": True,
        "data": {
            "items": [ProjectResponse.model_validate(p).model_dump(mode="json") for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "error": None,
    }


@router.get("/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a project by ID. Any member can view."""
    svc = ProjectService(db)
    project = await svc.get(project_id, uuid.UUID(user_id))
    return {
        "success": True,
        "data": ProjectResponse.model_validate(project).model_dump(mode="json"),
        "error": None,
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update project name or description. Requires editor/owner role."""
    svc = ProjectService(db)
    project = await svc.update(project_id, uuid.UUID(user_id), body.name, body.description)
    return {
        "success": True,
        "data": ProjectResponse.model_validate(project).model_dump(mode="json"),
        "error": None,
    }


@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project. Only the owner can delete."""
    svc = ProjectService(db)
    await svc.delete(project_id, uuid.UUID(user_id))
    return {"success": True, "data": None, "error": None}


@router.post("/{project_id}/members")
async def add_member(
    project_id: uuid.UUID,
    body: MemberAdd,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a project by email. Only the owner can add members."""
    svc = ProjectService(db)
    member = await svc.add_member(project_id, body.email, body.role, uuid.UUID(user_id))
    return {"success": True, "data": asdict(member), "error": None}


@router.get("/{project_id}/members")
async def list_members(
    project_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a project."""
    svc = ProjectService(db)
    members = await svc.list_members(project_id, uuid.UUID(user_id))
    return {"success": True, "data": [asdict(m) for m in members], "error": None}


@router.delete("/{project_id}/members/{member_user_id}")
async def remove_member(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from a project. Only the owner can remove."""
    svc = ProjectService(db)
    await svc.remove_member(project_id, member_user_id, uuid.UUID(user_id))
    return {"success": True, "data": None, "error": None}
