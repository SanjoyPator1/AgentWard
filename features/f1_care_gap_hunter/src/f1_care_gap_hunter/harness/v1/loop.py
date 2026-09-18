"""The F1 v1 engine: SimpleToolLoop.

Deliberately small: call the model, dispatch whatever tool calls it asked
for (to the MCP server, or to a local tool the caller provides), append the
results, repeat until a designated "stop tool" fires, the model asks for no
more tools, or the step budget runs out. No context compaction, no retry
policy, no planning artifact - those are v2+ decisions, made one at a time
and measured against this baseline, not assumed up front (the user is
learning agents; this loop is meant to be read start to finish).
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from agentward_harness.model import ModelConfig, call_model
from agentward_harness.trajectory import TrajectoryLogger, summarize
from mcp import Client

LocalToolHandler = Callable[[dict[str, Any]], Awaitable[Any] | Any]

TerminationReason = Literal["stop_tool_called", "no_tool_calls", "budget"]

# Debug artifact, not eval output: the exact, uncapped wire-format messages
# list this run sent to the model, overwritten after every step so the file
# always reflects the latest state while a run is still in progress. This is
# distinct from the trajectory log (summarize()'d, event-shaped) and from
# _cap_tool_result's effect on what actually reaches the model - this file
# shows precisely that, verbatim, for a human to read after something looks
# wrong in a run. Gitignored (see .gitignore) - it's a local debugging aid,
# not eval output or something to commit.
_MESSAGES_LOG_DIR = Path(__file__).resolve().parents[4] / "runs" / "chat_messages"

# A single oversized tool result can, on its own, push the very next model
# call over a provider's per-minute token budget - measured live: a 14-
# resource, ~14.5KB raw search_resources result was the direct cause of a
# 413 on Groq's free tier (8K TPM), one call after it entered the
# conversation. Capped here because this is what actually reaches the
# model's context, not just the much smaller trajectory-log summary.
_MAX_TOOL_RESULT_CHARS = 4000

# Best-effort recency key, in priority order, for whatever date-shaped field
# a FHIR resource happens to carry. Checked in this order because a resource
# only ever has one of these, never several - Observations use
# effectiveDateTime, Procedures use performedPeriod, MedicationRequests use
# authoredOn, Conditions use onsetDateTime, everything else falls back to
# meta.lastUpdated before giving up.
_DATE_FIELDS = ("effectiveDateTime", "performedPeriod", "authoredOn", "onsetDateTime")


def _item_recency_key(item: Any) -> str:
    """An ISO-8601-ish string to sort by, empty (sorts last) if none found."""
    if not isinstance(item, dict):
        return ""
    for field_name in _DATE_FIELDS:
        value = item.get(field_name)
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("start"), str):
            return value["start"]
    meta = item.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("lastUpdated"), str):
        return meta["lastUpdated"]
    return ""


def _cap_tool_result(text: str) -> str:
    """Cap a tool result to a size that reaches the model, preferring to drop
    whole items - oldest first - over slicing raw text or dropping arbitrarily.

    A blind character cut can sever a JSON object mid-field - measured live:
    it cut off `performedPeriod` on a Procedure that happened to serialise
    after that point, and the model had to re-fetch the same resource in
    full just to see the one field it needed. Fixed by trimming whole items
    instead. But *which* items survive matters just as much as whether they
    do: also measured live, keeping items in whatever order the FHIR server
    happened to return them (no query here requests a sort) kept the 5
    *oldest* of 11 matching procedures and silently dropped the 6 most
    recent ones - including the one that would have shown the gap being
    checked for did not actually exist. Every F1 check is fundamentally
    "did X happen recently", so recency, not result order, is what decides
    which items are worth keeping when not all of them fit.

    This is truncation, not real pagination - the dropped items are gone,
    not retrievable via a cursor. That is a known, accepted limit of this
    version; a model that needs the complete history rather than "was there
    a recent one" is not well served by this tool.
    """
    if len(text) <= _MAX_TOOL_RESULT_CHARS:
        return text

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None

    if isinstance(parsed, dict):
        list_key = next((k for k, v in parsed.items() if isinstance(v, list) and v), None)
        if list_key is not None:
            items = parsed[list_key]
            ranked = sorted(items, key=_item_recency_key, reverse=True)
            kept: list[Any] = []
            for item in ranked:
                trial = {**parsed, list_key: [*kept, item]}
                if kept and len(json.dumps(trial, default=str)) > _MAX_TOOL_RESULT_CHARS:
                    break
                kept.append(item)
            if len(kept) < len(items):
                parsed[list_key] = kept
                parsed["_truncated_note"] = (
                    f"Only the {len(kept)} most recent of {len(items)} {list_key} are shown "
                    f"(sorted newest first); {len(items) - len(kept)} older ones were "
                    "omitted for size and are not otherwise available. Each item shown is "
                    "complete."
                )
                return json.dumps(parsed, default=str)

    # No single list field to trim (e.g. one large free-text blob) - fall
    # back to a flagged raw cut, still better than an unbounded result.
    return (
        text[:_MAX_TOOL_RESULT_CHARS]
        + f"\n... ({len(text)} chars total, truncated. Narrow the search with "
        "more specific parameters or a smaller count instead of reading everything.)"
    )


@dataclass
class LocalTool:
    """A tool the loop can call without going through MCP at all.

    `submit_findings` (gap_agent.py) and `check_patient_gaps` (chat_agent.py)
    are both this: the point isn't just F1-specific, it's that not every
    tool a model needs comes from a server.
    """

    schema: dict[str, Any]  # OpenAI tool-definition shape
    handler: LocalToolHandler

    @property
    def name(self) -> str:
        return self.schema["function"]["name"]


@dataclass
class LoopResult:
    """What one `SimpleToolLoop.run()` produced."""

    messages: list[dict[str, Any]]
    terminated_by: TerminationReason
    total_steps: int
    total_tokens: int


class SimpleToolLoop:
    """model decides -> call tool -> observe -> decide again.

    One instance is built per run (it owns the open MCP connection and the
    trajectory logger for that run) and used for exactly one `run()` call -
    see gap_agent.py and chat_agent.py, the two callers.
    """

    def __init__(
        self,
        mcp_client: Client,
        mcp_tool_defs: list[dict[str, Any]],
        local_tools: list[LocalTool],
        config: ModelConfig,
        *,
        max_steps: int,
        stop_tool_names: set[str],
        trajectory: TrajectoryLogger,
        run_id: str = "unknown",
    ) -> None:
        self._mcp_client = mcp_client
        self._mcp_tool_defs = mcp_tool_defs
        self._local_tools = {tool.name: tool for tool in local_tools}
        self._config = config
        self._max_steps = max_steps
        self._stop_tool_names = stop_tool_names
        self._trajectory = trajectory
        self._messages_log_path = (
            _MESSAGES_LOG_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{run_id}.json"
        )

    async def run(self, messages: list[dict[str, Any]]) -> LoopResult:
        """Run the loop starting from `messages` (already including the
        system prompt and at least one user message) until termination.

        Does not mutate the list passed in - the caller may want to reuse
        the pre-call messages elsewhere (e.g. chat history bookkeeping).
        """
        messages = list(messages)
        all_tools = self._mcp_tool_defs + [tool.schema for tool in self._local_tools.values()]
        total_tokens = 0

        for step in range(self._max_steps):
            self._trajectory.llm_call_started(step=step, message_count=len(messages))
            self._persist_messages(messages)
            start = time.monotonic()
            reply = await call_model(messages, all_tools, self._config)
            duration_ms = (time.monotonic() - start) * 1000

            total_tokens += (reply.prompt_tokens or 0) + (reply.completion_tokens or 0)
            self._trajectory.llm_call_finished(
                step=step,
                reasoning=reply.reasoning,
                content=reply.content,
                tool_call_names=[tc.name for tc in reply.tool_calls],
                prompt_tokens=reply.prompt_tokens,
                completion_tokens=reply.completion_tokens,
                duration_ms=duration_ms,
            )

            if not reply.tool_calls:
                messages.append({"role": "assistant", "content": reply.content or ""})
                self._persist_messages(messages)
                return LoopResult(messages, "no_tool_calls", step + 1, total_tokens)

            messages.append(
                {
                    "role": "assistant",
                    "content": reply.content,
                    # tc.extra is spread in verbatim, not read or interpreted:
                    # some providers (Gemini's thinking models, confirmed
                    # live) attach opaque per-call data that must round-trip
                    # unchanged on the next outbound call or they reject the
                    # request. Providers that attach nothing (Ollama/qwen3)
                    # leave this a no-op - see ToolCallRequest.extra's
                    # docstring for why this isn't provider-specific code.
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": tc.arguments_json},
                            **(tc.extra or {}),
                        }
                        for tc in reply.tool_calls
                    ],
                }
            )

            stop_requested = False
            for tool_call in reply.tool_calls:
                try:
                    arguments = json.loads(tool_call.arguments_json)
                except json.JSONDecodeError:
                    arguments = {}

                is_local = tool_call.name in self._local_tools
                source = "local" if is_local else "mcp"
                self._trajectory.tool_call_started(
                    step=step, tool_name=tool_call.name, arguments=arguments, source=source
                )
                tool_start = time.monotonic()

                if is_local:
                    result_text, is_error = await self._call_local_tool(tool_call.name, arguments)
                else:
                    result_text, is_error = await self._call_mcp_tool(tool_call.name, arguments)

                tool_duration_ms = (time.monotonic() - tool_start) * 1000
                self._trajectory.tool_call_finished(
                    step=step,
                    tool_name=tool_call.name,
                    is_error=is_error,
                    result_summary=summarize(result_text),
                    # Live viewers only (see _LIVE_ONLY_KEYS) - much more
                    # headroom than the 500-char log summary since a human
                    # reading one result in a side panel, not a whole
                    # eval file, is what this serves.
                    result_full=summarize(result_text, max_len=20_000),
                    duration_ms=tool_duration_ms,
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": _cap_tool_result(result_text),
                    }
                )

                if tool_call.name in self._stop_tool_names:
                    stop_requested = True

            self._persist_messages(messages)
            if stop_requested:
                return LoopResult(messages, "stop_tool_called", step + 1, total_tokens)

        return LoopResult(messages, "budget", self._max_steps, total_tokens)

    def _persist_messages(self, messages: list[dict[str, Any]]) -> None:
        self._messages_log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self._messages_log_path.stem.split("_", 2)[-1],
            "provider": self._config.provider,
            "model": self._config.model,
            "updated_at": datetime.now().isoformat(),
            "messages": messages,
        }
        self._messages_log_path.write_text(json.dumps(payload, indent=2, default=str))

    async def _call_local_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        handler = self._local_tools[name].handler
        result = handler(arguments)
        if hasattr(result, "__await__"):
            result = await result
        return json.dumps(result, default=str), False

    async def _call_mcp_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        result = await self._mcp_client.call_tool(name, arguments)
        if result.structured_content is not None:
            return json.dumps(result.structured_content, default=str), result.is_error
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        return text, result.is_error


__all__ = ["LocalTool", "LoopResult", "SimpleToolLoop", "TerminationReason"]
