#!/usr/bin/env bash
set -euo pipefail

# Poll watch_patterns.log and stop when it becomes non-empty.
# Designed to be run in a terminal.
#
# Defaults to syzbot issue #3 bundle: repro/a9528028ab4ca83e8bac
#
# Examples:
#   tools/monitor_issue3_watch.sh
#   tools/monitor_issue3_watch.sh repro/a9528028ab4ca83e8bac
#   INTERVAL=1 TAIL_N=20 tools/monitor_issue3_watch.sh

BUNDLE_DIR=${1:-repro/a9528028ab4ca83e8bac}
INTERVAL=${INTERVAL:-2}
TAIL_N=${TAIL_N:-5}

WATCH_FILE="$BUNDLE_DIR/watch_patterns.log"
SERIAL_FILE="$BUNDLE_DIR/qemu-serial.log"

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "ERROR: bundle dir not found: $BUNDLE_DIR" >&2
  exit 2
fi

if [[ ! -f "$WATCH_FILE" ]]; then
  echo "ERROR: missing $WATCH_FILE" >&2
  echo "Hint: start the repro first (tools/run_issue3_manual.sh)." >&2
  exit 2
fi

echo "[mon] bundle=$BUNDLE_DIR"
echo "[mon] watching: $WATCH_FILE"
echo "[mon] interval=${INTERVAL}s tail_n=$TAIL_N"

last_lines=-1
while true; do
  lines=$(wc -l <"$WATCH_FILE" 2>/dev/null || echo 0)
  ts=$(date -Is)

  # Periodic status line (only print if changed, or every ~30 iterations).
  if [[ "$lines" != "$last_lines" ]]; then
    echo "[$ts] wc -l $WATCH_FILE => $lines"
    last_lines="$lines"
  fi

  if [[ "$lines" -gt 0 ]]; then
    echo ""
    echo "[mon] MATCH CAPTURED at $ts"
    echo "---- captured patterns (tail -n $((TAIL_N * 10)) ) ----"
    tail -n $((TAIL_N * 10)) "$WATCH_FILE" || true

    if [[ -f "$SERIAL_FILE" ]]; then
      echo "---- serial tail (last 200 lines) ----"
      tail -n 200 "$SERIAL_FILE" || true
    fi

    exit 0
  fi

  # Keep showing a tiny tail so you see it's alive.
  if [[ "$TAIL_N" -gt 0 ]]; then
    tail -n "$TAIL_N" "$WATCH_FILE" 2>/dev/null || true
  fi

  sleep "$INTERVAL"
done
