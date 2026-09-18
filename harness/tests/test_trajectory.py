from __future__ import annotations

import json
from pathlib import Path

from agentward_harness.trajectory import TrajectoryEvent, TrajectoryLogger, summarize


class TestTrajectoryLogger:
    def test_emits_to_callback(self) -> None:
        events: list[TrajectoryEvent] = []
        logger = TrajectoryLogger("run-1", on_event=events.append)

        logger.run_started(task_id="patient-2657", provider="ollama", model="qwen3:8b", config={})
        logger.llm_call_started(step=0, message_count=2)

        assert len(events) == 2
        assert events[0].event_type == "run_started"
        assert events[0].run_id == "run-1"
        assert events[0].data["task_id"] == "patient-2657"
        assert events[1].step == 0

    def test_writes_jsonl_and_can_resume_reading(self, tmp_path: Path) -> None:
        path = tmp_path / "run.jsonl"

        with TrajectoryLogger("run-2", jsonl_path=str(path)) as logger:
            logger.run_started(task_id="patient-1", provider="ollama", model="qwen3:8b", config={})
            logger.tool_call_started(
                step=1, tool_name="get_problem_list", arguments={"patient_id": "1"}, source="mcp"
            )
            logger.run_finished(
                findings=[],
                terminated_by="submit",
                total_steps=1,
                total_tokens=100,
                duration_ms=12.5,
            )

        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3
        parsed = [json.loads(line) for line in lines]
        assert parsed[0]["event_type"] == "run_started"
        assert parsed[1]["data"]["source"] == "mcp"
        assert parsed[2]["data"]["terminated_by"] == "submit"

    def test_no_sinks_does_not_error(self) -> None:
        logger = TrajectoryLogger("run-3")
        logger.run_started(task_id="x", provider="ollama", model="qwen3:8b", config={})
        logger.close()


class TestSummarize:
    def test_short_value_unchanged(self) -> None:
        assert summarize({"a": 1}) == '{"a": 1}'

    def test_long_string_truncated_with_length_note(self) -> None:
        long_text = "x" * 1000
        result = summarize(long_text, max_len=50)
        assert result.startswith("x" * 50)
        assert "1000 chars total" in result
