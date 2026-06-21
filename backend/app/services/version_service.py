import difflib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.prompt_version import PromptVersion
from app.repositories.prompt_repo import PromptRepository
from app.repositories.project_member_repo import ProjectMemberRepository
from app.repositories.version_repo import VersionRepository
from app.services.mixins import PromptAccessMixin


class VersionService(PromptAccessMixin):
    """Manages prompt version lifecycle: draft → pending_review → published → archived.

    State machine rules are defined in VALID_TRANSITIONS. Publishing a version
    auto-archives the previously published version and updates the prompt's
    current_version_id.
    """

    VALID_TRANSITIONS = {
        "draft": ["pending_review"],
        "pending_review": ["draft", "published"],
        "published": ["archived"],
        "archived": [],
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.version_repo = VersionRepository(session)
        self.prompt_repo = PromptRepository(session)
        self.member_repo = ProjectMemberRepository(session)

    async def list_versions(self, prompt_id: uuid.UUID, user_id: uuid.UUID, page: int, page_size: int):
        """List versions for a prompt, newest first."""
        await self._check_prompt_access(prompt_id, user_id)
        return await self.version_repo.find_by_prompt(prompt_id, page, page_size)

    async def get_version(self, version_id: uuid.UUID, user_id: uuid.UUID) -> PromptVersion:
        """Get a single version by ID."""
        version = await self.version_repo.find_by_id(version_id)
        if not version:
            raise NotFoundError("Version", str(version_id))
        await self._check_prompt_access(version.prompt_id, user_id)
        return version

    async def create_draft(self, prompt_id: uuid.UUID, user_id: uuid.UUID, content: str, variables: list[str], changelog: str | None) -> PromptVersion:
        """Create a new draft version with auto-incremented version number.

        Sets the parent_version_id to the prompt's current version for lineage tracking.
        """
        await self._check_prompt_access(prompt_id, user_id)

        prompt = await self.prompt_repo.find_by_id(prompt_id)
        version_number = await self.version_repo.get_next_version_number(prompt_id)
        parent_id = prompt.current_version_id

        version = PromptVersion(
            prompt_id=prompt_id,
            version_number=version_number,
            content=content,
            variables=variables,
            status="draft",
            created_by=user_id,
            parent_version_id=parent_id,
            changelog=changelog,
        )
        return await self.version_repo.create(version)

    async def transition(self, version_id: uuid.UUID, user_id: uuid.UUID, target: str) -> PromptVersion:
        """Transition a version to a new status following the state machine rules.

        When publishing, all previously published versions are archived and the
        prompt's current_version_id is updated.
        """
        version = await self.version_repo.find_by_id(version_id)
        if not version:
            raise NotFoundError("Version", str(version_id))
        await self._check_prompt_access(version.prompt_id, user_id)

        if target not in self.VALID_TRANSITIONS.get(version.status, []):
            raise ConflictError(f"Cannot transition from {version.status} to {target}")

        if target == "published":
            previous = await self.version_repo.find_published_by_prompt(version.prompt_id)
            for pv in previous:
                pv.status = "archived"

            prompt = await self.prompt_repo.find_by_id(version.prompt_id)
            prompt.current_version_id = version.id

        version.status = target
        return await self.version_repo.update(version)

    async def rollback(self, prompt_id: uuid.UUID, target_version_id: uuid.UUID, user_id: uuid.UUID) -> PromptVersion:
        """Set any existing version as the current version without changing its status."""
        await self._check_prompt_access(prompt_id, user_id)

        target = await self.version_repo.find_by_id(target_version_id)
        if not target or str(target.prompt_id) != str(prompt_id):
            raise NotFoundError("Version", str(target_version_id))

        prompt = await self.prompt_repo.find_by_id(prompt_id)
        prompt.current_version_id = target.id
        await self.prompt_repo.update(prompt)

        return target

    async def delete(self, version_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a version after verifying access.

        Clears FK references before deleting: unsets parent_version_id on
        child versions, and clears prompt.current_version_id if needed.
        """
        version = await self.version_repo.find_by_id(version_id)
        if not version:
            raise NotFoundError("Version", str(version_id))
        await self._check_prompt_access(version.prompt_id, user_id)

        prompt = await self.prompt_repo.find_by_id(version.prompt_id)
        if prompt and prompt.current_version_id == version.id:
            prompt.current_version_id = None

        children = await self.version_repo.find_by_parent_id(version_id)
        for child in children:
            child.parent_version_id = None

        await self.version_repo.delete(version)

    async def diff(self, version_a_id: uuid.UUID, version_b_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """Compute a line-level diff between two versions using difflib.SequenceMatcher.

        Returns categorized changes (replaced, added, removed) with context lines
        and a human-readable summary.
        """
        va = await self.version_repo.find_by_id(version_a_id)
        vb = await self.version_repo.find_by_id(version_b_id)
        if not va or not vb:
            raise NotFoundError("Version", str(version_a_id if not va else version_b_id))
        await self._check_prompt_access(va.prompt_id, user_id)

        a_lines = va.content.splitlines(keepends=False)
        b_lines = vb.content.splitlines(keepends=False)

        matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
        changes = []
        position = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                position += (i2 - i1)
                continue

            change = {
                "type": {"replace": "replaced", "delete": "removed", "insert": "added"}[tag],
                "position": position + 1,
                "context_before": a_lines[i1 - 1] if i1 > 0 and i1 <= len(a_lines) else None,
                "context_after": a_lines[i2] if i2 < len(a_lines) else None,
            }

            if tag in ("replace", "delete"):
                old_text = "\n".join(a_lines[i1:i2])
                change["old"] = old_text
                position += (i2 - i1)
            else:
                change["old"] = None

            if tag in ("replace", "insert"):
                new_text = "\n".join(b_lines[j1:j2])
                change["new"] = new_text
            else:
                change["new"] = None

            changes.append(change)

        type_labels = {"replaced": "modified", "added": "added", "removed": "deleted"}
        summary_parts = []
        for t in ("replaced", "added", "removed"):
            count = sum(1 for c in changes if c["type"] == t)
            if count:
                summary_parts.append(f"{count} {type_labels[t]}")
        summary = f"{len(changes)} changes: {', '.join(summary_parts)}" if summary_parts else "No changes"

        return {
            "version_a": {"number": va.version_number, "created_at": va.created_at.isoformat()},
            "version_b": {"number": vb.version_number, "created_at": vb.created_at.isoformat()},
            "changes": changes,
            "summary": summary,
        }
