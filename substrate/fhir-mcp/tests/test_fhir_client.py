"""Tests for the FHIR client, concentrating on the page-token origin check.

That check is a security boundary, not a convenience. A page token is a URL
that left the server, passed through a language model, and came back. Without
validation, a fabricated token turns `get_next_page` into a request forgery
primitive aimed at anything the server process can reach, which on a Docker
network is every other service in the compose file.

It is also the one piece of this server that has already had a bug: the first
version compared string prefixes and rejected HAPI's own legitimate paging
links, which use a query string on the base path.
"""

from __future__ import annotations

import pytest

from fhir_mcp.fhir_client import FhirClient, FhirError, _describe_operation_outcome

BASE = "http://localhost:8080/fhir"


@pytest.fixture
def client() -> FhirClient:
    return FhirClient(base_url=BASE)


class TestPageTokenOrigin:
    @pytest.mark.parametrize(
        "url",
        [
            # HAPI's real paging link shape: a query string on the base path.
            # This is the case the first implementation wrongly rejected.
            f"{BASE}?_getpages=53d30f9e-d936-430a-bc39-000000000000&_getpagesoffset=3",
            f"{BASE}/Patient?_count=10",
            f"{BASE}/Patient/2657",
            BASE,
        ],
    )
    def test_accepts_urls_from_this_server(self, client: FhirClient, url: str):
        assert client._is_same_server(url) is True

    @pytest.mark.parametrize(
        ("url", "why"),
        [
            ("http://example.com/steal", "different host entirely"),
            ("https://localhost:8080/fhir", "different scheme"),
            ("http://localhost:9999/fhir", "different port"),
            ("http://localhost:8080/admin", "same origin, outside the FHIR base path"),
            # The trailing-slash case: a path that merely starts with the same
            # characters is not beneath the base path.
            ("http://localhost:8080/fhirsomethingelse", "path prefix collision"),
            # Internal services reachable on the compose network. The exact
            # attack the check exists to stop.
            ("http://postgres:5432/", "another service on the docker network"),
        ],
    )
    def test_rejects_foreign_urls(self, client: FhirClient, url: str, why: str):
        assert client._is_same_server(url) is False, f"should reject: {why}"

    async def test_follow_raises_actionable_error(self, client: FhirClient):
        """The message has to tell the model what to do next, since the model
        is the thing that will read it."""
        with pytest.raises(FhirError) as exc:
            await client.follow("http://example.com/steal")
        message = str(exc.value)
        assert "does not point at this FHIR server" in message
        assert "Re-run the original search" in message


class TestOperationOutcome:
    def test_extracts_diagnostics(self):
        body = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "HAPI-2001: Resource not known"}],
        }
        assert _describe_operation_outcome(body) == "error: HAPI-2001: Resource not known"

    def test_falls_back_to_details_text(self):
        body = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "warning", "details": {"text": "Deprecated parameter"}}],
        }
        assert _describe_operation_outcome(body) == "warning: Deprecated parameter"

    def test_joins_multiple_issues(self):
        body = {
            "resourceType": "OperationOutcome",
            "issue": [
                {"severity": "error", "diagnostics": "first"},
                {"severity": "error", "diagnostics": "second"},
            ],
        }
        assert _describe_operation_outcome(body) == "error: first; error: second"

    def test_returns_none_for_a_normal_resource(self):
        """A Bundle or a Patient is not an error report and must not be read as one."""
        assert _describe_operation_outcome({"resourceType": "Bundle"}) is None

    def test_returns_none_when_no_issue_has_text(self):
        body = {"resourceType": "OperationOutcome", "issue": [{"severity": "error"}]}
        assert _describe_operation_outcome(body) is None
