#!/usr/bin/env bash
# Build the Synthea image (cached after the first run) and generate a
# population into data/synthea_output/<label>/, so different seeds and
# population sizes don't overwrite each other.
#
# Usage: ./generate.sh <seed> <population> [label]
#   ./generate.sh 1000 200
#   ./generate.sh 1000 2000 dev-2k
set -euo pipefail

SEED="${1:?usage: generate.sh <seed> <population> [label]}"
POPULATION="${2:?usage: generate.sh <seed> <population> [label]}"
LABEL="${3:-seed-${SEED}-n${POPULATION}}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$REPO_ROOT/data/synthea_output/$LABEL"
IMAGE_TAG="agentward/synthea:v4.0.0"

mkdir -p "$OUT_DIR"

docker build -t "$IMAGE_TAG" "$REPO_ROOT/substrate/synthea"
docker run --rm \
    -v "$OUT_DIR:/app/output" \
    "$IMAGE_TAG" \
    -s "$SEED" -p "$POPULATION"

echo "Generated into $OUT_DIR"
