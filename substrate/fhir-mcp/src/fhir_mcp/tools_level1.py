"""Level 1 tools: thin passthrough over the FHIR REST API.

These mirror what a FHIR client already does. The agent has to know FHIR to use
them: which resource type holds what, which search parameters exist, how to
join across resources. That is the point. Level 1 is the baseline that Level 2
(task-shaped tools) and Level 3 (code mode) get measured against in
Experiment 1, and a baseline that quietly did some of the work for the agent
would make the comparison meaningless.

Read-only on purpose. Create, update, and delete belong with F4, the prior
authorisation feature, where the permission gate and audit trail that should
sit in front of a write are actually designed. Shipping destructive tools now,
months before anything gates them, is the mistake B04 chapter 16 is about.

Every docstring here is a user interface whose user is a language model. They
are written for a reader that has the schema but no idea what our FHIR server
contains, so they say what the tool is for and when to reach for it, not just
what its arguments are.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Settings
from .fhir_client import FhirClient, FhirError
from .serialization import serialise

_R = TypeVar("_R")


def _actionable_errors(
    func: Callable[..., Awaitable[_R]],
) -> Callable[..., Awaitable[_R]]:
    """Turn a FhirError into a tool error the model is allowed to read.

    The SDK draws a hard line between anticipated and unanticipated failures.
    Raise `ToolError` and the call comes back with `is_error=True` carrying the
    message, which is what lets a model correct itself and retry. Let any other
    exception escape and it is treated as a crash: the model is told only
    "Error executing tool <name>" and the real message is withheld.

    A failed FHIR lookup is squarely the anticipated kind, so the messages
    written in `fhir_client` are converted here rather than being swallowed.

    The conversion lives at the tool boundary on purpose. `FhirClient` stays
    free of MCP imports, so an oracle or a test can use it without an MCP
    server in the picture.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> _R:
        try:
            return await func(*args, **kwargs)
        except FhirError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


class AppContext(BaseModel):
    """What the lifespan makes available to every tool call.

    Pydantic is not doing validation work here; this is a typed container so
    `ctx.request_context.lifespan_context.fhir` resolves for a type checker.
    """

    model_config = {"arbitrary_types_allowed": True}

    fhir: FhirClient
    settings: Settings


class ResourceResult(BaseModel):
    """One FHIR resource."""

    resource_type: str = Field(description="FHIR resource type, e.g. 'Patient'.")
    id: str = Field(description="Server-assigned logical id of this resource.")
    reference: str = Field(
        description=(
            "Canonical FHIR reference, e.g. 'Patient/2657'. Cite this when "
            "reporting evidence rather than restating the resource contents."
        )
    )
    resource: dict[str, Any] = Field(
        description="The resource body, shaped by the server's serialisation setting."
    )


class SearchResult(BaseModel):
    """One page of FHIR search results."""

    resource_type: str = Field(description="The resource type that was searched.")
    total_matching: int | None = Field(
        description=(
            "How many resources matched the search in total, across all pages, "
            "as reported by the FHIR server. This is the number to trust when "
            "asking whether anything matched at all. Null means the server "
            "declined to count, in which case absence cannot be concluded from "
            "this field."
        )
    )
    returned: int = Field(description="How many resources are in this page. Never the total.")
    resources: list[dict[str, Any]] = Field(
        description="This page of resources, shaped by the serialisation setting."
    )
    next_page_token: str | None = Field(
        description=(
            "Pass to get_next_page to fetch the following page. Null means this "
            "is the last page. Tokens are only valid for this server and should "
            "be treated as opaque."
        )
    )


def register(mcp: MCPServer, settings: Settings) -> None:
    """Attach the Level 1 tools to an MCP server.

    Registration order is the order tools appear in `tools/list`. The 2026-07-28
    specification says servers SHOULD return tools in a deterministic order so
    clients can cache the list and model prompt caches hit more often, and a
    stable registration order is how that is achieved here.

    Args:
        mcp: The server to register on.
        settings: Resolved configuration, captured for serialisation choice.
    """

    def _client(ctx: Context[AppContext]) -> FhirClient:
        """Pull the shared FHIR client out of the lifespan context."""
        return ctx.request_context.lifespan_context.fhir

    def _shape(resource: dict[str, Any]) -> dict[str, Any]:
        """Apply the configured serialisation strategy to one resource."""
        return serialise(resource, settings.serialisation)

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Read FHIR resource by id",
            # Hints let a host decide what needs an approval gate. These three
            # are the honest description of a GET: it changes nothing, repeats
            # safely, and touches only this server.
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def get_resource_by_id(
        resource_type: Annotated[
            str,
            Field(description="FHIR resource type, e.g. 'Patient', 'Condition'."),
        ],
        resource_id: Annotated[str, Field(description="The logical id of the resource to read.")],
        ctx: Context[AppContext],
    ) -> ResourceResult:
        """Read one FHIR resource when you already know its type and id.

        Use this to follow a reference you found elsewhere, for example the
        'Patient/2657' in an Encounter's subject field. If you do not already
        have an id, use search_resources instead: guessing ids does not work,
        they are assigned by the server.
        """
        resource = await _client(ctx).read(resource_type, resource_id)

        # Prefer what the server actually returned over what was asked for. A
        # server may canonicalise an id, and citing the id we guessed rather
        # than the one that exists would undermine the evidence trail F1 needs.
        actual_type = resource.get("resourceType", resource_type)
        actual_id = str(resource.get("id", resource_id))

        return ResourceResult(
            resource_type=actual_type,
            id=actual_id,
            reference=f"{actual_type}/{actual_id}",
            resource=_shape(resource),
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Search FHIR resources",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def search_resources(
        resource_type: Annotated[
            str,
            Field(description="FHIR resource type to search, e.g. 'Observation'."),
        ],
        search_params: Annotated[
            dict[str, str] | None,
            Field(
                description=(
                    "FHIR search parameters as name/value pairs, for example "
                    "{'patient': '2657', 'code': '4548-4'} to find HbA1c results "
                    "for one patient. Values are passed to the server as given. "
                    "Omit entirely to match all resources of this type."
                )
            ),
        ] = None,
        count: Annotated[
            int,
            Field(
                description=(
                    f"Maximum resources per page, 1 to {MAX_PAGE_SIZE}. "
                    f"Defaults to {DEFAULT_PAGE_SIZE}. Keep this small: a large "
                    f"page spends context on resources you may not need."
                ),
                ge=1,
                le=MAX_PAGE_SIZE,
            ),
        ] = DEFAULT_PAGE_SIZE,
        ctx: Context[AppContext] = None,  # type: ignore[assignment]
    ) -> SearchResult:
        """Search for FHIR resources matching some criteria.

        This is a single-resource-type search. FHIR search cannot join across
        resource types, so a question like "diabetics not on an ACE inhibitor"
        is several searches plus filtering on your side, not one call.

        Read total_matching, not the length of resources, when deciding whether
        anything matched. The two differ whenever results span more than one
        page, and concluding "none exist" from an empty page you never paged
        through is how a false result gets reported as fact.
        """
        params: dict[str, Any] = dict(search_params or {})

        # _count is FHIR's page size parameter. Setting it explicitly means the
        # page size is ours rather than whatever default the server happens to
        # apply, which keeps results comparable across servers and runs.
        params["_count"] = count

        # _total=accurate asks the server to report the true match count rather
        # than an estimate or nothing at all. F1 has to prove that a resource is
        # absent, and an absence can only be established from a real count.
        params.setdefault("_total", "accurate")

        bundle = await _client(ctx).search(resource_type, params)
        return _bundle_to_result(bundle, resource_type, _shape)

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Fetch next page of search results",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    @_actionable_errors
    async def get_next_page(
        page_token: Annotated[
            str,
            Field(
                description=(
                    "The next_page_token from a previous search_resources or get_next_page result."
                )
            ),
        ],
        ctx: Context[AppContext],
    ) -> SearchResult:
        """Fetch the next page of a search you already started.

        The protocol keeps no session, so there is no notion of "the current
        search" on the server. The token carries that. Hold on to it if you
        intend to page, and pass it back exactly as given.
        """
        bundle = await _client(ctx).follow(page_token)

        # A next link does not restate what type was searched, so recover it
        # from the entries themselves. An empty page leaves it genuinely
        # unknown, which is reported rather than guessed at.
        entries = bundle.get("entry") or []
        resource_type = "unknown"
        for entry in entries:
            found = (entry.get("resource") or {}).get("resourceType")
            if found:
                resource_type = found
                break

        return _bundle_to_result(bundle, resource_type, _shape)


def _bundle_to_result(
    bundle: dict[str, Any],
    resource_type: str,
    shape: Any,
) -> SearchResult:
    """Convert a FHIR searchset Bundle into our own result shape.

    A raw Bundle is mostly envelope: per-entry search modes, full URLs, and
    paging links the model has no use for. This keeps the resources, the two
    counts that matter, and a single opaque paging token.
    """
    entries = bundle.get("entry") or []
    resources = [shape(entry["resource"]) for entry in entries if entry.get("resource")]

    # Bundle.link is a list of {relation, url}. The "next" relation is present
    # only when more pages exist, which makes its absence the end-of-results
    # signal rather than something we have to compute.
    next_url: str | None = None
    for link in bundle.get("link") or []:
        if link.get("relation") == "next" and link.get("url"):
            next_url = link["url"]
            break

    return SearchResult(
        resource_type=resource_type,
        # `total` is absent when the server declined to count. Reporting None
        # rather than 0 keeps "no matches" distinct from "not counted", which
        # is exactly the distinction a care-gap claim rests on.
        total_matching=bundle.get("total"),
        returned=len(resources),
        resources=resources,
        next_page_token=next_url,
    )


__all__ = [
    "AppContext",
    "FhirError",
    "ResourceResult",
    "SearchResult",
    "register",
]
