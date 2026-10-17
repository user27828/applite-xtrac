#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_REPO="https://github.com/Unstructured-IO/unstructured-api.git"
UPSTREAM_REF_FILE="$SCRIPT_DIR/upstream-ref"
IMAGE_NAME="applite-xtrac-unstructured-io:latest"
UV_SYNC_LINE="RUN uv sync --no-dev --no-install-project --locked"
UV_CACHE_MOUNT="RUN --mount=type=cache,id=applite-xtrac-unstructured-uv,target=/home/notebook-user/.cache/uv,uid=1000,gid=1000,sharing=locked uv sync --no-dev --no-install-project --locked"

if [ ! -f "$UPSTREAM_REF_FILE" ]; then
    echo "Missing pinned Unstructured source revision: $UPSTREAM_REF_FILE" >&2
    exit 1
fi

UPSTREAM_REF="${UNSTRUCTURED_API_SOURCE_REF:-$(<"$UPSTREAM_REF_FILE")}"
if [[ ! "$UPSTREAM_REF" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Unstructured source revision must be a full 40-character Git commit SHA." >&2
    exit 1
fi

DOCKER_ARGS=()
FORCE_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --no-cache)
            DOCKER_ARGS+=("--no-cache")
            FORCE_BUILD=true
            ;;
        *)
            echo "Unsupported build option: $arg" >&2
            echo "Supported option: --no-cache" >&2
            exit 2
            ;;
    esac
done

if ! $FORCE_BUILD; then
    if CURRENT_REF="$(docker image inspect "$IMAGE_NAME" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>/dev/null)"; then
        if [ "$CURRENT_REF" = "$UPSTREAM_REF" ]; then
            echo "Unstructured image already built from $UPSTREAM_REF."
            exit 0
        fi
    fi
fi

if ! command -v git >/dev/null 2>&1; then
    echo "git is required to fetch the pinned Unstructured source." >&2
    exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required to build the Unstructured image." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to apply the cache-mount patch." >&2
    exit 1
fi

BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/applite-unstructured-build.XXXXXX")"
trap 'rm -rf -- "$BUILD_DIR"' EXIT
SOURCE_DIR="$BUILD_DIR/source"

git init --quiet "$SOURCE_DIR"
git -C "$SOURCE_DIR" remote add origin "$UPSTREAM_REPO"
git -C "$SOURCE_DIR" fetch --quiet --depth=1 origin "$UPSTREAM_REF"
git -C "$SOURCE_DIR" checkout --quiet --detach FETCH_HEAD

RESOLVED_REF="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
if [ "$RESOLVED_REF" != "$UPSTREAM_REF" ]; then
    echo "Fetched source revision $RESOLVED_REF does not match pinned revision $UPSTREAM_REF." >&2
    exit 1
fi

python3 - "$SOURCE_DIR/Dockerfile" <<'PY'
from pathlib import Path
import sys

dockerfile = Path(sys.argv[1])
content = dockerfile.read_text()
sync_line = "RUN uv sync --no-dev --no-install-project --locked"
cache_mount = (
    "RUN --mount=type=cache,id=applite-xtrac-unstructured-uv,"
    "target=/home/notebook-user/.cache/uv,uid=1000,gid=1000,sharing=locked "
    "uv sync --no-dev --no-install-project --locked"
)

if "ENV UV_LINK_MODE=copy" not in content:
    raise SystemExit("Upstream no longer sets UV_LINK_MODE=copy; the cache mount needs review.")

if cache_mount not in content:
    if content.count(sync_line) != 1:
        raise SystemExit(
            "Expected exactly one locked UV sync command in the upstream Dockerfile; "
            "the upstream build changed and needs review."
        )
    dockerfile.write_text(content.replace(sync_line, cache_mount, 1))
PY

rm -rf -- "$SOURCE_DIR/.git"

echo "Building Unstructured from upstream commit $UPSTREAM_REF with a persistent BuildKit UV cache."
DOCKER_BUILDKIT=1 docker build \
    --tag "$IMAGE_NAME" \
    --build-arg PIPELINE_PACKAGE=general \
    --label "org.opencontainers.image.source=https://github.com/Unstructured-IO/unstructured-api" \
    --label "org.opencontainers.image.revision=$UPSTREAM_REF" \
    "${DOCKER_ARGS[@]}" \
    "$SOURCE_DIR"
