"""synthea_id <-> HAPI id: the mapping every live run needs.

Synthea bundles are POSTed to HAPI, so HAPI mints its own sequential ids and
discards every id Synthea assigned - except Patient, which carries a separate
identifier (system=https://github.com/synthetichealth/synthea) that survives
the load intact and is searchable via `Patient?identifier=<uuid>` (confirmed
live, see bundles.PatientRecord.synthea_id's own docstring). Non-Patient
resources have no such anchor, which is why grading.py never compares
evidence references against the oracle's own.

This mapping is built grader/infra-side, not agent-side, on purpose: the
agent is never told about Synthea ids at all, so its prompt stays about the
clinical question, not about a data-loading accident. HAPI's ids are not
stable across a reload of the data, so a cached map must be rebuilt whenever
the FHIR server's data changes underneath it.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp import Client


async def build_patient_map(synthea_ids: list[str], mcp_url: str) -> dict[str, str]:
    """One `Patient?identifier=<uuid>` search per id, synthea_id -> hapi_id.

    Args:
        synthea_ids: Every patient's `PatientRecord.synthea_id`, e.g. from
            `bundles.load_all_patients`.
        mcp_url: The running fhir-mcp server, e.g. http://127.0.0.1:3001/mcp.

    Raises:
        ValueError: a synthea_id resolved to zero or more than one Patient,
            which would mean the loaded server data doesn't match what's on
            disk (a different cohort, or a reload that hasn't finished).
    """
    mapping: dict[str, str] = {}
    async with Client(mcp_url) as client:
        for synthea_id in synthea_ids:
            result = await client.call_tool(
                "search_resources",
                {
                    "resource_type": "Patient",
                    "search_params": {"identifier": synthea_id},
                    "count": 2,
                },
            )
            if result.is_error:
                text = "; ".join(getattr(b, "text", "") for b in result.content)
                raise ValueError(f"search_resources failed for identifier={synthea_id}: {text}")

            resources = result.structured_content["resources"]
            if len(resources) != 1:
                raise ValueError(
                    f"Expected exactly one Patient for identifier={synthea_id}, "
                    f"got {len(resources)}. Was the FHIR data reloaded?"
                )
            mapping[synthea_id] = str(resources[0]["id"])
    return mapping


def load_cached_map(path: Path) -> dict[str, str] | None:
    """A previously built map, or None if it doesn't exist yet."""
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_cached_map(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2) + "\n")


__all__ = ["build_patient_map", "load_cached_map", "save_cached_map"]
