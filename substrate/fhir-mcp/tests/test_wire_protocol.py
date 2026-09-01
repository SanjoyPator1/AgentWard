"""Tests against the actual HTTP wire, not the SDK's own client.

The earlier version of this server passed every test that used `mcp.Client`
on both ends, and still broke for a plain HTTP caller: `stateless_http`
defaults to `False`, so a request with no `Mcp-Protocol-Version` header fell
into the legacy transport path and was rejected with a bare
"Bad Request: Missing session ID", even though the whole design here targets
the stateless 2026-07-28 spec.

Testing only through the matching SDK client hid that, because the client
negotiates the header invisibly. These tests drive the ASGI app directly with
plain `httpx`, the way an independently written client or a different host
would, so a regression here is caught by `pytest`, not by a person running
curl by hand and finding out the hard way.

Two things make this fiddly, both discovered by trial and getting a real
error back, not assumed up front:

- `httpx.ASGITransport` does not run the ASGI lifespan protocol on its own,
  so the app's `lifespan` context (where the FHIR client gets created) is
  driven manually via `app.router.lifespan_context`.
- The SDK's DNS-rebinding protection checks the `Host` header against the
  address the server was told it is bound to, so the test client's base URL
  has to match `host:port` exactly, `http://localhost` alone is rejected.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette

from fhir_mcp.config import Settings
from fhir_mcp.server import build_server

HOST = "127.0.0.1"
PORT = 3001
BASE_URL = f"http://{HOST}:{PORT}"


def _settings() -> Settings:
    # Points at a FHIR server that need not actually exist: every test here
    # only reaches tools/list, which never touches FhirClient.
    return Settings(
        fhir_base_url="http://localhost:8080/fhir",
        serialisation="nested",
        request_timeout_seconds=5.0,
        host=HOST,
        port=PORT,
        allowed_hosts=(f"{HOST}:*",),
    )


def _app() -> Starlette:
    server = build_server(_settings())
    # stateless_http=True mirrors the flag set in server.main(). If that flag
    # is ever removed there, the "no header" test below is what starts
    # failing, which is the point.
    return server.streamable_http_app(stateless_http=True)


@asynccontextmanager
async def wire_client() -> AsyncIterator[httpx.AsyncClient]:
    """An httpx client talking to the real ASGI app in-process, lifespan and all.

    Deliberately not a pytest fixture. The session manager's lifespan opens an
    anyio task group, and its cancel scope has to exit in the same asyncio
    Task it was entered in; a `yield`-based pytest fixture's teardown can run
    as a separate scheduled continuation, which anyio then rejects with
    "Attempted to exit cancel scope in a different task than it was entered
    in". Calling this as a plain `async with` inside the test body keeps
    setup and teardown in one task, which is what actually fixed it, found by
    hitting the error rather than avoiding it in advance.
    """
    app = _app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL
        ) as client:
            yield client


def _parse_jsonrpc(response: httpx.Response) -> dict:
    """Both response shapes the transport can return carry one JSON object.

    A stateless request without the modern header comes back framed as a
    single SSE event (`event: message\\ndata: {...}`); the true 2026-07-28
    path returns plain JSON. Callers of this server should not have to care
    which one they got, so neither should the tests.
    """
    body = response.text
    if body.startswith("event:"):
        _, _, data_line = body.partition("data: ")
        body = data_line.strip()
    import json

    return json.loads(body)


class TestNoVersionHeader:
    """A caller that sends no `Mcp-Protocol-Version` header at all.

    This is the exact case that failed before `stateless_http=True` was set:
    "Bad Request: Missing session ID" instead of a real answer.
    """

    async def test_tools_list_succeeds(self):
        async with wire_client() as client:
            response = await client.post(
                "/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
        assert response.status_code == 200, response.text
        payload = _parse_jsonrpc(response)
        assert "error" not in payload, payload
        tool_names = {t["name"] for t in payload["result"]["tools"]}
        assert tool_names == {
            "get_resource_by_id",
            "search_resources",
            "get_next_page",
            "get_active_medications",
            "get_lab_trend",
            "get_problem_list",
            "find_cohort",
        }


class TestModernSpecCompliantRequest:
    """A caller that speaks the true 2026-07-28 wire format: the version
    header, and `_meta` nested inside `params` rather than at the top level
    of the request (a shape the specification's own examples do not make
    obvious, and the one place a first attempt at this test got wrong)."""

    def _meta(self) -> dict:
        return {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1.0"},
            "io.modelcontextprotocol/clientCapabilities": {},
        }

    async def test_tools_list_returns_complete_with_cache_hints(self):
        async with wire_client() as client:
            response = await client.post(
                "/mcp",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "tools/list",
                    "Mcp-Name": "tools/list",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {"_meta": self._meta()},
                },
            )
        assert response.status_code == 200, response.text
        result = _parse_jsonrpc(response)["result"]
        assert result["resultType"] == "complete"
        # The cache hint set in server.py should actually reach the wire.
        assert result["ttlMs"] == 300_000
        assert result["cacheScope"] == "public"
        # Servers SHOULD identify themselves; confirms serverInfo made it
        # into the response _meta rather than only being configured.
        assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "fhir-mcp"

    async def test_unknown_tool_is_reported_as_a_tool_error(self):
        """The specification's prose files "unknown tool" under protocol
        errors (a top-level JSON-RPC `error`). The installed SDK (2.1.1) does
        not do that in practice: calling a tool that does not exist comes
        back as an ordinary result with `isError: true` and an explanatory
        text block, the same shape as any other tool-execution failure. That
        is what this test asserts, because it is what was actually observed
        running against the real server, not what the spec's wording implied
        before checking. Either shape is something a model can act on; the
        thing worth guarding against is a bare crash with no message at all.
        """
        async with wire_client() as client:
            response = await client.post(
                "/mcp",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "tools/call",
                    "Mcp-Name": "no_such_tool",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "no_such_tool",
                        "arguments": {},
                        "_meta": self._meta(),
                    },
                },
            )
        payload = _parse_jsonrpc(response)
        assert "error" not in payload, payload
        result = payload["result"]
        assert result["isError"] is True
        assert "no_such_tool" in result["content"][0]["text"]
