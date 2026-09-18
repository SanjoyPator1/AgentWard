from __future__ import annotations

from pathlib import Path

from f1_care_gap_hunter.checkpoint import load_completed, run_with_checkpoint


def _to_json(value: str) -> dict:
    return {"value": value}


def _from_json(data: dict) -> str:
    return data["value"]


class TestRunWithCheckpoint:
    def test_fresh_run_computes_everything(self, tmp_path: Path) -> None:
        checkpoint_path = tmp_path / "run.jsonl"
        calls: list[str] = []

        def run_one(task_id: str) -> str:
            calls.append(task_id)
            return f"result-{task_id}"

        results = run_with_checkpoint(
            ["a", "b", "c"], run_one, checkpoint_path, to_json=_to_json, from_json=_from_json
        )

        assert results == ["result-a", "result-b", "result-c"]
        assert calls == ["a", "b", "c"]

    def test_resume_skips_completed_and_only_runs_the_rest(self, tmp_path: Path) -> None:
        checkpoint_path = tmp_path / "run.jsonl"
        calls: list[str] = []

        def run_one(task_id: str) -> str:
            calls.append(task_id)
            return f"result-{task_id}"

        # First "session": crashes after task "b" (simulated by only asking for a, b).
        run_with_checkpoint(
            ["a", "b"], run_one, checkpoint_path, to_json=_to_json, from_json=_from_json
        )
        calls.clear()

        # Second "session": resumes with the full task list.
        results = run_with_checkpoint(
            ["a", "b", "c"], run_one, checkpoint_path, to_json=_to_json, from_json=_from_json
        )

        assert calls == ["c"], "a and b must not be recomputed"
        assert results == ["result-a", "result-b", "result-c"]

    def test_a_crash_mid_run_loses_nothing_already_written(self, tmp_path: Path) -> None:
        checkpoint_path = tmp_path / "run.jsonl"

        def flaky_run_one(task_id: str) -> str:
            if task_id == "c":
                raise RuntimeError("simulated crash")
            return f"result-{task_id}"

        try:
            run_with_checkpoint(
                ["a", "b", "c", "d"],
                flaky_run_one,
                checkpoint_path,
                to_json=_to_json,
                from_json=_from_json,
            )
        except RuntimeError:
            pass

        completed = load_completed(checkpoint_path)
        assert set(completed) == {"a", "b"}

    def test_load_completed_on_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert load_completed(tmp_path / "does-not-exist.jsonl") == {}
