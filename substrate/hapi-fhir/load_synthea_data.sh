#!/usr/bin/env bash
# Load a generated Synthea dataset into a running HAPI FHIR server, in the
# order that actually works: hospitals, then practitioners, then patients.
# Patient bundles reference hospitals/practitioners by identifier, so those
# two have to exist first or the reference won't resolve.
#
# Usage: ./load_synthea_data.sh <label> [fhir_base_url]
#   ./load_synthea_data.sh seed-1000-n200
set -euo pipefail

LABEL="${1:?usage: load_synthea_data.sh <label> [fhir_base_url]}"
FHIR_BASE="${2:-http://localhost:8080/fhir}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="$REPO_ROOT/data/synthea_output/$LABEL/fhir"

if [ ! -d "$DATA_DIR" ]; then
    echo "No such folder: $DATA_DIR" >&2
    echo "Generate it first with substrate/synthea/generate.sh" >&2
    exit 1
fi

echo "Waiting for HAPI FHIR at $FHIR_BASE ..."
until curl -sf "$FHIR_BASE/metadata" > /dev/null; do
    sleep 2
done
echo "HAPI FHIR is up."

RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT

post_bundle() {
    local file="$1"
    local http_code
    http_code=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" \
        -H "Content-Type: application/fhir+json" \
        -d "@$file" \
        "$FHIR_BASE")
    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        echo "OK   $(basename "$file")"
    else
        echo "FAIL $(basename "$file") (HTTP $http_code)"
        cat "$RESPONSE_FILE"
    fi
}

echo "Loading hospitals..."
for f in "$DATA_DIR"/hospitalInformation*.json; do
    [ -e "$f" ] && post_bundle "$f"
done

echo "Loading practitioners..."
for f in "$DATA_DIR"/practitionerInformation*.json; do
    [ -e "$f" ] && post_bundle "$f"
done

echo "Loading patients..."
count=0
for f in "$DATA_DIR"/*.json; do
    base="$(basename "$f")"
    if [[ "$base" == hospitalInformation* || "$base" == practitionerInformation* ]]; then
        continue
    fi
    post_bundle "$f"
    count=$((count + 1))
done

echo "Done. Loaded $count patient bundles."
