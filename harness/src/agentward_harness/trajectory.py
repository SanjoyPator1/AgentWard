"""The trajectory event schema: one stream, three consumers.

Every step of an agent run emits one of these events. `eval_runner` appends
them to a JSONL file per run, `viewer_api` forwards them down an SSE stream,
and a CLI debug run can just print them, all three read the exact same
objects, so "what happened during this run" is never reconstructed
differently by each consumer. This is also the project's trajectory-logging
non-negotiable, satisfied once here rather than per feature.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TextIO

EventType = Literal[
    "run_started",
    "llm_call_started",
    "llm_call_finished",
    "tool_call_started",
    "tool_call_finished",
    "run_finished",
]

ToolSource = Literal["mcp", "local"]
TerminationReason = Literal["submit", "budget", "malformed"]

# Event data keys that reach a live on_event callback (the viewer's SSE
# path) but are stripped before a run is written to its jsonl file - kept
# out of the persisted eval log for the same size reason summarize() exists,
# without capping what a live viewer can show a human in the moment.
_LIVE_ONLY_KEYS = {"result_full"}


@dataclass
class TrajectoryEvent:
    """One thing that happened during an agent run.

    `data` holds the event-specific payload (see the `TrajectoryLogger.*`
    methods for what each event type carries) rather than a dataclass per
    event type, so a new event type never requires touching every consumer's
    dispatch code, a consumer that doesn't recognise a field just ignores it.
    """

    event_type: EventType
    run_id: str
    step: int | None
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


OnEvent = Callable[[TrajectoryEvent], None]


class TrajectoryLogger:
    """Emits TrajectoryEvents to an optional JSONL file and an optional callback.

    Both sinks are optional so the same agent code runs unchanged whether
    it's inside a checkpointed batch eval (file, no callback), a live viewer
    request (callback pushes down SSE, no file), or a CLI debug run (callback
    prints, no file). This is what makes `run_agent_on_patient` reusable
    across `eval_runner`, `viewer_api`, and `chat_agent` without any of them
    reading each other's output.
    """

    def __init__(
        self,
        run_id: str,
        *,
        jsonl_path: str | None = None,
        on_event: OnEvent | None = None,
    ) -> None:
        self.run_id = run_id
        self._on_event = on_event
        self._file: TextIO | None = open(jsonl_path, "a") if jsonl_path else None

    def _emit(self, event_type: EventType, step: int | None, **data: Any) -> None:
        timestamp = time.time()
        if self._file is not None:
            # live-only fields (see _LIVE_ONLY_KEYS) never reach the persisted
            # file - jsonl_path and on_event can both be set on the same run
            # (see run_agent_on_patient's docstring), so this has to filter
            # per sink rather than assume only one is active.
            persisted_data = {k: v for k, v in data.items() if k not in _LIVE_ONLY_KEYS}
            persisted_event = TrajectoryEvent(
                event_type=event_type,
                run_id=self.run_id,
                step=step,
                timestamp=timestamp,
                data=persisted_data,
            )
            self._file.write(persisted_event.to_json() + "\n")
            self._file.flush()
        if self._on_event is not None:
            live_event = TrajectoryEvent(
                event_type=event_type,
                run_id=self.run_id,
                step=step,
                timestamp=timestamp,
                data=data,
            )
            self._on_event(live_event)

    def run_started(
        self, *, task_id: str, provider: str, model: str, config: dict[str, Any]
    ) -> None:
        self._emit(
            "run_started", None, task_id=task_id, provider=provider, model=model, config=config
        )

    def llm_call_started(self, *, step: int, message_count: int) -> None:
        self._emit("llm_call_started", step, message_count=message_count)

    def llm_call_finished(
        self,
        *,
        step: int,
        reasoning: str | None,
        content: str | None,
        tool_call_names: list[str],
        prompt_tokens: int | None,
        completion_tokens: int | None,
        duration_ms: float,
    ) -> None:
        self._emit(
            "llm_call_finished",
            step,
            reasoning=reasoning,
            content=content,
            tool_call_names=tool_call_names,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
        )

    def tool_call_started(
        self, *, step: int, tool_name: str, arguments: dict[str, Any], source: ToolSource
    ) -> None:
        self._emit(
            "tool_call_started", step, tool_name=tool_name, arguments=arguments, source=source
        )

    def tool_call_finished(
        self,
        *,
        step: int,
        tool_name: str,
        is_error: bool,
        result_summary: str,
        result_full: str,
        duration_ms: float,
    ) -> None:
        self._emit(
            "tool_call_finished",
            step,
            tool_name=tool_name,
            is_error=is_error,
            result_summary=result_summary,
            result_full=result_full,
            duration_ms=duration_ms,
        )

    def run_finished(
        self,
        *,
        findings: list[dict[str, Any]],
        terminated_by: TerminationReason,
        total_steps: int,
        total_tokens: int,
        duration_ms: float,
    ) -> None:
        self._emit(
            "run_finished",
            None,
            findings=findings,
            terminated_by=terminated_by,
            total_steps=total_steps,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        )

    def close(self) -> None:
        if self._file is not None:
            self._file.close()

    def __enter__(self) -> TrajectoryLogger:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def summarize(value: Any, max_len: int = 500) -> str:
    """Truncate a tool result for the trajectory log.

    The full result already reached the model in the conversation; the log
    only needs enough to reconstruct what happened without ballooning the
    JSONL file with megabyte-scale FHIR payloads (some bundles run ~3MB per
    patient, see self-docs/03-agent-ward.md's cohort notes).
    """
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... ({len(text)} chars total)"


__all__ = [
    "EventType",
    "OnEvent",
    "TerminationReason",
    "ToolSource",
    "TrajectoryEvent",
    "TrajectoryLogger",
    "summarize",
]
