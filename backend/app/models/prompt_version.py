import uuid
from datetime import datetime, timezone

from sqlalchemy import text, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompts.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True
    )
    changelog: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )

    prompt: Mapped["Prompt"] = relationship(back_populates="versions", foreign_keys=[prompt_id])
