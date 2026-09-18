"""Provider switch: one function, every provider.

Ollama, Gemini, and Groq all expose an OpenAI-compatible chat-completions
endpoint, so a single call through the `openai` SDK, pointed at a different
base_url, speaks to any of them. This is the reason "OpenAI-style" and
"provider-agnostic" are the same decision here rather than a tradeoff: there
is no Anthropic-specific, Gemini-specific, or Groq-specific code anywhere in
the harness, only a config struct that picks base_url/api_key/model.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger("agentward_harness.model")

Provider = Literal["ollama", "gemini", "groq"]

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class ModelConfig:
    """Resolved provider settings for one model-calling session.

    Read once with `from_env()`, then threaded through explicitly rather than
    re-read per call, so a run's provider/model choice is fixed for its whole
    duration and can be stamped into the trajectory log as-is.
    """

    provider: Provider
    model: str
    base_url: str
    api_key: str

    @staticmethod
    def from_env() -> ModelConfig:
        """Build a ModelConfig from MODEL_PROVIDER and friends.

        Defaults to `ollama`, matching the project's own default: no API key
        required, works with nothing configured beyond `ollama serve` and the
        model already pulled.
        """
        provider = os.environ.get("MODEL_PROVIDER", "ollama").lower()
        if provider == "ollama":
            return ModelConfig(
                provider="ollama",
                model=os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                # Ollama never checks this; the OpenAI SDK just requires a non-empty string.
                api_key="ollama",
            )
        if provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "MODEL_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                    "Copy .env.example to .env and fill it in."
                )
            return ModelConfig(
                provider="gemini",
                model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                base_url=_GEMINI_BASE_URL,
                api_key=api_key,
            )
        if provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "MODEL_PROVIDER=groq but GROQ_API_KEY is not set. "
                    "Copy .env.example to .env and fill it in."
                )
            return ModelConfig(
                provider="groq",
                model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
                base_url=_GROQ_BASE_URL,
                api_key=api_key,
            )
        raise ValueError(
            f"Unknown MODEL_PROVIDER: {provider!r}. Expected 'ollama', 'gemini', or 'groq'."
        )


@dataclass
class ToolCallRequest:
    """One tool call the model asked for, normalised to the fields a
    dispatcher needs regardless of which provider produced it.

    `extra` holds whatever provider-specific data rode along with this
    particular tool call, verbatim and un-interpreted - opaque to us, and to
    every provider that doesn't send any (Ollama/qwen3 sends none, so this is
    `None` there). Some providers require it echoed back on the next turn's
    outbound tool call or they reject the request; see `SimpleToolLoop.run`
    for where that happens. This is a round-trip contract, not a
    Gemini-specific one - it exists so a provider we haven't tested yet that
    needs the same thing works without new code, and one that needs nothing
    is unaffected.
    """

    id: str
    name: str
    arguments_json: str
    extra: dict[str, Any] | None = None


@dataclass
class ModelReply:
    """One model turn, normalised across providers.

    `reasoning` is populated for models that separate thinking from the final
    answer. Verified live against Ollama's OpenAI-compatible endpoint: Qwen3's
    thinking arrives in an extra `reasoning` field on the message, not mixed
    into `content`. It is `None` for models with no separate thinking channel.
    """

    content: str | None
    reasoning: str | None
    tool_calls: list[ToolCallRequest]
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    raw: Any = field(repr=False, default=None)


async def _log_retryable_response(response: httpx.Response) -> None:
    """httpx response hook: log a 429/5xx before the SDK's own retry logic
    silently absorbs it, so a retry has a visible trace in the server log
    even though it produces no trajectory event of its own."""
    if response.status_code == 429 or response.status_code >= 500:
        retry_after = response.headers.get("retry-after")
        logger.warning(
            "Provider returned %s for %s (retryable) - retry-after=%s",
            response.status_code,
            response.request.url,
            retry_after,
        )


async def call_model(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    config: ModelConfig,
    *,
    max_tokens: int = 4000,
) -> ModelReply:
    """Call the configured provider's chat-completions endpoint.

    `tools` must already be in OpenAI function-calling shape (see
    `mcp_tools.to_openai_tools` for the MCP conversion). This function is the
    one place that knows base_url/api_key/model differ by provider;
    everything downstream (the loop, the trajectory log) works against
    `ModelReply` and never touches a provider SDK directly.

    Async, deliberately: this can take many seconds against a slow local
    model or a rate-limited API, and the loop that calls this runs inside an
    ASGI server (viewer_api.py) alongside an SSE stream that needs the event
    loop free to flush trace events as they happen. A blocking synchronous
    call here would freeze the whole server for that duration, silently
    starving the SSE stream of every event until the call finally returns.
    """
    # Free-tier per-minute token budgets are tight next to a multi-step tool-
    # calling loop's growing context (measured live: one nested chat turn hit
    # ~13.6K tokens/min against Groq's 7.5K limit). The SDK's own retry loop
    # already backs off and honours the provider's Retry-After header on a
    # 429; the default of 2 retries just isn't enough headroom for a burst
    # that blows through a whole minute's budget at once.
    #
    # The retry itself is otherwise invisible - it happens inside the SDK
    # with no trace event and no log line, so a slow step gives no signal
    # about whether it was actually retried or just a naturally slow call.
    # This hook logs every retryable response so that's answerable from the
    # server log without adding a new trajectory event type for it.
    http_client = httpx.AsyncClient(event_hooks={"response": [_log_retryable_response]})
    client = AsyncOpenAI(
        base_url=config.base_url, api_key=config.api_key, max_retries=6, http_client=http_client
    )
    response = await client.chat.completions.create(
        model=config.model,
        messages=messages,
        tools=tools or None,
        max_tokens=max_tokens,
    )
    choice = response.choices[0]
    message = choice.message

    # Ollama's OpenAI-compat layer returns Qwen3's thinking as a field outside
    # the OpenAI schema; the SDK exposes unrecognised fields via model_extra
    # rather than dropping them, so check there when the typed attribute is absent.
    reasoning = getattr(message, "reasoning", None)
    if reasoning is None and message.model_extra:
        reasoning = message.model_extra.get("reasoning")

    tool_calls = [
        ToolCallRequest(
            id=tc.id,
            name=tc.function.name,
            arguments_json=tc.function.arguments,
            extra=tc.model_extra or None,
        )
        for tc in (message.tool_calls or [])
    ]

    usage = response.usage
    return ModelReply(
        content=message.content,
        reasoning=reasoning,
        tool_calls=tool_calls,
        finish_reason=choice.finish_reason,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        raw=response,
    )


__all__ = ["ModelConfig", "ModelReply", "Provider", "ToolCallRequest", "call_model"]
