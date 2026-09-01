"""Run every registered gap check across a cohort, output a ranked worklist.

No model involved, same as substrate/fhir-mcp/scripts/smoke_test.py's own
"no model involved" pattern: this is a plain pass over the bundles, printing
what it found.

Usage:
    uv run python -m f1_care_gap_hunter.oracle <fhir_dir>
    uv run python -m f1_care_gap_hunter.oracle ../../data/synthea_output/seed-1000-n200/fhir
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .bundles import PatientRecord, load_all_patients
from .gaps import (
    Finding,
    check_diabetic_missing_eye_exam,
    check_diabetic_missing_hba1c,
    check_missing_colorectal_screening,
    check_uncontrolled_bp_despite_therapy,
)

GapCheck = Callable[[PatientRecord, date | None], Finding | None]

# Every check registered here runs against every patient. Adding a new gap
# type is: write the check in gaps.py, add it here, nothing else changes.
CHECKS: list[GapCheck] = [
    check_diabetic_missing_hba1c,
    check_diabetic_missing_eye_exam,
    check_uncontrolled_bp_despite_therapy,
    check_missing_colorectal_screening,
]


def run_oracle(fhir_dir: Path, as_of: date | None = None) -> list[Finding]:
    """Run every registered check against every patient in `fhir_dir`.

    Args:
        fhir_dir: A synthea_output/<label>/fhir/ directory.
        as_of: The date every check measures "overdue" from. Defaults to
            today; a fixed value makes a run reproducible.

    Returns:
        One Finding per (patient, gap) pair. A patient with no gaps
        contributes nothing; a patient with several gaps appears once per gap.
    """
    as_of = as_of or date.today()
    patients = load_all_patients(fhir_dir)

    findings: list[Finding] = []
    for patient in patients:
        for check in CHECKS:
            finding = check(patient, as_of)
            if finding is not None:
                findings.append(finding)
    return findings


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <fhir_dir>", file=sys.stderr)
        raise SystemExit(2)

    fhir_dir = Path(sys.argv[1])
    if not fhir_dir.is_dir():
        print(f"No such directory: {fhir_dir}", file=sys.stderr)
        raise SystemExit(1)

    findings = run_oracle(fhir_dir)

    patients_with_gaps = len({f.patient_synthea_id for f in findings})
    print(f"Checked patients in {fhir_dir}")
    print(f"Found {len(findings)} gaps across {patients_with_gaps} patients")
    print()
    print(json.dumps([asdict(f) for f in findings], indent=2))


if __name__ == "__main__":
    main()
