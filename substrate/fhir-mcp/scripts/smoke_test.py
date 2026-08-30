"""End-to-end check of fhir-mcp with no model involved.

Connects as a real MCP client over streamable HTTP, calls every tool against
the loaded Synthea data, and prints what came back.

This is the rule the project brief's "oracle before agent" discipline turns
into at the substrate stage: no tool ships without a plain script that calls it
and shows its output. A tool that has only ever been exercised by an agent has
not been tested, it has been guessed at.

Usage, with the server already running:

    uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from mcp import Client

SERVER_URL = os.environ.get("FHIR_MCP_URL", "http://localhost:3001/mcp")

# Widths chosen so output stays readable in a normal terminal.
BANNER = "=" * 72
RULE = "-" * 72


def show(label: str, value: Any, limit: int = 400) -> None:
    """Print a value, truncated, so one large resource cannot flood the output."""
    text = json.dumps(value, indent=2, default=str) if not isinstance(value, str) else value
    if len(text) > limit:
        text = text[:limit] + f"\n  ... [{len(text) - limit} more characters]"
    print(f"{label}:\n{text}")


async def main() -> int:
    print(BANNER)
    print(f"fhir-mcp smoke test against {SERVER_URL}")
    print(BANNER)

    try:
        async with Client(SERVER_URL) as client:
            # ---------------------------------------------------------------
            # 1. Discovery. What does this server say it offers?
            # ---------------------------------------------------------------
            print("\n[1] tools/list")
            print(RULE)
            tools = await client.list_tools()
            for tool in tools.tools:
                print(f"  {tool.name}")
                print(f"      {(tool.description or '').strip().splitlines()[0]}")
            print(f"\n  {len(tools.tools)} tools registered.")

            # ---------------------------------------------------------------
            # 2. A search. Confirms the server reaches HAPI FHIR at all, and
            #    shows the total-vs-returned distinction the tools care about.
            # ---------------------------------------------------------------
            print("\n[2] search_resources: Patient, page size 3")
            print(RULE)
            result = await client.call_tool(
                "search_resources",
                {"resource_type": "Patient", "count": 3},
            )
            data = result.structured_content
            assert data is not None, "expected structured content from search_resources"
            print(f"  total_matching : {data['total_matching']}")
            print(f"  returned       : {data['returned']}")
            print(f"  next_page_token: {str(data['next_page_token'])[:60]}...")

            first_patient_id = None
            if data["resources"]:
                first = data["resources"][0]
                first_patient_id = first.get("id")
                names = first.get("name") or [{}]
                given = (names[0].get("given") or ["?"])[0]
                family = names[0].get("family", "?")
                print(f"  first patient  : {given} {family} (id={first_patient_id})")

            # ---------------------------------------------------------------
            # 3. Paging. The stateless handle round trip: the token came out of
            #    the last result and goes back in as an ordinary argument.
            # ---------------------------------------------------------------
            if data["next_page_token"]:
                print("\n[3] get_next_page")
                print(RULE)
                page2 = await client.call_tool(
                    "get_next_page", {"page_token": data["next_page_token"]}
                )
                p2 = page2.structured_content
                assert p2 is not None
                print(f"  returned       : {p2['returned']}")
                print(f"  resource_type  : {p2['resource_type']}")
                print(f"  has more pages : {bool(p2['next_page_token'])}")
            else:
                print("\n[3] get_next_page: skipped, only one page of results")

            # ---------------------------------------------------------------
            # 4. Read by id, following an id discovered in step 2.
            # ---------------------------------------------------------------
            if first_patient_id:
                print(f"\n[4] get_resource_by_id: Patient/{first_patient_id}")
                print(RULE)
                one = await client.call_tool(
                    "get_resource_by_id",
                    {"resource_type": "Patient", "resource_id": first_patient_id},
                )
                r = one.structured_content
                assert r is not None
                print(f"  reference      : {r['reference']}")
                print(f"  body keys      : {sorted(r['resource'].keys())[:10]}")

            # ---------------------------------------------------------------
            # 5. A clinically shaped query, the kind F1 will actually make:
            #    conditions for one patient.
            # ---------------------------------------------------------------
            if first_patient_id:
                print(f"\n[5] search_resources: Condition for patient {first_patient_id}")
                print(RULE)
                conds = await client.call_tool(
                    "search_resources",
                    {
                        "resource_type": "Condition",
                        "search_params": {"patient": first_patient_id},
                        "count": 5,
                    },
                )
                c = conds.structured_content
                assert c is not None
                print(f"  total_matching : {c['total_matching']}")
                for cond in c["resources"][:5]:
                    code = cond.get("code", {})
                    text = code.get("text") or (code.get("coding") or [{}])[0].get("display", "?")
                    print(f"    - {text}")

            # ---------------------------------------------------------------
            # 6. The error path. A tool error should read as an instruction the
            #    model can act on, not as a stack trace.
            # ---------------------------------------------------------------
            print("\n[6] error handling: reading a resource that does not exist")
            print(RULE)
            bad = await client.call_tool(
                "get_resource_by_id",
                {"resource_type": "Patient", "resource_id": "does-not-exist-99999"},
            )
            print(f"  isError        : {bad.is_error}")
            for block in bad.content:
                if getattr(block, "text", None):
                    print(f"  message        : {block.text}")

            # ---------------------------------------------------------------
            # 7. A rejected page token. Tokens travel through the model, so a
            #    fabricated one must not become a request forgery primitive.
            # ---------------------------------------------------------------
            print("\n[7] safety: a page token pointing somewhere else")
            print(RULE)
            forged = await client.call_tool(
                "get_next_page", {"page_token": "http://example.com/steal"}
            )
            print(f"  isError        : {forged.is_error}")
            for block in forged.content:
                if getattr(block, "text", None):
                    print(f"  message        : {block.text}")

    except Exception as exc:  # noqa: BLE001 - a smoke test should report, not raise
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        print("\nIs the server running?  uv run python -m fhir_mcp.server")
        print("Is HAPI FHIR up?        docker compose ps")
        return 1

    print(f"\n{BANNER}")
    print("Smoke test finished.")
    print(BANNER)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
