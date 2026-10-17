#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_REPO="https://github.com/Unstructured-IO/unstructured-api.git"
UPSTREAM_REF_FILE="$SCRIPT_DIR/upstream-ref"

LATEST_REF="$(git ls-remote --exit-code "$UPSTREAM_REPO" refs/heads/main | awk 'NR == 1 { print $1 }')"
if [[ ! "$LATEST_REF" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Could not resolve the upstream main branch to a full Git commit SHA." >&2
    exit 1
fi

CURRENT_REF="$(<"$UPSTREAM_REF_FILE")"
if [ "$LATEST_REF" = "$CURRENT_REF" ]; then
    echo "Unstructured is already pinned to upstream main at $LATEST_REF."
    "$SCRIPT_DIR/build-image.sh" "$@"
    exit 0
fi

echo "Building Unstructured from upstream main at $LATEST_REF."
UNSTRUCTURED_API_SOURCE_REF="$LATEST_REF" "$SCRIPT_DIR/build-image.sh" "$@"

PIN_TEMP="$(mktemp "$SCRIPT_DIR/upstream-ref.XXXXXX")"
trap 'rm -f -- "$PIN_TEMP"' EXIT
printf '%s\n' "$LATEST_REF" > "$PIN_TEMP"
chmod 644 "$PIN_TEMP"
mv "$PIN_TEMP" "$UPSTREAM_REF_FILE"
trap - EXIT

echo "Updated Unstructured source pin to $LATEST_REF."
