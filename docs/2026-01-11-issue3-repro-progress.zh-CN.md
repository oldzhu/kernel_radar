# 2026-01-11: issue #3 (vhost_worker_killed) repro progress（简体中文）

[English](2026-01-11-issue3-repro-progress.md)

> 说明：本简体中文版本包含中文导读 + 英文原文（便于准确对照命令/日志/代码符号）。

## 中文导读（章节列表）

- What happened today
- Code changes made today
- End-of-day status

## English 原文

# 2026-01-11: issue #3 (vhost_worker_killed) repro progress

[简体中文](2026-01-11-issue3-repro-progress.zh-CN.md)

Target issue:
- extid: `a9528028ab4ca83e8bac`
- bug page: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac

Context:
- See prior notes in `docs/2026-01-10-issue3-repro-progress.md`.
- Primary goal remains: reproduce the hung-task signature involving `vhost_worker_killed()` live (not only from syzbot’s saved `crash.report`).

## What happened today

### A) Observed another early boot Oops/panic (no 9p involved)

We saw a reproducible boot-time crash soon after userspace starts (around udev):
- `Oops: int3: 0000 [#1] SMP KASAN NOPTI`
- `RIP: kmem_cache_alloc_noprof+0x9c/0x710`
- Example task: `Comm: udevd`
- Followed by: `Kernel panic - not syncing: Fatal exception in interrupt`

This prevented SSH from coming up in that attempt (helper waited for SSH, timed out).

We preserved the serial log excerpt for later comparison (bundle-local, gitignored):
- `repro/a9528028ab4ca83e8bac/qemu-serial.bootpanic.20260111-154335.log`

### B) Fixed a helper-script footgun: `--clean` accidentally started a new run

We accidentally triggered a new QEMU start while trying to clean up.
Root cause: the helper treated `--clean` as a flag but still defaulted to ACTION=start.

Fix implemented (see “Code changes”):
- `--clean` must be used with `--stop` (`--stop --clean`).

### C) Started a “low-concurrency” run to avoid the early crash

We started a fresh run with reduced concurrency:

```bash
cd /home/oldzhu/mylinux/kernel_radar
SMP=1 SSH_WAIT_SECS=240 EXECPROG_PROCS=1 EXECPROG_THREADED=0 EXECPROG_REPEAT=0 \
  tools/run_issue3_manual.sh
```

Notes:
- SSH came up after ~151 seconds.
- `syz-execprog` was started in the guest and continued making progress.

Even though the guest userland is minimal (BusyBox) and lacks tools like `pgrep`, we confirmed
forward progress by watching `execprog.out`:

```bash
ssh -p 10022 root@127.0.0.1 'tail -n 5 /root/repro/execprog.out'
# shows "executed programs: N" increasing over time
```

We also used a /proc-based scan to find processes without `pgrep`:

```bash
ssh -p 10022 root@127.0.0.1 \
  'for p in /proc/[0-9]*; do comm=$(cat $p/comm 2>/dev/null || true); \
    case "$comm" in syz-execprog|syz-executor) echo "pid=${p##*/} comm=$comm";; esac; \
  done'
```

### D) No hung-task signature yet in this low-concurrency run

In this run:
- `watch_patterns.log` stayed empty (no `INFO: task ... blocked`, no `vhost_worker_killed`).
- Serial log kept growing with typical fuzz noise (e.g., NILFS messages), indicating the guest was alive.

Hypothesis:
- The target hang may be timing-dependent and may require higher concurrency (more `-procs` and/or more vCPUs).
- However, higher concurrency previously correlated with early boot panics / instability.

Plan for next session:
- Ramp up gradually: `SMP=2` + `EXECPROG_PROCS=2`, then `4`, etc., watching for the early Oops/panic returning.

## Code changes made today

### 1) `tools/run_issue3_manual.sh`

Changes:
- Increased default SSH wait: `SSH_WAIT_SECS` default from `120` → `240`.
- Added tunable knobs for the guest workload:
  - `EXECPROG_SANDBOX` (default `none`)
  - `EXECPROG_PROCS` (default `6`)
  - `EXECPROG_THREADED` (default `1`)
  - `EXECPROG_REPEAT` (default `0`)
  - `EXECPROG_EXTRA_ARGS` (default empty)
- Safety: `--clean` is rejected unless used with `--stop`.

### 2) `tools/monitor_issue3_watch.sh`

Added a small terminal-friendly polling script that:
- repeatedly prints `wc -l` + `tail` of `watch_patterns.log`
- exits immediately when the watcher captures any pattern
- prints the captured pattern lines + a final tail of `qemu-serial.log`

Example usage:

```bash
cd /home/oldzhu/mylinux/kernel_radar
INTERVAL=1 TAIL_N=20 tools/monitor_issue3_watch.sh repro/a9528028ab4ca83e8bac
```

## End-of-day status

- `syz-execprog` can run for a long time (low concurrency) without the early boot crash.
- The target hung-task signature (`vhost_worker_killed`, `INFO: task ... blocked`) has not been reproduced live yet today.
- Next attempt should likely increase concurrency gradually to raise the hit rate while watching for the boot-time panic returning.
