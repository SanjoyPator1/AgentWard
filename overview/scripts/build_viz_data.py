"""Build committed JSON snapshots for the overview deck's D3 visualizations.

Reads directly from the raw Synthea bundles under data/synthea_output/ — the
same source the F1 oracle reads — so every number that ends up on a slide
traces to data, never to a hand-typed array of fake positions. Re-run this
whenever the underlying cohort changes; it is not run at build time.

    uv run --project ../features/f1_care_gap_hunter python build_viz_data.py

(from overview/scripts/, or use absolute paths — see REPO_ROOT below).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FHIR_DIR = REPO_ROOT / "data" / "synthea_output" / "seed-1000-n200" / "fhir"
OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "data"

sys.path.insert(0, str(REPO_ROOT / "features" / "f1_care_gap_hunter" / "src"))

from f1_care_gap_hunter.bundles import (  # noqa: E402
    PatientRecord,
    load_all_patients,
    load_patient_record,
)
from f1_care_gap_hunter.oracle import run_oracle  # noqa: E402

# Pinned so the deck's numbers don't drift day to day just because someone
# opened it on a different date. Bump deliberately, not as a side effect.
AS_OF = date(2026, 9, 10)

# Two real patients already named in self-docs and in the deck's own slides —
# reused here rather than picking new ones, so every doc and every slide is
# talking about the same people.
BUNDLE_PROFILE_PATIENT_FILE = (
    "Julius90_Jacobi462_e626d29e-238f-e3c2-3248-4bff871704bd.json"
)
CONDITIONS_PATIENT_FILE = "Adrienne302_Halvorson124_d82e9b33-5c3a-bf38-8c14-b74d13c6e016.json"
HBA1C_PATIENT_SYNTHEA_ID = "a8479560-2317-ddfa-b03b-4efadeb3586b"  # Elza246 Glennie916 Hickle134
HBA1C_LOINC = "4548-4"

_TAG_RE = re.compile(r"\(([a-z][a-z ]*)\)\s*$", re.IGNORECASE)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {path.relative_to(REPO_ROOT)}  ({path.stat().st_size:,} bytes)")


def condition_text(resource: dict[str, Any]) -> str:
    code = resource.get("code") or {}
    if code.get("text"):
        return code["text"]
    coding = (code.get("coding") or [{}])[0]
    return coding.get("display", "(untitled condition)")


def _coded_text(concept: dict[str, Any] | None) -> str | None:
    if not concept:
        return None
    if concept.get("text"):
        return concept["text"]
    coding = (concept.get("coding") or [{}])[0]
    return coding.get("display")


def resource_label(resource_type: str, r: dict[str, Any]) -> str:
    """A short human-readable label for one resource, for hover tooltips.
    Each resource type keeps what it actually has — FHIR doesn't give every
    type a `.code`, so this can't be one field lookup."""
    if resource_type == "Encounter":
        return (
            _coded_text((r.get("type") or [None])[0])
            or _coded_text(r.get("class"))
            or r.get("class", {}).get("code")
            or "Encounter"
        )
    if resource_type == "MedicationRequest":
        return (
            _coded_text(r.get("medicationCodeableConcept"))
            or "Medication request"
        )
    if resource_type in ("Claim", "ExplanationOfBenefit"):
        return _coded_text(r.get("type")) or f"{resource_type} {r.get('id', '')[:8]}"
    if resource_type == "CarePlan":
        return r.get("title") or _coded_text((r.get("category") or [None])[0]) or "Care plan"
    if resource_type == "CareTeam":
        return r.get("name") or "Care team"
    if resource_type == "DocumentReference":
        return _coded_text(r.get("type")) or "Document"
    if resource_type == "ImagingStudy":
        return _coded_text((r.get("procedureCode") or [None])[0]) or "Imaging study"
    if resource_type == "Device":
        return _coded_text(r.get("type")) or "Device"
    if resource_type == "Provenance":
        return "Provenance record"
    if resource_type == "Patient":
        return "Patient"
    if resource_type == "Immunization":
        return _coded_text(r.get("vaccineCode")) or "Immunization"
    # Condition, Observation, Procedure, Immunization, DiagnosticReport all
    # carry a real `.code`.
    return _coded_text(r.get("code")) or resource_type


def semantic_tag(text: str) -> str | None:
    """The SNOMED fully-specified-name tag at the end of a display string,
    e.g. "Essential hypertension (disorder)" -> "disorder". A naming
    convention, not a queryable field — see self-docs/05."""
    m = _TAG_RE.search(text)
    return m.group(1).lower() if m else None


# ---------------------------------------------------------------------------
# cohort.json + gap-findings.json  (Phase 1 — wired into the F1 slide)
# ---------------------------------------------------------------------------


def build_cohort_and_findings(patients: list[PatientRecord]) -> tuple[dict, list[dict]]:
    findings = run_oracle(FHIR_DIR, as_of=AS_OF)

    findings_by_patient: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        findings_by_patient[f.patient_synthea_id].append(asdict(f))

    rows = []
    for p in sorted(patients, key=lambda p: p.synthea_id):
        rows.append(
            {
                "id": p.synthea_id,
                "name": p.name,
                "age": p.age(AS_OF),
                "sex": p.patient.get("gender") or "unknown",
                "deceased": p.is_deceased,
                "gaps": findings_by_patient.get(p.synthea_id, []),
            }
        )

    gap_type_counts = Counter(f.gap_type for f in findings)
    gaps_per_patient = Counter(len(v) for v in findings_by_patient.values())

    summary = {
        "asOf": AS_OF.isoformat(),
        "totalPatients": len(patients),
        "alivePatients": sum(1 for p in patients if not p.is_deceased),
        "deceasedPatients": sum(1 for p in patients if p.is_deceased),
        "totalFindings": len(findings),
        "flaggedPatients": len(findings_by_patient),
        "gapTypeCounts": dict(sorted(gap_type_counts.items(), key=lambda kv: -kv[1])),
        "patientsByGapCount": {str(k): v for k, v in sorted(gaps_per_patient.items())},
    }

    cohort = {"summary": summary, "patients": rows}
    return cohort, [asdict(f) for f in findings]


# ---------------------------------------------------------------------------
# bundle-profile.json  (Phase 2 — slide 5, step 1)
# ---------------------------------------------------------------------------


def resource_date(r: dict[str, Any]) -> str | None:
    return (
        next(
            (
                r[k]
                for k in ("effectiveDateTime", "authoredOn", "recordedDate", "onsetDateTime")
                if isinstance(r.get(k), str)
            ),
            None,
        )
        or (r.get("period") or {}).get("start")
    )


def condition_breakdown(record: PatientRecord) -> dict:
    """Active-status + "(disorder)"-tag filtering for one patient's own
    Condition list — the same 73 -> 21 -> 11 style narrowing self-docs/05
    documents, generalised to any patient so a slide can stay honest about
    which single person its numbers describe."""
    all_conditions = record.resources("Condition")
    active = [
        c
        for c in all_conditions
        if (c.get("clinicalStatus", {}).get("coding") or [{}])[0].get("code") == "active"
    ]
    rows = []
    for c in active:
        text = condition_text(c)
        tag = semantic_tag(text)
        rows.append(
            {
                "id": c.get("id"),
                "text": text,
                "tag": tag,
                "isRealProblem": tag == "disorder",
                "onsetDate": c.get("onsetDateTime"),
            }
        )
    return {
        "totalAllConditions": len(all_conditions),
        "totalActive": len(active),
        "totalRealProblems": sum(1 for r in rows if r["isRealProblem"]),
        "conditions": rows,
    }


def build_bundle_profile() -> dict:
    path = FHIR_DIR / BUNDLE_PROFILE_PATIENT_FILE
    record = load_patient_record(path)

    counts = Counter()
    for resource_type, resources in record.resources_by_type.items():
        counts[resource_type] = len(resources)

    # Every resource in this one bundle, not just a sample — Slide 5 hovers
    # any of the 462 dots and shows that dot's own real record, not a
    # stand-in shared across every dot of its type.
    resources: list[dict[str, Any]] = []
    for resource_type, items in record.resources_by_type.items():
        for r in items:
            resources.append(
                {
                    "resourceType": resource_type,
                    "id": r.get("id"),
                    "label": resource_label(resource_type, r),
                    "date": resource_date(r),
                }
            )

    return {
        "patientFile": BUNDLE_PROFILE_PATIENT_FILE,
        "patientName": record.name,
        "totalResources": sum(counts.values()),
        "resourceCounts": dict(counts.most_common()),
        "resources": resources,
        "conditionBreakdown": condition_breakdown(record),
    }


# ---------------------------------------------------------------------------
# conditions.json  (Phase 2 — slide 5, steps 2-3)
# ---------------------------------------------------------------------------


def build_conditions(patients: list[PatientRecord]) -> dict:
    cohort_tags: Counter[str] = Counter()
    cohort_total = 0
    for p in patients:
        for c in p.resources("Condition"):
            cohort_total += 1
            tag = semantic_tag(condition_text(c))
            cohort_tags[tag or "untagged"] += 1

    example = load_patient_record(FHIR_DIR / CONDITIONS_PATIENT_FILE)
    breakdown = condition_breakdown(example)

    return {
        "cohortTotal": cohort_total,
        "cohortTagCounts": dict(cohort_tags.most_common()),
        # A second, richer real example (not used by the current slides) —
        # kept because self-docs/05 already documents this exact patient's
        # 73 -> 21 -> 11 breakdown independently; free to wire up later.
        "example": {
            "patientFile": CONDITIONS_PATIENT_FILE,
            "patientName": example.name,
            **breakdown,
        },
    }


# ---------------------------------------------------------------------------
# hba1c-timeline.json  (Phase 2 — new "Absence Is The Evidence" slide)
# ---------------------------------------------------------------------------


def build_hba1c_timeline() -> dict:
    matches = [
        p
        for p in FHIR_DIR.glob("*.json")
        if not p.name.startswith(("hospitalInformation", "practitionerInformation"))
    ]
    record: PatientRecord | None = None
    for path in matches:
        if HBA1C_PATIENT_SYNTHEA_ID in path.name:
            record = load_patient_record(path)
            break
    if record is None:
        raise RuntimeError(f"Could not find bundle file for {HBA1C_PATIENT_SYNTHEA_ID}")

    observations = []
    for o in record.resources("Observation"):
        coding = (o.get("code") or {}).get("coding") or []
        if any(c.get("system") == "http://loinc.org" and c.get("code") == HBA1C_LOINC for c in coding):
            value = (o.get("valueQuantity") or {}).get("value")
            unit = (o.get("valueQuantity") or {}).get("unit")
            eff = o.get("effectiveDateTime")
            observations.append({"id": o.get("id"), "date": eff, "value": value, "unit": unit})

    observations.sort(key=lambda r: r["date"] or "")

    # Mirrors gaps.py's own 6-month HbA1c window, computed the same way the
    # oracle computes it: as_of minus 6 calendar months.
    window_end = AS_OF
    window_start_month = window_end.month - 6
    window_start_year = window_end.year
    if window_start_month <= 0:
        window_start_month += 12
        window_start_year -= 1
    window_start = date(window_start_year, window_start_month, window_end.day)

    return {
        "patientSyntheaId": HBA1C_PATIENT_SYNTHEA_ID,
        "patientName": record.name,
        "asOf": AS_OF.isoformat(),
        "windowStart": window_start.isoformat(),
        "windowEnd": window_end.isoformat(),
        "observations": observations,
        "totalEver": len(observations),
        "totalInWindow": sum(
            1 for o in observations if o["date"] and window_start.isoformat() <= o["date"][:10] <= window_end.isoformat()
        ),
    }


def main() -> None:
    if not FHIR_DIR.is_dir():
        raise SystemExit(f"No such directory: {FHIR_DIR}")

    patients = load_all_patients(FHIR_DIR)
    print(f"loaded {len(patients)} patient bundles from {FHIR_DIR.relative_to(REPO_ROOT)}")

    cohort, findings = build_cohort_and_findings(patients)
    write_json(OUT_DIR / "cohort.json", cohort)
    write_json(OUT_DIR / "gap-findings.json", findings)
    write_json(OUT_DIR / "bundle-profile.json", build_bundle_profile())
    write_json(OUT_DIR / "conditions.json", build_conditions(patients))
    write_json(OUT_DIR / "hba1c-timeline.json", build_hba1c_timeline())


if __name__ == "__main__":
    main()
