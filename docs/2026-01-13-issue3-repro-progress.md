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
