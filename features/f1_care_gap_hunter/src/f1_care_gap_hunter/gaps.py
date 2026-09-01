"""Gap checks: each takes one patient's record and decides whether they have
a specific, named care gap.

Every check here returns a Finding or None, never raises for a patient who
simply doesn't qualify — a gap check ruling someone out is the normal case,
not a failure.

All codes below (SNOMED, LOINC, RxNorm) were verified directly against this
project's own loaded Synthea data before being hardcoded, not copied from
memory or a secondhand summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .bundles import PatientRecord

_LOINC_SYSTEM = "http://loinc.org"
_SNOMED_SYSTEM = "http://snomed.info/sct"
_RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"

_HBA1C_LOINC_CODE = "4548-4"
_HBA1C_DIAGNOSTIC_THRESHOLD = 6.5

_DIABETES_CONDITION_CODES = {"44054006"}  # Diabetes mellitus type 2 (disorder)
_DIABETES_COMPLICATION_CODES = {
    "127013003",  # Disorder of kidney due to diabetes mellitus
    "90781000119102",  # Microalbuminuria due to type 2 diabetes mellitus
    "157141000119108",  # Proteinuria due to type 2 diabetes mellitus
    "368581000119106",  # Neuropathy due to type 2 diabetes mellitus
    "1551000119108",  # Nonproliferative diabetic retinopathy due to type II diabetes mellitus
}
_DIABETES_MEDICATION_RXNORM_CODES = {
    "860975",  # 24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet
    "106892",  # insulin isophane/regular mix [Humulin]
}

# HEDIS's own age window for the Glycemic Status Assessment measure this
# check is modelled on.
_GSD_MIN_AGE = 18
_GSD_MAX_AGE = 75
_HBA1C_WINDOW_MONTHS = 6

_EYE_EXAM_CODES = {
    "722161008",  # Diabetic retinal eye exam (procedure)
    "700070005",  # Optical coherence tomography of retina (procedure)
}
_EYE_EXAM_WINDOW_MONTHS = 12
# NCQA's own EED measure allows a negative-retinopathy exam from the prior
# year (24 months back) to satisfy this when no retinopathy is present, and
# restricts a retinopathy-positive patient to the measurement year only. This
# check does not model that branch — one 12-month window for everyone — and
# says so here rather than presenting a simplified check as the full measure.

_SYSTOLIC_BP_LOINC_CODE = "8480-6"
_DIASTOLIC_BP_LOINC_CODE = "8462-4"
_BP_PANEL_LOINC_CODE = "85354-9"
_UNCONTROLLED_SYSTOLIC_THRESHOLD = 140
_UNCONTROLLED_DIASTOLIC_THRESHOLD = 90
_HYPERTENSION_CONDITION_CODE = "59621000"  # Essential hypertension (disorder)
# HEDIS's Controlling High Blood Pressure (CBP) measure's own age window.
_CBP_MIN_AGE = 18
_CBP_MAX_AGE = 85

_COLORECTAL_SCREENING_CODES = {
    "73761001": 10 * 12,  # Colonoscopy (procedure) - USPSTF interval: every 10 years
    "104435004": 12,  # Screening for occult blood in feces (procedure) - annual
}
# USPSTF's own combined grade A/B age range for colorectal cancer screening.
_CRC_MIN_AGE = 45
_CRC_MAX_AGE = 75


@dataclass
class Evidence:
    """One cited fact backing a finding.

    `reference` uses the id each resource carries in the raw Synthea bundle
    file, e.g. "Condition/d82e9b33-...-748" — not the numeric id HAPI assigns
    once the bundle is loaded onto the live FHIR server (Synthea's own
    per-resource id is a POST body, so HAPI mints its own on load; only
    Patient carries a separate, stable identifier that survives that step,
    see bundles.PatientRecord.synthea_id). These references are for tracing
    the oracle's own reasoning, not for an agent to dereference against the
    live server directly.
    """

    reference: str
    description: str


@dataclass
class Finding:
    """One patient, one gap, with the evidence that justifies it."""

    patient_synthea_id: str
    patient_name: str
    gap_type: str
    rationale: str
    evidence: list[Evidence] = field(default_factory=list)


def _coding_matches(concept: dict[str, Any] | None, system: str, codes: set[str]) -> bool:
    if not concept:
        return False
    return any(
        c.get("system") == system and c.get("code") in codes for c in concept.get("coding") or []
    )


def _effective_date(resource: dict[str, Any]) -> date | None:
    """When an Observation was recorded."""
    value = resource.get("effectiveDateTime")
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _reference_id(reference: str) -> str:
    """The trailing id from a FHIR reference string, regardless of shape.

    Raw Synthea bundle files reference other resources in the same bundle as
    "urn:uuid:<uuid>" (confirmed live: this is what reasonReference actually
    contains here, not "Condition/<id>" — that form is only how a *live*
    FHIR server represents the same reference after loading). Handling both
    means this helper works unchanged if this code is ever pointed at a
    server-fetched resource instead of a raw bundle.
    """
    return reference.rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def _performed_date(procedure: dict[str, Any]) -> date | None:
    """When a Procedure happened. Confirmed live: every Procedure this
    module checks for uses performedPeriod, not performedDateTime — a Period
    with start/end, not a single instant."""
    period = procedure.get("performedPeriod") or {}
    value = period.get("start")
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _months_before(reference: date, months: int) -> date:
    """`reference` minus a whole number of calendar months.

    Clamps the day when the target month is shorter, e.g. 2026-08-31 minus 6
    months is 2026-02-28, not an invalid 2026-02-31 or a wrong 2026-03-03.
    """
    month_index = reference.month - 1 - months
    year = reference.year + month_index // 12
    month = month_index % 12 + 1
    day = reference.day
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1


def _find_diabetes_evidence(patient: PatientRecord) -> list[Evidence]:
    """Enough evidence to justify calling this patient diabetic, not every
    resource that happens to qualify.

    Condition-code alone misses most actual diabetics on this data: Synthea
    tracks diabetes as an internal module attribute and only emits the
    "Diabetes mellitus type 2" Condition during a wellness-visit encounter,
    so a patient can carry years of diabetic complications with no diabetes
    Condition on record at all. Measured on this project's loaded data:
    Condition-code alone finds 9 patients; adding complications, diabetes
    medications, and a diagnostic-level HbA1c brings that to 25.

    One citation per distinct diagnosis code, not per occurrence — a patient
    with several years of routine metformin refills is one fact ("on a
    diabetes medication"), not one citation per refill. Only the most recent
    qualifying HbA1c is cited, matching how a clinician would actually read
    the chart: the current picture, not the full history.
    """
    evidence: list[Evidence] = []
    diabetes_codes = _DIABETES_CONDITION_CODES | _DIABETES_COMPLICATION_CODES

    seen_condition_codes: set[str] = set()
    for condition in patient.resources("Condition"):
        code = condition.get("code") or {}
        matched = {c.get("code") for c in code.get("coding") or []} & diabetes_codes
        if not matched or matched <= seen_condition_codes:
            continue
        seen_condition_codes |= matched
        evidence.append(
            Evidence(
                reference=f"Condition/{condition.get('id')}",
                description=code.get("text", "diabetes-related condition"),
            )
        )

    for med_request in patient.resources("MedicationRequest"):
        concept = med_request.get("medicationCodeableConcept")
        if _coding_matches(concept, _RXNORM_SYSTEM, _DIABETES_MEDICATION_RXNORM_CODES):
            evidence.append(
                Evidence(
                    reference=f"MedicationRequest/{med_request.get('id')}",
                    description=(concept or {}).get("text", "diabetes medication"),
                )
            )
            break

    qualifying_observations = [
        obs
        for obs in patient.resources("Observation")
        if _coding_matches(obs.get("code"), _LOINC_SYSTEM, {_HBA1C_LOINC_CODE})
        and ((obs.get("valueQuantity") or {}).get("value") or 0) >= _HBA1C_DIAGNOSTIC_THRESHOLD
    ]
    if qualifying_observations:
        latest = max(qualifying_observations, key=lambda o: o.get("effectiveDateTime", ""))
        value = latest["valueQuantity"]["value"]
        when = latest.get("effectiveDateTime", "")[:10]
        evidence.append(
            Evidence(
                reference=f"Observation/{latest.get('id')}", description=f"HbA1c {value}% on {when}"
            )
        )

    return evidence


def check_diabetic_missing_hba1c(
    patient: PatientRecord, as_of: date | None = None
) -> Finding | None:
    """A diabetic patient with no HbA1c result in the last 6 months.

    Modelled on NCQA's Glycemic Status Assessment (GSD) measure: ages 18-75,
    most recent result in the measurement window. Deceased patients are
    excluded entirely — measuring "no recent result" against someone who
    can't have a recent result isn't a care gap, it's a wrong denominator.

    Args:
        patient: The patient to check.
        as_of: The date to measure "recent" from. Defaults to today; a fixed
            value makes this reproducible in tests.
    """
    as_of = as_of or date.today()

    if patient.is_deceased:
        return None

    age = patient.age(as_of=as_of)
    if age is None or not (_GSD_MIN_AGE <= age <= _GSD_MAX_AGE):
        return None

    diabetes_evidence = _find_diabetes_evidence(patient)
    if not diabetes_evidence:
        return None

    cutoff = _months_before(as_of, _HBA1C_WINDOW_MONTHS)
    has_recent_result = any(
        _coding_matches(obs.get("code"), _LOINC_SYSTEM, {_HBA1C_LOINC_CODE})
        and (effective := _effective_date(obs)) is not None
        and effective >= cutoff
        for obs in patient.resources("Observation")
    )
    if has_recent_result:
        return None

    return Finding(
        patient_synthea_id=patient.synthea_id,
        patient_name=patient.name,
        gap_type="diabetic_missing_hba1c",
        rationale=f"Diabetic, age {age}, no HbA1c result on or after {cutoff.isoformat()}.",
        evidence=diabetes_evidence,
    )


def check_diabetic_missing_eye_exam(
    patient: PatientRecord, as_of: date | None = None
) -> Finding | None:
    """A diabetic patient with no retinal eye exam in the last 12 months.

    Modelled on NCQA's Eye Exam for Patients with Diabetes (EED) measure,
    simplified: EED allows a negative-retinopathy exam from the prior year
    to satisfy a retinopathy-free patient, and restricts a retinopathy-
    positive patient to the current measurement year only. This check does
    not model that branch, one 12-month window for every diabetic, and says
    so rather than silently passing off a simplification as the full measure.
    """
    as_of = as_of or date.today()

    if patient.is_deceased:
        return None

    age = patient.age(as_of=as_of)
    if age is None or not (_GSD_MIN_AGE <= age <= _GSD_MAX_AGE):
        return None

    diabetes_evidence = _find_diabetes_evidence(patient)
    if not diabetes_evidence:
        return None

    cutoff = _months_before(as_of, _EYE_EXAM_WINDOW_MONTHS)
    has_recent_exam = any(
        _coding_matches(proc.get("code"), _SNOMED_SYSTEM, _EYE_EXAM_CODES)
        and (performed := _performed_date(proc)) is not None
        and performed >= cutoff
        for proc in patient.resources("Procedure")
    )
    if has_recent_exam:
        return None

    return Finding(
        patient_synthea_id=patient.synthea_id,
        patient_name=patient.name,
        gap_type="diabetic_missing_eye_exam",
        rationale=f"Diabetic, age {age}, no retinal eye exam on or after {cutoff.isoformat()}.",
        evidence=diabetes_evidence,
    )


def _find_hypertension_therapy_evidence(patient: PatientRecord) -> list[Evidence]:
    """A Condition citation for hypertension, plus one citation for a
    medication that names it as the reason — "on treatment", not just "has
    the diagnosis". On this project's real data every hypertensive patient
    is on a medication that reasonReferences their hypertension Condition
    directly, but this check still verifies that link rather than assuming
    it, since a different Synthea run is not guaranteed to have it.
    """
    evidence: list[Evidence] = []
    hypertension_condition_ids: set[str] = set()

    for condition in patient.resources("Condition"):
        if _coding_matches(condition.get("code"), _SNOMED_SYSTEM, {_HYPERTENSION_CONDITION_CODE}):
            hypertension_condition_ids.add(condition.get("id"))
            evidence.append(
                Evidence(
                    reference=f"Condition/{condition.get('id')}",
                    description=condition.get("code", {}).get("text", "Essential hypertension"),
                )
            )

    if not hypertension_condition_ids:
        return []

    for med_request in patient.resources("MedicationRequest"):
        reason_refs = {
            _reference_id(r.get("reference", "")) for r in med_request.get("reasonReference") or []
        }
        if reason_refs & hypertension_condition_ids:
            concept = med_request.get("medicationCodeableConcept") or {}
            evidence.append(
                Evidence(
                    reference=f"MedicationRequest/{med_request.get('id')}",
                    description=concept.get("text", "antihypertensive medication"),
                )
            )
            break

    # Only a diagnosis, no medication naming it as the reason: not "on
    # therapy", so this check does not apply.
    if len(evidence) < 2:
        return []

    return evidence


def check_uncontrolled_bp_despite_therapy(
    patient: PatientRecord, as_of: date | None = None
) -> Finding | None:
    """A hypertensive patient on medication for it whose latest blood
    pressure reading is still at or above 140/90.

    This is a reframed version of the brief's original "hypertensive on no
    medication" example. Measured directly on this project's data: that
    original gap is degenerate here, 0 of 40 hypertensive patients lack a
    prescribed antihypertensive, because Synthea's hypertension module always
    prescribes one. "Uncontrolled despite treatment" (HEDIS's own Controlling
    High Blood Pressure measure) asks a real question instead, and has real
    yield: 15 of 40 measured this way.
    """
    as_of = as_of or date.today()

    if patient.is_deceased:
        return None

    age = patient.age(as_of=as_of)
    if age is None or not (_CBP_MIN_AGE <= age <= _CBP_MAX_AGE):
        return None

    therapy_evidence = _find_hypertension_therapy_evidence(patient)
    if not therapy_evidence:
        return None

    bp_readings = [
        obs
        for obs in patient.resources("Observation")
        if _coding_matches(obs.get("code"), _LOINC_SYSTEM, {_BP_PANEL_LOINC_CODE})
    ]
    if not bp_readings:
        return None  # on therapy, but nothing to judge control against

    latest = max(
        (r for r in bp_readings if _effective_date(r) is not None),
        key=_effective_date,
        default=None,
    )
    if latest is None:
        return None

    systolic = diastolic = None
    for component in latest.get("component") or []:
        code = component.get("code")
        value = (component.get("valueQuantity") or {}).get("value")
        if _coding_matches(code, _LOINC_SYSTEM, {_SYSTOLIC_BP_LOINC_CODE}):
            systolic = value
        elif _coding_matches(code, _LOINC_SYSTEM, {_DIASTOLIC_BP_LOINC_CODE}):
            diastolic = value

    if systolic is None or diastolic is None:
        return None

    is_uncontrolled = (
        systolic >= _UNCONTROLLED_SYSTOLIC_THRESHOLD
        or diastolic >= _UNCONTROLLED_DIASTOLIC_THRESHOLD
    )
    if not is_uncontrolled:
        return None

    when = latest.get("effectiveDateTime", "")[:10]
    therapy_evidence.append(
        Evidence(
            reference=f"Observation/{latest.get('id')}",
            description=f"BP {systolic:g}/{diastolic:g} mmHg on {when}",
        )
    )

    return Finding(
        patient_synthea_id=patient.synthea_id,
        patient_name=patient.name,
        gap_type="uncontrolled_bp_despite_therapy",
        rationale=(
            f"On antihypertensive therapy, latest BP {systolic:g}/{diastolic:g} "
            f"on {when} still >= 140/90."
        ),
        evidence=therapy_evidence,
    )


def check_missing_colorectal_screening(
    patient: PatientRecord, as_of: date | None = None
) -> Finding | None:
    """A patient of screening age with no colorectal cancer screening on
    record within that screening method's own interval.

    Modelled on USPSTF's combined grade A/B recommendation (ages 45-75).
    Recognises the two screening methods that actually appear in this
    project's data — colonoscopy (10-year interval) and fecal occult blood
    testing (annual) — each checked against its own interval, not a single
    interval applied to both; crediting only colonoscopy would overstate this
    gap for a patient who is actually being screened annually by the other
    method.
    """
    as_of = as_of or date.today()

    if patient.is_deceased:
        return None

    age = patient.age(as_of=as_of)
    if age is None or not (_CRC_MIN_AGE <= age <= _CRC_MAX_AGE):
        return None

    for procedure in patient.resources("Procedure"):
        code = procedure.get("code")
        matched_codes = {c.get("code") for c in (code or {}).get("coding") or []} & set(
            _COLORECTAL_SCREENING_CODES
        )
        if not matched_codes:
            continue
        performed = _performed_date(procedure)
        if performed is None:
            continue
        interval_months = min(_COLORECTAL_SCREENING_CODES[c] for c in matched_codes)
        if performed >= _months_before(as_of, interval_months):
            return None  # screened within this method's own interval

    return Finding(
        patient_synthea_id=patient.synthea_id,
        patient_name=patient.name,
        gap_type="missing_colorectal_screening",
        rationale=f"Age {age}, no colorectal cancer screening within the applicable interval.",
        evidence=[],
    )


__all__ = [
    "Evidence",
    "Finding",
    "check_diabetic_missing_eye_exam",
    "check_diabetic_missing_hba1c",
    "check_missing_colorectal_screening",
    "check_uncontrolled_bp_despite_therapy",
]
