import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_member import ProjectMember


class ProjectMemberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_project(self, project_id: uuid.UUID) -> list[dict]:
        q = (
            select(
                ProjectMember.user_id,
                ProjectMember.role,
            )
            .where(ProjectMember.project_id == project_id)
        )
        result = await self.session.execute(q)
        return [{"user_id": str(row[0]), "role": row[1]} for row in result.all()]

    async def find_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        q = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def add(self, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> ProjectMember:
        member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.flush()
        return member

    async def remove(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        q = delete(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        result = await self.session.execute(q)
        return result.rowcount > 0

    async def find_user_projects(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        q = select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
        result = await self.session.execute(q)
        return [row[0] for row in result.all()]
