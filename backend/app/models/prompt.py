import uuid
from datetime import datetime, timezone

from sqlalchemy import text, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_versions.id", use_alter=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()"), onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="prompts")
    current_version: Mapped["PromptVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["PromptVersion"]] = relationship(
        back_populates="prompt", foreign_keys="PromptVersion.prompt_id", lazy="selectin"
    )
    test_suites: Mapped[list["TestSuite"]] = relationship(back_populates="prompt", lazy="selectin")
