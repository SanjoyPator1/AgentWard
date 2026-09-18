from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from f1_care_gap_hunter.bundles import load_all_patients
from f1_care_gap_hunter.grading import (
    GAP_TYPES,
    AgentFinding,
    AgentRun,
    compute_baselines,
    grade_run,
)
from f1_care_gap_hunter.oracle import run_oracle

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FHIR_DIR = _REPO_ROOT / "data" / "synthea_output" / "seed-1000-n200" / "fhir"
_AS_OF = date(2026, 9, 10)

# data/ is gitignored (674MB of generated Synthea output) and may not exist
# on a fresh clone - skip rather than fail when it isn't there, but run for
# real whenever it is, since these are the numbers the whole grading design
# leans on (see grading.py's module docstring).
requires_real_cohort = pytest.mark.skipif(
    not _FHIR_DIR.is_dir(), reason=f"real Synthea cohort not present at {_FHIR_DIR}"
)


class TestGradeRun:
    @requires_real_cohort
    def test_perfect_agent_scores_one(self) -> None:
        oracle_findings = run_oracle(_FHIR_DIR, as_of=_AS_OF)

        by_patient: dict[str, set[str]] = {}
        for finding in oracle_findings:
            by_patient.setdefault(finding.patient_synthea_id, set()).add(finding.gap_type)

        agent_runs = [
            AgentRun(
                patient_synthea_id=patient_id,
                findings=[
                    AgentFinding(gap_type=gt, rationale="matches oracle") for gt in gap_types
                ],
                terminated_by="submit",
            )
            for patient_id, gap_types in by_patient.items()
        ]

        report = grade_run(oracle_findings, agent_runs)
        overall = report.overall
        assert overall.precision == 1.0
        assert overall.recall == 1.0
        assert report.patients_with_false_gap == 0

    def test_false_positive_counted_against_its_own_gap_type(self) -> None:
        oracle_findings: list = []
        agent_runs = [
            AgentRun(
                patient_synthea_id="p1",
                findings=[AgentFinding(gap_type="missing_colorectal_screening", rationale="x")],
                terminated_by="submit",
            )
        ]
        report = grade_run(oracle_findings, agent_runs)
        score = report.by_gap_type["missing_colorectal_screening"]
        assert score.false_positives == 1
        assert score.true_positives == 0
        assert report.patients_with_false_gap == 1

    def test_non_terminating_runs_excluded_not_scored_as_empty(self) -> None:
        from f1_care_gap_hunter.gaps import Finding

        oracle_findings = [
            Finding(
                patient_synthea_id="p1",
                patient_name="Test Patient",
                gap_type="missing_colorectal_screening",
                rationale="x",
            )
        ]
        agent_runs = [
            AgentRun(patient_synthea_id="p1", findings=[], terminated_by="budget"),
        ]
        report = grade_run(oracle_findings, agent_runs)

        assert report.patients_excluded_non_terminating == 1
        assert report.patients_graded == 0
        # Excluded, not silently scored as a false negative for guessing nothing.
        assert report.by_gap_type["missing_colorectal_screening"].false_negatives == 0

    def test_empty_batch_scores_have_no_denominator(self) -> None:
        report = grade_run([], [])
        assert report.overall.precision is None
        assert report.overall.recall is None


class TestGapTypesConstant:
    def test_matches_the_four_oracle_gap_types(self) -> None:
        assert GAP_TYPES == {
            "diabetic_missing_hba1c",
            "diabetic_missing_eye_exam",
            "uncontrolled_bp_despite_therapy",
            "missing_colorectal_screening",
        }


@requires_real_cohort
class TestBaselinesAgainstRealCohort:
    """These numbers are load-bearing for the whole grading design (see
    grading.py's module docstring) - verified once independently against the
    committed oracle fixture before the agent was ever run, and pinned here
    so a change to the oracle or the cohort surfaces immediately."""

    @pytest.fixture(scope="class")
    @classmethod
    def patients(cls) -> list:
        return load_all_patients(_FHIR_DIR)

    @pytest.fixture(scope="class")
    @classmethod
    def oracle_findings(cls) -> list:
        return run_oracle(_FHIR_DIR, as_of=_AS_OF)

    def test_always_empty_baseline(self, patients: list, oracle_findings: list) -> None:
        baselines = compute_baselines(patients, oracle_findings, _AS_OF)
        report = baselines["always_empty"]
        # Zero predictions makes precision 0/0 - undefined, not 0.0. Reporting
        # it as None rather than manufacturing a number is grading.py's own
        # documented choice (GapTypeScore.precision/recall docstrings).
        assert report.overall.precision is None
        assert report.overall.recall == 0.0
        assert report.patients_with_false_gap == 0

    def test_age_only_colorectal_guess_baseline(
        self, patients: list, oracle_findings: list
    ) -> None:
        baselines = compute_baselines(patients, oracle_findings, _AS_OF)
        report = baselines["age_only_colorectal_guess"]
        assert report.overall.precision == pytest.approx(0.485, abs=0.001)
        assert report.overall.recall == pytest.approx(0.493, abs=0.001)
        assert report.patients_with_false_gap == 35

    def test_always_all_four_baseline(self, patients: list, oracle_findings: list) -> None:
        baselines = compute_baselines(patients, oracle_findings, _AS_OF)
        report = baselines["always_all_four"]
        assert report.overall.recall == 1.0
        assert report.overall.precision == pytest.approx(0.077, abs=0.001)
