import uuid

from pydantic import BaseModel, field_validator


class BaseSchema(BaseModel):
    """Base schema that coerces UUID → str for all fields."""

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v
