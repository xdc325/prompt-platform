import json
from typing import AsyncIterator

import httpx

from app.core.config import settings
from app.providers.base import BaseProvider, ChatResult, ProviderAPIError, RateLimitError


class ClaudeProvider(BaseProvider):
    provider_name = "claude"

    def __init__(self):
        super().__init__()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.anthropic.com",
                headers={
                    "x-api-key": settings.anthropic_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def _call_api(self, model: str, prompt: str, params: dict) -> ChatResult:
        client = await self._get_client()
        body = {
            "model": model,
            "max_tokens": params.pop("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
            **params,
        }

        response = await client.post("/v1/messages", json=body)
        if response.status_code == 429:
            raise RateLimitError("Claude rate limited")
        if response.status_code >= 500:
            raise ProviderAPIError(f"Claude server error: {response.status_code}", response.status_code)
        if response.status_code != 200:
            raise ProviderAPIError(f"Claude error: {response.text}", response.status_code)

        data = response.json()
        return ChatResult(
            content=data["content"][0]["text"],
            model=model,
            usage=data.get("usage"),
        )

    async def _call_stream_api(self, model: str, prompt: str, params: dict) -> AsyncIterator[str]:
        client = await self._get_client()
        body = {
            "model": model,
            "max_tokens": params.pop("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            **params,
        }

        async with client.stream("POST", "/v1/messages", json=body) as response:
            if response.status_code == 429:
                raise RateLimitError("Claude rate limited")
            if response.status_code != 200:
                raise ProviderAPIError(f"Claude error: {await response.aread()}", response.status_code)

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line.removeprefix("data: ")
                    try:
                        event = json.loads(data_str)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if "text" in delta:
                                yield delta["text"]
                    except (json.JSONDecodeError, KeyError):
                        continue
