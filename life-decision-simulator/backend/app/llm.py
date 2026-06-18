from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Optional, Type, TypeVar

from openai import AsyncOpenAI
from httpx import Timeout
from pydantic import BaseModel, ValidationError

from .config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: Optional[AsyncOpenAI] = None

# Limits concurrent LLM calls to 1 to stay within free-tier TPM limits (Groq: 6k TPM)
_llm_semaphore = asyncio.Semaphore(1)


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "ollama",
            timeout=Timeout(connect=30.0, read=120.0, write=30.0, pool=10.0),
        )
    return _client


async def chat(
    messages: list[dict],
    agent_name: str = "unknown",
    response_format: Optional[dict] = None,
    temperature: float = 0.3,
) -> str:
    """Raw LLM call, serialized via semaphore to avoid rate-limit bursts."""
    client = get_client()
    prompt_hash = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:8]

    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    async with _llm_semaphore:
        t0 = time.perf_counter()
        response = await client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000

        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        logger.info(
            "[%s] hash=%s latency=%.0fms tokens=%d",
            agent_name,
            prompt_hash,
            latency_ms,
            tokens,
        )

        # Brief pause after each call to stay well within TPM limits
        await asyncio.sleep(1.5)

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
