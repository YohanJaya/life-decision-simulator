from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

from openai import AsyncOpenAI
from httpx import Timeout
from pydantic import BaseModel, ValidationError

from .config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_WINDOW_SECONDS = 60.0

_client: Optional[AsyncOpenAI] = None


@dataclass
class _Reservation:
    timestamp: float
    tokens: int


class TokenRateLimiter:
    """Sliding-window limiter enforcing both requests-per-minute and tokens-per-minute.

    Providers like Groq reject bursts with HTTP 429 once either the RPM or TPM ceiling
    is crossed within a rolling 60s window. Each call reserves an *estimated* token cost
    up front, then reconciles to the response's actual usage, keeping the window accurate
    for whatever runs next.
    """

    def __init__(self, rpm: int, tpm: int) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self._window: deque[_Reservation] = deque()
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        while self._window and self._window[0].timestamp < cutoff:
            self._window.popleft()

    async def acquire(self, estimated_tokens: int) -> _Reservation:
        # A single call can never need more than the entire per-minute budget.
        estimated_tokens = max(1, min(estimated_tokens, self.tpm))
        while True:
            async with self._lock:
                now = time.monotonic()
                self._prune(now)
                used = sum(r.tokens for r in self._window)
                if len(self._window) < self.rpm and used + estimated_tokens <= self.tpm:
                    reservation = _Reservation(now, estimated_tokens)
                    self._window.append(reservation)
                    return reservation
                # Window is full; the oldest reservation frees capacity when it ages out.
                wait = _WINDOW_SECONDS - (now - self._window[0].timestamp) + 0.05
            logger.info("rate limiter waiting %.1fs (rpm/tpm window full)", wait)
            await asyncio.sleep(max(wait, 0.1))

    async def reconcile(self, reservation: _Reservation, actual_tokens: int) -> None:
        async with self._lock:
            reservation.tokens = max(1, actual_tokens)


_concurrency = asyncio.Semaphore(settings.llm_max_concurrency)
_rate_limiter = TokenRateLimiter(rpm=settings.llm_rpm, tpm=settings.llm_tpm)


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "ollama",
            timeout=Timeout(connect=30.0, read=120.0, write=30.0, pool=10.0),
            max_retries=4,  # honor provider Retry-After on the rare 429 that slips through
        )
    return _client


async def chat(
    messages: list[dict],
    agent_name: str = "unknown",
    response_format: Optional[dict] = None,
    temperature: float = 0.3,
) -> str:
    """Raw LLM call, throttled to stay under the provider's RPM/TPM ceilings."""
    client = get_client()
    serialized = json.dumps(messages)
    prompt_hash = hashlib.sha256(serialized.encode()).hexdigest()[:8]

    # Rough estimate: ~4 chars/token for the prompt, plus a reservation for the response.
    # Reconciled to actual usage after the call so the window self-corrects.
    estimated_tokens = len(serialized) // 4 + settings.llm_completion_token_budget

    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    async with _concurrency:
        reservation = await _rate_limiter.acquire(estimated_tokens)
        t0 = time.perf_counter()
        response = await client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000

        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else estimated_tokens
        await _rate_limiter.reconcile(reservation, tokens)

        logger.info(
            "[%s] hash=%s latency=%.0fms tokens=%d",
            agent_name,
            prompt_hash,
            latency_ms,
            tokens,
        )

    return content


async def chat_json(
    messages: list[dict],
    agent_name: str = "unknown",
    temperature: float = 0.3,
) -> dict:
    content = await chat(
        messages=messages,
        agent_name=agent_name,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(content)


async def chat_json_validated(
    messages: list[dict],
    model_class: Type[T],
    agent_name: str = "unknown",
    temperature: float = 0.3,
) -> T:
    """JSON mode call with Pydantic validation. Retries once on failure."""
    content = await chat(
        messages=messages,
        agent_name=agent_name,
        response_format={"type": "json_object"},
        temperature=temperature,
    )

    def _try_parse(raw: str) -> T:
        data = json.loads(raw)
        return model_class.model_validate(data)

    try:
        return _try_parse(content)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("[%s] validation error, retrying: %s", agent_name, exc)
        retry_messages = messages + [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": (
                    f"The output failed validation with this error:\n{exc}\n\n"
                    "Please fix the JSON so it matches the required schema exactly."
                ),
            },
        ]
        content2 = await chat(
            messages=retry_messages,
            agent_name=f"{agent_name}/retry",
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        return _try_parse(content2)
