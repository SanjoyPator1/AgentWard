"""Level 3: code mode - a fallback for questions no Level 1/2 tool answers.

Exposes one tool, run_fhir_code, that runs model-written Python in a
locked-down subprocess (sandbox.py) against a small `fhir` object (search,
get_by_id, narrate) instead of one MCP tool call per fact. The tool's own
docstring below is where the "use this only as a fallback" rule is stated
for the model today; a harness system prompt is where the human-facing
version of that rule belongs once one exists - nothing prompt-shaped lives
in this server.

Errors from the sandboxed script - a raised exception, a timeout, a resource
limit hit - surface as an ordinary tool error through the same ToolError
path Level 1/2 already use, so the model sees a traceback and can rewrite
its code. No separate retry mechanism is needed for that.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import Settings
from .sandbox import SandboxError, run_sandboxed

_TIMEOUT_SECONDS = 10.0


def register(mcp: MCPServer, settings: Settings) -> None:
    """Attach the Level 3 tool to an MCP server."""

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Run Python against FHIR data",
            read_only_hint=True,
            destructive_hint=False,
            # Re-running the same code isn't guaranteed to reproduce the same
            # result (the underlying data can change between calls), unlike
            # Level 1/2's tools, which are.
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def run_fhir_code(
        code: Annotated[
            str,
            Field(
                description=(
                    "Python source to run. Available: fhir.search(resource_type, "
                    "params=None, count=20) - one page of up to 100 resources, no "
                    "next-page token and no pagination (unlike search_resources); "
                    "narrow the search instead of trying to page through everything. "
                    "Also: fhir.get_by_id(resource_type, resource_id), and "
                    "fhir.narrate(resources, resource_type) to format a list of "
                    "resources as prose before printing. Also available: datetime. "
                    "No filesystem or network access beyond the FHIR server, no other "
                    "imports. End with a print() statement - only what the script "
                    "prints is returned, not its return value."
                )
            ),
        ],
    ) -> str:
        """Run Python against FHIR data for a question no fixed tool covers.

        A fallback, not a first choice. Every existing tool already does its
        one job in a single call, which is cheaper and more reliable than a
        script re-deriving the same logic - check whether search_resources,
        get_active_medications, get_lab_trend, get_problem_list, or
        find_cohort already answers the question before reaching for this.

        Use this for a question that needs its own computation across
        several fetches: a comparison, a count, a filter no existing tool
        exposes.

        If the answer is more than a one-line fact, format it with
        fhir.narrate(...) before printing - print a short prose summary, not
        a raw dict or list.
        """
        try:
            return await run_sandboxed(code, settings.fhir_base_url, _TIMEOUT_SECONDS)
        except SandboxError as exc:
            raise ToolError(str(exc)) from exc


__all__ = ["register"]
