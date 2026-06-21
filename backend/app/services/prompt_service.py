import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.prompt import Prompt
from app.repositories.project_member_repo import ProjectMemberRepository
from app.repositories.prompt_repo import PromptRepository


class PromptService:
    """Manages prompt CRUD within a project, enforcing project-level access control."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.prompt_repo = PromptRepository(session)
        self.member_repo = ProjectMemberRepository(session)

    async def _check_project_access(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Verify the user has editor/owner access to the project."""
        member = await self.member_repo.find_member(project_id, user_id)
        if not member or member.role not in ("owner", "editor"):
            raise ForbiddenError("Access denied")

    async def create(self, project_id: uuid.UUID, name: str, description: str | None, user_id: uuid.UUID) -> Prompt:
        """Create a new prompt in the given project."""
        await self._check_project_access(project_id, user_id)
        prompt = Prompt(
            project_id=project_id, name=name, description=description, created_by=user_id
        )
        return await self.prompt_repo.create(prompt)

    async def list_by_project(
        self, project_id: uuid.UUID, user_id: uuid.UUID, page: int, page_size: int, search: str | None = None
    ) -> tuple[list[Prompt], int]:
        """List prompts in a project with optional name search and pagination."""
        await self._check_project_access(project_id, user_id)
        return await self.prompt_repo.find_by_project(project_id, page, page_size, search)

    async def get(self, prompt_id: uuid.UUID, user_id: uuid.UUID) -> Prompt:
        """Get a single prompt by ID, checking project access."""
        prompt = await self.prompt_repo.find_by_id(prompt_id)
        if not prompt:
            raise NotFoundError("Prompt", str(prompt_id))
        await self._check_project_access(prompt.project_id, user_id)
        return prompt

    async def update(
        self, prompt_id: uuid.UUID, user_id: uuid.UUID, name: str | None, description: str | None
    ) -> Prompt:
        """Update a prompt's name and/or description."""
        prompt = await self.get(prompt_id, user_id)
        if name is not None:
            prompt.name = name
        if description is not None:
            prompt.description = description
        return await self.prompt_repo.update(prompt)

    async def delete(self, prompt_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a prompt."""
        prompt = await self.get(prompt_id, user_id)
        await self.prompt_repo.delete(prompt)

    async def set_current_version(self, prompt_id: uuid.UUID, version_id: uuid.UUID) -> None:
        """Set the active (current) version for a prompt."""
        prompt = await self.prompt_repo.find_by_id(prompt_id)
        if prompt:
            prompt.current_version_id = version_id
            await self.prompt_repo.update(prompt)
