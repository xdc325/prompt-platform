import difflib
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.experiment import Experiment
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.experiment_result_repo import ExperimentResultRepository
from app.repositories.project_member_repo import ProjectMemberRepository
from app.repositories.prompt_repo import PromptRepository
from app.repositories.version_repo import VersionRepository
from app.providers import get_provider
from app.services.mixins import PromptAccessMixin


class ExperimentService(PromptAccessMixin):
    """Manages A/B experiments comparing two prompt versions, playground, and compare operations.

    Only one experiment can run per prompt at a time. Results track latency,
    output, and quality scores for each version.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.experiment_repo = ExperimentRepository(session)
        self.result_repo = ExperimentResultRepository(session)
        self.prompt_repo = PromptRepository(session)
        self.version_repo = VersionRepository(session)
        self.member_repo = ProjectMemberRepository(session)

    async def create_experiment(
        self, prompt_id: uuid.UUID, version_a_id: uuid.UUID, version_b_id: uuid.UUID,
        traffic_split: dict, user_id: uuid.UUID,
    ) -> Experiment:
        """Create a new A/B experiment. Fails if another experiment is already running."""
        await self._check_prompt_access(prompt_id, user_id)

        running = await self.experiment_repo.find_running_by_prompt(prompt_id)
        if running:
            raise ConflictError("An experiment is already running for this prompt")

        experiment = Experiment(
            prompt_id=prompt_id,
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            traffic_split=traffic_split,
            status="running",
        )
        return await self.experiment_repo.create(experiment)

    async def list_experiments(self, prompt_id: uuid.UUID, user_id: uuid.UUID, page: int, page_size: int):
        """List experiments for a prompt with pagination."""
        await self._check_prompt_access(prompt_id, user_id)
        return await self.experiment_repo.find_by_prompt(prompt_id, page, page_size)

    async def get_experiment(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """Get experiment details including aggregated result summary."""
        experiment = await self.experiment_repo.find_by_id(experiment_id)
        if not experiment:
            raise NotFoundError("Experiment", str(experiment_id))
        await self._check_prompt_access(experiment.prompt_id, user_id)

        summary = await self.result_repo.summary_by_experiment(experiment_id)
        result = {
            "id": str(experiment.id),
            "prompt_id": str(experiment.prompt_id),
            "version_a_id": str(experiment.version_a_id),
            "version_b_id": str(experiment.version_b_id),
            "traffic_split": experiment.traffic_split,
            "status": experiment.status,
            "started_at": experiment.started_at,
            "ended_at": experiment.ended_at,
            "summary": summary,
        }
        return result

    async def stop_experiment(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> Experiment:
        """Stop a running experiment, setting its status to completed."""
        experiment = await self.experiment_repo.find_by_id(experiment_id)
        if not experiment:
            raise NotFoundError("Experiment", str(experiment_id))
        await self._check_prompt_access(experiment.prompt_id, user_id)

        if experiment.status != "running":
            raise ConflictError("Experiment is not running")

        experiment.status = "completed"
        experiment.ended_at = datetime.now(timezone.utc)
        return await self.experiment_repo.update(experiment)

    async def delete_experiment(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete an experiment."""
        experiment = await self.experiment_repo.find_by_id(experiment_id)
        if not experiment:
            raise NotFoundError("Experiment", str(experiment_id))
        await self._check_prompt_access(experiment.prompt_id, user_id)
        await self.experiment_repo.delete(experiment)

    async def list_results(self, experiment_id: uuid.UUID, user_id: uuid.UUID, page: int, page_size: int):
        """List individual results for an experiment with pagination."""
        experiment = await self.experiment_repo.find_by_id(experiment_id)
        if not experiment:
            raise NotFoundError("Experiment", str(experiment_id))
        await self._check_prompt_access(experiment.prompt_id, user_id)
        return await self.result_repo.find_by_experiment(experiment_id, page, page_size)

    async def playground(self, prompt_id: uuid.UUID, version_id: uuid.UUID, input_text: str, model: str, user_id: uuid.UUID) -> dict:
        """Execute a single prompt version against an LLM and return the output."""
        await self._check_prompt_access(prompt_id, user_id)
        version = await self.version_repo.find_by_id(version_id)
        if not version:
            raise NotFoundError("Version", str(version_id))

        prompt = version.content.replace("{input}", input_text)

        # Validate API key before calling the provider
        provider = None
        if model.startswith("deepseek") and not settings.deepseek_api_key:
            raise ConflictError("DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY")
        elif model.startswith("claude") and not settings.anthropic_api_key:
            raise ConflictError("Anthropic API Key 未配置，请在 .env 中设置 ANTHROPIC_API_KEY")
        elif not model.startswith("deepseek") and not model.startswith("claude") and not settings.openai_api_key:
            raise ConflictError("OpenAI API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")

        provider = get_provider(model)
        result = await provider.chat(model=model, prompt=prompt, params={"temperature": 0}, use_cache=False)

        return {
            "version_id": str(version_id),
            "input": input_text,
            "output": result.content,
            "model": model,
        }

    async def compare(self, prompt_id: uuid.UUID, version_a_id: uuid.UUID, version_b_id: uuid.UUID, input_text: str, model: str, user_id: uuid.UUID) -> dict:
        """Run the same input through two prompt versions and diff their outputs word-by-word."""
        await self._check_prompt_access(prompt_id, user_id)

        va = await self.version_repo.find_by_id(version_a_id)
        vb = await self.version_repo.find_by_id(version_b_id)
        if not va or not vb:
            raise NotFoundError("Version", str(version_a_id if not va else version_b_id))

        if model.startswith("deepseek") and not settings.deepseek_api_key:
            raise ConflictError("DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY")
        elif model.startswith("claude") and not settings.anthropic_api_key:
            raise ConflictError("Anthropic API Key 未配置，请在 .env 中设置 ANTHROPIC_API_KEY")
        elif not model.startswith("deepseek") and not model.startswith("claude") and not settings.openai_api_key:
            raise ConflictError("OpenAI API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")

        provider = get_provider(model)
        prompt_a = va.content.replace("{input}", input_text)
        prompt_b = vb.content.replace("{input}", input_text)

        t0 = time.monotonic()
        result_a = await provider.chat(model=model, prompt=prompt_a, params={"temperature": 0}, use_cache=False)
        latency_a = round((time.monotonic() - t0) * 1000)

        t0 = time.monotonic()
        result_b = await provider.chat(model=model, prompt=prompt_b, params={"temperature": 0}, use_cache=False)
        latency_b = round((time.monotonic() - t0) * 1000)

        a_words = result_a.content.split()
        b_words = result_b.content.split()
        matcher = difflib.SequenceMatcher(None, a_words, b_words)
        output_diff = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                output_diff.append({"type": "same", "text": " ".join(a_words[i1:i2])})
            elif tag == "replace":
                output_diff.append({"type": "changed", "a": " ".join(a_words[i1:i2]), "b": " ".join(b_words[j1:j2])})
            elif tag == "delete":
                output_diff.append({"type": "removed", "a": " ".join(a_words[i1:i2])})
            elif tag == "insert":
                output_diff.append({"type": "added", "b": " ".join(b_words[j1:j2])})

        return {
            "input": input_text,
            "results": [
                {"version": f"v{va.version_number}", "output": result_a.content, "latency_ms": latency_a, "cost": 0},
                {"version": f"v{vb.version_number}", "output": result_b.content, "latency_ms": latency_b, "cost": 0},
            ],
            "output_diff": output_diff,
        }
