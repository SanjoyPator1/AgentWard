"""Loading raw Synthea-generated FHIR bundles directly off disk.

The oracle reads these files, not the live HAPI FHIR server: an oracle is
only worth anything as an independent source of truth, and depending on the
same server an agent depends on would make load order and server state part
of what gets tested, not just the data itself.

Deliberately imports nothing from substrate/fhir-mcp. The oracle grades an
agent built on those tools; it must not share code with them, or a bug common
to both would go uncaught by both.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

_SYNTHEA_IDENTIFIER_SYSTEM = "https://github.com/synthetichealth/synthea"


def find_patient_bundle_files(fhir_dir: Path) -> list[Path]:
    """List the per-patient bundle files in a synthea_output/<label>/fhir/ directory.

    Excludes hospitalInformation*/practitionerInformation*: those two hold
    Organizations and Practitioners shared across the whole population, not
    one patient's own record (see data/README.md for why Synthea splits them
    out this way).
    """
    return sorted(
        f
        for f in fhir_dir.glob("*.json")
        if not f.name.startswith("hospitalInformation")
        and not f.name.startswith("practitionerInformation")
    )


@dataclass
class PatientRecord:
    """One patient's full record, resources grouped by type.

    Everything about one patient — Encounters, Conditions, Observations,
    MedicationRequests, all of it — lives in a single Synthea bundle file, so
    answering a question about one patient never needs joining across files.
    """

    synthea_id: str
    """The stable id Synthea assigns this patient (Patient.identifier with
    system=https://github.com/synthetichealth/synthea). Resolvable on the
    live FHIR server via Patient?identifier={synthea_id} (confirmed live:
    this exact id resolves to whatever numeric id HAPI assigned on load), so
    a finding computed here can still be checked against the loaded server
    later, even though HAPI's own ids aren't known until load time."""

    patient: dict[str, Any]
    resources_by_type: dict[str, list[dict[str, Any]]]

    def resources(self, resource_type: str) -> list[dict[str, Any]]:
        """All of this patient's resources of one type, e.g. 'Condition'."""
        return self.resources_by_type.get(resource_type, [])

    @property
    def name(self) -> str:
        names = self.patient.get("name") or []
        official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
        given = " ".join(official.get("given") or [])
        family = official.get("family", "")
        return f"{given} {family}".strip() or "(unnamed)"

    @property
    def birth_date(self) -> str | None:
        return self.patient.get("birthDate")

    @property
    def is_deceased(self) -> bool:
        return (
            bool(self.patient.get("deceasedDateTime"))
            or self.patient.get("deceasedBoolean") is True
        )

    def age_reference_date(self, as_of: date | None = None) -> date | None:
        """The date to compute this patient's age as of: `as_of` (or today,
        if omitted) for a living patient, their recorded date of death for
        one who isn't. None when known deceased but undated, since guessing
        at a living patient's reference date for someone already dead would
        be wrong, not just imprecise.

        A caller checking something else against its own `as_of` (a gap
        check's measurement window, say) must pass that same value here too
        — otherwise a living patient's age would be computed against the
        real "today" while the rest of the check uses a different date,
        which could disagree right around a birthday.

        Mirrors fhir_mcp.tools_level2's identical rule, kept as an
        independent implementation on purpose: the oracle must not import
        anything from the tool layer it exists to grade.
        """
        deceased_datetime = self.patient.get("deceasedDateTime")
        if isinstance(deceased_datetime, str) and deceased_datetime:
            try:
                return date.fromisoformat(deceased_datetime[:10])
            except ValueError:
                return None
        if self.patient.get("deceasedBoolean") is True:
            return None
        return as_of or date.today()

    def age(self, as_of: date | None = None) -> int | None:
        """Whole years old, as of age_reference_date(as_of). None if undeterminable."""
        if not self.birth_date:
            return None
        reference = self.age_reference_date(as_of)
        if reference is None:
            return None
        try:
            born = date.fromisoformat(self.birth_date)
        except ValueError:
            return None
        years = reference.year - born.year
        if (reference.month, reference.day) < (born.month, born.day):
            years -= 1
        return years


def parse_patient_bundle(bundle: dict[str, Any], source: str = "<bundle>") -> PatientRecord:
    """Turn one parsed Synthea bundle into a PatientRecord.

    Args:
        bundle: The decoded Bundle JSON.
        source: Identifies the bundle in error messages, e.g. a file path.

    Raises:
        ValueError: if no Patient resource is found, or it has no Synthea
            identifier — both would mean this isn't the kind of bundle this
            function expects, and continuing would produce a PatientRecord
            silently missing the one thing everything else keys off.
    """
    resources_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    patient: dict[str, Any] | None = None

    for entry in bundle.get("entry") or []:
        resource = entry.get("resource")
        if not resource:
            continue
        resource_type = resource.get("resourceType")
        resources_by_type[resource_type].append(resource)
        if resource_type == "Patient":
            patient = resource

    if patient is None:
        raise ValueError(f"No Patient resource found in {source}")

    synthea_id = next(
        (
            i["value"]
            for i in patient.get("identifier", [])
            if i.get("system") == _SYNTHEA_IDENTIFIER_SYSTEM
        ),
        None,
    )
    if synthea_id is None:
        raise ValueError(f"Patient in {source} has no Synthea identifier")

    return PatientRecord(
        synthea_id=synthea_id, patient=patient, resources_by_type=dict(resources_by_type)
    )


def load_patient_record(bundle_path: Path) -> PatientRecord:
    """Read and parse one patient bundle file."""
    bundle = json.loads(bundle_path.read_text())
    return parse_patient_bundle(bundle, source=str(bundle_path))


def load_all_patients(fhir_dir: Path) -> list[PatientRecord]:
    """Load every patient bundle in a synthea_output/<label>/fhir/ directory."""
    return [load_patient_record(f) for f in find_patient_bundle_files(fhir_dir)]


__all__ = [
    "PatientRecord",
    "find_patient_bundle_files",
    "load_all_patients",
    "load_patient_record",
    "parse_patient_bundle",
]
