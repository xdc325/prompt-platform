from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas import BaseSchema


class ProjectCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ProjectResponse(BaseSchema):
    id: str
    name: str
    description: str | None
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseSchema):
    email: EmailStr
    role: str = Field(default="editor", pattern=r"^(editor|viewer)$")


class MemberResponse(BaseSchema):
    user_id: str
    email: str
    display_name: str
    role: str
