# 2026-01-24 — f8850bc3986562f79619 — monitoring + ReproC run（简体中文）

[English](2026-01-24-f8850bc3986562f79619-monitoring-and-repro-run.md)

> 说明：本简体中文版本包含中文导读 + 英文原文（便于准确对照命令/日志/代码符号）。

## 中文导读（章节列表）

- Goal
- Setup / how it was run
- Observation
- Next
- Additional reruns (same day)

## English 原文

# 2026-01-24 — f8850bc3986562f79619 — monitoring + ReproC run

[简体中文](2026-01-24-f8850bc3986562f79619-monitoring-and-repro-run.zh-CN.md)

## Goal
Attempt to reproduce the syzbot report:
- extid: `f8850bc3986562f79619`
- title: `INFO: rcu detected stall in br_handle_frame (6)`

## Setup / how it was run
Repro bundle directory:
- `repro/f8850bc3986562f79619/`

QEMU was run in daemon mode (persistent serial log + pidfile), with snapshot mode (no disk persistence):

```bash
cd repro/f8850bc3986562f79619
DAEMONIZE=1 ./run_qemu.sh
# serial: qemu-serial.log
# pid:    qemu.pid
# ssh:    root@localhost -p 10022
```

Guest is Buildroot and did not include a compiler or syzkaller executors (`syz-execprog`/`syz-executor`), so the ReproC binary was built on the host and copied in via scp:

```bash
# host build (static)
gcc -O2 -static -pthread -o repro repro.c

# copy to guest
scp -P 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null repro root@localhost:/root/

# run inside guest (example)
ssh -p 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@localhost '/root/repro & echo REPRO_PID=$!'
```

## Observation
While the repro was running, the serial log captured an RCU stall report. Notably:
- `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:`
- followed by NMI backtraces and an RCU GP kthread starvation report (`rcu_preempt kthread starved ...`).
- shortly after, SSH became unresponsive (banner exchange timeout). QEMU process remained alive, but no further serial output was observed beyond the stall stacks.

Excerpt from `qemu-serial.log` (trimmed):

```text
[  242.521441][    C1] hrtimer: interrupt took 87634924810 ns
...
[  429.960892][    C0] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[  429.960892][    C0] rcu:     1-...!: (1 GPs behind) idle=d2dc/1/0x4000000000000000 softirq=19806/19807 fqs=0
[  429.960892][    C0] rcu:     (detected by 0, t=10502 jiffies, g=24285, q=183 ncpus=2)
[  429.960892][    C0] Sending NMI from CPU 0 to CPUs 1:
...
[  429.960892][    C0] rcu: rcu_preempt kthread starved for 10502 jiffies! g=24285 f0x0 RCU_GP_WAIT_FQS(5)
```

### Notes
- This run did **not** show `br_handle_frame` in the serial log (simple string search returned no matches).
- Even without the exact `br_handle_frame` signature, the repro appears to be stressing networking/bridge paths (lots of virtual netdevice setup is visible before the stall).

## Next
Try a rerun with more resources to reduce scheduler starvation effects:

```bash
cd repro/f8850bc3986562f79619
SMP=4 MEM=4096 DAEMONIZE=1 SERIAL_LOG=$PWD/qemu-serial-2cpu4g.log PIDFILE=$PWD/qemu-2cpu4g.pid ./run_qemu.sh
```

Then rerun the same ReproC steps and re-check whether `br_handle_frame` appears in the stall stacks.

## Additional reruns (same day)

### run2 / run3 (SMP=4 MEM=4096)
Trying `SMP=4 MEM=4096` increased early-boot instability: both runs hit a KASAN `int3` and then
`Kernel panic - not syncing: Fatal exception in interrupt` before reaching sshd.

Artifacts:
- `repro/f8850bc3986562f79619/qemu-serial-run2.log`
- `repro/f8850bc3986562f79619/qemu-serial-run3.log`

### run4 (SMP=2 MEM=4096)
Using 2 vCPUs (original) but more RAM was able to boot to sshd, start the repro, and then
trigger a stall + watchdog panic:

- SSH became unresponsive shortly after starting `/root/repro`.
- Serial log showed `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:` and later
	`Kernel panic - not syncing: softlockup: hung tasks`.

Artifacts:
- `repro/f8850bc3986562f79619/qemu-serial-run4.log`

Notes:
- `br_handle_frame` still did not appear as a string in the captured serial output.
