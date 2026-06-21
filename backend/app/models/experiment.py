import uuid
from datetime import datetime, timezone

from sqlalchemy import text, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompts.id"), nullable=False
    )
    version_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False
    )
    version_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=False
    )
    traffic_split: Mapped[dict] = mapped_column(JSONB, default=lambda: {"a": 0.5, "b": 0.5})
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    results: Mapped[list["ExperimentResult"]] = relationship(back_populates="experiment", lazy="selectin")
