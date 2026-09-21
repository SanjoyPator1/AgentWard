"""The F1 chat agent: same engine, raw FHIR tools, conversational framing.

One agent, one loop: it applies the four gap rules itself directly against
the 7 fhir-mcp tools, the same rules `build_system_prompt` gives the
single-patient agent (shared via `_investigation_rules` in prompts.py), with
no nested sub-agent call in between. This is a deliberate v1 simplicity
choice over the earlier design (a local `check_patient_gaps` tool that
delegated to a fresh, nested `run_agent_on_patient` call per patient) - see
the plan discussion this decision came from. `run_agent_on_patient` and
`gap_agent.py` are unchanged and still used directly by `eval_runner` for
grading; this module just no longer calls them.

The one local tool this agent does get is `code_lookup`'s
`lookup_medical_code` - for a question outside the four hardcoded rules
(e.g. "find patients with asthma"), there is no code to hardcode, and this
keeps the model from recalling one from memory instead. Not given to
gap_agent.py: the four graded gap types never need it, so it stays off the
critical path of every eval run.

Known, accepted trade-off of this simpler design: a cohort question (e.g.
"top 5 diabetics with a gap") now accumulates every candidate's FHIR data in
this one agent's own growing context, rather than each candidate getting its
own fresh, disposable context. That's a real regression for cohort
questions specifically; single-patient questions are unaffected.

This agent never reads eval_runner's checkpoint file. It is fully
self-sufficient by design: a cohort question costs live tool calls every
time, not a lookup against a precomputed worklist that might be stale or
use a different model.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from agentward_harness.mcp_tools import to_openai_tools
from agentward_harness.model import ModelConfig
from agentward_harness.trajectory import OnEvent, TrajectoryLogger
from mcp import Client

from . import code_lookup
from .loop import SimpleToolLoop
from .prompts import build_chat_system_prompt

_DEFAULT_MAX_STEPS = 24


@dataclass
class ChatTurnResult:
    """One chat turn's outcome: the reply text, and the full updated message
    history for the caller to send back on the next turn - chat state lives
    in the caller (the browser), not here."""

    messages: list[dict[str, Any]]
    reply: str
    total_steps: int
    total_tokens: int


async def run_chat_turn(
    conversation_history: list[dict[str, Any]],
    user_message: str,
    *,
    mcp_url: str,
    config: ModelConfig,
    as_of: date,
    max_steps: int = _DEFAULT_MAX_STEPS,
    on_event: OnEvent | None = None,
) -> ChatTurnResult:
    """Run one chat turn: append `user_message` to the history, let the
    agent use tools freely, return once it produces a final text reply.

    Args:
        conversation_history: Prior turns' messages, or an empty list to
            start a fresh conversation (the system prompt is added
            automatically in that case).
        user_message: The new question.
        mcp_url: The running fhir-mcp server.
        config: Which model/provider to call.
        as_of: The "today" this cohort's data is measured against - stated
            in the prompt and used to compute every gap's cutoff date.
        max_steps: Step budget for this turn. Higher than the gap agent's
            18, since a cohort question can chain find_cohort plus a full
            investigation of each candidate, all in this one agent's loop.
        on_event: Optional live callback - the viewer's SSE path.
    """
    run_id = str(uuid.uuid4())
    start = time.monotonic()

    with TrajectoryLogger(run_id, on_event=on_event) as trajectory:
        trajectory.run_started(
            task_id="chat", provider=config.provider, model=config.model, config={}
        )

        async with Client(mcp_url) as mcp_client:
            # Level 3 (run_fhir_code) is excluded here on purpose: using it well
            # depends on prompt guidance (when to reach for it, narrating its
            # output) that this prompt doesn't give the model. fhir-mcp exposing
            # it is not the same as this harness being ready to use it.
            mcp_tools = [
                t for t in (await mcp_client.list_tools()).tools if t.name != "run_fhir_code"
            ]
            mcp_tool_defs = to_openai_tools(mcp_tools)
            server_instructions = mcp_client.instructions

            loop = SimpleToolLoop(
                mcp_client=mcp_client,
                mcp_tool_defs=mcp_tool_defs,
                local_tools=[code_lookup.tool()],
                config=config,
                max_steps=max_steps,
                stop_tool_names=set(),  # a chat turn ends on "no more tool calls"
                trajectory=trajectory,
                run_id=run_id,
            )

            if conversation_history:
                messages = list(conversation_history)
            else:
                system_prompt = build_chat_system_prompt(
                    as_of, mcp_instructions=server_instructions
                )
                messages = [{"role": "system", "content": system_prompt}]
            messages.append({"role": "user", "content": user_message})

            result = await loop.run(messages)

        duration_ms = (time.monotonic() - start) * 1000
        reply = next(
            (m["content"] for m in reversed(result.messages) if m["role"] == "assistant"), ""
        )
        trajectory.run_finished(
            findings=[],
            terminated_by="submit" if result.terminated_by == "no_tool_calls" else "budget",
            total_steps=result.total_steps,
            total_tokens=result.total_tokens,
            duration_ms=duration_ms,
        )

    return ChatTurnResult(
        messages=result.messages,
        reply=reply or "",
        total_steps=result.total_steps,
        total_tokens=result.total_tokens,
    )


__all__ = ["ChatTurnResult", "run_chat_turn"]
