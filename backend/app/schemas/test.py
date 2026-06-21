from datetime import datetime

from pydantic import Field

from app.schemas import BaseSchema


class TestCase(BaseSchema):
    input: str = Field(min_length=1)
    expected: str | None = None


class TestSuiteCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    test_cases: list[TestCase] = Field(min_length=1)


class TestSuiteUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    test_cases: list[TestCase] | None = None


class TestSuiteResponse(BaseSchema):
    id: str
    prompt_id: str
    name: str
    test_cases: list
    created_at: datetime

    model_config = {"from_attributes": True}


class TestRunRequest(BaseSchema):
    version_id: str
    model: str = "deepseek-chat"


class TestRunResponse(BaseSchema):
    id: str
    test_suite_id: str
    version_id: str
    status: str
    results: list | None
    pass_rate: float | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
