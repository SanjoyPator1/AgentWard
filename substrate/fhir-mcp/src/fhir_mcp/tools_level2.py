"""Level 2 tools: task-shaped, built on top of Level 1's thin passthrough.

Each tool here answers one specific clinical question that would otherwise
take the agent several Level 1 calls, and some FHIR knowledge, to get right.
See self-docs/05-level2-tools-plan.md for the design reasoning behind each
one, including what was deliberately left out and why.

Read-only, for the same reason as Level 1: see tools_level1.py's module
docstring.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Settings
from .fhir_client import FhirError
from .tools_level1 import AppContext, _actionable_errors

_RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"
_SNOMED_SYSTEM = "http://snomed.info/sct"


class MedicationResult(BaseModel):
    """One active medication, with the reason it was prescribed when the
    server records one."""

    reference: str = Field(
        description="FHIR reference to the MedicationRequest, e.g. 'MedicationRequest/7262'."
    )
    medication_text: str = Field(
        description=(
            "The medication's display name, already resolved. Some records name the "
            "medication inline; others only reference a separate Medication resource, "
            "which this tool has already looked up so the caller never has to make a "
            "second call to find out what the drug actually is."
        )
    )
    rxnorm_code: str | None = Field(
        description="The RxNorm code for this medication, or null if none was coded."
    )
    authored_on: str | None = Field(description="When this medication was prescribed, if recorded.")
    reason_reference: str | None = Field(
        description=(
            "FHIR reference to the Condition this medication treats, e.g. 'Condition/8871', "
            "when the server recorded a coded link. Cite this rather than reason_text when present."
        )
    )
    reason_text: str | None = Field(
        description=(
            "Free-text reason this medication was prescribed, only present when the server "
            "recorded a reason but not as a reference to a specific Condition."
        )
    )


class ActiveMedicationsResult(BaseModel):
    """A patient's active medications, in one call."""

    patient_reference: str = Field(description="Echoes the input, e.g. 'Patient/2685'.")
    total_matching: int | None = Field(
        description=(
            "How many active medications this patient has, as reported by the FHIR server. "
            "Null means the server declined to count. This tool does not paginate: it asks "
            "for up to 100 in one call, since a patient with more active medications than "
            "that would itself be a notable data situation worth knowing about, not something "
            "to silently truncate."
        )
    )
    returned: int = Field(
        description="How many medications are in this result. Never more than total_matching."
    )
    medications: list[MedicationResult] = Field(description="The active medications themselves.")


def _resolve_medication(
    request: dict[str, Any],
    included_medications: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Get the medicationCodeableConcept for a MedicationRequest, resolving
    a medicationReference against the Medications the search already
    included, if that's the shape this particular record used.

    About 30% of MedicationRequest records on this project's Synthea data use
    medicationReference instead of an inline medicationCodeableConcept. A
    tool that only reads the latter silently drops those.
    """
    concept = request.get("medicationCodeableConcept")
    if concept is not None:
        return concept

    reference = (request.get("medicationReference") or {}).get("reference")
    if not reference:
        return None

    medication = included_medications.get(reference)
    return medication.get("code") if medication else None


def _describe_medication(concept: dict[str, Any] | None) -> tuple[str, str | None]:
    """Pull a display name and an RxNorm code out of a CodeableConcept.

    Prefers the concept's own `text` (Synthea always populates this), falls
    back to a coding's `display` if `text` is absent. Returns a placeholder
    text rather than raising: a medication this tool cannot describe is still
    real and still active, and reporting nothing at all would be worse than a
    placeholder that's honest about what happened.
    """
    if not concept:
        return "(medication details unavailable)", None

    text = concept.get("text")
    rxnorm_code = None
    for coding in concept.get("coding") or []:
        if coding.get("system") == _RXNORM_SYSTEM:
            rxnorm_code = coding.get("code")
        if not text and coding.get("display"):
            text = coding["display"]

    return text or "(medication details unavailable)", rxnorm_code


def _describe_reason(request: dict[str, Any]) -> tuple[str | None, str | None]:
    """Get the reason a medication was prescribed, preferring a coded
    reference over free text, matching the ResourceResult convention of
    citing a FHIR reference as evidence over restating content as prose."""
    reason_references = request.get("reasonReference") or []
    if reason_references:
        return reason_references[0].get("reference"), None

    reason_codes = request.get("reasonCode") or []
    if reason_codes:
        concept = reason_codes[0]
        text = concept.get("text")
        if not text:
            codings = concept.get("coding") or []
            text = codings[0].get("display") if codings else None
        return None, text

    return None, None


class ObservationValue(BaseModel):
    """One dated result within a lab trend."""

    reference: str = Field(
        description="FHIR reference to the Observation, e.g. 'Observation/9931'."
    )
    effective_date: str | None = Field(description="When this result was recorded.")
    value: float | str | None = Field(
        description=(
            "The result's numeric value when the Observation carries one (most labs). "
            "A text value when it doesn't. Null if neither is present."
        )
    )
    unit: str | None = Field(
        description="The unit for a numeric value, e.g. '%'. Null for a text value."
    )


class LabTrendResult(BaseModel):
    """A patient's results for one lab code, over one time window."""

    patient_reference: str = Field(description="Echoes the input, e.g. 'Patient/2685'.")
    code: str = Field(description="Echoes the input, e.g. 'http://loinc.org|4548-4'.")
    window_start: str = Field(description="Echoes the input start_date.")
    window_end: str = Field(
        description="The end_date used: either the input, or today's date if none was given."
    )
    total_ever: int | None = Field(
        description=(
            "How many results this patient has for this code, ever, with no date filter. "
            "Null means the server declined to count. Compare against total_in_window: "
            "a code present here but absent there is a genuine gap, not a code the patient "
            "never had at all — those are different findings and this tool reports both "
            "rather than collapsing them into one number."
        )
    )
    total_in_window: int | None = Field(
        description="How many of those results fall within window_start..window_end, inclusive."
    )
    returned: int = Field(
        description="How many results are in `values` (capped, see values' own note)."
    )
    values: list[ObservationValue] = Field(
        description=(
            "Results within the window, newest first. Capped by `count`; "
            "total_in_window is the true count."
        )
    )


def _resolve_window_end(end_date: str | None) -> str:
    """today's date, in the server's own clock, when the caller doesn't supply one."""
    return end_date or date.today().isoformat()


def _validate_window(start_date: str, end_date: str) -> None:
    """Reject a malformed or backwards window before it reaches the FHIR server.

    Raises FhirError rather than a bare ValueError so this reaches the model
    as an actionable message via _actionable_errors, the same as a failure
    that came from the FHIR server itself rather than from validation here.
    """
    try:
        parsed_start = date.fromisoformat(start_date)
        parsed_end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise FhirError(
            f"start_date and end_date must be ISO dates like '2026-02-28'. Got "
            f"start_date={start_date!r}, end_date={end_date!r}."
        ) from exc

    if parsed_start > parsed_end:
        raise FhirError(
            f"start_date ({start_date}) is after end_date ({end_date}). "
            f"Swap them, or omit end_date to default to today."
        )


def _extract_observation_value(resource: dict[str, Any]) -> tuple[float | str | None, str | None]:
    """Get a numeric value and unit when present, a text value when not.

    Most lab Observations carry valueQuantity; a handful of other Observation
    shapes (not expected for the numeric lab codes this tool targets, but not
    this tool's job to reject) carry valueString instead. Reporting nothing
    for either would be a silent gap in a result that is supposed to prove a
    lab result did or didn't exist.
    """
    quantity = resource.get("valueQuantity")
    if quantity is not None:
        return quantity.get("value"), quantity.get("unit")

    text = resource.get("valueString")
    if text is not None:
        return text, None

    return None, None


class ProblemResult(BaseModel):
    """One condition judged to be a real medical problem, not just anything
    FHIR happened to record about the patient."""

    reference: str = Field(description="FHIR reference to the Condition, e.g. 'Condition/8871'.")
    display_text: str = Field(
        description="The condition's display text, e.g. 'Essential hypertension (disorder)'."
    )
    snomed_code: str | None = Field(description="The SNOMED CT code, or null if none was coded.")
    onset_date: str | None = Field(description="When this condition began, if recorded.")
    clinical_status: str | None = Field(
        description="e.g. 'active'. Every entry here matches the active filter below."
    )


class ProblemListResult(BaseModel):
    """A patient's real medical problems, separated from everything else
    FHIR's Condition resource is also used to record."""

    patient_reference: str = Field(description="Echoes the input, e.g. 'Patient/2685'.")
    total_all_conditions: int | None = Field(
        description=(
            "Every Condition this patient has on record, any status, any kind — including "
            "things that are not medical problems at all, e.g. social or biographical facts "
            "Synthea also records as Conditions. Context for how much this tool filtered out."
        )
    )
    total_active_conditions: int | None = Field(
        description=(
            "How many of those are clinicalStatus=active, before the disorder filter below is "
            "applied. Compare against `returned`: if this tool examined fewer active conditions "
            "than exist (capped at 100), that would be visible as a gap between the two."
        )
    )
    returned: int = Field(
        description=(
            "How many active conditions were judged to be real medical problems. There is no "
            "separate, more-accurate 'total_problems' number: this judgment is a text check on "
            "SNOMED's naming convention (see problems' own field descriptions), not something "
            "the FHIR server can count for us, so this is the count of what was actually examined."
        )
    )
    problems: list[ProblemResult] = Field(
        description=(
            "One entry per Condition judged to be a real problem. Not deduplicated: if the same "
            "condition was genuinely recorded twice, both appear, with their own FHIR references."
        )
    )


def _is_disorder(condition_code: dict[str, Any] | None) -> bool:
    """True if a Condition's coded text carries SNOMED's '(disorder)' tag.

    Condition.category is useless for this on this project's data: it is
    uniformly "encounter-diagnosis" whether the Condition is a real diagnosis
    or something like "Has a criminal record", so it cannot tell the two
    apart. This is a text check on SNOMED's fully-specified-name convention
    instead, not a coded FHIR property — Synthea always appends the tag, so
    it works here, but a maintainer should not mistake this for a queryable
    field.
    """
    if not condition_code:
        return False
    text = (condition_code.get("text") or "").strip()
    return text.endswith("(disorder)")


def _extract_snomed_code(condition_code: dict[str, Any] | None) -> str | None:
    """Get the SNOMED CT code from a Condition.code CodeableConcept."""
    if not condition_code:
        return None
    for coding in condition_code.get("coding") or []:
        if coding.get("system") == _SNOMED_SYSTEM:
            return coding.get("code")
    return None


def _extract_clinical_status(condition: dict[str, Any]) -> str | None:
    """Get the clinicalStatus code, e.g. 'active', off a Condition resource."""
    codings = (condition.get("clinicalStatus") or {}).get("coding") or []
    return codings[0].get("code") if codings else None


class CohortPatient(BaseModel):
    """One patient matching a cohort search."""

    reference: str = Field(description="FHIR reference to the Patient, e.g. 'Patient/2685'.")
    age: int | None = Field(
        description=(
            "Age in whole years: as of today for a living patient, as of their recorded date "
            "of death for a deceased one (a dead patient's age does not keep incrementing). "
            "Null if birthDate is missing, or if the patient is known deceased but with no "
            "recorded date, since neither 'today' nor any other date can be trusted then."
        )
    )
    deceased: bool = Field(description="Whether the server records this patient as deceased.")


class CohortResult(BaseModel):
    """Patients who have a given condition, optionally narrowed by age.

    Deliberately narrow: a single condition code, a single age range, on
    Patient only. This is not a general cross-resource query tool — see
    self-docs/05-level2-tools-plan.md's Phase 4 for why that line is held
    deliberately, even though this tool crosses Condition and Patient to do
    the one thing it does.
    """

    code: str = Field(description="Echoes the input, e.g. 'http://snomed.info/sct|44054006'.")
    min_age: int | None = Field(description="Echoes the input.")
    max_age: int | None = Field(description="Echoes the input.")
    total_matching_conditions: int | None = Field(
        description=(
            "How many Condition resources matched this code, as reported by the FHIR server. "
            "Not the number of patients: a patient recorded with this condition twice counts "
            "twice here, but once in `returned`, which counts unique patients. Read `returned` "
            "for cohort size, this field only for a sense of how much was examined."
        )
    )
    returned: int = Field(
        description="How many unique patients matched, after deduplication and any age filter."
    )
    patients: list[CohortPatient] = Field(description="The matching patients themselves.")


def _age_reference_date(patient: dict[str, Any]) -> date | None:
    """The date to compute a patient's age as of: today if alive, their date
    of death if not. Returns None when the patient is known deceased but the
    server recorded no date, since guessing an age as of "today" for someone
    already dead would be wrong, not just imprecise.
    """
    deceased_datetime = patient.get("deceasedDateTime")
    if isinstance(deceased_datetime, str) and deceased_datetime:
        try:
            return date.fromisoformat(deceased_datetime[:10])
        except ValueError:
            return None

    if patient.get("deceasedBoolean") is True:
        return None

    return date.today()


def _compute_age(birth_date: str | None, as_of: date | None) -> int | None:
    """Whole years between a birth date and a reference date."""
    if not birth_date or as_of is None:
        return None
    try:
        born = date.fromisoformat(birth_date)
    except ValueError:
        return None

    age = as_of.year - born.year
    if (as_of.month, as_of.day) < (born.month, born.day):
        age -= 1
    return age


def register(mcp: MCPServer, settings: Settings) -> None:
    """Attach the Level 2 tools to an MCP server.

    Args:
        mcp: The server to register on.
        settings: Resolved configuration. Unused directly by Level 2 tools so
            far, accepted for signature symmetry with tools_level1.register
            and because a future Level 2 tool is likely to need it.
    """

    def _client(ctx: Context[AppContext]):
        return ctx.request_context.lifespan_context.fhir

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get active medications",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def get_active_medications(
        patient_id: Annotated[
            str, Field(description="The logical id of the patient, e.g. '2685'.")
        ],
        ctx: Context[AppContext],
    ) -> ActiveMedicationsResult:
        """Get everything a patient is currently prescribed, with why when recorded.

        This resolves what Level 1's search_resources cannot do in one call:
        about 30% of medication records only reference a separate Medication
        resource rather than naming the drug inline, and following that
        reference is exactly the step FHIR agent research has found models
        fail most often. This tool does that resolution once, here, so the
        caller always gets an actual drug name back.

        Only active medications are returned. A stopped or completed
        prescription is not part of what a patient is currently taking, which
        is the question this tool answers.
        """
        client = _client(ctx)
        bundle = await client.search(
            "MedicationRequest",
            {
                "patient": patient_id,
                "status": "active",
                "_include": "MedicationRequest:medication",
                "_count": 100,
                "_total": "accurate",
            },
        )

        entries = bundle.get("entry") or []
        included_medications = {
            f"Medication/{resource['id']}": resource
            for entry in entries
            if (resource := entry.get("resource") or {}).get("resourceType") == "Medication"
        }

        results: list[MedicationResult] = []
        for entry in entries:
            resource = entry.get("resource") or {}
            if resource.get("resourceType") != "MedicationRequest":
                continue

            concept = _resolve_medication(resource, included_medications)
            medication_text, rxnorm_code = _describe_medication(concept)
            reason_reference, reason_text = _describe_reason(resource)

            results.append(
                MedicationResult(
                    reference=f"MedicationRequest/{resource.get('id')}",
                    medication_text=medication_text,
                    rxnorm_code=rxnorm_code,
                    authored_on=resource.get("authoredOn"),
                    reason_reference=reason_reference,
                    reason_text=reason_text,
                )
            )

        return ActiveMedicationsResult(
            patient_reference=f"Patient/{patient_id}",
            total_matching=bundle.get("total"),
            returned=len(results),
            medications=results,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get lab result trend",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def get_lab_trend(
        patient_id: Annotated[
            str, Field(description="The logical id of the patient, e.g. '2685'.")
        ],
        code: Annotated[
            str,
            Field(
                description=(
                    "A system|code pair identifying the lab, e.g. 'http://loinc.org|4548-4' for "
                    "HbA1c. Pass the exact code; this tool does not search by name."
                )
            ),
        ],
        start_date: Annotated[
            str,
            Field(description="Start of the window to check, as an ISO date, e.g. '2026-02-28'."),
        ],
        end_date: Annotated[
            str | None,
            Field(description="End of the window, as an ISO date. Defaults to today if omitted."),
        ] = None,
        count: Annotated[
            int,
            Field(
                description=(
                    f"Maximum results to return, 1 to {MAX_PAGE_SIZE}. "
                    f"Defaults to {DEFAULT_PAGE_SIZE}."
                ),
                ge=1,
                le=MAX_PAGE_SIZE,
            ),
        ] = DEFAULT_PAGE_SIZE,
        ctx: Context[AppContext] = None,  # type: ignore[assignment]
    ) -> LabTrendResult:
        """Get a patient's results for one lab code, and say plainly if there aren't any.

        Reports two counts, not one, because "no result" is ambiguous
        otherwise: total_ever (has this code ever been recorded at all, with
        no date filter) and total_in_window (how many fall in the window
        asked about). A patient who has never had this test and a patient
        whose last one was years ago produce different total_ever values but
        could otherwise look identical — proving a care gap depends on
        telling those two apart, not just seeing an empty page.

        This tool does not compute start_date for you from something like
        "6 months ago" — pass the literal date. window_start/window_end in
        the result echo exactly what was searched, so a miscalculated date is
        visible in the response rather than silently baked into a count with
        no way to double-check it.
        """
        client = _client(ctx)
        window_end = _resolve_window_end(end_date)
        _validate_window(start_date, window_end)

        ever_bundle = await client.search(
            "Observation",
            {"patient": patient_id, "code": code, "_total": "accurate", "_count": 1},
        )

        window_bundle = await client.search(
            "Observation",
            {
                "patient": patient_id,
                "code": code,
                "date": [f"ge{start_date}", f"le{window_end}"],
                "_sort": "-date",
                "_total": "accurate",
                "_count": count,
            },
        )

        values: list[ObservationValue] = []
        for entry in window_bundle.get("entry") or []:
            resource = entry.get("resource") or {}
            if resource.get("resourceType") != "Observation":
                continue
            value, unit = _extract_observation_value(resource)
            values.append(
                ObservationValue(
                    reference=f"Observation/{resource.get('id')}",
                    effective_date=resource.get("effectiveDateTime"),
                    value=value,
                    unit=unit,
                )
            )

        return LabTrendResult(
            patient_reference=f"Patient/{patient_id}",
            code=code,
            window_start=start_date,
            window_end=window_end,
            total_ever=ever_bundle.get("total"),
            total_in_window=window_bundle.get("total"),
            returned=len(values),
            values=values,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get problem list",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def get_problem_list(
        patient_id: Annotated[
            str, Field(description="The logical id of the patient, e.g. '2685'.")
        ],
        ctx: Context[AppContext],
    ) -> ProblemListResult:
        """Get what is actually wrong with this patient, medically.

        FHIR records a Condition resource for anything noted about a patient
        during a visit, not just diseases: on this project's own data, one
        patient's 73 Condition entries include "Received higher education"
        and "Has a criminal record" alongside "Essential hypertension" and
        "Type 2 diabetes" — all the exact same resource type, with no
        reliable field marking one a real medical problem and the other
        background trivia. This tool filters to the ones that are: active,
        and carrying SNOMED's "(disorder)" tag on their coded name.

        Duplicates are not collapsed. If a condition genuinely appears twice
        in the record, both appear here, each with its own reference.
        """
        client = _client(ctx)

        all_bundle = await client.search(
            "Condition",
            {"patient": patient_id, "_total": "accurate", "_count": 1},
        )
        active_bundle = await client.search(
            "Condition",
            {
                "patient": patient_id,
                "clinical-status": "active",
                "_total": "accurate",
                "_count": 100,
            },
        )

        problems: list[ProblemResult] = []
        for entry in active_bundle.get("entry") or []:
            resource = entry.get("resource") or {}
            if resource.get("resourceType") != "Condition":
                continue

            code = resource.get("code")
            if not _is_disorder(code):
                continue

            problems.append(
                ProblemResult(
                    reference=f"Condition/{resource.get('id')}",
                    display_text=(code or {}).get("text") or "(no display text)",
                    snomed_code=_extract_snomed_code(code),
                    onset_date=resource.get("onsetDateTime"),
                    clinical_status=_extract_clinical_status(resource),
                )
            )

        return ProblemListResult(
            patient_reference=f"Patient/{patient_id}",
            total_all_conditions=all_bundle.get("total"),
            total_active_conditions=active_bundle.get("total"),
            returned=len(problems),
            problems=problems,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Find cohort by condition",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def find_cohort(
        code: Annotated[
            str,
            Field(
                description=(
                    "A system|code pair identifying the condition, e.g. "
                    "'http://snomed.info/sct|44054006' for type 2 diabetes."
                )
            ),
        ],
        ctx: Context[AppContext],
        min_age: Annotated[
            int | None,
            Field(description="Only include patients at least this old. Omit for no lower bound."),
        ] = None,
        max_age: Annotated[
            int | None,
            Field(description="Only include patients at most this old. Omit for no upper bound."),
        ] = None,
    ) -> CohortResult:
        """Find every patient recorded with one specific condition, optionally by age.

        Deliberately narrow, on purpose: one condition code, one age range,
        nothing else. A question spanning more than one criterion (a
        condition AND a lab value AND a medication, say) needs several calls
        plus reasoning over the results, the same as Level 1's
        search_resources — this tool does not plan that reasoning for you.

        A patient's age is computed as of today if they are alive, or as of
        their recorded date of death if they are not (age null if that date
        is unknown). A patient whose age cannot be determined is excluded
        whenever min_age or max_age is given, since neither including nor
        excluding them could be confirmed correct.
        """
        client = _client(ctx)

        seen_patients: dict[str, dict[str, Any]] = {}
        total_matching_conditions: int | None = None
        examined = 0
        # Far above any realistic population on this substrate; a guard against
        # a runaway loop, not a limit expected to bind in practice.
        safety_cap = 2000

        bundle: dict[str, Any] | None = await client.search(
            "Condition",
            {
                "code": code,
                "_include": "Condition:subject",
                "_count": 100,
                "_total": "accurate",
            },
        )

        while bundle is not None and examined < safety_cap:
            if total_matching_conditions is None:
                total_matching_conditions = bundle.get("total")

            entries = bundle.get("entry") or []
            for entry in entries:
                resource = entry.get("resource") or {}
                if resource.get("resourceType") == "Patient":
                    seen_patients.setdefault(f"Patient/{resource['id']}", resource)
            examined += len(entries)

            next_url = next(
                (
                    link["url"]
                    for link in bundle.get("link") or []
                    if link.get("relation") == "next" and link.get("url")
                ),
                None,
            )
            bundle = await client.follow(next_url) if next_url else None

        patients: list[CohortPatient] = []
        for reference, patient in seen_patients.items():
            deceased = (
                bool(patient.get("deceasedDateTime")) or patient.get("deceasedBoolean") is True
            )
            age = _compute_age(patient.get("birthDate"), _age_reference_date(patient))

            if min_age is not None and (age is None or age < min_age):
                continue
            if max_age is not None and (age is None or age > max_age):
                continue

            patients.append(CohortPatient(reference=reference, age=age, deceased=deceased))

        return CohortResult(
            code=code,
            min_age=min_age,
            max_age=max_age,
            total_matching_conditions=total_matching_conditions,
            returned=len(patients),
            patients=patients,
        )


__all__ = [
    "ActiveMedicationsResult",
    "CohortPatient",
    "CohortResult",
    "LabTrendResult",
    "MedicationResult",
    "ObservationValue",
    "ProblemListResult",
    "ProblemResult",
    "register",
]
