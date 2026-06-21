import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

import redis.asyncio as aioredis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatResult:
    """Result from an LLM chat call."""
    content: str
    model: str
    usage: dict | None = None
    cached: bool = False


class RateLimitError(Exception):
    """Raised when the provider returns a 429 rate limit response."""
    pass


class ProviderAPIError(Exception):
    """Raised for non-200 responses from the provider API."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code


class BaseProvider(ABC):
    """Abstract base for LLM providers with retry, caching, and rate limiting.

    Subclasses must implement _call_api and _call_stream_api. The base class
    handles cache lookup (Redis), concurrency limiting (asyncio.Semaphore),
    and retry logic (tenacity with exponential backoff).
    """

    provider_name: str = "base"

    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrent)
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        """Lazily initialize and return a Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        return self._redis

    def _cache_key(self, model: str, prompt: str, params: dict) -> str:
        """Generate a deterministic SHA-256 cache key from model + prompt + params."""
        raw = json.dumps({"model": model, "prompt": prompt, "params": params}, sort_keys=True)
        return f"llm:cache:{hashlib.sha256(raw.encode()).hexdigest()}"

    async def _get_cache(self, cache_key: str) -> str | None:
        """Retrieve a cached response from Redis. Returns None on any error."""
        try:
            r = await self._get_redis()
            cached = await r.get(cache_key)
            return cached.decode("utf-8") if cached else None
        except Exception:
            return None

    async def _set_cache(self, cache_key: str, content: str):
        """Store a response in Redis with the configured TTL."""
        try:
            r = await self._get_redis()
            await r.setex(cache_key, settings.cache_ttl_seconds, content.encode("utf-8"))
        except Exception:
            pass

    @abstractmethod
    async def _call_api(self, model: str, prompt: str, params: dict) -> ChatResult:
        """Provider-specific API call. Must be implemented by subclasses."""
        ...

    @abstractmethod
    async def _call_stream_api(self, model: str, prompt: str, params: dict) -> AsyncIterator[str]:
        """Provider-specific streaming API call. Must be implemented by subclasses."""
        ...

    async def chat(self, model: str, prompt: str, params: dict | None = None, use_cache: bool = True) -> ChatResult:
        """Send a prompt to the LLM with caching, retry, and rate limiting.

        Cache is checked before the API call (if use_cache=True) and populated after.
        """
        params = params or {}
        cache_key = self._cache_key(model, prompt, params)

        if use_cache:
            cached = await self._get_cache(cache_key)
            if cached:
                logger.info("llm_cache_hit", provider=self.provider_name, model=model)
                return ChatResult(content=cached, model=model, cached=True)

        async with self._semaphore:
            result = await self._call_with_retry(model, prompt, params)

        if use_cache:
            await self._set_cache(cache_key, result.content)

        return result

    async def chat_stream(self, model: str, prompt: str, params: dict | None = None) -> AsyncIterator[str]:
        """Stream a prompt through the LLM with retry and rate limiting (no caching)."""
        params = params or {}
        async with self._semaphore:
            async for chunk in self._call_with_retry_stream(model, prompt, params):
                yield chunk

    async def _call_with_retry(self, model: str, prompt: str, params: dict) -> ChatResult:
        """Call the provider API with tenacity retry (3 attempts, exponential backoff)."""

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((RateLimitError, ProviderAPIError)),
            reraise=True,
        )
        async def _do_call():
            try:
                return await self._call_api(model, prompt, params)
            except (RateLimitError, ProviderAPIError):
                raise
            except Exception as e:
                raise ProviderAPIError(str(e), status_code=502)

        try:
            return await _do_call()
        except (RateLimitError, ProviderAPIError):
            raise
        except Exception as e:
            raise LLMProviderError(str(e), self.provider_name) from e

    async def _call_with_retry_stream(self, model: str, prompt: str, params: dict) -> AsyncIterator[str]:
        """Stream with manual retry loop (tenacity doesn't support async generators)."""
        attempt = 0
        while attempt < 3:
            try:
                async for chunk in self._call_stream_api(model, prompt, params):
                    yield chunk
                return
            except (RateLimitError, ProviderAPIError):
                attempt += 1
                if attempt >= 3:
                    raise LLMProviderError("Max retries exceeded", self.provider_name)
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                raise LLMProviderError(str(e), self.provider_name) from e
