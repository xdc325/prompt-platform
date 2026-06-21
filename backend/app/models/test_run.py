import uuid
from datetime import datetime, timezone

from sqlalchemy import text, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_suites.id"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    results: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
