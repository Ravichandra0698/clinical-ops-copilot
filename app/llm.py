# llm.py
# Purpose: a thin, safe wrapper around whichever LLM we use.
# The rest of the app talks to "an LLM client" and never to a provider directly.
# That is why switching from a paid API to a free local model needs ONE new class
# here and ZERO changes to the API endpoint.

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx  # a modern HTTP library; we use it to talk to the local Ollama server

try:
    import anthropic  # only needed if you choose the paid Anthropic provider
except ImportError:   # not installed? that's fine when using Ollama
    anthropic = None

from app.config import settings

logger = logging.getLogger("llm")


@dataclass
class LLMResult:
    """What every LLM call returns, regardless of provider."""
    text: str            # the model's answer
    model: str           # which model actually answered
    input_tokens: int    # tokens we sent (the prompt)
    output_tokens: int   # tokens we received (the answer)
    latency_ms: int      # how long the call took, in milliseconds


class LLMError(Exception):
    """Any provider problem, translated into an HTTP status the API can return."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class LLMClient(Protocol):
    """The shape every client must have. A Protocol is a promise, not a base class:
    anything with a matching `complete` method counts, including test fakes."""

    async def complete(self, system: str, user: str, max_tokens: int | None = None) -> LLMResult: ...


# =============================================================================
# FREE option: a local open-source model served by Ollama
# =============================================================================
class OllamaLLM:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # `transport` is normally None. Tests pass a fake transport so no real server is needed.
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=settings.llm_timeout_seconds,
            transport=transport,
        )

    async def complete(self, system: str, user: str, max_tokens: int | None = None) -> LLMResult:
        start = time.perf_counter()
        payload = {
            "model": settings.ollama_model,
            "stream": False,  # wait for the whole answer instead of receiving it word by word
            "messages": [
                {"role": "system", "content": system},  # instructions that frame every answer
                {"role": "user", "content": user},      # the actual question
            ],
            "options": {"num_predict": max_tokens or settings.llm_max_tokens},  # cap the answer length
        }
        try:
            response = await self._client.post("/api/chat", json=payload)
        # Order matters: specific errors must be caught before general ones.
        except httpx.ConnectError as exc:        # nothing is listening: Ollama isn't running
            raise LLMError("Ollama is not running. Start the Ollama app and try again", 503) from exc
        except httpx.TimeoutException as exc:    # no answer within our timeout
            raise LLMError("The model took too long to respond", 504) from exc
        except httpx.HTTPError as exc:           # any other network problem
            raise LLMError("Could not reach the model service", 502) from exc

        if response.status_code == 404:  # Ollama says 404 when the model was never downloaded
            raise LLMError(
                f"Model '{settings.ollama_model}' is not installed. "
                f"Run: ollama pull {settings.ollama_model}", 503)
        if response.status_code != 200:
            logger.error("Ollama status error %s: %s", response.status_code, response.text[:300])
            raise LLMError(f"Model service error ({response.status_code})", 502)

        data = response.json()
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = LLMResult(
            text=data["message"]["content"],
            model=data.get("model", settings.ollama_model),
            input_tokens=data.get("prompt_eval_count", 0),  # Ollama reports token counts too
            output_tokens=data.get("eval_count", 0),
            latency_ms=latency_ms,
        )
        logger.info("llm_call provider=ollama model=%s in=%d out=%d ms=%d", result.model,
                    result.input_tokens, result.output_tokens, latency_ms)
        return result


# =============================================================================
# PAID option: Anthropic cloud API (optional, kept so you can compare)
# =============================================================================
class AnthropicLLM:
    def __init__(self) -> None:
        if anthropic is None:
            raise LLMError("The 'anthropic' package is not installed (pip install anthropic)", 500)
        if settings.anthropic_api_key is None:
            raise LLMError("ANTHROPIC_API_KEY is not configured", 500)
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    async def complete(self, system: str, user: str, max_tokens: int | None = None) -> LLMResult:
        start = time.perf_counter()
        try:
            response = await self._client.messages.create(
                model=settings.llm_model,
                max_tokens=max_tokens or settings.llm_max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError as exc:
            raise LLMError("The model is busy, please try again shortly", 429) from exc
        except anthropic.APITimeoutError as exc:
            raise LLMError("The model took too long to respond", 504) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the model service", 502) from exc
        except anthropic.AuthenticationError as exc:
            logger.error("LLM authentication failed: %s", exc.message)
            raise LLMError("The server's LLM credentials are invalid", 500) from exc
        except anthropic.APIStatusError as exc:
            logger.error("LLM status error %s: %s", exc.status_code, exc.message)
            raise LLMError(f"Model service error ({exc.status_code})", 502) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        text = "".join(block.text for block in response.content if block.type == "text")
        logger.info("llm_call provider=anthropic model=%s in=%d out=%d ms=%d", response.model,
                    response.usage.input_tokens, response.usage.output_tokens, latency_ms)
        return LLMResult(text=text, model=response.model,
                         input_tokens=response.usage.input_tokens,
                         output_tokens=response.usage.output_tokens,
                         latency_ms=latency_ms)


@lru_cache  # build the client once and reuse it, instead of on every request
def get_llm() -> LLMClient:
    """FastAPI dependency: endpoints ask for this, and tests can replace it.
    The provider is chosen by the LLM_PROVIDER setting."""
    if settings.llm_provider == "ollama":
        return OllamaLLM()
    if settings.llm_provider == "anthropic":
        return AnthropicLLM()
    raise LLMError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'", 500)