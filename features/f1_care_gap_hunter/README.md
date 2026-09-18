# F1 — Care Gap Hunter

Across a cohort, find everyone overdue for care a guideline says they should
have had, and rank the worklist with cited evidence.

This folder holds the whole feature: the oracle, the v1 agent it grades, the
eval runner and grader, and a Next.js viewer to watch it work.

## What the oracle is, and why it comes first

The oracle is a plain Python pass over the raw Synthea bundles — no model,
no FHIR server, no MCP. It reads `data/synthea_output/<label>/fhir/*.json`
directly and computes the correct list of care gaps by code: loops,
comparisons, date arithmetic. It exists so the agent (built later, using
`substrate/fhir-mcp`'s tools) can be graded automatically against a real
answer key, instead of a human or another model eyeballing whether its
output looks right.

Deliberately independent of `substrate/fhir-mcp`: the oracle must not import
anything from the tool layer it's meant to grade, or a bug shared by both
would go uncaught by both.

## Running it

```
uv sync
uv run python -m f1_care_gap_hunter.oracle ../../data/synthea_output/seed-1000-n200/fhir
```

Prints a summary line, then the full worklist as JSON — one entry per
(patient, gap) pair, each with the FHIR evidence that justifies it.

```
uv run pytest          # tests
uv run ruff check .    # lint
```

## The checks

Four gap types, each modelled on a real HEDIS/USPSTF measure, each with
codes verified directly against this project's own loaded data before being
hardcoded.

**Diabetic, no HbA1c result in the last 6 months.** The brief's own worked
example. The tricky part isn't the HbA1c check itself, it's deciding who
counts as diabetic: Synthea under-codes diabetes on this data (it tracks
diabetes as an internal module attribute and only emits the actual
"Diabetes mellitus type 2" diagnosis during a wellness-visit encounter), so
a patient can carry years of diabetic complications with no diabetes
diagnosis on record at all. Condition-code alone finds 9 diabetics on this
data; adding complications, diabetes medications, and a diagnostic-level
HbA1c brings that to 25.

```
Patient: Elza246 Glennie916 Hickle134
Diabetic, age 49, no HbA1c result on or after 2026-03-01.
  Condition/a8479560-...-118        Diabetes mellitus type 2 (disorder)
  MedicationRequest/a8479560-...9   Metformin hydrochloride 500 MG ER
  Observation/a8479560-...77        HbA1c 7.53% on 2019-10-05
```

**Diabetic, no retinal eye exam in the last 12 months.** Simplified from
NCQA's own Eye Exam measure, which allows a negative-retinopathy exam from
the prior year to count, and restricts a retinopathy-positive patient to the
current year only — this check applies one 12-month window to everyone
instead, and says so in its own docstring rather than quietly passing off
the simplification as the full measure.

**On antihypertensive therapy, latest blood pressure still at or above
140/90.** A reframed version of the brief's original "hypertensive on no
medication" example — measured directly on this data, that original gap is
degenerate: 0 of 40 hypertensive patients lack a prescribed antihypertensive,
because Synthea's hypertension module always prescribes one. This checks
whether treatment is actually working instead, matching HEDIS's own
Controlling High Blood Pressure measure.

```
Patient: Aron520 Myles862 Kozey370
On antihypertensive therapy, latest BP 122/92 on 2026-08-19 still >= 140/90.
  Condition/ade90afa-...-bb          Essential hypertension (disorder)
  MedicationRequest/ade90afa-...48   Hydrochlorothiazide 25 MG Oral Tablet
  Observation/ade90afa-...f6         BP 122/92 mmHg on 2026-08-19
```

**Age 45-75, no colorectal cancer screening within that method's own
interval.** Recognises the two screening methods that actually appear in
this data — colonoscopy (10-year interval) and fecal occult blood testing
(annual) — checked against their own intervals rather than one interval
applied to both, so a patient screened annually by the second method isn't
wrongly flagged as overdue for the first.

## A note on evidence references

Evidence citations use the id each resource carries in the raw Synthea
bundle file (e.g. `Condition/ade90afa-dcc6-73bd-2b90-1458b0e347bb`), not the
numeric id HAPI assigns once the same bundle is loaded onto the live FHIR
server. Synthea's resources are POSTed rather than PUT with a fixed id, so
HAPI mints its own on load. Only `Patient` carries a separate identifier
(`https://github.com/synthetichealth/synthea`) that survives that step —
confirmed live, resolvable via `Patient?identifier={id}` — which is what
`PatientRecord.synthea_id` uses to identify a patient across both worlds.
These evidence references are for tracing the oracle's own reasoning, not
for an agent to dereference against the live server directly.

## The agent (v1)

A hand-rolled tool-calling loop (`harness/v1/loop.py`'s `SimpleToolLoop`),
no LangGraph, no Agents SDK, deliberately, so the loop's mechanics stay
visible rather than hidden behind a framework. One patient at a time: the
model gets fhir-mcp's 7 read-only tools plus a local `submit_findings` tool
and a system prompt (`harness/v1/prompts.py`) stating the same rules
`gaps.py` encodes, including the traps that make an agent wrong even while
searching correctly (diabetes is often implied, not diagnosed; a `null`
count means "the server declined to count", not zero; BP values live in
`component[]`, not `valueQuantity`, so they must go through `search_resources`
directly rather than `get_lab_trend`).

Model calls go through `agentward-harness` (`../../harness/`), which speaks
one wire format, OpenAI's chat-completions shape, to both providers Ollama
and Gemini expose it under, so the same agent code runs against a local
`qwen3:8b` or a hosted Gemini model with only `.env` changing. See
`.env.example`.

## Grading

`grading.py` compares only the *set* of gap types per patient, agent vs.
oracle, never evidence references, since those live in permanently
incomparable id spaces (Synthea UUIDs vs. whatever HAPI minted on load, see
`patient_map.py`). It reports per gap type, never a pooled number: three
baselines (`compute_baselines`) ship alongside every real run because an
agent making zero clinical tool calls already reaches P=0.485 by guessing
colorectal-by-age alone on this cohort, a real run landing near that isn't
doing the task. See `grading.py`'s module docstring for the full reasoning
and the exact baseline numbers.

## Running it

```
uv sync

# The oracle (unchanged):
uv run python -m f1_care_gap_hunter.oracle ../../data/synthea_output/seed-1000-n200/fhir

# The agent, graded, checkpointed (needs fhir-mcp running, and either
# `ollama serve` with qwen3:8b pulled, or GEMINI_API_KEY set):
cp .env.example .env   # then edit
uv run python -m f1_care_gap_hunter.eval_runner --limit 10

# The viewer's API:
uv run uvicorn f1_care_gap_hunter.viewer_api:app --reload --port 8000
```

Then, in `viewer/`: `npm install && npm run dev` (Next.js, Tailwind v4,
TypeScript) for a worklist view and a live chat with a step-by-step trace of
every model call and tool call, MCP or local.

## Layout

```
src/f1_care_gap_hunter/
  bundles.py       loading raw Synthea bundles; PatientRecord, age/deceased logic
  gaps.py          the four gap checks
  oracle.py        runs every check across a cohort, outputs the worklist
  harness/v1/
    loop.py        SimpleToolLoop: the tool-calling engine, provider-agnostic
    gap_agent.py   run_agent_on_patient() - the one reusable core
    chat_agent.py  run_chat_turn() - conversational, uses gap_agent as a tool
    prompts.py     the system prompts, stating the same rules gaps.py encodes
  patient_map.py   synthea_id <-> HAPI id (the id-mismatch fix)
  grading.py       agent vs. oracle, metrics, baselines
  checkpoint.py    resume for long batch runs
  eval_runner.py   CLI: run + checkpoint + grade against the oracle
  viewer_api.py    FastAPI + SSE backend for viewer/
viewer/            Next.js: worklist + chat, live trace
tests/
```
