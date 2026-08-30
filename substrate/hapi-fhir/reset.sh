#!/usr/bin/env bash
# Full reset: wipes the Postgres volume and brings up a fresh, empty stack.
# Data now persists across normal restarts (that's the point of Postgres),
# so a plain container restart no longer clears it, this does.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

docker compose down -v
docker compose up -d hapi-fhir
