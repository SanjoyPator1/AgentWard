"""Runtime configuration for the fhir-mcp server.

Everything here is read from the environment once at startup. Nothing in the
tool layer reads `os.environ` directly, so the settings a given run used are
knowable from one object, which matters when an eval result has to be
attributed to a specific configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, get_args

# The serialisation strategies from Experiment 3 in the project brief. How a
# FHIR resource is shaped before the model sees it changes what the model gets
# right, so the choice is configuration rather than something hardcoded inside
# each tool.
SerialisationStrategy = Literal["nested", "flattened", "compact"]

_VALID_STRATEGIES = get_args(SerialisationStrategy)

# FHIR servers cap page size themselves, but asking for an unbounded page is
# how a tool result turns into 40 KB of JSON the model cannot use. This is the
# default page size when a caller does not specify one.
DEFAULT_PAGE_SIZE = 20

# An upper bound the caller cannot exceed. A model that asks for 10,000
# results in one call is making a mistake we should absorb rather than pass on
# to the FHIR server.
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for one server process."""

    fhir_base_url: str
    """Base URL of the FHIR server, e.g. http://localhost:8080/fhir"""

    serialisation: SerialisationStrategy
    """How resources are shaped before being returned to the model."""

    request_timeout_seconds: float
    """Per-request timeout against the FHIR server."""

    host: str
    """Interface the MCP server binds to."""

    port: int
    """Port the MCP server listens on."""

    allowed_hosts: tuple[str, ...]
    """Host header patterns the transport's DNS-rebinding check accepts.

    `127.0.0.1:*`, `localhost:*`, and `[::1]:*` always pass, for the plain
    `uv run` dev workflow. `fhir-mcp:*` is also always included: the name this
    server is reached by from a sibling container on the repo-root
    docker-compose network (the mcp-inspector service, for one), which is not
    a loopback address and so needs an explicit entry. FHIR_MCP_ALLOWED_HOSTS
    adds more, comma-separated, for setups that reach this server under some
    other name.
    """

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables, with defaults that work
        against the local Docker substrate with no configuration at all.

        Raises:
            ValueError: if FHIR_MCP_SERIALISATION is set to an unknown strategy.
                Failing loudly at startup is better than silently falling back
                to a default and reporting an experiment result for the wrong
                configuration.
        """
        serialisation = os.environ.get("FHIR_MCP_SERIALISATION", "nested")
        if serialisation not in _VALID_STRATEGIES:
            raise ValueError(
                f"FHIR_MCP_SERIALISATION={serialisation!r} is not a known strategy. "
                f"Valid values: {', '.join(_VALID_STRATEGIES)}"
            )

        extra_hosts = tuple(
            h.strip() for h in os.environ.get("FHIR_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()
        )

        return cls(
            # Matches the HAPI FHIR service in the repo-root docker-compose.yml.
            fhir_base_url=os.environ.get("FHIR_MCP_BASE_URL", "http://localhost:8080/fhir").rstrip(
                "/"
            ),
            serialisation=serialisation,  # type: ignore[arg-type]
            request_timeout_seconds=float(os.environ.get("FHIR_MCP_TIMEOUT_SECONDS", "30")),
            host=os.environ.get("FHIR_MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("FHIR_MCP_PORT", "3001")),
            allowed_hosts=(
                "127.0.0.1:*",
                "localhost:*",
                "[::1]:*",
                "fhir-mcp:*",
            )
            + extra_hosts,
        )
