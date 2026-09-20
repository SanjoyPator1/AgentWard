"""Registry of chat-agent implementations by version.

Each version is a self-contained package (harness/v1, harness/v2, ...) with
its own run_chat_turn. This module is the one place callers (viewer_api.py
today, eval_runner.py later if it adopts versioning too) resolve a version
string to a callable, instead of importing a specific submodule directly.
"""

from __future__ import annotations

from typing import Callable

from .v1.chat_agent import run_chat_turn as _chat_v1

CHAT_AGENTS: dict[str, Callable] = {
    "v1": _chat_v1,
}

DEFAULT_CHAT_VERSION = "v1"


def get_chat_agent(version: str | None) -> Callable:
    key = version or DEFAULT_CHAT_VERSION
    try:
        return CHAT_AGENTS[key]
    except KeyError:
        raise ValueError(
            f"Unknown harness version {key!r}; available: {sorted(CHAT_AGENTS)}"
        ) from None


__all__ = ["CHAT_AGENTS", "DEFAULT_CHAT_VERSION", "get_chat_agent"]
