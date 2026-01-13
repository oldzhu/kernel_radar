#!/usr/bin/env bash
set -euo pipefail

# Disassemble the syzbot bundle kernel's vhost_worker_killed() by address.
#
# Why: the bundle vmlinux is typically stripped, so we cannot do
#   objdump --disassemble=vhost_worker_killed
# Instead we:
#   1) boot the bundle kernel
#   2) read the runtime address from /proc/kallsyms
#   3) extract vmlinux from bzImage
#   4) objdump using --start-address/--stop-address
#
# Usage:
#   cd /home/oldzhu/mylinux/kernel_radar
#   EXTID=a9528028ab4ca83e8bac tools/disassemble_issue3_bundle_vhost_worker_killed.sh
#
# Notes:
# - Expects the VM to already be up and reachable via SSH (default port 10022).
# - Uses ~/mylinux/linux/scripts/extract-vmlinux to extract an ELF from bzImage.

EXTID=${EXTID:-a9528028ab4ca83e8bac}
REPO_ROOT=${REPO_ROOT:-"$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"}
BUNDLE_DIR=${BUNDLE_DIR:-"$REPO_ROOT/repro/$EXTID"}

SSH_HOST=${SSH_HOST:-127.0.0.1}
SSH_PORT=${SSH_PORT:-10022}
SSH_OPTS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o ConnectTimeout=5
  -p "$SSH_PORT"
  root@"$SSH_HOST"
)

VMLINUX_EXTRACTOR=${VMLINUX_EXTRACTOR:-"$HOME/mylinux/linux/scripts/extract-vmlinux"}
VMLINUX=${VMLINUX:-"$BUNDLE_DIR/vmlinux.from_bzImage"}
BZIMAGE=${BZIMAGE:-"$BUNDLE_DIR/bzImage"}

WIN=${WIN:-0x1200}
OUT=${OUT:-"$BUNDLE_DIR/tmp_disas_vhost_worker_killed_full.txt"}

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "error: BUNDLE_DIR not found: $BUNDLE_DIR" >&2
  exit 1
fi

if [[ ! -f "$BZIMAGE" ]]; then
  echo "error: bzImage not found: $BZIMAGE" >&2
  exit 1
fi

if [[ ! -x "$VMLINUX_EXTRACTOR" ]]; then
  echo "error: vmlinux extractor not executable: $VMLINUX_EXTRACTOR" >&2
  echo "hint: set VMLINUX_EXTRACTOR=/path/to/extract-vmlinux" >&2
  exit 1
fi

kallsyms_get() {
  ssh "${SSH_OPTS[@]}" "$@"
}

VMLINUX_ADDR_HEX=$(kallsyms_get "grep -m1 -w vhost_worker_killed /proc/kallsyms | awk '{print \$1}'")
if [[ -z "$VMLINUX_ADDR_HEX" ]]; then
  echo "error: failed to read vhost_worker_killed address from /proc/kallsyms" >&2
  exit 1
fi

MUTEX_LOCK_NESTED=$(kallsyms_get "grep -m1 -w mutex_lock_nested /proc/kallsyms || true")
MUTEX_UNLOCK=$(kallsyms_get "grep -m1 -w mutex_unlock /proc/kallsyms || true")

if [[ ! -f "$VMLINUX" ]]; then
  echo "extracting vmlinux from bzImage -> $VMLINUX" >&2
  "$VMLINUX_EXTRACTOR" "$BZIMAGE" > "$VMLINUX"
fi

START=$((16#$VMLINUX_ADDR_HEX))
STOP=$((START + WIN))

{
  echo "# Generated: $(date -Is)"
  echo "# extid: $EXTID"
  echo "# vhost_worker_killed: $VMLINUX_ADDR_HEX"
  [[ -n "$MUTEX_LOCK_NESTED" ]] && echo "# $MUTEX_LOCK_NESTED"
  [[ -n "$MUTEX_UNLOCK" ]] && echo "# $MUTEX_UNLOCK"
  echo "# objdump: --start-address=0x$(printf '%x' "$START") --stop-address=0x$(printf '%x' "$STOP")"
  echo
  objdump -d --no-show-raw-insn --start-address="$START" --stop-address="$STOP" "$VMLINUX"
} > "$OUT"

echo "wrote: $OUT" >&2
