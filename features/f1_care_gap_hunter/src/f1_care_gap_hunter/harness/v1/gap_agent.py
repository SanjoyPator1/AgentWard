"""run_agent_on_patient(): the one reusable core.

Called by eval_runner (batch, checkpointed, graded against the oracle),
viewer_api (live, one patient, streamed to the browser), and chat_agent (as
a nested tool call, one patient at a time). None of the three read each
other's data - each just calls this function fresh, per the project's own
design decision to keep the eval pipeline and the live viewer fully
decoupled.
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

from ...grading import GAP_TYPES, AgentFinding, AgentRun
from .loop import LocalTool, SimpleToolLoop
from .prompts import build_system_prompt

SUBMIT_FINDINGS_TOOL_NAME = "submit_findings"

# Step budget: a correct pass needs roughly 9 calls (Patient, problem list,
# HbA1c trend, eye-exam procedure search, colonoscopy search, FOBT search,
# BP panel search, medication list, submit). 18 leaves real margin for one
# fumbled parameter or an extra clarifying search, without being unbounded.
_DEFAULT_MAX_STEPS = 18


def _submit_findings_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_FINDINGS_TOOL_NAME,
            "description": (
                "Submit your final answer for this patient: every care gap you have "
                "positively confirmed. Call this exactly once, after investigating all "
                "four gap types. An empty list is a valid, correct answer for a patient "
                "with no gaps - most patients have none."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gap_type": {
                                    "type": "string",
                                    "enum": sorted(GAP_TYPES),
                                    "description": "Must be exactly one of these four values.",
                                },
                                "rationale": {
                                    "type": "string",
                                    "description": (
                                        "One sentence explaining why this is a gap, citing "
                                        "the specific facts (dates, values) you found."
                                    ),
                                },
                                "evidence": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "reference": {
                                                "type": "string",
                                                "description": (
                                                    "A FHIR reference exactly as a tool "
                                                    "returned it, e.g. 'Condition/8871'."
                                                ),
                                            },
                                            "description": {"type": "string"},
                                        },
                                        "required": ["reference", "description"],
                                    },
                                },
                            },
                            "required": ["gap_type", "rationale"],
                        },
                    }
                },
                "required": ["findings"],
            },
        },
    }


@dataclass
class AgentPatientRunResult:
    """Everything one run produced: the grading-ready AgentRun, plus the raw
    step/token counts anyone (a viewer, a cost report) might want."""

    agent_run: AgentRun
    hapi_patient_id: str
    total_steps: int
    total_tokens: int


async def run_agent_on_patient(
    hapi_patient_id: str,
    patient_synthea_id: str,
    *,
    mcp_url: str,
    config: ModelConfig,
    as_of: date,
    max_steps: int = _DEFAULT_MAX_STEPS,
    on_event: OnEvent | None = None,
    trajectory_jsonl_path: str | None = None,
) -> AgentPatientRunResult:
    """Run the F1 v1 agent against one patient on the live FHIR server.

    Args:
        hapi_patient_id: The bare id HAPI assigned this patient - what the
            agent is actually told to query with.
        patient_synthea_id: The oracle-side id, carried through purely so the
            resulting AgentRun can be graded against `run_oracle()`'s output.
            The agent itself is never told this value (see patient_map.py).
        mcp_url: The running fhir-mcp server, e.g. http://127.0.0.1:3001/mcp.
        config: Which model/provider to call.
        as_of: Must match whatever `run_oracle()` was called with, or the
            agent is silently answering a different question than the one
            it's graded against.
        max_steps: Step budget passed to SimpleToolLoop.
        on_event: Optional live callback - the viewer's SSE path.
        trajectory_jsonl_path: Optional file to append trajectory events to -
            the eval path. The two are not mutually exclusive.
    """
    run_id = str(uuid.uuid4())
    findings: list[AgentFinding] = []

    def handle_submit(arguments: dict[str, Any]) -> dict[str, Any]:
        for raw in arguments.get("findings", []):
            findings.append(
                AgentFinding(
                    gap_type=raw["gap_type"],
                    rationale=raw.get("rationale", ""),
                    evidence=raw.get("evidence", []),
                )
            )
        return {"received": len(findings)}

    submit_tool = LocalTool(schema=_submit_findings_schema(), handler=handle_submit)
    start = time.monotonic()

    with TrajectoryLogger(
        run_id, jsonl_path=trajectory_jsonl_path, on_event=on_event
    ) as trajectory:
        trajectory.run_started(
            task_id=patient_synthea_id,
            provider=config.provider,
            model=config.model,
            config={
                "max_steps": max_steps,
                "as_of": as_of.isoformat(),
                "hapi_patient_id": hapi_patient_id,
            },
        )

        async with Client(mcp_url) as mcp_client:
            mcp_tool_defs = to_openai_tools((await mcp_client.list_tools()).tools)
            server_instructions = mcp_client.instructions

            loop = SimpleToolLoop(
                mcp_client=mcp_client,
                mcp_tool_defs=mcp_tool_defs,
                local_tools=[submit_tool],
                config=config,
                max_steps=max_steps,
                stop_tool_names={SUBMIT_FINDINGS_TOOL_NAME},
                trajectory=trajectory,
                run_id=run_id,
            )

            system_prompt = build_system_prompt(as_of, mcp_instructions=server_instructions)
            task_prompt = (
                f"Investigate patient {hapi_patient_id} (use this bare id as the "
                "patient_id argument to every tool). Find every care gap that applies, "
                "or confirm that none do."
            )
            result = await loop.run(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt},
                ]
            )

        if result.terminated_by == "stop_tool_called":
            terminated_by = "submit"
        elif result.terminated_by == "budget":
            terminated_by = "budget"
        else:
            # The model stopped asking for tools without ever calling
            # submit_findings - treated as a malformed run, not "no gaps".
            terminated_by = "malformed"

        agent_run = AgentRun(
            patient_synthea_id=patient_synthea_id, findings=findings, terminated_by=terminated_by
        )

        trajectory.run_finished(
            findings=[finding.__dict__ for finding in findings],
            terminated_by=terminated_by,
            total_steps=result.total_steps,
            total_tokens=result.total_tokens,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    return AgentPatientRunResult(
        agent_run=agent_run,
        hapi_patient_id=hapi_patient_id,
        total_steps=result.total_steps,
        total_tokens=result.total_tokens,
    )


__all__ = ["AgentPatientRunResult", "run_agent_on_patient"]
