"""Tests for the serialisation strategies.

These matter more than they look. Experiment 3 compares agent accuracy across
these three strategies, so a bug that silently drops a field would not show up
as a crash, it would show up as a worse experiment result attributed to the
wrong cause.
"""

from __future__ import annotations

import pytest

from fhir_mcp.serialization import compact, flatten, serialise

# A cut-down Condition with the shapes that actually occur in Synthea output:
# nested objects, lists of objects, a narrative blob, and server metadata.
SAMPLE_CONDITION = {
    "resourceType": "Condition",
    "id": "8871",
    "meta": {"versionId": "1", "lastUpdated": "2026-08-29T11:00:00Z"},
    "text": {"status": "generated", "div": "<div>Type 2 diabetes mellitus</div>"},
    "clinicalStatus": {
        "coding": [
            {"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}
        ]
    },
    "code": {
        "coding": [
            {"system": "http://snomed.info/sct", "code": "44054006", "display": "Type 2 diabetes"}
        ],
        "text": "Type 2 diabetes",
    },
    "subject": {"reference": "Patient/2657"},
    "onsetDateTime": "2019-03-12",
}


class TestCompact:
    def test_drops_narrative_and_metadata(self):
        result = compact(SAMPLE_CONDITION)
        assert "text" not in result
        assert "meta" not in result

    def test_keeps_every_clinical_field(self):
        result = compact(SAMPLE_CONDITION)
        for field in ("resourceType", "id", "code", "subject", "onsetDateTime", "clinicalStatus"):
            assert field in result, f"compact dropped {field}, which is clinical content"

    def test_does_not_mutate_input(self):
        original = dict(SAMPLE_CONDITION)
        compact(SAMPLE_CONDITION)
        assert SAMPLE_CONDITION == original

    def test_nested_extensions_survive(self):
        """Only top-level extensions are dropped. At depth an extension can be
        the only place a value lives, so removing it would change meaning."""
        resource = {
            "resourceType": "Patient",
            "address": [{"extension": [{"url": "geo", "valueString": "x"}]}],
        }
        result = compact(resource)
        assert result["address"][0]["extension"][0]["valueString"] == "x"


class TestFlatten:
    def test_scalar_at_root(self):
        assert flatten({"id": "8871"}) == {"id": "8871"}

    def test_nested_object_becomes_dotted_path(self):
        assert flatten({"subject": {"reference": "Patient/2657"}}) == {
            "subject.reference": "Patient/2657"
        }

    def test_list_entries_are_indexed(self):
        result = flatten({"name": [{"given": ["Ada", "Lovelace"]}]})
        assert result == {"name.0.given.0": "Ada", "name.0.given.1": "Lovelace"}

    @pytest.mark.parametrize("empty", [{}, []])
    def test_empty_containers_are_preserved(self, empty):
        """Field-exists-but-empty must stay distinguishable from field-absent.

        F1 has to prove the absence of a resource, so collapsing the two would
        corrupt exactly the claim that feature makes.
        """
        result = flatten({"resourceType": "Condition", "note": empty})
        assert "note" in result
        assert result["note"] == empty

    def test_loses_no_leaf_values(self):
        flat = flatten(SAMPLE_CONDITION)
        assert flat["code.coding.0.display"] == "Type 2 diabetes"
        assert flat["subject.reference"] == "Patient/2657"
        assert flat["onsetDateTime"] == "2019-03-12"

    def test_no_nested_containers_remain(self):
        """The whole point of flattening: nothing left for a model to traverse."""
        flat = flatten(SAMPLE_CONDITION)
        for key, value in flat.items():
            if value in ({}, []):
                continue  # deliberately preserved, see above
            assert not isinstance(value, (dict, list)), f"{key} is still nested"


class TestSerialise:
    def test_nested_returns_equal_content(self):
        assert serialise(SAMPLE_CONDITION, "nested") == SAMPLE_CONDITION

    def test_nested_returns_a_copy_not_the_original(self):
        """Callers must not be able to mutate the HTTP client's decoded response."""
        result = serialise(SAMPLE_CONDITION, "nested")
        result["injected"] = True
        assert "injected" not in SAMPLE_CONDITION

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown serialisation strategy"):
            serialise(SAMPLE_CONDITION, "no-such-strategy")  # type: ignore[arg-type]

    def test_compact_is_smaller_than_nested(self):
        """The reason compact exists. If this ever stops holding, the strategy
        is not earning its place in the experiment."""
        import json

        nested_size = len(json.dumps(serialise(SAMPLE_CONDITION, "nested")))
        compact_size = len(json.dumps(serialise(SAMPLE_CONDITION, "compact")))
        assert compact_size < nested_size
