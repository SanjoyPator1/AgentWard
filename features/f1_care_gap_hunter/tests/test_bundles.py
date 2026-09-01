"""Tests for bundle parsing and the age/deceased logic every gap check relies on."""

from __future__ import annotations

from datetime import date

import pytest

from f1_care_gap_hunter.bundles import parse_patient_bundle

SYNTHEA_ID = "test-patient-0001"


def _bundle_with_patient(**patient_fields) -> dict:
    patient = {
        "resourceType": "Patient",
        "id": SYNTHEA_ID,
        "identifier": [
            {"system": "https://github.com/synthetichealth/synthea", "value": SYNTHEA_ID}
        ],
        "name": [{"use": "official", "given": ["Test"], "family": "Patient"}],
        **patient_fields,
    }
    return {"resourceType": "Bundle", "type": "transaction", "entry": [{"resource": patient}]}


class TestParsePatientBundle:
    def test_extracts_synthea_id(self):
        record = parse_patient_bundle(_bundle_with_patient(birthDate="1960-01-01"))
        assert record.synthea_id == SYNTHEA_ID

    def test_missing_patient_raises(self):
        with pytest.raises(ValueError, match="No Patient resource"):
            parse_patient_bundle({"resourceType": "Bundle", "entry": []})

    def test_missing_synthea_identifier_raises(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [{"resource": {"resourceType": "Patient", "id": "x", "identifier": []}}],
        }
        with pytest.raises(ValueError, match="no Synthea identifier"):
            parse_patient_bundle(bundle)

    def test_groups_resources_by_type(self):
        bundle = _bundle_with_patient(birthDate="1960-01-01")
        bundle["entry"].append({"resource": {"resourceType": "Condition", "id": "c1"}})
        bundle["entry"].append({"resource": {"resourceType": "Condition", "id": "c2"}})
        record = parse_patient_bundle(bundle)
        assert len(record.resources("Condition")) == 2
        assert record.resources("Observation") == []


class TestName:
    def test_prefers_official_name(self):
        bundle = _bundle_with_patient(
            birthDate="1960-01-01",
            name=[
                {"use": "maiden", "given": ["Old"], "family": "Name"},
                {"use": "official", "given": ["Current"], "family": "Name"},
            ],
        )
        assert parse_patient_bundle(bundle).name == "Current Name"


class TestAge:
    def test_alive_patient_uses_as_of(self):
        record = parse_patient_bundle(_bundle_with_patient(birthDate="1960-06-15"))
        assert record.age(as_of=date(2026, 6, 15)) == 66
        assert record.age(as_of=date(2026, 6, 14)) == 65

    def test_deceased_patient_age_fixed_at_death(self):
        record = parse_patient_bundle(
            _bundle_with_patient(
                birthDate="1956-07-17", deceasedDateTime="2013-12-25T18:35:28+00:00"
            )
        )
        # Passing a much later as_of must not change a dead patient's age.
        assert record.age(as_of=date(2026, 9, 1)) == 57
        assert record.is_deceased is True

    def test_deceased_boolean_true_with_no_date_gives_unknown_age(self):
        record = parse_patient_bundle(
            _bundle_with_patient(birthDate="1960-01-01", deceasedBoolean=True)
        )
        assert record.age(as_of=date(2026, 9, 1)) is None
        assert record.is_deceased is True

    def test_no_birth_date_gives_unknown_age(self):
        record = parse_patient_bundle(_bundle_with_patient())
        assert record.age(as_of=date(2026, 9, 1)) is None
