"""lookup_medical_code: a local tool for the code the chat agent was not
already given one for.

Added after a reproduced failure: asked to find patients with asthma, with
no hardcoded code to use, the model recalled a plausible-looking SNOMED code
from its own training data and got it wrong - it named 233604007, which is
actually "Pneumonia (disorder)", not asthma. This tool exists so the agent
looks a code up against a real terminology server instead of recalling one
from memory, the same reason none of this project's other tools let the
model guess a FHIR search parameter.

Three public, no-auth NLM/HL7 terminology services, one per code system:

    snomed   tx.fhir.org's public FHIR terminology server, ValueSet/$expand
             over the full SNOMED CT International edition.
    loinc    NLM's Clinical Table Search Service (the loinc_items table).
    rxnorm   NLM's RxNav, approximate-term search over RxNorm.

Deliberately not wired into gap_agent.py / eval_runner: the four graded gap
types already have every code they need hardcoded in prompts.py, so adding
this here would put a live network call on the critical path of every eval
run for a case that never actually occurs there. This is chat_agent.py-only,
for whatever a person asks that isn't one of those four rules.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import httpx

from .loop import LocalTool

CodeSystem = Literal["snomed", "loinc", "rxnorm"]

LOOKUP_TOOL_NAME = "lookup_medical_code"

_TIMEOUT_SECONDS = 10.0
_MAX_CANDIDATES = 5

# tx.fhir.org's ValueSet/$expand `filter` is a text-index match, not a
# relevance ranking - confirmed live: searching "asthma" put "Asthma
# (disorder)" itself at position 35 of 254, behind things like "Asthma
# society member". Fetch a wide pool from the server, then rank it
# ourselves before ever showing the model a top 5.
_SNOMED_FETCH_COUNT = 50

# SNOMED's trailing semantic tag, e.g. "Asthma (disorder)" -> "Asthma". The
# reverse of tools_level2.py's `_is_disorder` (which checks the tag is
# present); here we strip it to compare the bare clinical term.
_SEMANTIC_TAG_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _strip_semantic_tag(display: str) -> str:
    return _SEMANTIC_TAG_RE.sub("", display).strip()


def _snomed_rank_key(term_lower: str, display: str) -> tuple[int, int]:
    """Lower sorts first. Tier 0: the bare term itself (ignoring SNOMED's
    semantic tag) - "Asthma (disorder)" for "asthma". Tier 1: the term
    appears as a whole word anywhere - "Childhood asthma (disorder)" or
    "Asthma without status asthmaticus". Tier 2: everything else the
    server's index matched some other way (a synonym, a substring inside a
    longer word). Shorter display text breaks ties within a tier, since a
    general concept is usually named more plainly than a narrow one."""
    bare_lower = _strip_semantic_tag(display).lower()
    if bare_lower == term_lower:
        tier = 0
    elif re.search(rf"\b{re.escape(term_lower)}\b", bare_lower):
        tier = 1
    else:
        tier = 2
    return (tier, len(bare_lower))

# term -> result, kept for the life of the process. Unbounded on purpose: the
# vocabulary of terms one chat session asks about is tiny, and v1 does not
# need an eviction policy for that.
_cache: dict[tuple[CodeSystem, str], dict[str, Any]] = {}


def schema() -> dict[str, Any]:
    """OpenAI tool-definition shape - the same convention gap_agent.py's
    submit_findings schema uses."""
    return {
        "type": "function",
        "function": {
            "name": LOOKUP_TOOL_NAME,
            "description": (
                "Look up the real code for a medical term against a public terminology "
                "server. Use this for ANY condition, lab, or medication code you need that "
                "is not already given to you in your instructions - never recall a SNOMED, "
                "LOINC, or RxNorm code from memory. A wrong guess looks identical to a right "
                "one in your own output, and this project has a confirmed case of exactly "
                "that (a guessed asthma code turned out to be pneumonia's). If this tool "
                "errors or returns no candidates, say so to the person you're talking to "
                "rather than falling back on a remembered code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "system": {
                        "type": "string",
                        "enum": ["snomed", "loinc", "rxnorm"],
                        "description": (
                            "snomed for a condition, procedure, or finding; loinc for a lab "
                            "or observation; rxnorm for a medication."
                        ),
                    },
                    "term": {
                        "type": "string",
                        "description": "The plain-English term to look up, e.g. 'asthma'.",
                    },
                },
                "required": ["system", "term"],
            },
        },
    }


async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
    system = arguments.get("system")
    term = (arguments.get("term") or "").strip()
    if system not in ("snomed", "loinc", "rxnorm"):
        return {"error": f"Unknown system {system!r}. Must be snomed, loinc, or rxnorm."}
    if not term:
        return {"error": "term is required."}

    cache_key = (system, term.lower())
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            if system == "snomed":
                result = await lookup_snomed(client, term)
            elif system == "loinc":
                result = await lookup_loinc(client, term)
            else:
                result = await lookup_rxnorm(client, term)
    except httpx.HTTPError as exc:
        # Deliberately still a normal (non-error) tool result, not a raised
        # exception: SimpleToolLoop._call_local_tool has no try/except of
        # its own, so raising here would crash the whole chat turn over one
        # unreachable server instead of letting the model see the failure
        # and say so, which is the actual point of this tool existing.
        return {
            "system": system,
            "term": term,
            "error": f"The {system} terminology server could not be reached: {exc}",
        }

    _cache[cache_key] = result
    return result


async def lookup_snomed(client: httpx.AsyncClient, term: str) -> dict[str, Any]:
    response = await client.get(
        "https://tx.fhir.org/r4/ValueSet/$expand",
        params={
            "url": "http://snomed.info/sct?fhir_vs",
            "filter": term,
            "count": _SNOMED_FETCH_COUNT,
        },
        headers={"Accept": "application/fhir+json"},
    )
    response.raise_for_status()
    expansion = response.json().get("expansion", {})
    term_lower = term.strip().lower()
    ranked = sorted(
        (c for c in expansion.get("contains", []) if c.get("code")),
        key=lambda c: _snomed_rank_key(term_lower, c.get("display") or ""),
    )
    candidates = [
        {"code": c.get("code"), "display": c.get("display")} for c in ranked[:_MAX_CANDIDATES]
    ]
    return {
        "system": "snomed",
        "term": term,
        "total_matching": expansion.get("total"),
        "returned": len(candidates),
        "candidates": candidates,
    }


async def lookup_loinc(client: httpx.AsyncClient, term: str) -> dict[str, Any]:
    response = await client.get(
        "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search",
        params={"terms": term, "maxList": _MAX_CANDIDATES},
    )
    response.raise_for_status()
    # This service's shape is a fixed 4-element array, not an object: total
    # count, the matched codes, an unused extra-fields slot (null unless the
    # `ef` param is passed), then one display-string list per result.
    total, codes, _extra, displays = response.json()
    candidates = [
        {"code": code, "display": (display[0] if display else None)}
        for code, display in zip(codes, displays, strict=True)
    ]
    return {
        "system": "loinc",
        "term": term,
        "total_matching": total,
        "returned": len(candidates),
        "candidates": candidates,
    }


async def lookup_rxnorm(client: httpx.AsyncClient, term: str) -> dict[str, Any]:
    response = await client.get(
        "https://rxnav.nlm.nih.gov/REST/approximateTerm.json",
        params={"term": term, "maxEntries": 20},
    )
    response.raise_for_status()
    raw_candidates = (response.json().get("approximateGroup") or {}).get("candidate") or []

    # RxNav returns one row per (rxcui, source) pair, so the same rxcui
    # repeats several times with a display name present on only some of the
    # rows. Keep the first name found for each rxcui, in the API's own rank
    # order (best match first).
    names_by_code: dict[str, str | None] = {}
    order: list[str] = []
    for row in raw_candidates:
        code = row.get("rxcui")
        if not code:
            continue
        if code not in names_by_code:
            names_by_code[code] = row.get("name")
            order.append(code)
        elif not names_by_code[code] and row.get("name"):
            names_by_code[code] = row["name"]

    candidates = [
        {"code": code, "display": names_by_code[code]} for code in order[:_MAX_CANDIDATES]
    ]
    return {
        "system": "rxnorm",
        "term": term,
        "total_matching": len(order),
        "returned": len(candidates),
        "candidates": candidates,
    }


def tool() -> LocalTool:
    """Build the LocalTool for chat_agent.py to register."""
    return LocalTool(schema=schema(), handler=handler)


__all__ = [
    "LOOKUP_TOOL_NAME",
    "handler",
    "lookup_loinc",
    "lookup_rxnorm",
    "lookup_snomed",
    "schema",
    "tool",
]
