import uuid
from datetime import datetime, timezone

from sqlalchemy import text, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TestSuite(Base):
    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    test_cases: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )

    prompt: Mapped["Prompt"] = relationship(back_populates="test_suites")
