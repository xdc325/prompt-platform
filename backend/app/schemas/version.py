from datetime import datetime

from pydantic import Field

from app.schemas import BaseSchema


class VersionCreate(BaseSchema):
    content: str = Field(min_length=1)
    variables: list[str] = []
    changelog: str | None = None


class VersionResponse(BaseSchema):
    id: str
    prompt_id: str
    version_number: int
    content: str
    variables: list
    status: str
    created_by: str
    parent_version_id: str | None
    changelog: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DiffChange(BaseSchema):
    type: str
    position: int
    old: str | None = None
    new: str | None = None
    context_before: str | None = None
    context_after: str | None = None


class DiffResponse(BaseSchema):
    version_a: dict
    version_b: dict
    changes: list[DiffChange]
    summary: str
