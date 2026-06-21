import uuid

from sqlalchemy import text, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(1), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    experiment: Mapped["Experiment"] = relationship(back_populates="results")
