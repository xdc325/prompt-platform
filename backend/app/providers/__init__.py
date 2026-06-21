from app.providers.base import BaseProvider, ChatResult
from app.providers.openai import OpenAIProvider
from app.providers.claude import ClaudeProvider
from app.providers.deepseek import DeepSeekProvider

__all__ = ["BaseProvider", "ChatResult", "OpenAIProvider", "ClaudeProvider", "DeepSeekProvider"]


def get_provider(model: str) -> BaseProvider:
    """Return the appropriate LLM provider for the given model name."""
    if model.startswith("deepseek"):
        return DeepSeekProvider()
    if model.startswith("claude"):
        return ClaudeProvider()
    return OpenAIProvider()
