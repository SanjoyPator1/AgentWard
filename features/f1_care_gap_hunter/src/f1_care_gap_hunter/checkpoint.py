"""Append-only resume for long batch runs.

Every feature's eval run needs this same shape: given a list of task ids and
a function that computes one result, skip whatever is already in the
checkpoint file and append whatever is new the moment it finishes - so a
crash at patient 140/217 loses nothing before it. Feature-owned rather than
shared in harness/, since there is no competing design to version here (see
the self-docs conversation), just a place it needs to live.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def load_completed(path: Path) -> dict[str, dict[str, Any]]:
    """Every task_id already recorded in a checkpoint file, mapped to its
    raw JSON result. Empty if the file doesn't exist yet - the normal case
    for a fresh run."""
    if not path.exists():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        completed[record["task_id"]] = record["result"]
    return completed


def run_with_checkpoint(
    task_ids: Iterable[str],
    run_one: Callable[[str], T],
    checkpoint_path: Path,
    *,
    to_json: Callable[[T], dict[str, Any]],
    from_json: Callable[[dict[str, Any]], T],
) -> list[T]:
    """Run `run_one` for every task_id not already checkpointed, appending
    each result as soon as it finishes, and return every result - freshly
    computed or recovered from disk - in `task_ids` order.

    `to_json`/`from_json` round-trip one result through the checkpoint file,
    so a resumed run gets back the same shape (e.g. a grading.AgentRun) a
    fresh run would have produced, not a raw dict the caller has to
    special-case.
    """
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    completed = load_completed(checkpoint_path)

    results: list[T] = []
    with checkpoint_path.open("a") as f:
        for task_id in task_ids:
            if task_id in completed:
                results.append(from_json(completed[task_id]))
                continue
            result = run_one(task_id)
            f.write(json.dumps({"task_id": task_id, "result": to_json(result)}) + "\n")
            f.flush()
            results.append(result)
    return results


__all__ = ["load_completed", "run_with_checkpoint"]
