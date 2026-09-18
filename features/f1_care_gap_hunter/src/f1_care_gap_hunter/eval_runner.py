"""CLI: run the F1 v1 agent across a cohort, checkpointed, graded against
the oracle - plus the three baselines printed alongside every real run.

    uv run python -m f1_care_gap_hunter.eval_runner --limit 5
    uv run python -m f1_care_gap_hunter.eval_runner --provider gemini --limit 20

Requires fhir-mcp reachable (default http://127.0.0.1:3001/mcp) and, for
--provider ollama (the default), a running `ollama serve` with the model
pulled. See ../../.env.example.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date
from pathlib import Path

from agentward_harness.model import ModelConfig
from dotenv import load_dotenv

from .bundles import load_all_patients
from .checkpoint import run_with_checkpoint
from .grading import AgentFinding, AgentRun, GradeReport, compute_baselines, grade_run
from .harness.v1.gap_agent import run_agent_on_patient
from .oracle import run_oracle
from .patient_map import build_patient_map, load_cached_map, save_cached_map

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FEATURE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FHIR_DIR = _REPO_ROOT / "data" / "synthea_output" / "seed-1000-n200" / "fhir"
_RUNS_DIR = _FEATURE_ROOT / "runs"

# A .env file does nothing on its own - something has to load it into the
# process environment before ModelConfig.from_env() reads os.environ. Must
# happen at import time, before main() runs, since --provider only overrides
# MODEL_PROVIDER after this.
load_dotenv(_FEATURE_ROOT / ".env")

# Pinned rather than date.today(): the oracle's two date-sensitive checks
# drift the answer key over time (+1/+4/+10 findings at +30/+90/+180 days on
# this cohort), so the agent and the oracle must share one fixed "today" or
# their answers stop being comparable. Bump deliberately, matching
# overview/scripts/build_viz_data.py's own AS_OF, not as a side effect.
DEFAULT_AS_OF = date(2026, 9, 10)


def _agent_run_to_json(run: AgentRun) -> dict:
    return {
        "patient_synthea_id": run.patient_synthea_id,
        "terminated_by": run.terminated_by,
        "findings": [
            {"gap_type": f.gap_type, "rationale": f.rationale, "evidence": f.evidence}
            for f in run.findings
        ],
    }


def _agent_run_from_json(data: dict) -> AgentRun:
    return AgentRun(
        patient_synthea_id=data["patient_synthea_id"],
        terminated_by=data["terminated_by"],
        findings=[AgentFinding(**f) for f in data["findings"]],
    )


async def _run_one_async(
    synthea_id: str,
    *,
    hapi_id_by_synthea: dict[str, str],
    mcp_url: str,
    config: ModelConfig,
    as_of: date,
    max_steps: int,
    trajectory_path: Path,
) -> AgentRun:
    hapi_id = hapi_id_by_synthea[synthea_id]
    result = await run_agent_on_patient(
        hapi_patient_id=hapi_id,
        patient_synthea_id=synthea_id,
        mcp_url=mcp_url,
        config=config,
        as_of=as_of,
        max_steps=max_steps,
        trajectory_jsonl_path=str(trajectory_path),
    )
    return result.agent_run


def _print_report(label: str, report: GradeReport) -> None:
    print(f"--- {label} ---")
    print(
        f"  graded={report.patients_graded} "
        f"excluded_non_terminating={report.patients_excluded_non_terminating} "
        f"patients_with_false_gap={report.patients_with_false_gap} "
        f"terminated_by={dict(report.terminated_by_counts)}"
    )
    for gap_type, score in sorted(report.by_gap_type.items()):
        p = f"{score.precision:.3f}" if score.precision is not None else "n/a"
        r = f"{score.recall:.3f}" if score.recall is not None else "n/a"
        print(
            f"    {gap_type:35s} P={p:>6} R={r:>6} "
            f"tp={score.true_positives} fp={score.false_positives} fn={score.false_negatives}"
        )
    overall = report.overall
    p = f"{overall.precision:.3f}" if overall.precision is not None else "n/a"
    r = f"{overall.recall:.3f}" if overall.recall is not None else "n/a"
    print(f"    {'OVERALL (do not lead with this - see grading.py)':50s} P={p:>6} R={r:>6}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fhir-dir", type=Path, default=_DEFAULT_FHIR_DIR)
    parser.add_argument("--mcp-url", default="http://127.0.0.1:3001/mcp")
    parser.add_argument("--provider", choices=["ollama", "gemini", "groq"], default=None)
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N patients.")
    parser.add_argument("--max-steps", type=int, default=18)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=DEFAULT_AS_OF,
        help="Must match the oracle's as_of, or the answer key drifts (default 2026-09-10).",
    )
    parser.add_argument(
        "--run-id", default=None, help="Reuse a prior value to resume that run's checkpoint."
    )
    args = parser.parse_args()

    if args.provider:
        os.environ["MODEL_PROVIDER"] = args.provider
    config = ModelConfig.from_env()

    model_slug = config.model.replace(":", "-")
    run_id = args.run_id or f"f1_{config.provider}_{model_slug}_{args.as_of.isoformat()}"
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = _RUNS_DIR / f"{run_id}.checkpoint.jsonl"
    trajectory_path = _RUNS_DIR / f"{run_id}.trajectory.jsonl"

    print(f"Loading patients from {args.fhir_dir} ...")
    patients = load_all_patients(args.fhir_dir)
    if args.limit:
        patients = patients[: args.limit]
    print(f"{len(patients)} patients loaded.")

    print(f"Computing oracle answer key (as_of={args.as_of.isoformat()}) ...")
    oracle_findings = run_oracle(args.fhir_dir, as_of=args.as_of)

    map_path = _RUNS_DIR / "patient_map.json"
    hapi_id_by_synthea = load_cached_map(map_path) or {}
    missing_ids = [p.synthea_id for p in patients if p.synthea_id not in hapi_id_by_synthea]
    if missing_ids:
        print(f"Building patient id map via {args.mcp_url} ({len(missing_ids)} lookups) ...")
        hapi_id_by_synthea.update(asyncio.run(build_patient_map(missing_ids, args.mcp_url)))
        save_cached_map(map_path, hapi_id_by_synthea)

    def run_one(synthea_id: str) -> AgentRun:
        return asyncio.run(
            _run_one_async(
                synthea_id,
                hapi_id_by_synthea=hapi_id_by_synthea,
                mcp_url=args.mcp_url,
                config=config,
                as_of=args.as_of,
                max_steps=args.max_steps,
                trajectory_path=trajectory_path,
            )
        )

    print(f"Running agent ({config.provider}/{config.model}). Checkpoint: {checkpoint_path}\n")
    agent_runs = run_with_checkpoint(
        [p.synthea_id for p in patients],
        run_one,
        checkpoint_path,
        to_json=_agent_run_to_json,
        from_json=_agent_run_from_json,
    )

    print("\n=== Grading ===\n")
    _print_report(f"{config.provider}/{config.model}", grade_run(oracle_findings, agent_runs))

    print("=== Baselines (see grading.py's module docstring for why these matter) ===\n")
    for name, baseline_report in compute_baselines(patients, oracle_findings, args.as_of).items():
        _print_report(name, baseline_report)


if __name__ == "__main__":
    main()
