import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.project import Project
from app.models.prompt import Prompt
from app.models.prompt_version import PromptVersion
from app.repositories.project_member_repo import ProjectMemberRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.user_repo import UserRepository


@dataclass
class MemberInfo:
    """Project member details returned by the service layer."""
    user_id: str
    email: str
    display_name: str
    role: str


class ProjectService:
    """Manages project CRUD, member management, and role-based access control."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.member_repo = ProjectMemberRepository(session)
        self.user_repo = UserRepository(session)

    async def _require_access(self, project_id: uuid.UUID, user_id: uuid.UUID, roles: tuple[str, ...]) -> Project:
        """Verify the user has one of the required roles (or is the project owner).

        Raises NotFoundError if the project doesn't exist, ForbiddenError otherwise.
        """
        project = await self.project_repo.find_by_id(project_id)
        if not project:
            raise NotFoundError("Project", str(project_id))

        if project.owner_id == user_id:
            return project

        member = await self.member_repo.find_member(project_id, user_id)
        if not member or member.role not in roles:
            raise ForbiddenError("Access denied")

        return project

    async def create(self, name: str, description: str | None, owner_id: uuid.UUID) -> Project:
        """Create a new project and add the creator as owner."""
        project = Project(name=name, description=description, owner_id=owner_id)
        project = await self.project_repo.create(project)
        await self.member_repo.add(project.id, owner_id, "owner")
        return project

    async def list_my_projects(self, user_id: uuid.UUID, page: int, page_size: int) -> tuple[list[Project], int]:
        """List projects the user is a member of, paginated at the database level."""
        project_ids = await self.member_repo.find_user_projects(user_id)
        if not project_ids:
            return [], 0
        return await self.project_repo.find_by_ids(project_ids, page, page_size)

    async def get(self, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
        """Get a project by ID. Any member (owner/editor/viewer) can view."""
        return await self._require_access(project_id, user_id, ("owner", "editor", "viewer"))

    async def update(self, project_id: uuid.UUID, user_id: uuid.UUID, name: str | None, description: str | None) -> Project:
        """Update project name/description. Requires owner or editor role."""
        project = await self._require_access(project_id, user_id, ("owner", "editor"))
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        return await self.project_repo.update(project)

    async def delete(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a project and all related data. Only the owner can delete."""
        project = await self._require_access(project_id, user_id, ("owner",))

        # Cascade-delete all related data in order to satisfy FK constraints
        prompts = await self.session.execute(
            select(Prompt).where(Prompt.project_id == project_id)
        )
        prompt_list = list(prompts.scalars().all())

        for prompt in prompt_list:
            # Clear current_version FK
            prompt.current_version_id = None

            # Clear parent_version FK on child versions
            versions = await self.session.execute(
                select(PromptVersion).where(PromptVersion.prompt_id == prompt.id)
            )
            version_list = list(versions.scalars().all())
            for v in version_list:
                v.parent_version_id = None

            await self.session.flush()

            # Delete dependent rows for each version
            for v in version_list:
                await self.session.execute(
                    text("DELETE FROM test_runs WHERE version_id = :vid"), {"vid": v.id}
                )
                await self.session.execute(
                    text("DELETE FROM experiment_results WHERE experiment_id IN (SELECT id FROM experiments WHERE version_a_id = :vid OR version_b_id = :vid)"), {"vid": v.id}
                )
                await self.session.execute(
                    text("DELETE FROM experiments WHERE version_a_id = :vid OR version_b_id = :vid"), {"vid": v.id}
                )

            # Delete versions
            for v in version_list:
                await self.session.delete(v)

            # Delete test suites and their runs
            await self.session.execute(
                text("DELETE FROM test_runs WHERE test_suite_id IN (SELECT id FROM test_suites WHERE prompt_id = :pid)"), {"pid": prompt.id}
            )
            await self.session.execute(
                text("DELETE FROM test_suites WHERE prompt_id = :pid"), {"pid": prompt.id}
            )

            await self.session.delete(prompt)

        # Delete project members
        await self.session.execute(
            text("DELETE FROM project_members WHERE project_id = :pid"), {"pid": project_id}
        )

        await self.project_repo.delete(project)

    async def add_member(self, project_id: uuid.UUID, email: str, role: str, actor_id: uuid.UUID) -> MemberInfo:
        """Add a user to a project by email. Only the owner can add members."""
        await self._require_access(project_id, actor_id, ("owner",))

        invited = await self.user_repo.find_by_email(email)
        if not invited:
            raise NotFoundError("User", email)

        existing = await self.member_repo.find_member(project_id, invited.id)
        if existing:
            raise ConflictError("User is already a member")

        await self.member_repo.add(project_id, invited.id, role)
        return MemberInfo(
            user_id=str(invited.id),
            email=invited.email,
            display_name=invited.display_name,
            role=role,
        )

    async def list_members(self, project_id: uuid.UUID, user_id: uuid.UUID) -> list[MemberInfo]:
        """List all members of a project. Any member can view."""
        await self._require_access(project_id, user_id, ("owner", "editor", "viewer"))

        members = await self.member_repo.find_by_project(project_id)
        result = []
        for m in members:
            u = await self.user_repo.find_by_id(uuid.UUID(m["user_id"]))
            if u:
                result.append(MemberInfo(
                    user_id=str(u.id), email=u.email,
                    display_name=u.display_name, role=m["role"],
                ))
        return result

    async def remove_member(self, project_id: uuid.UUID, target_user_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        """Remove a member from a project. Only the owner can remove, and cannot remove the owner."""
        await self._require_access(project_id, actor_id, ("owner",))

        target = await self.member_repo.find_member(project_id, target_user_id)
        if not target:
            raise NotFoundError("Member", str(target_user_id))
        if target.role == "owner":
            raise ConflictError("Cannot remove the project owner")

        await self.member_repo.remove(project_id, target_user_id)
