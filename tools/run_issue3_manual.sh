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

# Kernel selection (A/B testing)
USE_LOCALIMAGE=${USE_LOCALIMAGE:-0}
KERNEL_IMAGE=${KERNEL_IMAGE:-""}

# Optional tracing passthrough (see repro/*/run_qemu.sh)
FTRACE_DUMP_ON_OOPS=${FTRACE_DUMP_ON_OOPS:-1}
TRACE_BUF_SIZE_KB=${TRACE_BUF_SIZE_KB:-1024}
APPEND_EXTRA=${APPEND_EXTRA:-""}

# Syzkaller binaries location (host)
SYZ_BIN=${SYZ_BIN:-"$HOME/mylinux/syzkaller/bin/linux_amd64"}
SYZ_EXECPROG=${SYZ_EXECPROG:-"$SYZ_BIN/syz-execprog"}
SYZ_EXECUTOR=${SYZ_EXECUTOR:-"$SYZ_BIN/syz-executor"}

# Optional 9p share
REPRO_SYZ=${REPRO_SYZ:-"$BUNDLE_DIR/repro.syz"}

# Optional alternate repro file (keeps original syzbot bundle untouched).
# Example: REPRO_SYZ=$BUNDLE_DIR/repro.local.syz
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
SSH_WAIT_SECS=${SSH_WAIT_SECS:-240}

# syz-execprog knobs (guest-side workload)
EXECPROG_SANDBOX=${EXECPROG_SANDBOX:-none}
EXECPROG_PROCS=${EXECPROG_PROCS:-6}
EXECPROG_THREADED=${EXECPROG_THREADED:-1}
EXECPROG_REPEAT=${EXECPROG_REPEAT:-0}
EXECPROG_EXTRA_ARGS=${EXECPROG_EXTRA_ARGS:-}

# Monitoring
WATCH=${WATCH:-1}
WATCH_PATTERNS=${WATCH_PATTERNS:-'INFO: task|blocked for more than|hung task|vhost_worker_killed|BUG:|KASAN:|panic|Oops'}

# Auto-archive logs on first watcher hit.
AUTO_ARCHIVE_ON_HIT=${AUTO_ARCHIVE_ON_HIT:-1}
ARCHIVE_TAG=${ARCHIVE_TAG:-""}
STOP_ON_HIT=${STOP_ON_HIT:-0}

# Optional: stream guest /root/repro/execprog.out to a host file via a long-lived ssh tail.
# Useful when execprog is run with -output/-debug so we can preserve the last printed program.
CAPTURE_EXECPROG=${CAPTURE_EXECPROG:-0}
EXECPROG_STREAM_LOG=${EXECPROG_STREAM_LOG:-"$BUNDLE_DIR/execprog_stream.log"}
EXECPROG_STREAM_MAX_BYTES=${EXECPROG_STREAM_MAX_BYTES:-5242880}
EXECPROG_STREAM_TRIM_SECS=${EXECPROG_STREAM_TRIM_SECS:-5}

usage() {
  cat <<EOF
Usage: $0 [--stop|--status] [--clean]

Environment overrides:
  EXTID=...            syzbot extid (default: $EXTID)
  BUNDLE_DIR=...       path to repro bundle (default: $BUNDLE_DIR)
  SYZ_BIN=...          dir containing syz-execprog/syz-executor
  HOSTFWD_PORT=...     host forwarded SSH port (default: $HOSTFWD_PORT)
  MEM=... SMP=...      QEMU resources
  USE_LOCALIMAGE=0|1   boot localimage/bzImage instead of bundle bzImage
  KERNEL_IMAGE=...     explicit kernel path for QEMU (overrides USE_LOCALIMAGE)
  PERSIST=1            persist disk changes (default snapshot mode)
  DAEMONIZE=0|1        run qemu detached (default: $DAEMONIZE)
  FTRACE_DUMP_ON_OOPS=0|1 dump ftrace buffer on oops/panic (default: $FTRACE_DUMP_ON_OOPS)
  TRACE_BUF_SIZE_KB=... ftrace ring buffer size (default: $TRACE_BUF_SIZE_KB)
  APPEND_EXTRA='...'   extra kernel cmdline appended for QEMU
  USE_9P=0|1           enable 9p share (default: $USE_9P)
  SHARE_DIR=...        host dir to share (required if USE_9P=1)
  WATCH=0|1            start serial-log watcher (default: $WATCH)
  AUTO_ARCHIVE_ON_HIT=0|1 archive logs on first watcher hit (default: $AUTO_ARCHIVE_ON_HIT)
  ARCHIVE_TAG=...      suffix for runs/<timestamp>-<tag>/ (default: empty)
  STOP_ON_HIT=0|1      stop VM after archiving (default: $STOP_ON_HIT)
  EXECPROG_SANDBOX=... syz-execprog -sandbox (default: $EXECPROG_SANDBOX)
  EXECPROG_PROCS=...   syz-execprog -procs (default: $EXECPROG_PROCS)
  EXECPROG_THREADED=0|1 syz-execprog -threaded (default: $EXECPROG_THREADED)
  EXECPROG_REPEAT=...  syz-execprog -repeat (default: $EXECPROG_REPEAT)
  EXECPROG_EXTRA_ARGS='...' extra args appended to syz-execprog
  CAPTURE_EXECPROG=0|1 stream /root/repro/execprog.out to host (default: $CAPTURE_EXECPROG)
  EXECPROG_STREAM_LOG=... host path for streamed execprog.out (default: $EXECPROG_STREAM_LOG)
  EXECPROG_STREAM_MAX_BYTES=... max bytes to keep in execprog stream log (default: $EXECPROG_STREAM_MAX_BYTES, 0 disables trimming)
  EXECPROG_STREAM_TRIM_SECS=... how often to trim the stream log (default: $EXECPROG_STREAM_TRIM_SECS)
  --stop               stop QEMU + watcher (uses qemu.pid / watcher.pid)
  --status             show QEMU/watcher status and log sizes
  --clean              (with --stop) also remove qemu.pid/watcher.pid

What it does:
  1) Ensure bundle exists (or prompt you to run the downloader)
  2) Restart QEMU (daemon mode by default)
  3) Wait for SSH to become reachable
  4) scp syz-execprog/syz-executor + repro file into /root/repro (as repro.syz)
  5) Start syz-execprog in the background in the guest
  6) Start a host-side serial-log watcher (optional)
EOF
}

ACTION=start
CLEAN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --stop)
      ACTION=stop
      shift
      ;;
    --status)
      ACTION=status
      shift
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    *)
      echo "Unknown arg: $1" >&2
      echo "Run with --help for usage." >&2
      exit 2
      ;;
  esac
done

if [[ "$CLEAN" == "1" && "$ACTION" == "start" ]]; then
  echo "ERROR: --clean must be used with --stop (e.g. --stop --clean)." >&2
  exit 2
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

stop_vm() {
  local stopped=0

  if [[ -f execprog_tail.pid ]]; then
    local tpid
    tpid=$(cat execprog_tail.pid 2>/dev/null || true)
    if [[ -n "${tpid:-}" ]] && kill -0 "$tpid" 2>/dev/null; then
      echo "[host] stopping execprog tail pid=$tpid"
      kill "$tpid" 2>/dev/null || true
      sleep 0.2
      kill -9 "$tpid" 2>/dev/null || true
      stopped=1
    fi
  fi

  if [[ -f execprog_trim.pid ]]; then
    local cpid
    cpid=$(cat execprog_trim.pid 2>/dev/null || true)
    if [[ -n "${cpid:-}" ]] && kill -0 "$cpid" 2>/dev/null; then
      echo "[host] stopping execprog trim pid=$cpid"
      kill "$cpid" 2>/dev/null || true
      sleep 0.2
      kill -9 "$cpid" 2>/dev/null || true
      stopped=1
    fi
  fi

  if [[ -f watcher.pid ]]; then
    local wpid
    wpid=$(cat watcher.pid 2>/dev/null || true)
    if [[ -n "${wpid:-}" ]] && kill -0 "$wpid" 2>/dev/null; then
      echo "[host] stopping watcher pid=$wpid"
      kill "$wpid" 2>/dev/null || true
      sleep 0.2
      kill -9 "$wpid" 2>/dev/null || true
      stopped=1
    fi
  fi

  if [[ -f qemu.pid ]]; then
    local qpid
    qpid=$(cat qemu.pid 2>/dev/null || true)
    if [[ -n "${qpid:-}" ]] && kill -0 "$qpid" 2>/dev/null; then
      echo "[host] stopping qemu pid=$qpid"
      kill "$qpid" 2>/dev/null || true
      sleep 1
      kill -9 "$qpid" 2>/dev/null || true
      stopped=1
    fi
  fi

  if [[ "$CLEAN" == "1" ]]; then
    rm -f qemu.pid watcher.pid execprog_tail.pid execprog_trim.pid
  fi

  if [[ "$stopped" == "0" ]]; then
    echo "[host] nothing to stop (no running qemu/watcher found)"
  fi
}

status_vm() {
  echo "[host] bundle=$BUNDLE_DIR"
  if [[ -f qemu.pid ]]; then
    qpid=$(cat qemu.pid 2>/dev/null || true)
    if [[ -n "${qpid:-}" ]] && kill -0 "$qpid" 2>/dev/null; then
      echo "[host] qemu: running pid=$qpid"
    else
      echo "[host] qemu: not running (qemu.pid present: ${qpid:-empty})"
    fi
  else
    echo "[host] qemu: no qemu.pid"
  fi

  if [[ -f watcher.pid ]]; then
    wpid=$(cat watcher.pid 2>/dev/null || true)
    if [[ -n "${wpid:-}" ]] && kill -0 "$wpid" 2>/dev/null; then
      echo "[host] watcher: running pid=$wpid"
    else
      echo "[host] watcher: not running (watcher.pid present: ${wpid:-empty})"
    fi
  else
    echo "[host] watcher: no watcher.pid"
  fi

  if [[ -f execprog_tail.pid ]]; then
    tpid=$(cat execprog_tail.pid 2>/dev/null || true)
    if [[ -n "${tpid:-}" ]] && kill -0 "$tpid" 2>/dev/null; then
      echo "[host] execprog_tail: running pid=$tpid"
    else
      echo "[host] execprog_tail: not running (execprog_tail.pid present: ${tpid:-empty})"
    fi
  else
    echo "[host] execprog_tail: no execprog_tail.pid"
  fi

  if [[ -f execprog_trim.pid ]]; then
    cpid=$(cat execprog_trim.pid 2>/dev/null || true)
    if [[ -n "${cpid:-}" ]] && kill -0 "$cpid" 2>/dev/null; then
      echo "[host] execprog_trim: running pid=$cpid"
    else
      echo "[host] execprog_trim: not running (execprog_trim.pid present: ${cpid:-empty})"
    fi
  else
    echo "[host] execprog_trim: no execprog_trim.pid"
  fi

  if [[ -f qemu-serial.log ]]; then
    echo "[host] qemu-serial.log: $(wc -l < qemu-serial.log) lines, $(ls -lh qemu-serial.log | awk '{print $5}')"
  else
    echo "[host] qemu-serial.log: missing"
  fi
  if [[ -f watch_patterns.log ]]; then
    echo "[host] watch_patterns.log: $(wc -l < watch_patterns.log) lines, $(ls -lh watch_patterns.log | awk '{print $5}')"
  else
    echo "[host] watch_patterns.log: missing"
  fi

  if [[ -f "$EXECPROG_STREAM_LOG" ]]; then
    echo "[host] execprog_stream.log: $(wc -l < "$EXECPROG_STREAM_LOG") lines, $(ls -lh "$EXECPROG_STREAM_LOG" | awk '{print $5}')"
  fi
}

if [[ "$ACTION" == "stop" ]]; then
  stop_vm
  exit 0
fi

if [[ "$ACTION" == "status" ]]; then
  status_vm
  exit 0
fi

echo "[host] bundle=$BUNDLE_DIR"
echo "[host] qemu: MEM=$MEM SMP=$SMP HOSTFWD_PORT=$HOSTFWD_PORT PERSIST=$PERSIST DAEMONIZE=$DAEMONIZE"

stop_vm || true

rm -f qemu.pid qemu-serial.log watch_patterns.log watcher.pid
rm -f .auto_archived_once
rm -f execprog_tail.pid
rm -f execprog_trim.pid

# Start QEMU
if [[ -z "$KERNEL_IMAGE" && "$USE_LOCALIMAGE" == "1" ]]; then
  KERNEL_IMAGE="$BUNDLE_DIR/localimage/bzImage"
fi

qemu_env=(MEM="$MEM" SMP="$SMP" HOSTFWD_PORT="$HOSTFWD_PORT" PERSIST="$PERSIST" DAEMONIZE="$DAEMONIZE" FTRACE_DUMP_ON_OOPS="$FTRACE_DUMP_ON_OOPS" TRACE_BUF_SIZE_KB="$TRACE_BUF_SIZE_KB")
if [[ -n "$KERNEL_IMAGE" ]]; then
  qemu_env+=(KERNEL_IMAGE="$KERNEL_IMAGE")
fi
if [[ -n "$APPEND_EXTRA" ]]; then
  qemu_env+=(APPEND_EXTRA="$APPEND_EXTRA")
fi
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
  ls -l "$SYZ_EXECPROG" "$SYZ_EXECUTOR" "$REPRO_SYZ"
  echo "[host] mkdir /root/repro";
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p "$SSH_PORT" root@"$SSH_HOST" 'mkdir -p /root/repro'
  echo "[host] scp binaries+repro";
  scp -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SYZ_EXECPROG" "$SYZ_EXECUTOR" \
    root@"$SSH_HOST":/root/repro/
  scp -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$REPRO_SYZ" \
    root@"$SSH_HOST":/root/repro/repro.syz

  # Keep the VM alive longer: kernel cmdline doesn't support panic_on_oops=0,
  # and syzbot images often default panic_on_oops/panic_on_warn to 1.
  # Try both sysctl and direct /proc writes; ignore failures.
  echo "[host] set sysctls (panic_on_oops=0 panic_on_warn=0)";
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p "$SSH_PORT" root@"$SSH_HOST" \
    'set +e; \
     sysctl -w kernel.panic_on_oops=0 2>/dev/null; \
     sysctl -w kernel.panic_on_warn=0 2>/dev/null; \
     echo 0 >/proc/sys/kernel/panic_on_oops 2>/dev/null; \
     echo 0 >/proc/sys/kernel/panic_on_warn 2>/dev/null; \
     true'

  echo "[host] start execprog";
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p "$SSH_PORT" root@"$SSH_HOST" \
    'set -e; cd /root/repro; chmod +x syz-execprog syz-executor; rm -f execprog.out; \
     nohup ./syz-execprog -executor=./syz-executor -sandbox='"$EXECPROG_SANDBOX"' -procs='"$EXECPROG_PROCS"' -threaded='"$EXECPROG_THREADED"' -repeat='"$EXECPROG_REPEAT"' '"$EXECPROG_EXTRA_ARGS"' repro.syz \
       >execprog.out 2>&1 & echo execprog_pid=$!'
  echo "[host] tail execprog.out (may fail later if ssh degrades)";
  timeout 8s ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
    -p "$SSH_PORT" root@"$SSH_HOST" 'tail -n 20 /root/repro/execprog.out' || true
  echo "[host] stage_done $(date -Is)"
} | tee "$stage_log"

echo "[host] stage_log=$stage_log"

# Optionally stream guest execprog.out to the host for better post-mortem when the VM panics.
if [[ "$CAPTURE_EXECPROG" == "1" ]]; then
  echo "[host] starting execprog.out stream -> $EXECPROG_STREAM_LOG"
  rm -f "$EXECPROG_STREAM_LOG"
  nohup ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
    -p "$SSH_PORT" root@"$SSH_HOST" 'tail -n 0 -f /root/repro/execprog.out' \
    >"$EXECPROG_STREAM_LOG" 2>&1 &
  echo $! > "$BUNDLE_DIR/execprog_tail.pid"
  echo "[host] execprog_tail_pid=$(cat "$BUNDLE_DIR/execprog_tail.pid")"

  if [[ "$EXECPROG_STREAM_MAX_BYTES" != "0" ]]; then
    echo "[host] trimming execprog stream: max_bytes=$EXECPROG_STREAM_MAX_BYTES every ${EXECPROG_STREAM_TRIM_SECS}s"
    (
      while true; do
        sleep "$EXECPROG_STREAM_TRIM_SECS"
        [[ -f "$EXECPROG_STREAM_LOG" ]] || continue
        sz=$(stat -c%s "$EXECPROG_STREAM_LOG" 2>/dev/null || echo 0)
        if [[ "$sz" -gt "$EXECPROG_STREAM_MAX_BYTES" ]]; then
          tmp="$EXECPROG_STREAM_LOG.tmp"
          tail -c "$EXECPROG_STREAM_MAX_BYTES" "$EXECPROG_STREAM_LOG" >"$tmp" 2>/dev/null || true
          mv -f "$tmp" "$EXECPROG_STREAM_LOG" 2>/dev/null || true
        fi
      done
    ) >/dev/null 2>&1 &
    echo $! > "$BUNDLE_DIR/execprog_trim.pid"
    echo "[host] execprog_trim_pid=$(cat "$BUNDLE_DIR/execprog_trim.pid")"
  fi
fi

# Start watcher
if [[ "$WATCH" == "1" ]]; then
  echo "[host] starting serial-log watcher (patterns: $WATCH_PATTERNS)"
  : > "$BUNDLE_DIR/watch_patterns.log"
  bash -c "set -euo pipefail; \
    serial='$BUNDLE_DIR/qemu-serial.log'; \
    out='$BUNDLE_DIR/watch_patterns.log'; \
    flag='$BUNDLE_DIR/.auto_archived_once'; \
    stdbuf -oL tail -n 0 -F \"\$serial\" | \
      stdbuf -oL egrep --line-buffered '$WATCH_PATTERNS' | \
      while IFS= read -r line; do \
        printf '%s\n' \"\$line\" | tee -a \"\$out\" >/dev/null; \
        if [[ '$AUTO_ARCHIVE_ON_HIT' == '1' ]] && [[ ! -f \"\$flag\" ]]; then \
          : >\"\$flag\"; \
          TAG='$ARCHIVE_TAG' \
          REPRO_SYZ='$REPRO_SYZ' \
          KERNEL_IMAGE='$KERNEL_IMAGE' \
          USE_LOCALIMAGE='$USE_LOCALIMAGE' \
          MEM='$MEM' SMP='$SMP' HOSTFWD_PORT='$HOSTFWD_PORT' APPEND_EXTRA='$APPEND_EXTRA' \
            '$REPO_ROOT/tools/archive_repro_run.sh' '$BUNDLE_DIR' || true; \
          if [[ '$STOP_ON_HIT' == '1' ]]; then \
            EXTID='$EXTID' REPO_ROOT='$REPO_ROOT' BUNDLE_DIR='$BUNDLE_DIR' '$REPO_ROOT/tools/run_issue3_manual.sh' --stop || true; \
          fi; \
        fi; \
      done" \
    >/dev/null 2>&1 &
  echo $! > "$BUNDLE_DIR/watcher.pid"
  echo "[host] watcher_pid=$(cat "$BUNDLE_DIR/watcher.pid")"
  echo "[host] follow: tail -f '$BUNDLE_DIR/watch_patterns.log'"
fi

echo "[host] done. If SSH starts failing, rely on:"
echo "  tail -f '$BUNDLE_DIR/watch_patterns.log'"
echo "  tail -n 200 '$BUNDLE_DIR/qemu-serial.log'"
