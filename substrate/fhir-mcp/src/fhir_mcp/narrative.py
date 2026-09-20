"""Narrative serialisation: FHIR resources rendered as prose, not JSON.

`nested`, `flattened`, and `compact` (serialization.py) are all the same
axis: they reshape one resource's JSON, but the model still has to parse
structure and classify fields itself (is this medication active or
historical? is this component systolic or diastolic?) at the same time as
reasoning about the answer. Grouping and labelling that classification into
prose up front measurably helps small and mid-size models, because it
removes a reasoning step they handle unreliably from raw JSON.

That's why this module works differently from serialization.py: it takes a
whole page of same-type resources at once, not one resource in isolation,
because grouping ("currently active" vs. "historical") is the entire point.

Renderers exist for the ten clinically-relevant resource types this project
actually deals with. Anything else falls back to `_narrate_generic`, which
is honestly weaker: it can drop noise, same as `compact`, but it cannot
classify or group, which is where the real benefit of narrative comes from.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"

# Same rationale as serialization.py's _COMPACT_DROP_FIELDS: server
# bookkeeping and implementation-guide noise, never clinical signal.
_GENERIC_DROP_FIELDS = frozenset({"text", "meta", "extension", "modifierExtension"})


def narrate(resources: list[dict[str, Any]], resource_type: str) -> str:
    """Render a page of same-type FHIR resources as prose.

    Args:
        resources: One or more resources of the same type. A single-resource
            page (e.g. from get_resource_by_id) is just a list of length one.
        resource_type: The FHIR resource type all of `resources` share.

    Returns:
        A prose summary. Never raises on an unrecognised resource type or
        malformed resource - a narrative renderer's job is to describe
        whatever is actually there, not to validate it.
    """
    if not resources:
        return f"No {resource_type} resources."
    renderer = _RENDERERS.get(resource_type, _narrate_generic)
    return renderer(resources)


def _display_text(concept: dict[str, Any] | None, *, system: str | None = None) -> str | None:
    """Get a human-readable name out of a CodeableConcept.

    Prefers `text` (Synthea always populates this), falls back to a coding's
    `display`, optionally preferring one from a specific code system first.
    """
    if not concept:
        return None
    text = concept.get("text")
    if text:
        return text
    codings = concept.get("coding") or []
    if system:
        for coding in codings:
            if coding.get("system") == system and coding.get("display"):
                return coding["display"]
    for coding in codings:
        if coding.get("display"):
            return coding["display"]
    return None


def _quantity_text(value_quantity: dict[str, Any] | None) -> str | None:
    if not value_quantity:
        return None
    value = value_quantity.get("value")
    unit = value_quantity.get("unit") or value_quantity.get("code") or ""
    if value is None:
        return None
    return f"{value} {unit}".strip()


def _resource_value_text(resource: dict[str, Any]) -> str | None:
    """Get whatever value an Observation-shaped resource actually carries."""
    if "valueQuantity" in resource:
        return _quantity_text(resource.get("valueQuantity"))
    if "valueString" in resource:
        return resource.get("valueString")
    if "valueCodeableConcept" in resource:
        return _display_text(resource.get("valueCodeableConcept"))
    if "valueBoolean" in resource:
        return "yes" if resource.get("valueBoolean") else "no"
    return None


def _narrate_conditions(resources: list[dict[str, Any]]) -> str:
    active: list[str] = []
    other: list[str] = []
    for r in resources:
        name = _display_text(r.get("code")) or "(unnamed condition)"
        status = ((r.get("clinicalStatus") or {}).get("coding") or [{}])[0].get("code")
        date = r.get("onsetDateTime") or r.get("recordedDate")
        line = f"{name}" + (f", onset {date}" if date else "") + f" [Condition/{r.get('id')}]"
        (active if status == "active" else other).append(line)

    sections = []
    if active:
        sections.append("Active conditions:\n" + "\n".join(f"- {line}" for line in active))
    if other:
        label = "Other conditions (resolved/inactive/unspecified status):"
        sections.append(label + "\n" + "\n".join(f"- {line}" for line in other))
    return "\n\n".join(sections) if sections else "No conditions on record."


def _narrate_observations(resources: list[dict[str, Any]]) -> str:
    # Group by test name so a mixed page (e.g. several different lab codes)
    # doesn't read as one undifferentiated list.
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in resources:
        name = _display_text(r.get("code")) or "(unnamed observation)"
        groups.setdefault(name, []).append(r)

    sections = []
    for name, entries in groups.items():
        entries_sorted = sorted(
            entries, key=lambda r: r.get("effectiveDateTime") or "", reverse=True
        )
        lines = []
        for r in entries_sorted:
            date = r.get("effectiveDateTime") or "(no date)"
            components = r.get("component") or []
            if components:
                parts = []
                for comp in components:
                    comp_name = _display_text(comp.get("code")) or "component"
                    comp_value = _quantity_text(comp.get("valueQuantity")) or "(no value)"
                    parts.append(f"{comp_name} {comp_value}")
                value_text = ", ".join(parts)
            else:
                value_text = _resource_value_text(r) or "(no value)"
            lines.append(f"- {date}: {value_text} [Observation/{r.get('id')}]")
        sections.append(f"{name}:\n" + "\n".join(lines))
    return "\n\n".join(sections)


def _narrate_procedures(resources: list[dict[str, Any]]) -> str:
    lines = []
    resources_sorted = sorted(
        resources,
        key=lambda r: (r.get("performedPeriod") or {}).get("start")
        or r.get("performedDateTime")
        or "",
        reverse=True,
    )
    for r in resources_sorted:
        name = _display_text(r.get("code")) or "(unnamed procedure)"
        date = (r.get("performedPeriod") or {}).get("start") or r.get("performedDateTime")
        status = r.get("status")
        line = f"- {name}"
        if date:
            line += f", performed {date}"
        if status and status != "completed":
            line += f" ({status})"
        line += f" [Procedure/{r.get('id')}]"
        lines.append(line)
    return "Procedures:\n" + "\n".join(lines)


def _narrate_medications(resources: list[dict[str, Any]]) -> str:
    active: list[str] = []
    historical: list[str] = []
    for r in resources:
        concept = r.get("medicationCodeableConcept")
        name = _display_text(concept, system=_RXNORM_SYSTEM) if concept else None
        name = name or "(medication reference not resolved - see medicationReference)"
        started = r.get("authoredOn")
        line = f"{name}" + (f", started {started}" if started else "")
        line += f" [MedicationRequest/{r.get('id')}]"
        (active if r.get("status") == "active" else historical).append(line)

    sections = []
    if active:
        sections.append(
            "Currently active medications:\n" + "\n".join(f"- {line}" for line in active)
        )
    if historical:
        sections.append(
            "Historical/discontinued medications:\n"
            + "\n".join(f"- {line}" for line in historical)
        )
    return "\n\n".join(sections) if sections else "No medications on record."


def _narrate_patient(resources: list[dict[str, Any]]) -> str:
    # Patients aren't grouped by status - render each one as its own short
    # paragraph of demographics.
    lines = []
    for r in resources:
        names = r.get("name") or []
        official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
        given = " ".join(official.get("given") or [])
        family = official.get("family", "")
        full_name = f"{given} {family}".strip() or "(no name on record)"

        deceased_dt = r.get("deceasedDateTime")
        deceased_bool = r.get("deceasedBoolean")
        if deceased_dt:
            status = f"deceased ({deceased_dt})"
        elif deceased_bool:
            status = "deceased (date not recorded)"
        else:
            status = "living"

        birth_date = r.get("birthDate") or "(unknown)"
        gender = r.get("gender") or "(unspecified)"
        lines.append(
            f"{full_name}: born {birth_date}, {gender}, {status} [Patient/{r.get('id')}]"
        )
    return "\n".join(lines)


def _narrate_immunizations(resources: list[dict[str, Any]]) -> str:
    lines = []
    for r in sorted(
        resources, key=lambda r: r.get("occurrenceDateTime") or "", reverse=True
    ):
        name = _display_text(r.get("vaccineCode")) or "(unnamed vaccine)"
        date = r.get("occurrenceDateTime") or "(no date)"
        status = r.get("status", "")
        line = f"- {name}, {date}"
        if status and status != "completed":
            line += f" ({status})"
        line += f" [Immunization/{r.get('id')}]"
        lines.append(line)
    return "Immunizations:\n" + "\n".join(lines)


def _narrate_encounters(resources: list[dict[str, Any]]) -> str:
    lines = []
    for r in sorted(
        resources, key=lambda r: (r.get("period") or {}).get("start") or "", reverse=True
    ):
        types = r.get("type") or []
        name = _display_text(types[0]) if types else None
        name = name or "(unspecified encounter)"
        start = (r.get("period") or {}).get("start", "(no date)")
        status = r.get("status", "")
        lines.append(f"- {name}, {start} ({status}) [Encounter/{r.get('id')}]")
    return "Encounters:\n" + "\n".join(lines)


def _narrate_allergies(resources: list[dict[str, Any]]) -> str:
    lines = []
    for r in resources:
        name = _display_text(r.get("code")) or "(unnamed allergen)"
        status = ((r.get("clinicalStatus") or {}).get("coding") or [{}])[0].get("code", "unknown")
        criticality = r.get("criticality")
        line = f"- {name} (status: {status}"
        if criticality:
            line += f", criticality: {criticality}"
        line += f") [AllergyIntolerance/{r.get('id')}]"
        lines.append(line)
    return "Allergies/intolerances:\n" + "\n".join(lines)


def _narrate_diagnostic_reports(resources: list[dict[str, Any]]) -> str:
    lines = []
    for r in sorted(
        resources, key=lambda r: r.get("effectiveDateTime") or "", reverse=True
    ):
        name = _display_text(r.get("code")) or "(unnamed report)"
        date = r.get("effectiveDateTime", "(no date)")
        conclusion = r.get("conclusion")
        line = f"- {name}, {date}"
        if conclusion:
            line += f": {conclusion}"
        line += f" [DiagnosticReport/{r.get('id')}]"
        lines.append(line)
    return "Diagnostic reports:\n" + "\n".join(lines)


def _narrate_care_plans(resources: list[dict[str, Any]]) -> str:
    lines = []
    for r in resources:
        categories = r.get("category") or []
        name = _display_text(categories[0]) if categories else None
        name = name or r.get("title") or "(unspecified care plan)"
        status = r.get("status", "")
        start = (r.get("period") or {}).get("start")
        line = f"- {name} ({status}"
        if start:
            line += f", started {start}"
        line += f") [CarePlan/{r.get('id')}]"
        lines.append(line)
    return "Care plans:\n" + "\n".join(lines)


def _narrate_generic(resources: list[dict[str, Any]]) -> str:
    """Fallback for any resource type without a tuned renderer.

    Deliberately weaker than the renderers above: this can drop noisy fields
    (same list as compact()), but it cannot classify or group, which is
    where narrative's actual benefit over JSON comes from. It exists so an
    unhandled resource type degrades to readable prose rather than either
    crashing or silently returning nothing.
    """
    blocks = []
    skip = _GENERIC_DROP_FIELDS | {"id", "resourceType"}
    for r in resources:
        resource_type = r.get("resourceType", "Resource")
        fields = {k: v for k, v in r.items() if k not in skip}
        field_lines = "; ".join(f"{k}: {v}" for k, v in fields.items())
        blocks.append(f"{resource_type}/{r.get('id')}: {field_lines}")
    return "\n".join(blocks)


_RENDERERS: dict[str, Callable[[list[dict[str, Any]]], str]] = {
    "Condition": _narrate_conditions,
    "Observation": _narrate_observations,
    "Procedure": _narrate_procedures,
    "MedicationRequest": _narrate_medications,
    "Patient": _narrate_patient,
    "Immunization": _narrate_immunizations,
    "Encounter": _narrate_encounters,
    "AllergyIntolerance": _narrate_allergies,
    "DiagnosticReport": _narrate_diagnostic_reports,
    "CarePlan": _narrate_care_plans,
}

__all__ = ["narrate"]
