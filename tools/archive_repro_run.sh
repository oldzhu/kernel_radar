#!/usr/bin/env bash
set -euo pipefail

# Archive current repro run artifacts into repro/<extid>/runs/<timestamp>/.
# Safe by default: does NOT copy disk images.
#
# Usage:
#   tools/archive_repro_run.sh /path/to/repro/<extid>
#   TAG=panic tools/archive_repro_run.sh repro/a9528028ab4ca83e8bac
#
# Inputs (optional env):
#   TAG=...            suffix in directory name
#   REPRO_SYZ=...      path to repro file used (copied as repro.used.syz)
#   KERNEL_IMAGE=...   kernel path used for this run
#   APPEND_EXTRA=...   extra kernel cmdline
#   HOSTFWD_PORT=...   forwarded SSH port
#   MEM=... SMP=...    QEMU resources
#   EXTID=...          extid (for metadata)
#   USE_LOCALIMAGE=... 0/1 (for metadata)

BUNDLE_DIR=${1:-}
if [[ -z "$BUNDLE_DIR" ]]; then
  echo "Usage: $0 /path/to/repro/<extid>" >&2
  exit 2
fi
if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "ERROR: bundle dir not found: $BUNDLE_DIR" >&2
  exit 2
fi

TAG=${TAG:-}
TS=$(date +%Y%m%d-%H%M%S)
RUNS_DIR="$BUNDLE_DIR/runs"
mkdir -p "$RUNS_DIR"

suffix=""
if [[ -n "$TAG" ]]; then
  # sanitize: keep alnum, dash, underscore
  safe=$(echo "$TAG" | tr -cd '[:alnum:]_-' | cut -c1-40)
  [[ -n "$safe" ]] && suffix="-$safe"
fi

OUT_DIR="$RUNS_DIR/$TS$suffix"
mkdir -p "$OUT_DIR"

copy_if_exists() {
  local src=$1
  local dst=$2
  if [[ -f "$src" ]]; then
    cp -f "$src" "$dst"
  fi
}

# Core logs
copy_if_exists "$BUNDLE_DIR/qemu-serial.log"       "$OUT_DIR/qemu-serial.log"
copy_if_exists "$BUNDLE_DIR/watch_patterns.log"    "$OUT_DIR/watch_patterns.log"
copy_if_exists "$BUNDLE_DIR/execprog_stream.log"   "$OUT_DIR/execprog_stream.log"

# Stage log: pick newest matching temp stage log
latest_stage=$(ls -1t "$BUNDLE_DIR"/.tmp_stage_run.*.txt 2>/dev/null | head -n 1 || true)
if [[ -n "$latest_stage" ]]; then
  cp -f "$latest_stage" "$OUT_DIR/$(basename "$latest_stage")"
fi

# Configs / repros
copy_if_exists "$BUNDLE_DIR/kernel.config" "$OUT_DIR/kernel.config"
copy_if_exists "$BUNDLE_DIR/repro.syz"     "$OUT_DIR/repro.bundle.syz"

if [[ -n "${REPRO_SYZ:-}" && -f "$REPRO_SYZ" ]]; then
  cp -f "$REPRO_SYZ" "$OUT_DIR/repro.used.syz"
fi

# Localimage artifacts (if present)
if [[ -d "$BUNDLE_DIR/localimage" ]]; then
  copy_if_exists "$BUNDLE_DIR/localimage/config"  "$OUT_DIR/local-kernel.config"
  copy_if_exists "$BUNDLE_DIR/localimage/bzImage" "$OUT_DIR/local-kernel.bzImage"
fi

# Capture QEMU cmdline if still running
qemu_cmdline=""
if [[ -f "$BUNDLE_DIR/qemu.pid" ]]; then
  qpid=$(cat "$BUNDLE_DIR/qemu.pid" 2>/dev/null || true)
  if [[ -n "${qpid:-}" ]] && kill -0 "$qpid" 2>/dev/null; then
    qemu_cmdline=$(tr '\0' ' ' <"/proc/$qpid/cmdline" 2>/dev/null || true)
  fi
fi

# Metadata
{
  echo "timestamp=$TS"
  echo "bundle_dir=$BUNDLE_DIR"
  echo "extid=${EXTID:-}"
  echo "tag=${TAG:-}"
  echo "repro_syz=${REPRO_SYZ:-}"
  echo "kernel_image=${KERNEL_IMAGE:-}"
  echo "use_localimage=${USE_LOCALIMAGE:-}"
  echo "mem=${MEM:-}"
  echo "smp=${SMP:-}"
  echo "hostfwd_port=${HOSTFWD_PORT:-}"
  echo "append_extra=${APPEND_EXTRA:-}"
  if command -v git >/dev/null 2>&1; then
    # best-effort: if this is run inside the repo, capture commit
    repo_root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel 2>/dev/null || true)
    if [[ -n "$repo_root" ]]; then
      echo "kernel_radar_repo=$repo_root"
      echo "kernel_radar_head=$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)"
    fi
  fi
  [[ -n "$qemu_cmdline" ]] && echo "qemu_cmdline=$qemu_cmdline"
} >"$OUT_DIR/metadata.txt"

# Convenience symlink to last archive
ln -sfn "$(basename "$OUT_DIR")" "$RUNS_DIR/last"

echo "[ok] archived -> $OUT_DIR"