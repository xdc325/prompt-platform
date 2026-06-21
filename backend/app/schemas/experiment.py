from datetime import datetime

from pydantic import Field

from app.schemas import BaseSchema


class ExperimentCreate(BaseSchema):
    version_a_id: str
    version_b_id: str
    traffic_split: dict = Field(default={"a": 0.5, "b": 0.5})


class ExperimentResponse(BaseSchema):
    id: str
    prompt_id: str
    version_a_id: str
    version_b_id: str
    traffic_split: dict
    status: str
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class ExperimentDetailResponse(ExperimentResponse):
    summary: dict | None = None


class ExperimentResultResponse(BaseSchema):
    id: str
    experiment_id: str
    version: str
    input: str
    output: str
    latency_ms: int
    cost: float
    quality_score: int | None

    model_config = {"from_attributes": True}


class PlaygroundRequest(BaseSchema):
    version_id: str
    input: str = Field(min_length=1)
    model: str = "gpt-3.5-turbo"


class CompareRequest(BaseSchema):
    version_a_id: str
    version_b_id: str
    input: str = Field(min_length=1)
    model: str = "gpt-3.5-turbo"
