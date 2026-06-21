import uuid

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.prompt import Prompt


class PromptAccessMixin:
    """Shared access check for services that operate on prompts.

    Requires self.prompt_repo and self.member_repo to be set by the inheriting class.
    """

    prompt_repo: object
    member_repo: object

    async def _check_prompt_access(self, prompt_id: uuid.UUID, user_id: uuid.UUID) -> Prompt:
        """Verify the user has editor/owner access to the prompt's project.

        Raises NotFoundError if the prompt doesn't exist, ForbiddenError if the
        user lacks sufficient permissions.
        """
        prompt = await self.prompt_repo.find_by_id(prompt_id)
        if not prompt:
            raise NotFoundError("Prompt", str(prompt_id))
        member = await self.member_repo.find_member(prompt.project_id, user_id)
        if not member or member.role not in ("owner", "editor"):
            raise ForbiddenError("Access denied")
        return prompt
