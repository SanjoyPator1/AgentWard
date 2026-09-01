# F1 — Care Gap Hunter

Across a cohort, find everyone overdue for care a guideline says they should
have had, and rank the worklist with cited evidence.

This folder holds the whole feature: the oracle (built), the eval set, and
the agent it grades (both not built yet).

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

## Layout

```
src/f1_care_gap_hunter/
  bundles.py   loading raw Synthea bundles; PatientRecord, age/deceased logic
  gaps.py      the four gap checks
  oracle.py    runs every check across a cohort, outputs the worklist
tests/
```
