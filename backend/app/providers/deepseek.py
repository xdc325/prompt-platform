from app.core.config import settings
from app.providers.openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    provider_name = "deepseek"

    def __init__(self):
        super().__init__(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
