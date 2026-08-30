"""A thin async HTTP client for a FHIR server.

Deliberately small. It handles connection reuse, timeouts, and turning FHIR's
error responses into messages a language model can act on. It does not shape
resources (that is `serialization.py`) and it knows nothing about MCP.

Keeping it MCP-agnostic means the same client is usable from an oracle script
or a test without standing up an MCP server.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class FhirError(Exception):
    """A FHIR request failed in a way the caller should be told about.

    The message is written to be read by a language model deciding what to do
    next, not by a developer reading a stack trace. A tool error that says
    exactly what went wrong and what would fix it lets the model self-correct;
    a raw traceback does not.
    """


def _describe_operation_outcome(body: dict[str, Any]) -> str | None:
    """Extract the human-readable part of a FHIR OperationOutcome.

    FHIR servers report errors as an OperationOutcome resource with a list of
    issues. The useful text is usually in `diagnostics`, occasionally only in
    `details.text`.

    Returns:
        A single-line summary, or None if this does not look like an
        OperationOutcome.
    """
    if body.get("resourceType") != "OperationOutcome":
        return None

    messages: list[str] = []
    for issue in body.get("issue", []):
        text = issue.get("diagnostics") or issue.get("details", {}).get("text")
        if text:
            severity = issue.get("severity", "error")
            messages.append(f"{severity}: {text}")

    return "; ".join(messages) if messages else None


class FhirClient:
    """Async client for one FHIR server.

    Construct it once for the life of the process and share it. Creating a new
    client per request throws away connection pooling, which on a 15-step agent
    loop is measurable.
    """

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={
                # FHIR R4 JSON. Being explicit avoids servers negotiating down
                # to XML, which nothing downstream is prepared to parse.
                "Accept": "application/fhir+json",
            },
            # HAPI redirects in a few cases; following them keeps the client
            # from surfacing a 3xx as an error.
            follow_redirects=True,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def close(self) -> None:
        """Release the connection pool. Called from the server's lifespan."""
        await self._client.aclose()

    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        """Fetch one resource by type and id.

        Args:
            resource_type: A FHIR resource type, e.g. "Patient".
            resource_id: The server-assigned logical id.

        Returns:
            The decoded resource.

        Raises:
            FhirError: if the resource does not exist or the server refused.
        """
        return await self._get(f"{self._base_url}/{resource_type}/{resource_id}")

    async def search(self, resource_type: str, params: dict[str, Any]) -> dict[str, Any]:
        """Run a FHIR search and return the raw Bundle.

        Args:
            resource_type: The resource type to search, e.g. "Condition".
            params: FHIR search parameters, passed through as query string.

        Returns:
            The decoded searchset Bundle.
        """
        return await self._get(f"{self._base_url}/{resource_type}", params=params)

    async def follow(self, url: str) -> dict[str, Any]:
        """Fetch a URL the server itself handed us, such as a Bundle next link.

        Args:
            url: An absolute URL previously returned by this FHIR server.

        Raises:
            FhirError: if the URL does not belong to the configured server.
                A page token is data that travelled out to the model and back,
                so it is treated as untrusted input. Without this check, a
                fabricated token would turn a paging tool into a request
                forgery primitive pointed at anything reachable from the
                server process.
        """
        if not self._is_same_server(url):
            raise FhirError(
                "That page token does not point at this FHIR server and was refused. "
                "Page tokens are only valid when returned by a previous search on "
                "this server. Re-run the original search to get a fresh one."
            )
        return await self._get(url)

    def _is_same_server(self, url: str) -> bool:
        """Check that a URL belongs to the configured FHIR server.

        Parsed rather than prefix-matched. HAPI returns paging links shaped like
        `{base}?_getpages=...`, a query string on the base path itself, which a
        naive `startswith(base + "/")` test rejects as foreign. Comparing the
        parsed origin and path handles that correctly, and is the right way to
        make an origin decision regardless.
        """
        base = urlparse(self._base_url)
        target = urlparse(url)

        # Origin must match exactly. `netloc` covers host and port together, so
        # a token pointing at a different port on the same host is refused too.
        if (target.scheme, target.netloc) != (base.scheme, base.netloc):
            return False

        # The path must be the base path itself or somewhere beneath it. The
        # trailing-slash form stops `/fhirsomethingelse` passing as `/fhir`.
        base_path = base.path.rstrip("/")
        return target.path == base_path or target.path.startswith(base_path + "/")

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Issue a GET and convert any failure into an actionable FhirError."""
        try:
            response = await self._client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise FhirError(
                f"The FHIR server did not respond within the timeout. "
                f"If this was a broad search, narrow it with more specific "
                f"parameters or a smaller page size. ({exc})"
            ) from exc
        except httpx.RequestError as exc:
            raise FhirError(
                f"Could not reach the FHIR server at {self._base_url}. "
                f"It may not be running. ({exc})"
            ) from exc

        if response.is_success:
            try:
                return response.json()
            except ValueError as exc:
                raise FhirError(
                    "The FHIR server returned a response that was not valid JSON."
                ) from exc

        # Past here the server answered but refused. Try to surface its own
        # explanation, which is far more useful than the status code alone.
        detail: str | None = None
        try:
            detail = _describe_operation_outcome(response.json())
        except ValueError:
            detail = None

        if response.status_code == 404:
            raise FhirError(
                f"No such resource: {url.removeprefix(self._base_url + '/')}. "
                f"It does not exist on this server. Confirm the id is correct, "
                f"or search for the resource instead of reading it by id."
                + (f" Server said: {detail}" if detail else "")
            )

        if response.status_code == 400:
            raise FhirError(
                "The FHIR server rejected the request as malformed. This usually "
                "means an unsupported search parameter or a badly formatted value."
                + (f" Server said: {detail}" if detail else "")
            )

        raise FhirError(
            f"The FHIR server returned HTTP {response.status_code}."
            + (f" Server said: {detail}" if detail else "")
        )
