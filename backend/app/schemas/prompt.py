from datetime import datetime

from pydantic import Field

from app.schemas import BaseSchema


class PromptCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class PromptUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class PromptResponse(BaseSchema):
    id: str
    project_id: str
    name: str
    description: str | None
    current_version_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
