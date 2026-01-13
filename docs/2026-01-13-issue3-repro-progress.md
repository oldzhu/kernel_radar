# 2026-01-13 — syzbot issue #3 repro progress (extid a9528028ab4ca83e8bac)

Context: continuing local reproduction of the issue-3 vhost/vsock hang (expected `vhost_worker_killed()`/hung-task signature) using the `kernel_radar` QEMU+syz-execprog workflow.

## What changed / key outcomes

- We confirmed the previous blocker was **not vhost**: repeated hard failures were `Oops: int3` followed by `Kernel panic - not syncing: Fatal exception in interrupt`.
- Two distinct "int3 in kmalloc" failure modes were observed:
  - **Boot-time tracing init path** (workqueue `eval_map_wq` / `tracer_init_tracefs_work_func`).
  - **Runtime udevd/sysfs path** (PID `udevd`, `uevent_show()` in the stack).
- The local instrumented kernel was unstable due to an `int3` in `__kmalloc_cache_noprof` at an `arch_static_branch` site; we mitigated by disabling jump labels (`CONFIG_JUMP_LABEL=n`).
- After rebuilding, the local kernel boots reliably and `syz-execprog` makes forward progress (program counter steadily increasing in the execprog stream log). This unblocks continued attempts to reach the intended vhost hang.

## Runner / scripts used today

Everything below is from the `kernel_radar` workspace.

### Generate alternate repro (disable wifi + ieee802154)

We created an alternate repro file that only edits the JSON options line (keeps the syzbot bundle intact):

- Script: `tools/make_issue3_repro_local.sh`
- Output: `repro/a9528028ab4ca83e8bac/repro.local.syz`

Command:

- `cd /home/oldzhu/mylinux/kernel_radar && tools/make_issue3_repro_local.sh`

### Run QEMU + syz-execprog using an alternate repro file

We ran the standard orchestrator and selected the alternate repro via `REPRO_SYZ=...`.

- Script: `tools/run_issue3_manual.sh`

Typical command (local kernel):

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac \
  USE_LOCALIMAGE=1 \
  REPRO_SYZ=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/repro.local.syz \
  APPEND_EXTRA='ip=dhcp panic_on_warn=0 panic_on_oops=0' \
  FTRACE_DUMP_ON_OOPS=1 TRACE_BUF_SIZE_KB=4096 \
  CAPTURE_EXECPROG=1 SSH_WAIT_SECS=360 \
  tools/run_issue3_manual.sh`

A/B run (bundle kernel):

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac \
  USE_LOCALIMAGE=0 \
  REPRO_SYZ=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/repro.local.syz \
  APPEND_EXTRA='ip=dhcp panic_on_warn=0 panic_on_oops=0' \
  FTRACE_DUMP_ON_OOPS=1 TRACE_BUF_SIZE_KB=4096 \
  CAPTURE_EXECPROG=1 SSH_WAIT_SECS=360 \
  tools/run_issue3_manual.sh`

Stop/clean between runs:

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac tools/run_issue3_manual.sh --stop --clean`

### Build/rebuild local kernel for this issue

We build from `~/mylinux/linux` into `repro/<extid>/localimage/build/` and stage artifacts under `repro/<extid>/localimage/`.

- Script: `tools/build_issue3_local_kernel.sh`

Command:

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac tools/build_issue3_local_kernel.sh`

Config fragment note:

- The fragment is now tracked in-repo as `tools/issue3_localimage.fragment.config`.
- It includes `CONFIG_JUMP_LABEL=n` to avoid the recurring `int3` traps observed at `arch_static_branch` sites.

## Debug commands used today (triage)

Serial / watcher quick checks:

- `tail -n 200 repro/a9528028ab4ca83e8bac/qemu-serial.log`
- `tail -n 120 repro/a9528028ab4ca83e8bac/watch_patterns.log`
- `tail -n 50 repro/a9528028ab4ca83e8bac/execprog_stream.log`

Address→source mapping for local kernel (when diagnosing `__kmalloc_cache_noprof+0x97/0x790`):

- `nm -n repro/a9528028ab4ca83e8bac/localimage/vmlinux | grep __kmalloc_cache_noprof`
- `addr2line -e repro/a9528028ab4ca83e8bac/localimage/vmlinux -f -p <addr>`
- `objdump -d --no-show-raw-insn --start-address=<addr> --stop-address=<addr> repro/a9528028ab4ca83e8bac/localimage/vmlinux`

## Current state (end of day)

- Local kernel boots with the new fragment, SSH is stable.
- `syz-execprog` is running and executing programs continuously (execprog stream counter increases).
- No vhost hung-task signature captured yet; continue monitoring `watch_patterns.log` for `hung task`, `blocked for more than`, and `vhost_worker_killed`.

## vhost_worker_killed lock-order: commit, local patch, and bundle proof

### Upstream commit that introduced vhost_worker_killed()

In `~/mylinux/linux`, the vhost SIGKILL path (and the `vhost_worker_killed()` callback) was introduced by:

- Commit: `db5247d9bf5c6ade9fd70b4e4897441e0269b233`
- Subject: `vhost_task: Handle SIGKILL by flushing work and exiting`
- Author: Mike Christie `<michael.christie@oracle.com>`
- Files: `drivers/vhost/vhost.c`, `drivers/vhost/vhost.h`, `include/linux/sched/vhost_task.h`, `kernel/vhost_task.c`

In that commit’s original implementation, `vhost_worker_killed()` holds `worker->mutex` while iterating `dev->vqs[]` and taking each `vq->mutex`. This creates an AB/BA deadlock risk with other paths that hold `vq->mutex` and then need `worker->mutex` (or vice versa), matching the syzbot hung-task signature we’re chasing.

Verify on the local source tree:

- `cd ~/mylinux/linux && git show db5247d9bf5c6ade9fd70b4e4897441e0269b233 -- drivers/vhost/vhost.c`

### “Restructure” status in ~/mylinux/linux: it’s currently a local working-tree patch

The “drop `worker->mutex` before taking `vq->mutex`, then re-acquire post-RCU to update attachment counters” behavior we discussed is **not** present as a committed change in `~/mylinux/linux` history right now. It exists as an **uncommitted local patch** in the working tree (likely added during debugging along with `trace_printk`-based lock tracing).

Verify the local patch exists:

- `cd ~/mylinux/linux && git diff -- drivers/vhost/vhost.c | less`
- `cd ~/mylinux/linux && git blame -L 475,521 drivers/vhost/vhost.c`

### Proving the downloaded syzbot bundle kernel still has the “old” behavior (binary)

Because the bundle ELF we extracted from `bzImage` is stripped, we disassemble `vhost_worker_killed()` by **runtime address**:

1) Boot the bundle kernel (A/B mode):

- `cd ~/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac USE_LOCALIMAGE=0 tools/run_issue3_manual.sh`

2) Fetch the function’s runtime address from the guest:

- `ssh -p 10022 root@127.0.0.1 'grep -m1 -w vhost_worker_killed /proc/kallsyms'`

3) Extract vmlinux from `bzImage` (host-side) and disassemble by address:

- `cd repro/a9528028ab4ca83e8bac && ~/mylinux/linux/scripts/extract-vmlinux bzImage > vmlinux.from_bzImage`
- `objdump -d --no-show-raw-insn --start-address=<addr> --stop-address=$((<addr>+0x1200)) vmlinux.from_bzImage > tmp_disas_vhost_worker_killed_full.txt`

4) Confirm lock ordering in the disassembly:

- We see `mutex_lock_nested(&worker->mutex)` and later `mutex_lock_nested(&vq->mutex)` before the worker mutex is released.

Saved artifact from this workflow:

- `repro/a9528028ab4ca83e8bac/tmp_disas_vhost_worker_killed_full.txt`

For convenience, this is now scripted:

- `tools/disassemble_issue3_bundle_vhost_worker_killed.sh`

## Late-session updates (auto-archive + higher concurrency)

### Auto-archive-on-hit added

Goal: make sure the first appearance of `hung task` / `vhost_worker_killed` / `Oops` / `panic` is snapshotted immediately under `repro/<extid>/runs/`.

- New helper: `tools/archive_repro_run.sh`
  - Creates `repro/<extid>/runs/<timestamp>[-tag]/`.
  - Copies core logs (`qemu-serial.log`, `watch_patterns.log`, `execprog_stream.log`), plus `kernel.config`, `repro.syz`, and localimage kernel artifacts if present.
  - Explicitly avoids copying large images like `disk.raw`.
- Runner wiring: `tools/run_issue3_manual.sh`
  - New knobs: `AUTO_ARCHIVE_ON_HIT=1`, `ARCHIVE_TAG=...`, `STOP_ON_HIT=1`.
  - On the first watcher match, it archives and (optionally) stops the VM.

Commits:

- `81c14b2` tools: auto-archive repro run on watcher hit

### Watcher robustness fixes

Two small but important fixes landed while iterating:

- Reset `.auto_archived_once` on clean starts so auto-archive triggers correctly across repeated runs.
- Ensure the default `WATCH_PATTERNS` does not accidentally contain an embedded newline (which can cause confusing matches and noisy behavior).

Commits:

- `84db349` tools: reset auto-archive state each run
- `a34595a` tools: prevent watcher newline pattern

### High-concurrency run (to try to reproduce faster)

We bumped the workload concurrency via `syz-execprog -procs`.

Command used (local kernel + repro.local.syz, procs=12):

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac \
  USE_LOCALIMAGE=1 \
  REPRO_SYZ=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/repro.local.syz \
  MEM=4096 SMP=4 TRACE_BUF_SIZE_KB=16384 SSH_WAIT_SECS=600 \
  CAPTURE_EXECPROG=1 \
  EXECPROG_PROCS=12 EXECPROG_THREADED=1 EXECPROG_REPEAT=0 \
  AUTO_ARCHIVE_ON_HIT=1 STOP_ON_HIT=1 ARCHIVE_TAG=issue3-procs12 \
  tools/run_issue3_manual.sh`

Status check commands:

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac tools/run_issue3_manual.sh --status`
- `tail -n 30 repro/a9528028ab4ca83e8bac/execprog_stream.log`
- `tail -f repro/a9528028ab4ca83e8bac/watch_patterns.log`

### One-off cleanup: stale watcher pipelines

We found multiple old `tail -F .../qemu-serial.log | egrep | tee -a .../watch_patterns.log` pipelines lingering in the process table from prior experiments. Those are not tracked by the current `watcher.pid`, but they can create confusing state.

Cleanup commands used:

- `pkill -f 'tail -n 0 -F /home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/qemu-serial\.log' || true`
- `pkill -f 'tee -a /home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/watch_patterns\.log' || true`
- `pkill -f 'egrep --line-buffered' || true`

## Tomorrow (2026-01-14) — pick 3 new issues checklist

Goal: switch to three new syzbot issues efficiently, avoiding spending time on already-fixed reports.

1) Select candidates

- Use the pick guides:
  - `docs/how-we-picked-top-3-syzbot-issues.md`
  - `docs/how-we-picked-unclaimed-syzbot-issues.md`
  - `docs/how-to-check-if-an-issue-is-already-being-worked.md`

2) For each chosen extid, set up a repro folder and runner

- Create `repro/<extid>/` with the syzbot bundle artifacts (`disk.raw`, `bzImage`, `repro.syz`, etc).
- Clone the issue-3 runner pattern:
  - `tools/run_issue3_manual.sh` (adapt into `tools/run_issueX_manual.sh` if needed)
  - Keep auto-archive on watcher hit enabled.

3) Fast “already fixed?” sanity check

- Prefer booting the **bundle** kernel first.
- If the suspected function is missing symbols/stripped, use the same address-based workflow:
  - `ssh ... 'grep -m1 <symbol> /proc/kallsyms'`
  - `scripts/extract-vmlinux bzImage > vmlinux.from_bzImage`
  - `objdump --start-address/--stop-address ...`

4) Start runs with stability-first defaults

- Disable unrelated subsystems in a `repro.local.syz` if early crashes appear (like we did for wifi/ieee802154).
- Keep `panic_on_oops=0 panic_on_warn=0` unless you explicitly need early stop.

5) Archive and summarize

- For each issue, collect the first “interesting” run in `repro/<extid>/runs/<ts>-<tag>/`.
- Write one short daily note in `docs/YYYY-MM-DD-issueX-*.md` capturing:
  - exact env vars / runner command
  - signature / first stack
  - hypothesis + next action
