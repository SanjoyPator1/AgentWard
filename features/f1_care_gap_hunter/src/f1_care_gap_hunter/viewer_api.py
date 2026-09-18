"""FastAPI + SSE backend for the F1 viewer: worklist and chat.

Both live surfaces are built on the exact same run_agent_on_patient /
run_chat_turn core as eval_runner - see harness/v1's module docstrings for
why that's one function, not three. Trajectory events ARE the SSE payloads;
there is no second schema translating one into the other.

Run it directly:

    uv run uvicorn f1_care_gap_hunter.viewer_api:app --reload --port 8000

Deliberately does not read eval_runner's checkpoint file anywhere in this
module - every run here is live, on demand, self-sufficient (see the
self-docs conversation this design comes from).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

from agentward_harness.model import ModelConfig
from agentward_harness.trajectory import TrajectoryEvent
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .bundles import PatientRecord, load_all_patients
from .harness import CHAT_AGENTS, DEFAULT_CHAT_VERSION, get_chat_agent
from .harness.v1.gap_agent import run_agent_on_patient
from .patient_map import build_patient_map, load_cached_map, save_cached_map

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("f1_care_gap_hunter.viewer_api")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FEATURE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FHIR_DIR = _REPO_ROOT / "data" / "synthea_output" / "seed-1000-n200" / "fhir"
_RUNS_DIR = _FEATURE_ROOT / "runs"
_MAP_PATH = _RUNS_DIR / "patient_map.json"

# Must run before the os.environ.get() calls just below - a .env file does
# nothing until something loads it into the process environment.
load_dotenv(_FEATURE_ROOT / ".env")

_MCP_URL = os.environ.get("FHIR_MCP_URL", "http://127.0.0.1:3001/mcp")
_AS_OF = date.fromisoformat(os.environ.get("AGENT_AS_OF", "2026-09-10"))

app = FastAPI(title="AgentWard F1 Viewer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_patients: list[PatientRecord] = []
_hapi_id_by_synthea: dict[str, str] = {}


@app.on_event("startup")
async def _load_patients() -> None:
    global _patients
    _patients = load_all_patients(_DEFAULT_FHIR_DIR)
    # Built eagerly, not lazily, and for every patient, not just whichever
    # ones a request happens to touch first: a patient with no hapi_id yet
    # is not a state any endpoint should ever hand to the frontend, since a
    # synthea_id sent to the agent by mistake means nothing to HAPI and fails
    # in a way that gives no hint where the real mistake was made.
    await _ensure_patient_map()


def _resolve_config(provider: str | None) -> ModelConfig:
    if provider:
        os.environ["MODEL_PROVIDER"] = provider
    return ModelConfig.from_env()


def _describe_exception(exc: BaseException) -> str:
    """The MCP SDK's transport uses anyio task groups internally, and an
    ExceptionGroup's own message ("unhandled errors in a TaskGroup (1
    sub-exception)") names none of its actual contents. This recurses into
    one to describe the real leaf exceptions instead, which is what actually
    failed and is what a viewer of the error needs to see.
    """
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(_describe_exception(sub) for sub in exc.exceptions)
    return f"{type(exc).__name__}: {exc}"


async def _ensure_patient_map() -> None:
    """Build (or extend) the synthea_id<->hapi_id map for whichever patients
    aren't in it yet. Cheap after the first call; the whole point of caching
    this to disk is to not re-do 217 identifier searches per server restart.
    """
    global _hapi_id_by_synthea
    _hapi_id_by_synthea = load_cached_map(_MAP_PATH) or {}
    missing = [p.synthea_id for p in _patients if p.synthea_id not in _hapi_id_by_synthea]
    if not missing:
        return
    built = await build_patient_map(missing, _MCP_URL)
    _hapi_id_by_synthea.update(built)
    save_cached_map(_MAP_PATH, _hapi_id_by_synthea)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/harness-versions")
def list_harness_versions() -> dict[str, Any]:
    return {"versions": sorted(CHAT_AGENTS), "default": DEFAULT_CHAT_VERSION}


@app.get("/patients")
def list_patients(query: str = "") -> list[dict[str, Any]]:
    """A searchable patient list for the optional chat/worklist selector,
    sourced straight from the raw bundles - browsing names is a convenience,
    not an investigation, so it doesn't need a live server round trip."""
    query_lower = query.lower()
    results = [
        {
            "synthea_id": p.synthea_id,
            "hapi_id": _hapi_id_by_synthea.get(p.synthea_id),
            "name": p.name,
            "age": p.age(as_of=_AS_OF),
            "deceased": p.is_deceased,
        }
        for p in _patients
        if not query or query_lower in p.name.lower()
    ]
    return results[:50]


class InvestigateRequest(BaseModel):
    synthea_id: str
    provider: str | None = None


@app.post("/investigate")
async def investigate(req: InvestigateRequest) -> EventSourceResponse:
    """SSE stream of one patient's live investigation: every LLM call and
    every tool call, as they happen, ending in a run_finished event."""
    config = _resolve_config(req.provider)
    await _ensure_patient_map()
    hapi_id = _hapi_id_by_synthea.get(req.synthea_id)

    if hapi_id is None:

        async def _error() -> Any:
            yield {"event": "error", "data": json.dumps({"message": "Unknown patient"})}

        return EventSourceResponse(_error())

    return EventSourceResponse(_stream_investigate(hapi_id, req.synthea_id, config))


async def _stream_investigate(hapi_id: str, synthea_id: str, config: ModelConfig) -> Any:
    events: asyncio.Queue[TrajectoryEvent | None] = asyncio.Queue()
    error_holder: dict[str, str] = {}

    def on_event(event: TrajectoryEvent) -> None:
        events.put_nowait(event)

    async def runner() -> None:
        try:
            await run_agent_on_patient(
                hapi_patient_id=hapi_id,
                patient_synthea_id=synthea_id,
                mcp_url=_MCP_URL,
                config=config,
                as_of=_AS_OF,
                on_event=on_event,
            )
        except Exception as exc:  # noqa: BLE001 - must reach the client, not vanish
            logger.exception("investigation failed for patient %s", hapi_id)
            error_holder["message"] = _describe_exception(exc)
        finally:
            await events.put(None)

    task = asyncio.ensure_future(runner())
    while (event := await events.get()) is not None:
        yield {"event": event.event_type, "data": event.to_json()}
    await task

    # A failure here (MCP unreachable, model API error, ...) is caught inside
    # runner() and surfaced as its own event, rather than left to propagate
    # out of the generator with no signal reaching the client at all.
    if "message" in error_holder:
        yield {"event": "error", "data": json.dumps({"message": error_holder["message"]})}


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = []
    message: str
    provider: str | None = None
    harness_version: str | None = None


@app.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    """SSE stream of one chat turn: live steps, then a final `chat_reply`
    event carrying the reply text and the updated message history for the
    client to send back on the next turn - chat state lives in the browser,
    not here."""
    config = _resolve_config(req.provider)
    run_chat_turn = get_chat_agent(req.harness_version)
    return EventSourceResponse(_stream_chat(req.messages, req.message, config, run_chat_turn))


async def _stream_chat(
    messages: list[dict[str, Any]],
    message: str,
    config: ModelConfig,
    run_chat_turn: Callable[..., Awaitable[Any]],
) -> Any:
    events: asyncio.Queue[TrajectoryEvent | None] = asyncio.Queue()
    result_holder: dict[str, Any] = {}
    error_holder: dict[str, str] = {}

    def on_event(event: TrajectoryEvent) -> None:
        events.put_nowait(event)

    async def runner() -> None:
        try:
            result_holder["result"] = await run_chat_turn(
                messages, message, mcp_url=_MCP_URL, config=config, as_of=_AS_OF, on_event=on_event
            )
        except Exception as exc:  # noqa: BLE001 - must reach the client, not vanish
            logger.exception("chat turn failed")
            error_holder["message"] = _describe_exception(exc)
        finally:
            await events.put(None)

    task = asyncio.ensure_future(runner())
    while (event := await events.get()) is not None:
        yield {"event": event.event_type, "data": event.to_json()}
    await task

    # A failure inside run_chat_turn is caught in runner() and surfaced here
    # as its own event, so the client always gets either a reply or an
    # explicit error - never a stream that just stops with no explanation.
    if "message" in error_holder:
        yield {"event": "error", "data": json.dumps({"message": error_holder["message"]})}
        return

    result = result_holder["result"]
    yield {
        "event": "chat_reply",
        "data": json.dumps({"reply": result.reply, "messages": result.messages}),
    }


class CohortRunRequest(BaseModel):
    limit: int = 20
    provider: str | None = None


@app.post("/runs")
async def start_cohort_run(req: CohortRunRequest) -> EventSourceResponse:
    """SSE stream of a small, live, uncheckpointed cohort run for the
    worklist view - deliberately not the eval pipeline's machinery. That
    checkpointing exists for large graded batch runs (see checkpoint.py);
    this is an exploratory run a viewer triggers on demand."""
    config = _resolve_config(req.provider)
    await _ensure_patient_map()
    patients = _patients[: req.limit]
    return EventSourceResponse(_stream_cohort_run(patients, config))


async def _stream_cohort_run(patients: list[PatientRecord], config: ModelConfig) -> Any:
    for patient in patients:
        hapi_id = _hapi_id_by_synthea.get(patient.synthea_id)
        if hapi_id is None:
            continue
        try:
            result = await run_agent_on_patient(
                hapi_patient_id=hapi_id,
                patient_synthea_id=patient.synthea_id,
                mcp_url=_MCP_URL,
                config=config,
                as_of=_AS_OF,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced, not a silent stall
            logger.exception("cohort run failed for patient %s", patient.synthea_id)
            yield {"event": "error", "data": json.dumps({"message": _describe_exception(exc)})}
            return
        yield {
            "event": "patient_done",
            "data": json.dumps(
                {
                    "patient_synthea_id": patient.synthea_id,
                    "patient_name": patient.name,
                    "findings": [f.__dict__ for f in result.agent_run.findings],
                    "terminated_by": result.agent_run.terminated_by,
                }
            ),
        }
    yield {"event": "run_complete", "data": "{}"}


__all__ = ["app"]
