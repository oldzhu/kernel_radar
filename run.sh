#!/usr/bin/env bash
set -euo pipefail

# Wrapper for kernel_radar.py
# - Uses local venv at .venv/
# - Writes a date-stamped report into reports/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONFIG_PATH="$SCRIPT_DIR/config.yaml"
SINCE_HOURS="24"
OUT_DIR="$SCRIPT_DIR/reports"
INCLUDE_SEEN="0"

usage() {
  cat <<'USAGE'
Usage: ./run.sh [--since-hours N] [--config PATH] [--out-dir DIR] [--include-seen]

Defaults:
  --since-hours 24
  --config      ./config.yaml
  --out-dir     ./reports

Output:
  Creates a markdown file named like: kernel-digest-YYYY-MM-DD.md
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since-hours)
      SINCE_HOURS="$2"; shift 2 ;;
    --config)
      CONFIG_PATH="$2"; shift 2 ;;
    --out-dir)
      OUT_DIR="$2"; shift 2 ;;
    --include-seen)
      INCLUDE_SEEN="1"; shift 1 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  echo "Missing venv at $SCRIPT_DIR/.venv. Create it first:" >&2
  echo "  sudo apt-get install -y python3-venv" >&2
  echo "  cd $SCRIPT_DIR && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# Date-stamped report name (UTC date; stable for daily timer)
DATE_UTC="$(date -u +%F)"
OUT_PATH="$OUT_DIR/kernel-digest-$DATE_UTC.md"

ARGS=("$SCRIPT_DIR/kernel_radar.py" --config "$CONFIG_PATH" --since-hours "$SINCE_HOURS" --out "$OUT_PATH")
if [[ "$INCLUDE_SEEN" == "1" ]]; then
  ARGS+=(--include-seen)
fi

"$SCRIPT_DIR/.venv/bin/python" "${ARGS[@]}"

echo "Wrote: $OUT_PATH"
