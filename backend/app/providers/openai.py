import json
from typing import AsyncIterator

import httpx

from app.core.config import settings
from app.providers.base import BaseProvider, ChatResult, ProviderAPIError, RateLimitError


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._api_key = api_key or settings.openai_api_key
        self._base_url = base_url or settings.openai_base_url

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            if not self._api_key:
                raise ProviderAPIError(
                    f"{self.provider_name.upper()}_API_KEY is not configured. "
                    "Set it in .env or docker-compose.yml.",
                    status_code=400,
                )
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def _call_api(self, model: str, prompt: str, params: dict) -> ChatResult:
        client = await self._get_client()
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], **params}

        response = await client.post("/chat/completions", json=body)
        if response.status_code == 429:
            raise RateLimitError("OpenAI rate limited")
        if response.status_code >= 500:
            raise ProviderAPIError(f"OpenAI server error: {response.status_code}", response.status_code)
        if response.status_code != 200:
            raise ProviderAPIError(f"OpenAI error: {response.text}", response.status_code)

        data = response.json()
        return ChatResult(
            content=data["choices"][0]["message"]["content"],
            model=model,
            usage=data.get("usage"),
        )

    async def _call_stream_api(self, model: str, prompt: str, params: dict) -> AsyncIterator[str]:
        client = await self._get_client()
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True, **params}

        async with client.stream("POST", "/chat/completions", json=body) as response:
            if response.status_code == 429:
                raise RateLimitError("OpenAI rate limited")
            if response.status_code != 200:
                raise ProviderAPIError(f"OpenAI error: {await response.aread()}", response.status_code)

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line.removeprefix("data: ")
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
