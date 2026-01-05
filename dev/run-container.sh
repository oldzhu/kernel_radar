#!/usr/bin/env bash
set -euo pipefail

# Build + run a Ubuntu 24.04 container with kernel contribution tools.
#
# Design choices:
# - Container is for build/tooling only.
# - Email sending stays on the host (simpler + keeps SMTP creds off container).
# - Mounts your $HOME into the container so your upstream linux checkout is accessible.
#
# Usage:
#   ./dev/run-container.sh
#   ./dev/run-container.sh --shell
#   ./dev/run-container.sh --cmd "bash -lc 'cd ~/linux && make help'"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="kernel-radar-kernel-dev:ubuntu24"

ENGINE=""
if command -v podman >/dev/null 2>&1; then
  ENGINE="podman"
elif command -v docker >/dev/null 2>&1; then
  ENGINE="docker"
else
  echo "ERROR: need podman or docker" >&2
  exit 1
fi

MODE="shell"
CMD=("bash")

usage() {
  cat <<'USAGE'
Usage:
  ./dev/run-container.sh [--build] [--shell] [--cmd "..."]

Options:
  --build         Rebuild the image
  --shell         Start an interactive shell (default)
  --cmd STRING    Run a command non-interactively

Notes:
  - Mounts your $HOME into the container at the same path.
  - Runs as your UID/GID to avoid root-owned build artifacts.
USAGE
}

BUILD="0"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      BUILD="1"; shift ;;
    --shell)
      MODE="shell"; CMD=("bash"); shift ;;
    --cmd)
      MODE="cmd"; CMD=("bash" "-lc" "$2"); shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

# Build image (or ensure it exists)
if [[ "$BUILD" == "1" ]]; then
  "$ENGINE" build -t "$IMAGE_NAME" -f "$REPO_ROOT/dev/Dockerfile" "$REPO_ROOT"
else
  if ! "$ENGINE" image exists "$IMAGE_NAME" 2>/dev/null; then
    "$ENGINE" build -t "$IMAGE_NAME" -f "$REPO_ROOT/dev/Dockerfile" "$REPO_ROOT"
  fi
fi

UID_GID="$(id -u):$(id -g)"
HOME_DIR="${HOME}"

# If you use SELinux + podman, you may need :Z on binds; we keep it simple here.
RUN_ARGS=(
  --rm
  -it
  -w "$PWD"
  -e "HOME=$HOME_DIR"
  -e "USER=${USER:-user}"
  -e "TERM=${TERM:-xterm-256color}"
  -e "CCACHE_DIR=$HOME_DIR/.ccache"
  -v "$HOME_DIR:$HOME_DIR"
  -v "/etc/passwd:/etc/passwd:ro"
  -v "/etc/group:/etc/group:ro"
)

# Docker uses a different syntax for userns flags; keep default.
RUN_ARGS+=(--user "$UID_GID")

exec "$ENGINE" run "${RUN_ARGS[@]}" "$IMAGE_NAME" "${CMD[@]}"
