"""Tests for the gap checks, against hand-built fixtures.

Every code used here is real, verified against this project's own loaded
Synthea data (see gaps.py's module docstring) — these are realistic fixtures,
not arbitrary made-up values.
"""

from __future__ import annotations

from datetime import date

from f1_care_gap_hunter.bundles import PatientRecord, parse_patient_bundle
from f1_care_gap_hunter.gaps import (
    Evidence,
    _months_before,
    _reference_id,
    check_diabetic_missing_eye_exam,
    check_diabetic_missing_hba1c,
    check_missing_colorectal_screening,
    check_uncontrolled_bp_despite_therapy,
)

SYNTHEA_ID = "test-patient-0001"


def _bundle(*resources: dict) -> dict:
    """A minimal Synthea-shaped transaction Bundle around given resources."""
    entries = [{"resource": r, "fullUrl": f"urn:uuid:{r.get('id')}"} for r in resources]
    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def _patient_resource(*, birth_date: str, deceased: str | None = None) -> dict:
    resource = {
        "resourceType": "Patient",
        "id": SYNTHEA_ID,
        "identifier": [
            {"system": "https://github.com/synthetichealth/synthea", "value": SYNTHEA_ID}
        ],
        "name": [{"use": "official", "given": ["Test"], "family": "Patient"}],
        "birthDate": birth_date,
    }
    if deceased:
        resource["deceasedDateTime"] = deceased
    return resource


def _condition(condition_id: str, snomed_code: str, text: str) -> dict:
    return {
        "resourceType": "Condition",
        "id": condition_id,
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": snomed_code}],
            "text": text,
        },
    }


def _hba1c_observation(obs_id: str, effective_date: str, value: float) -> dict:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4"}]},
        "effectiveDateTime": f"{effective_date}T10:00:00+00:00",
        "valueQuantity": {"value": value, "unit": "%"},
    }


def _record(patient: dict, *resources: dict) -> PatientRecord:
    return parse_patient_bundle(_bundle(patient, *resources))


def _procedure(proc_id: str, snomed_code: str, text: str, performed_date: str) -> dict:
    return {
        "resourceType": "Procedure",
        "id": proc_id,
        "status": "completed",
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": snomed_code}],
            "text": text,
        },
        "performedPeriod": {
            "start": f"{performed_date}T10:00:00+00:00",
            "end": f"{performed_date}T10:30:00+00:00",
        },
    }


def _bp_observation(obs_id: str, effective_date: str, systolic: float, diastolic: float) -> dict:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
        "effectiveDateTime": f"{effective_date}T10:00:00+00:00",
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                "valueQuantity": {"value": systolic, "unit": "mm[Hg]"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
                "valueQuantity": {"value": diastolic, "unit": "mm[Hg]"},
            },
        ],
    }


def _hypertension_medication(med_id: str, condition_id: str) -> dict:
    return {
        "resourceType": "MedicationRequest",
        "id": med_id,
        "status": "active",
        "medicationCodeableConcept": {"text": "amLODIPine 2.5 MG Oral Tablet"},
        # Raw Synthea bundles reference other resources in the same bundle
        # as "urn:uuid:<id>", confirmed live — not "Condition/<id>", which is
        # only how a live FHIR server represents the same reference.
        "reasonReference": [{"reference": f"urn:uuid:{condition_id}"}],
    }


class TestReferenceId:
    def test_urn_uuid_form(self):
        """The shape raw Synthea bundles actually use."""
        assert _reference_id("urn:uuid:d82e9b33-5c3a-bf38-4911-66727b455b2f") == (
            "d82e9b33-5c3a-bf38-4911-66727b455b2f"
        )

    def test_resource_type_slash_id_form(self):
        """The shape a live FHIR server represents the same reference as."""
        assert _reference_id("Condition/8871") == "8871"


class TestMonthsBefore:
    def test_ordinary_subtraction(self):
        assert _months_before(date(2026, 8, 31), 6) == date(2026, 2, 28)

    def test_no_leap_year_clamp(self):
        assert _months_before(date(2025, 8, 31), 6) == date(2025, 2, 28)

    def test_leap_year_clamp(self):
        assert _months_before(date(2024, 8, 31), 6) == date(2024, 2, 29)

    def test_crosses_year_boundary(self):
        assert _months_before(date(2026, 2, 15), 6) == date(2025, 8, 15)


class TestCheckDiabeticMissingHbA1c:
    def test_diabetic_with_no_recent_result_is_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
            _hba1c_observation("o1", "2013-01-01", 6.9),
        )
        finding = check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        assert finding.gap_type == "diabetic_missing_hba1c"
        assert finding.patient_synthea_id == SYNTHEA_ID
        assert any(e.reference == "Condition/c1" for e in finding.evidence)

    def test_diabetic_with_recent_result_is_not_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
            _hba1c_observation("o1", "2026-06-01", 6.9),
        )
        assert check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31)) is None

    def test_non_diabetic_is_never_a_gap(self):
        patient = _record(_patient_resource(birth_date="1960-01-01"))
        assert check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31)) is None

    def test_under_coded_diabetic_found_via_complication(self):
        """No 'Diabetes mellitus type 2' Condition at all, only a complication
        — the exact under-coding pattern measured on this project's real data."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "127013003", "Disorder of kidney due to diabetes mellitus (disorder)"),
        )
        finding = check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        assert finding.evidence == [
            Evidence(
                reference="Condition/c1",
                description="Disorder of kidney due to diabetes mellitus (disorder)",
            )
        ]

    def test_under_coded_diabetic_found_via_medication(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            {
                "resourceType": "MedicationRequest",
                "id": "m1",
                "status": "active",
                "medicationCodeableConcept": {
                    "coding": [
                        {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975"}
                    ],
                    "text": "24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet",
                },
            },
        )
        finding = check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        assert finding.evidence[0].reference == "MedicationRequest/m1"

    def test_repeated_medication_refills_cited_once_not_per_refill(self):
        metformin = {
            "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975"}],
            "text": "24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet",
        }
        refills = [
            {
                "resourceType": "MedicationRequest",
                "id": f"m{i}",
                "status": "completed",
                "medicationCodeableConcept": metformin,
            }
            for i in range(5)
        ]
        patient = _record(_patient_resource(birth_date="1960-01-01"), *refills)
        finding = check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        medication_citations = [
            e for e in finding.evidence if e.reference.startswith("MedicationRequest/")
        ]
        assert len(medication_citations) == 1

    def test_only_the_most_recent_qualifying_hba1c_is_cited(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _hba1c_observation("older", "2010-01-01", 6.8),
            _hba1c_observation("newer", "2013-06-01", 7.9),
        )
        finding = check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        hba1c_citations = [e for e in finding.evidence if e.reference.startswith("Observation/")]
        assert len(hba1c_citations) == 1
        assert hba1c_citations[0].reference == "Observation/newer"

    def test_deceased_patient_is_never_a_gap(self):
        """A dead patient cannot be overdue for a future test."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01", deceased="2015-01-01T00:00:00+00:00"),
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
        )
        assert check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31)) is None

    def test_patient_outside_age_window_is_not_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="2020-01-01"),  # 6 years old at as_of
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
        )
        assert check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31)) is None

    def test_elevated_hba1c_alone_counts_as_diabetes_evidence(self):
        """No Condition or medication at all, just a diagnostic-level HbA1c
        result — the fourth denominator strategy this check relies on."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _hba1c_observation("o1", "2013-01-01", 7.5),
        )
        finding = check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31))
        assert finding is not None

    def test_prediabetic_hba1c_does_not_count_as_diabetes_evidence(self):
        """Below the diagnostic threshold: prediabetes, not diabetes, and
        this check should not fire on it."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _hba1c_observation("o1", "2013-01-01", 6.0),
        )
        assert check_diabetic_missing_hba1c(patient, as_of=date(2026, 8, 31)) is None


class TestCheckDiabeticMissingEyeExam:
    def test_diabetic_with_no_recent_exam_is_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
            _procedure("p1", "722161008", "Diabetic retinal eye exam (procedure)", "2020-01-01"),
        )
        finding = check_diabetic_missing_eye_exam(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        assert finding.gap_type == "diabetic_missing_eye_exam"

    def test_diabetic_with_recent_exam_is_not_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
            _procedure("p1", "722161008", "Diabetic retinal eye exam (procedure)", "2026-06-01"),
        )
        assert check_diabetic_missing_eye_exam(patient, as_of=date(2026, 8, 31)) is None

    def test_oct_retina_also_counts_as_a_recent_exam(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "44054006", "Diabetes mellitus type 2 (disorder)"),
            _procedure(
                "p1",
                "700070005",
                "Optical coherence tomography of retina (procedure)",
                "2026-06-01",
            ),
        )
        assert check_diabetic_missing_eye_exam(patient, as_of=date(2026, 8, 31)) is None

    def test_non_diabetic_is_never_a_gap(self):
        patient = _record(_patient_resource(birth_date="1960-01-01"))
        assert check_diabetic_missing_eye_exam(patient, as_of=date(2026, 8, 31)) is None


class TestCheckUncontrolledBpDespiteTherapy:
    def test_uncontrolled_bp_on_therapy_is_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "59621000", "Essential hypertension (disorder)"),
            _hypertension_medication("m1", "c1"),
            _bp_observation("o1", "2026-08-01", 150, 95),
        )
        finding = check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        assert finding.gap_type == "uncontrolled_bp_despite_therapy"

    def test_controlled_bp_on_therapy_is_not_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "59621000", "Essential hypertension (disorder)"),
            _hypertension_medication("m1", "c1"),
            _bp_observation("o1", "2026-08-01", 118, 76),
        )
        assert check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31)) is None

    def test_diastolic_alone_over_threshold_is_still_uncontrolled(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "59621000", "Essential hypertension (disorder)"),
            _hypertension_medication("m1", "c1"),
            _bp_observation("o1", "2026-08-01", 130, 92),
        )
        assert check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31)) is not None

    def test_uses_the_latest_reading_not_an_old_one(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "59621000", "Essential hypertension (disorder)"),
            _hypertension_medication("m1", "c1"),
            _bp_observation("older", "2020-01-01", 160, 100),
            _bp_observation("newer", "2026-08-01", 118, 76),
        )
        assert check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31)) is None

    def test_hypertensive_but_no_medication_reason_referencing_it_is_not_on_therapy(self):
        """A hypertension diagnosis with no medication actually linked to it
        is not 'on therapy', regardless of BP readings."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "59621000", "Essential hypertension (disorder)"),
            _bp_observation("o1", "2026-08-01", 150, 95),
        )
        assert check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31)) is None

    def test_no_bp_reading_at_all_is_not_a_gap(self):
        """On therapy, but nothing to judge control against — not the same
        claim as 'confirmed uncontrolled'."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _condition("c1", "59621000", "Essential hypertension (disorder)"),
            _hypertension_medication("m1", "c1"),
        )
        assert check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31)) is None

    def test_not_hypertensive_is_never_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _bp_observation("o1", "2026-08-01", 150, 95),
        )
        assert check_uncontrolled_bp_despite_therapy(patient, as_of=date(2026, 8, 31)) is None


class TestCheckMissingColorectalScreening:
    def test_no_screening_ever_is_a_gap(self):
        patient = _record(_patient_resource(birth_date="1960-01-01"))
        finding = check_missing_colorectal_screening(patient, as_of=date(2026, 8, 31))
        assert finding is not None
        assert finding.gap_type == "missing_colorectal_screening"

    def test_recent_colonoscopy_is_not_a_gap(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _procedure("p1", "73761001", "Colonoscopy (procedure)", "2020-01-01"),
        )
        assert check_missing_colorectal_screening(patient, as_of=date(2026, 8, 31)) is None

    def test_colonoscopy_older_than_ten_years_is_a_gap_again(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _procedure("p1", "73761001", "Colonoscopy (procedure)", "2010-01-01"),
        )
        assert check_missing_colorectal_screening(patient, as_of=date(2026, 8, 31)) is not None

    def test_recent_fit_test_satisfies_screening_too(self):
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _procedure(
                "p1", "104435004", "Screening for occult blood in feces (procedure)", "2026-06-01"
            ),
        )
        assert check_missing_colorectal_screening(patient, as_of=date(2026, 8, 31)) is None

    def test_fit_test_from_last_year_is_a_gap_again(self):
        """FIT is annual, unlike colonoscopy's 10-year interval — a FIT test
        13 months old should not satisfy this check."""
        patient = _record(
            _patient_resource(birth_date="1960-01-01"),
            _procedure(
                "p1", "104435004", "Screening for occult blood in feces (procedure)", "2025-07-01"
            ),
        )
        assert check_missing_colorectal_screening(patient, as_of=date(2026, 8, 31)) is not None

    def test_outside_age_window_is_never_a_gap(self):
        patient = _record(_patient_resource(birth_date="1990-01-01"))  # 36 at as_of
        assert check_missing_colorectal_screening(patient, as_of=date(2026, 8, 31)) is None
