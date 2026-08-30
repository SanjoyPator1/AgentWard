"""Serialisation strategies: how a FHIR resource is shaped for the model.

This module is Experiment 3 from the project brief. The finding it builds on
is our own: how FHIR data is serialised changes what a model gets right. Every
tool return value passes through here, so the experiment is a configuration
change rather than an edit to twelve tool implementations.

The three strategies:

    nested      The resource exactly as FHIR returns it. Most faithful,
                most tokens. The baseline everything else is measured against.

    flattened   Nested paths collapsed to dotted keys. Same information,
                no structural nesting for the model to traverse.

    compact     Nested, minus the fields that carry little signal for
                clinical reasoning and cost a lot of tokens.

`compact` is deliberately type-agnostic. Per-resource-type projections (only
the fields that matter for a Condition, say) belong to the Level 2 task-shaped
tools, not to a Level 1 passthrough that must work for all ~150 resource types.
"""

from __future__ import annotations

from typing import Any

from .config import SerialisationStrategy

# Fields dropped by the `compact` strategy.
#
# `text` is FHIR's human-readable narrative, an XHTML blob that restates data
# already present in the structured fields. On Synthea output it is routinely
# the largest single field in a resource and adds nothing a model can act on
# that the structured fields do not already carry.
#
# `meta` is server bookkeeping (version id, last-updated, profile URLs). It
# matters for concurrency control on the write path, so `compact` is not
# appropriate for a read-modify-write cycle. It is not clinical information.
#
# `extension` and `modifierExtension` hold implementation-guide additions.
# Synthea populates these with generator metadata rather than clinical facts.
_COMPACT_DROP_FIELDS = frozenset({"text", "meta", "extension", "modifierExtension"})


def serialise(resource: dict[str, Any], strategy: SerialisationStrategy) -> dict[str, Any]:
    """Shape one FHIR resource according to the configured strategy.

    Args:
        resource: A FHIR resource as decoded JSON.
        strategy: Which shaping to apply.

    Returns:
        A new dict. The input is never mutated, because the same resource may
        be serialised more than once when comparing strategies.
    """
    if strategy == "nested":
        # Deliberately a shallow copy rather than the original object: callers
        # should not be able to mutate the client's decoded response.
        return dict(resource)
    if strategy == "flattened":
        return flatten(resource)
    if strategy == "compact":
        return compact(resource)

    # Unreachable while Settings validates at startup, but a silent wrong
    # answer here would corrupt an experiment result rather than fail it.
    raise ValueError(f"Unknown serialisation strategy: {strategy!r}")


def compact(resource: dict[str, Any]) -> dict[str, Any]:
    """Drop high-token, low-signal fields, preserving structure elsewhere.

    Only the top level is filtered. Nested occurrences of `extension` are left
    alone on purpose: at depth they are sometimes the only place a value lives,
    and removing them could change the meaning of the resource rather than just
    its size.
    """
    return {k: v for k, v in resource.items() if k not in _COMPACT_DROP_FIELDS}


def flatten(resource: dict[str, Any]) -> dict[str, Any]:
    """Collapse a nested resource into dotted-path keys.

    Lists become indexed paths, so nothing is lost and every value keeps an
    unambiguous address:

        {"name": [{"given": ["Ada"]}]}  ->  {"name.0.given.0": "Ada"}

    Empty containers are preserved as empty containers rather than dropped, so
    "the field exists but is empty" stays distinguishable from "the field is
    absent". For F1, which has to prove the *absence* of a resource, that
    distinction is the whole task.
    """
    flat: dict[str, Any] = {}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if not node:
                flat[path] = {}
                return
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            if not node:
                flat[path] = []
                return
            for index, value in enumerate(node):
                walk(value, f"{path}.{index}")
        else:
            flat[path] = node

    walk(resource, "")
    return flat
