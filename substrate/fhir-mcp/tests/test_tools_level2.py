"""Tests for Level 2's pure-logic helpers: medication reference resolution
and reason extraction.

These are exactly the pieces that fail silently if wrong: a medication whose
name never got resolved would just look like any other, not crash, so the
logic is tested directly rather than trusted by inspection.
"""

from __future__ import annotations

from datetime import date

import pytest

from fhir_mcp.fhir_client import FhirError
from fhir_mcp.tools_level2 import (
    _age_reference_date,
    _compute_age,
    _describe_medication,
    _describe_reason,
    _extract_clinical_status,
    _extract_observation_value,
    _extract_snomed_code,
    _is_disorder,
    _resolve_medication,
    _resolve_window_end,
    _validate_window,
)

RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"


class TestResolveMedication:
    def test_inline_codeable_concept_used_directly(self):
        request = {
            "medicationCodeableConcept": {
                "text": "lisinopril 10 MG Oral Tablet",
                "coding": [{"system": RXNORM, "code": "314076"}],
            }
        }
        concept = _resolve_medication(request, included_medications={})
        assert concept["text"] == "lisinopril 10 MG Oral Tablet"

    def test_reference_resolved_against_included_medications(self):
        """The ~30% shape: no inline concept, only a reference to a
        Medication resource that arrived via _include."""
        request = {"medicationReference": {"reference": "Medication/2860"}}
        included = {
            "Medication/2860": {
                "resourceType": "Medication",
                "id": "2860",
                "code": {"text": "sodium fluoride 0.0272 MG/MG Oral Gel"},
            }
        }
        concept = _resolve_medication(request, included)
        assert concept["text"] == "sodium fluoride 0.0272 MG/MG Oral Gel"

    def test_reference_with_nothing_included_returns_none(self):
        """A medicationReference the search didn't manage to include (should
        not happen with _include set, but the server is not ours to trust
        blindly) resolves to None rather than raising."""
        request = {"medicationReference": {"reference": "Medication/9999"}}
        assert _resolve_medication(request, included_medications={}) is None

    def test_neither_shape_present_returns_none(self):
        assert _resolve_medication({}, included_medications={}) is None


class TestDescribeMedication:
    def test_prefers_concept_text(self):
        concept = {
            "text": "albuterol 5 MG/ML Inhalation Solution",
            "coding": [{"system": RXNORM, "code": "245314", "display": "albuterol"}],
        }
        text, code = _describe_medication(concept)
        assert text == "albuterol 5 MG/ML Inhalation Solution"
        assert code == "245314"

    def test_falls_back_to_coding_display_when_text_absent(self):
        concept = {
            "coding": [{"system": RXNORM, "code": "310798", "display": "Hydrochlorothiazide 25 MG"}]
        }
        text, code = _describe_medication(concept)
        assert text == "Hydrochlorothiazide 25 MG"
        assert code == "310798"

    def test_none_concept_gives_placeholder_not_a_crash(self):
        text, code = _describe_medication(None)
        assert "unavailable" in text
        assert code is None

    def test_non_rxnorm_coding_yields_no_code(self):
        """A concept coded in some other system should not be misreported as
        an RxNorm code just because a coding entry exists."""
        concept = {
            "text": "a compounded medication",
            "coding": [{"system": "http://example.com/other", "code": "X"}],
        }
        text, code = _describe_medication(concept)
        assert text == "a compounded medication"
        assert code is None


class TestDescribeReason:
    def test_reason_reference_preferred_over_reason_code(self):
        request = {
            "reasonReference": [
                {"reference": "Condition/8871", "display": "Essential hypertension (disorder)"}
            ],
            "reasonCode": [{"text": "should not be used"}],
        }
        reference, text = _describe_reason(request)
        assert reference == "Condition/8871"
        assert text is None

    def test_reason_code_used_when_no_reference(self):
        request = {"reasonCode": [{"text": "hyperlipidemia"}]}
        reference, text = _describe_reason(request)
        assert reference is None
        assert text == "hyperlipidemia"

    def test_reason_code_falls_back_to_coding_display(self):
        request = {"reasonCode": [{"coding": [{"display": "hyperlipidemia"}]}]}
        reference, text = _describe_reason(request)
        assert reference is None
        assert text == "hyperlipidemia"

    def test_neither_present_returns_both_none(self):
        assert _describe_reason({}) == (None, None)


class TestResolveWindowEnd:
    def test_explicit_end_date_passed_through(self):
        assert _resolve_window_end("2024-12-31") == "2024-12-31"

    def test_none_defaults_to_today(self):
        assert _resolve_window_end(None) == date.today().isoformat()


class TestValidateWindow:
    def test_valid_window_does_not_raise(self):
        _validate_window("2022-01-01", "2024-12-31")  # should not raise

    def test_start_after_end_raises_actionable_error(self):
        with pytest.raises(FhirError, match="is after end_date"):
            _validate_window("2025-01-01", "2020-01-01")

    def test_equal_start_and_end_does_not_raise(self):
        """A one-day window is a valid, if narrow, window."""
        _validate_window("2024-06-01", "2024-06-01")

    @pytest.mark.parametrize("bad_date", ["not-a-date", "2024-13-01", "06/01/2024", ""])
    def test_malformed_date_raises_actionable_error(self, bad_date: str):
        with pytest.raises(FhirError, match="ISO dates"):
            _validate_window(bad_date, "2024-12-31")


class TestExtractObservationValue:
    def test_prefers_value_quantity(self):
        resource = {"valueQuantity": {"value": 6.23, "unit": "%"}}
        value, unit = _extract_observation_value(resource)
        assert value == 6.23
        assert unit == "%"

    def test_falls_back_to_value_string(self):
        resource = {"valueString": "Negative"}
        value, unit = _extract_observation_value(resource)
        assert value == "Negative"
        assert unit is None

    def test_neither_present_returns_both_none(self):
        assert _extract_observation_value({}) == (None, None)


class TestIsDisorder:
    """Every case here is a real SNOMED semantic tag measured on this
    project's own loaded Synthea data, not a hypothetical."""

    @pytest.mark.parametrize(
        "text",
        [
            "Essential hypertension (disorder)",
            "Obstructive sleep apnea syndrome (disorder)",
            "Chronic obstructive bronchitis (disorder)",
        ],
    )
    def test_disorder_tag_passes(self, text: str):
        assert _is_disorder({"text": text}) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Risk activity involvement (finding)",
            "Received higher education (finding)",
            "Has a criminal record (finding)",
            "Past pregnancy history of miscarriage (situation)",
            "Body mass index 30+ - obesity (finding)",
        ],
    )
    def test_non_disorder_tags_fail(self, text: str):
        assert _is_disorder({"text": text}) is False

    def test_no_code_returns_false(self):
        assert _is_disorder(None) is False

    def test_no_text_field_returns_false(self):
        assert _is_disorder({"coding": [{"code": "59621000"}]}) is False


class TestExtractSnomedCode:
    def test_extracts_snomed_coding(self):
        code = {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "59621000",
                    "display": "Essential hypertension",
                }
            ]
        }
        assert _extract_snomed_code(code) == "59621000"

    def test_ignores_non_snomed_coding(self):
        code = {"coding": [{"system": "http://example.com/other", "code": "X"}]}
        assert _extract_snomed_code(code) is None

    def test_none_returns_none(self):
        assert _extract_snomed_code(None) is None


class TestExtractClinicalStatus:
    def test_extracts_status_code(self):
        condition = {
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                    }
                ]
            }
        }
        assert _extract_clinical_status(condition) == "active"

    def test_missing_status_returns_none(self):
        assert _extract_clinical_status({}) is None


class TestAgeReferenceDate:
    def test_alive_patient_uses_today(self):
        assert _age_reference_date({}) == date.today()

    def test_deceased_with_date_uses_that_date(self):
        assert _age_reference_date({"deceasedDateTime": "2020-06-15T00:00:00+00:00"}) == date(
            2020, 6, 15
        )

    def test_deceased_boolean_true_with_no_date_returns_none(self):
        """Known dead, but no date recorded: guessing 'today' would be wrong,
        not just imprecise, so this must not silently fall back to it."""
        assert _age_reference_date({"deceasedBoolean": True}) is None

    def test_deceased_boolean_false_uses_today(self):
        assert _age_reference_date({"deceasedBoolean": False}) == date.today()


class TestComputeAge:
    def test_birthday_already_passed_this_year(self):
        assert _compute_age("1960-01-01", date(2026, 6, 15)) == 66

    def test_birthday_not_yet_reached_this_year(self):
        assert _compute_age("1960-12-31", date(2026, 6, 15)) == 65

    def test_birthday_is_today(self):
        assert _compute_age("1960-06-15", date(2026, 6, 15)) == 66

    def test_no_birth_date_returns_none(self):
        assert _compute_age(None, date(2026, 6, 15)) is None

    def test_no_reference_date_returns_none(self):
        """The deceased-with-no-date case: _age_reference_date already
        returned None, and this must not substitute a guess for it."""
        assert _compute_age("1960-01-01", None) is None

    def test_malformed_birth_date_returns_none_not_a_crash(self):
        assert _compute_age("not-a-date", date(2026, 6, 15)) is None
