"""Grade an agent's findings against the oracle's answer key.

Comparison is by (patient, gap_type) set membership only. Evidence
references are never compared to the oracle's own: non-Patient resources
carry no anchor across the Synthea-to-HAPI id boundary (see patient_map.py's
module docstring), so the two id spaces are permanently incomparable.
Checking an agent's evidence for resolvability (does the cited reference
exist, does it belong to this patient) is a live-run concern, not a
post-hoc grading one, and belongs next to the run itself.

Reporting rule, load-bearing: report per gap type, never lead with a pooled
number. missing_colorectal_screening is 33 of the 67 oracle findings on this
cohort and reduces to "alive, aged 45-75, no colonoscopy in 10 years" - a
pooled score mostly measures whether the agent can read a birthDate.

Three baselines are computed alongside every real run for exactly this
reason. Verified against the committed oracle fixture
(overview/src/data/{gap-findings,cohort}.json, 217 patients, as_of
2026-09-10):

    always submit empty            P=0.000  R=0.000  patients_with_false_gap=0
    age-only colorectal guess       P=0.485  R=0.493  patients_with_false_gap=35
    always submit all four          P=0.077  R=1.000  patients_with_false_gap=214

An agent making zero clinical tool calls already reaches P=0.485 by guessing
colorectal-by-age alone - a real run landing near that number is not doing
the task, however plausible its trace looks. And the silent (always-empty)
agent has a *perfect* false-gap rate of 0.000, which is why that metric must
never be reported alone: it directly rewards doing nothing.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from agentward_harness.trajectory import TerminationReason

from .bundles import PatientRecord
from .gaps import Finding

GAP_TYPES: frozenset[str] = frozenset(
    {
        "diabetic_missing_hba1c",
        "diabetic_missing_eye_exam",
        "uncontrolled_bp_despite_therapy",
        "missing_colorectal_screening",
    }
)

# Mirrors gaps.py's own USPSTF colorectal age window (45-75) as an
# independent constant, on purpose: grading must not import the checks it
# grades, the same rule bundles.py already follows for fhir_mcp's age logic.
_CRC_MIN_AGE = 45
_CRC_MAX_AGE = 75


@dataclass
class AgentFinding:
    """One (gap_type, rationale, evidence) the agent submitted for one patient."""

    gap_type: str
    rationale: str
    evidence: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AgentRun:
    """What one `run_agent_on_patient()` call produced, in grading-ready form.

    `patient_synthea_id` is carried through so this can be compared directly
    against `run_oracle()`'s output, even though the agent itself only ever
    saw the HAPI id (see patient_map.py) - the id translation happens once,
    grader-side, well before grading itself.
    """

    patient_synthea_id: str
    findings: list[AgentFinding]
    terminated_by: TerminationReason


@dataclass
class GapTypeScore:
    """TP/FP/FN for one gap type, or the pooled total under the special key
    used by `GradeReport.overall`."""

    gap_type: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float | None:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else None

    @property
    def recall(self) -> float | None:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else None


@dataclass
class GradeReport:
    """One run's grade. Print alongside `compute_baselines`' output, never
    alone - see the module docstring for why."""

    by_gap_type: dict[str, GapTypeScore]
    patients_graded: int
    patients_excluded_non_terminating: int
    patients_with_false_gap: int
    terminated_by_counts: dict[str, int]

    @property
    def overall(self) -> GapTypeScore:
        """The pooled total. Exists for completeness, not for leading a
        report with - see module docstring."""
        overall = GapTypeScore(gap_type="__overall__")
        for score in self.by_gap_type.values():
            overall.true_positives += score.true_positives
            overall.false_positives += score.false_positives
            overall.false_negatives += score.false_negatives
        return overall


def grade_run(oracle_findings: list[Finding], agent_runs: list[AgentRun]) -> GradeReport:
    """Compare one batch of agent runs against the oracle's findings.

    `agent_runs` should cover the same patients `oracle_findings` was
    computed over - typically all 217, not just the 48 with a gap. Without
    the no-gap patients in the batch, precision is unmeasurable: every false
    positive on a healthy patient would simply go uncounted.

    A run that did not end by calling `submit_findings` (`terminated_by !=
    "submit"`) is excluded from every P/R count and reported separately as
    an abstention, never silently graded as "no gaps" - a non-terminating
    agent would otherwise inherit the always-empty baseline's near-perfect
    score for doing nothing at all.
    """
    oracle_by_patient: dict[str, set[str]] = defaultdict(set)
    for finding in oracle_findings:
        oracle_by_patient[finding.patient_synthea_id].add(finding.gap_type)

    by_gap_type = {gap_type: GapTypeScore(gap_type=gap_type) for gap_type in GAP_TYPES}
    patients_with_false_gap = 0
    excluded = 0
    terminated_by_counts: dict[str, int] = defaultdict(int)

    for run in agent_runs:
        terminated_by_counts[run.terminated_by] += 1
        if run.terminated_by != "submit":
            excluded += 1
            continue

        expected = oracle_by_patient.get(run.patient_synthea_id, set())
        submitted = {finding.gap_type for finding in run.findings}

        if submitted - expected:
            patients_with_false_gap += 1

        for gap_type in GAP_TYPES:
            score = by_gap_type[gap_type]
            in_expected = gap_type in expected
            in_submitted = gap_type in submitted
            if in_expected and in_submitted:
                score.true_positives += 1
            elif in_submitted:
                score.false_positives += 1
            elif in_expected:
                score.false_negatives += 1

    return GradeReport(
        by_gap_type=by_gap_type,
        patients_graded=len(agent_runs) - excluded,
        patients_excluded_non_terminating=excluded,
        patients_with_false_gap=patients_with_false_gap,
        terminated_by_counts=dict(terminated_by_counts),
    )


def compute_baselines(
    patients: list[PatientRecord], oracle_findings: list[Finding], as_of: date
) -> dict[str, GradeReport]:
    """Three do-nothing-clever agents, graded the same way as a real run.

    Computed fresh from `patients` every call, rather than hardcoded, so
    they track the fixtures automatically if the cohort ever changes. The
    docstring numbers above are what this produces on the current 217-patient
    cohort - a useful sanity check if this function is ever touched.
    """

    def make_run(patient: PatientRecord, gap_types: set[str]) -> AgentRun:
        return AgentRun(
            patient_synthea_id=patient.synthea_id,
            findings=[
                AgentFinding(gap_type=gap_type, rationale="(baseline, not a real finding)")
                for gap_type in gap_types
            ],
            terminated_by="submit",
        )

    def age_only_colorectal_guess(patient: PatientRecord) -> set[str]:
        if patient.is_deceased:
            return set()
        age = patient.age(as_of=as_of)
        if age is not None and _CRC_MIN_AGE <= age <= _CRC_MAX_AGE:
            return {"missing_colorectal_screening"}
        return set()

    return {
        "always_empty": grade_run(oracle_findings, [make_run(p, set()) for p in patients]),
        "age_only_colorectal_guess": grade_run(
            oracle_findings, [make_run(p, age_only_colorectal_guess(p)) for p in patients]
        ),
        "always_all_four": grade_run(
            oracle_findings, [make_run(p, set(GAP_TYPES)) for p in patients]
        ),
    }


__all__ = [
    "GAP_TYPES",
    "AgentFinding",
    "AgentRun",
    "GapTypeScore",
    "GradeReport",
    "compute_baselines",
    "grade_run",
]
