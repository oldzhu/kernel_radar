#!/usr/bin/env bash
set -euo pipefail

# Helper script to run the manual repro workflow for syzbot issue #3.
# Keeps everything transparent (it just runs the documented shell commands).
#
# Default target: extid a9528028ab4ca83e8bac
#
# Usage examples:
#   tools/run_issue3_manual.sh
#   EXTID=a9528028ab4ca83e8bac MEM=4096 SMP=4 tools/run_issue3_manual.sh
#   HOSTFWD_PORT=10023 tools/run_issue3_manual.sh
#   SYZ_BIN=$HOME/mylinux/syzkaller/bin/linux_amd64 tools/run_issue3_manual.sh
#
# Optional (less stable): enable 9p share (may trigger early KASAN in some runs)
#   USE_9P=1 SHARE_DIR=$HOME/mylinux tools/run_issue3_manual.sh

EXTID=${EXTID:-a9528028ab4ca83e8bac}
REPO_ROOT=${REPO_ROOT:-"$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"}
BUNDLE_DIR=${BUNDLE_DIR:-"$REPO_ROOT/repro/$EXTID"}

# QEMU runner env passthrough
MEM=${MEM:-2048}
SMP=${SMP:-2}
HOSTFWD_PORT=${HOSTFWD_PORT:-10022}
PERSIST=${PERSIST:-0}
DAEMONIZE=${DAEMONIZE:-1}

# Syzkaller binaries location (host)
SYZ_BIN=${SYZ_BIN:-"$HOME/mylinux/syzkaller/bin/linux_amd64"}
SYZ_EXECPROG=${SYZ_EXECPROG:-"$SYZ_BIN/syz-execprog"}
SYZ_EXECUTOR=${SYZ_EXECUTOR:-"$SYZ_BIN/syz-executor"}

# Optional 9p share
USE_9P=${USE_9P:-0}
SHARE_DIR=${SHARE_DIR:-""}
SHARE_MOUNT=${SHARE_MOUNT:-/mnt/host}

# SSH probe settings
SSH_HOST=${SSH_HOST:-127.0.0.1}
SSH_PORT=${SSH_PORT:-$HOSTFWD_PORT}
SSH_OPTS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o ConnectTimeout=5
  -p "$SSH_PORT"
  root@"$SSH_HOST"
)
SSH_WAIT_SECS=${SSH_WAIT_SECS:-120}

# Monitoring
WATCH=${WATCH:-1}
WATCH_PATTERNS=${WATCH_PATTERNS:-'INFO: task|blocked for more than|hung task|vhost_worker_killed|BUG:|KASAN:|panic|Oops'}

usage() {
  cat <<EOF
Usage: $0

Environment overrides:
  EXTID=...            syzbot extid (default: $EXTID)
  BUNDLE_DIR=...       path to repro bundle (default: $BUNDLE_DIR)
  SYZ_BIN=...          dir containing syz-execprog/syz-executor
  HOSTFWD_PORT=...     host forwarded SSH port (default: $HOSTFWD_PORT)
  MEM=... SMP=...      QEMU resources
  PERSIST=1            persist disk changes (default snapshot mode)
  DAEMONIZE=0|1        run qemu detached (default: $DAEMONIZE)
  USE_9P=0|1           enable 9p share (default: $USE_9P)
  SHARE_DIR=...        host dir to share (required if USE_9P=1)
  WATCH=0|1            start serial-log watcher (default: $WATCH)

What it does:
  1) Ensure bundle exists (or prompt you to run the downloader)
  2) Restart QEMU (daemon mode by default)
  3) Wait for SSH to become reachable
  4) scp syz-execprog/syz-executor + repro.syz into /root/repro
  5) Start syz-execprog in the background in the guest
  6) Start a host-side serial-log watcher (optional)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "$REPO_ROOT" || ! -f "$REPO_ROOT/tools/syzbot_prepare_qemu_repro.py" ]]; then
  echo "ERROR: REPO_ROOT does not look like kernel_radar: $REPO_ROOT" >&2
  exit 2
fi

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "Bundle not found: $BUNDLE_DIR" >&2
  echo "Create it with:" >&2
  echo "  cd $REPO_ROOT && ./tools/syzbot_prepare_qemu_repro.py --extid $EXTID" >&2
  exit 2
fi

if [[ ! -x "$BUNDLE_DIR/run_qemu.sh" ]]; then
  echo "ERROR: missing run_qemu.sh in bundle: $BUNDLE_DIR" >&2
  exit 2
fi

if [[ ! -f "$BUNDLE_DIR/repro.syz" ]]; then
  echo "ERROR: missing repro.syz in bundle: $BUNDLE_DIR" >&2
  exit 2
fi

if [[ ! -x "$SYZ_EXECPROG" || ! -x "$SYZ_EXECUTOR" ]]; then
  echo "ERROR: missing syzkaller runner binaries on host:" >&2
  echo "  $SYZ_EXECPROG" >&2
  echo "  $SYZ_EXECUTOR" >&2
  echo "Set SYZ_BIN=... or build syzkaller first." >&2
  exit 2
fi

cd "$BUNDLE_DIR"

echo "[host] bundle=$BUNDLE_DIR"
echo "[host] qemu: MEM=$MEM SMP=$SMP HOSTFWD_PORT=$HOSTFWD_PORT PERSIST=$PERSIST DAEMONIZE=$DAEMONIZE"

# Stop VM if already running
if [[ -f qemu.pid ]]; then
  old_pid=$(cat qemu.pid || true)
  if [[ -n "${old_pid:-}" ]]; then
    echo "[host] stopping existing qemu pid=$old_pid"
    kill "$old_pid" 2>/dev/null || true
    sleep 1
    kill -9 "$old_pid" 2>/dev/null || true
  fi
fi

rm -f qemu.pid qemu-serial.log watch_patterns.log watcher.pid

# Start QEMU
qemu_env=(MEM="$MEM" SMP="$SMP" HOSTFWD_PORT="$HOSTFWD_PORT" PERSIST="$PERSIST" DAEMONIZE="$DAEMONIZE")
if [[ "$USE_9P" == "1" ]]; then
  if [[ -z "$SHARE_DIR" ]]; then
    echo "ERROR: USE_9P=1 requires SHARE_DIR=..." >&2
    exit 2
  fi
  qemu_env+=(SHARE_DIR="$SHARE_DIR" SHARE_MOUNT="$SHARE_MOUNT")
  echo "[host] 9p enabled: SHARE_DIR=$SHARE_DIR SHARE_MOUNT=$SHARE_MOUNT" >&2
fi

echo "[host] starting qemu..."
( env "${qemu_env[@]}" ./run_qemu.sh )

# Wait for SSH
echo "[host] waiting for SSH on $SSH_HOST:$SSH_PORT (timeout ${SSH_WAIT_SECS}s)"
ssh_up=0
for i in $(seq 1 "$SSH_WAIT_SECS"); do
  if timeout 2s ssh "${SSH_OPTS[@]}" true 2>/dev/null; then
    echo "[host] ssh_up_after_seconds=$i"
    ssh_up=1
    break
  fi
  sleep 1
done

if [[ "$ssh_up" != "1" ]]; then
  echo "[host] SSH did not come up within ${SSH_WAIT_SECS}s." >&2
  echo "[host] Check serial log: tail -n 200 $BUNDLE_DIR/qemu-serial.log" >&2
  exit 1
fi

# Stage binaries + repro
stage_log="$BUNDLE_DIR/.tmp_stage_run.$(date +%Y%m%d-%H%M%S).txt"
{
  echo "[host] stage_start $(date -Is)"
  echo "[host] local_bins:";
  ls -l "$SYZ_EXECPROG" "$SYZ_EXECUTOR" "$BUNDLE_DIR/repro.syz"
  echo "[host] mkdir /root/repro";
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p "$SSH_PORT" root@"$SSH_HOST" 'mkdir -p /root/repro'
  echo "[host] scp binaries+repro";
  scp -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SYZ_EXECPROG" "$SYZ_EXECUTOR" "$BUNDLE_DIR/repro.syz" \
    root@"$SSH_HOST":/root/repro/
  echo "[host] start execprog";
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p "$SSH_PORT" root@"$SSH_HOST" \
    'set -e; cd /root/repro; chmod +x syz-execprog syz-executor; rm -f execprog.out; \
     nohup ./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz \
       >execprog.out 2>&1 & echo execprog_pid=$!'
  echo "[host] tail execprog.out (may fail later if ssh degrades)";
  timeout 8s ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
    -p "$SSH_PORT" root@"$SSH_HOST" 'tail -n 20 /root/repro/execprog.out' || true
  echo "[host] stage_done $(date -Is)"
} | tee "$stage_log"

echo "[host] stage_log=$stage_log"

# Start watcher
if [[ "$WATCH" == "1" ]]; then
  echo "[host] starting serial-log watcher (patterns: $WATCH_PATTERNS)"
  bash -c "stdbuf -oL tail -n 0 -F '$BUNDLE_DIR/qemu-serial.log' | \
    stdbuf -oL egrep --line-buffered '$WATCH_PATTERNS' | \
    tee -a '$BUNDLE_DIR/watch_patterns.log'" \
    >/dev/null 2>&1 &
  echo $! > "$BUNDLE_DIR/watcher.pid"
  echo "[host] watcher_pid=$(cat "$BUNDLE_DIR/watcher.pid")"
  echo "[host] follow: tail -f '$BUNDLE_DIR/watch_patterns.log'"
fi

echo "[host] done. If SSH starts failing, rely on:"
echo "  tail -f '$BUNDLE_DIR/watch_patterns.log'"
echo "  tail -n 200 '$BUNDLE_DIR/qemu-serial.log'"
