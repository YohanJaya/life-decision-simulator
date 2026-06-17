from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from .config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.ollama_base_url,
            api_key="ollama",  # Ollama accepts any non-empty key
        )
    return _client


async def chat(
    messages: list[dict],
    agent_name: str = "unknown",
    response_format: Optional[dict] = None,
    temperature: float = 0.3,
) -> str:
    """Raw LLM call. Returns the text content of the first choice."""
    client = get_client()
    prompt_hash = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:8]

    kwargs: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

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
    return content


async def chat_json(
    messages: list[dict],
    agent_name: str = "unknown",
    temperature: float = 0.3,
) -> dict:
    """Call LLM in JSON mode. Returns parsed dict."""
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
    """Call LLM in JSON mode and validate the result against a Pydantic model.

    On validation failure, retries once with the error appended to the prompt,
    then raises if the retry also fails.
    """
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
