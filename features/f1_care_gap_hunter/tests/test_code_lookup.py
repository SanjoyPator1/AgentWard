"""code_lookup tested entirely offline via httpx.MockTransport - no live
call to tx.fhir.org, clinicaltables.nlm.nih.gov, or rxnav.nlm.nih.gov, the
same "no network in tests" philosophy test_loop.py applies to the model and
MCP layers.
"""

from __future__ import annotations

import httpx

from f1_care_gap_hunter.harness.v1 import code_lookup


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_lookup_snomed_parses_expansion_contains():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["filter"] == "asthma"
        return httpx.Response(
            200,
            json={
                "resourceType": "ValueSet",
                "expansion": {
                    "total": 14,
                    "contains": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "195967001",
                            "display": "Asthma",
                        },
                        {
                            "system": "http://snomed.info/sct",
                            "code": "233604007",
                            "display": "Pneumonia (disorder)",
                        },
                    ],
                },
            },
        )

    async with _client(handler) as client:
        result = await code_lookup.lookup_snomed(client, "asthma")

    assert result["total_matching"] == 14
    assert result["returned"] == 2
    assert result["candidates"][0] == {"code": "195967001", "display": "Asthma"}


async def test_lookup_snomed_promotes_exact_match_over_servers_own_order():
    # The real shape of a reproduced bug: tx.fhir.org's own order for
    # "asthma" put these 5 distractors ahead of "Asthma (disorder)" itself
    # (which the live server placed at position 35 of 254 - nowhere near a
    # naive top-5). Confirms the fix reorders rather than just trusting the
    # server's already-broken ranking.
    distractors = [
        {"code": "18197001", "display": "Asthmatoid wheeze"},
        {"code": "41997000", "display": "Asthmatic pulmonary alveolitis"},
        {"code": "55570000", "display": "Asthma without status asthmaticus"},
        {"code": "56018004", "display": "Wheezing"},
        {"code": "161105008", "display": "Asthma society member"},
    ]
    real_code = {"code": "195967001", "display": "Asthma (disorder)"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert int(request.url.params["count"]) >= 6  # asked for more than just top 5
        return httpx.Response(
            200,
            json={
                "resourceType": "ValueSet",
                "expansion": {"total": 254, "contains": [*distractors, real_code]},
            },
        )

    async with _client(handler) as client:
        result = await code_lookup.lookup_snomed(client, "asthma")

    assert result["candidates"][0] == {"code": "195967001", "display": "Asthma (disorder)"}


async def test_lookup_snomed_ranks_whole_word_match_above_unrelated_synonym_hit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resourceType": "ValueSet",
                "expansion": {
                    "total": 2,
                    "contains": [
                        {"code": "56018004", "display": "Wheezing"},  # no "asthma" at all
                        {
                            "code": "233678006",
                            "display": "Childhood asthma (disorder)",
                        },
                    ],
                },
            },
        )

    async with _client(handler) as client:
        result = await code_lookup.lookup_snomed(client, "asthma")

    assert result["candidates"][0]["code"] == "233678006"


async def test_lookup_loinc_parses_four_element_array():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["terms"] == "hemoglobin a1c"
        return httpx.Response(
            200,
            json=[
                2,
                ["4548-4", "17856-6"],
                None,
                [["Hemoglobin A1c/Hemoglobin.total in Blood"], ["Hemoglobin A1c"]],
            ],
        )

    async with _client(handler) as client:
        result = await code_lookup.lookup_loinc(client, "hemoglobin a1c")

    assert result["total_matching"] == 2
    assert result["candidates"] == [
        {"code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood"},
        {"code": "17856-6", "display": "Hemoglobin A1c"},
    ]


async def test_lookup_rxnorm_dedupes_by_rxcui_keeping_first_name():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["term"] == "hydrochlorothiazide"
        return httpx.Response(
            200,
            json={
                "approximateGroup": {
                    "candidate": [
                        {"rxcui": "5487", "name": "Hydrochlorothiazide", "source": "USP"},
                        {"rxcui": "5487", "source": "GS"},  # same drug, no name on this row
                        {"rxcui": "310798", "name": "Hydrochlorothiazide 25 MG Oral Tablet"},
                    ]
                }
            },
        )

    async with _client(handler) as client:
        result = await code_lookup.lookup_rxnorm(client, "hydrochlorothiazide")

    assert result["total_matching"] == 2  # 2 distinct rxcui, not 3 rows
    assert result["candidates"] == [
        {"code": "5487", "display": "Hydrochlorothiazide"},
        {"code": "310798", "display": "Hydrochlorothiazide 25 MG Oral Tablet"},
    ]


async def test_handler_rejects_unknown_system_without_any_network_call():
    result = await code_lookup.handler({"system": "icd10", "term": "asthma"})
    assert "error" in result


async def test_handler_rejects_empty_term():
    result = await code_lookup.handler({"system": "snomed", "term": "  "})
    assert "error" in result


async def test_handler_caches_by_system_and_lowercased_term(monkeypatch):
    calls = 0

    async def fake_lookup_snomed(client, term):
        nonlocal calls
        calls += 1
        return {
            "system": "snomed",
            "term": term,
            "total_matching": 1,
            "returned": 1,
            "candidates": [],
        }

    monkeypatch.setattr(code_lookup, "lookup_snomed", fake_lookup_snomed)
    code_lookup._cache.clear()

    await code_lookup.handler({"system": "snomed", "term": "Asthma"})
    await code_lookup.handler({"system": "snomed", "term": "asthma"})  # same term, different case

    assert calls == 1


async def test_handler_reports_unreachable_server_instead_of_raising(monkeypatch):
    async def fake_lookup_snomed(client, term):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(code_lookup, "lookup_snomed", fake_lookup_snomed)
    code_lookup._cache.clear()

    result = await code_lookup.handler({"system": "snomed", "term": "gout"})

    assert "error" in result
    assert "could not be reached" in result["error"]
