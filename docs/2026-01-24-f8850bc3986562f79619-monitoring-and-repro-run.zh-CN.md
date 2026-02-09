# 2026-01-24 — f8850bc3986562f79619 — 监控 + 运行 ReproC

[English](2026-01-24-f8850bc3986562f79619-monitoring-and-repro-run.md)

## 目标

尝试复现 syzbot 报告：

- extid: `f8850bc3986562f79619`
- title: `INFO: rcu detected stall in br_handle_frame (6)`

## 环境与运行方式

repro bundle 目录：

- `repro/f8850bc3986562f79619/`

QEMU 以 daemon 模式运行（持续写串口日志 + pidfile），并开启 snapshot 模式（不持久化磁盘改动）：

```bash
cd repro/f8850bc3986562f79619
DAEMONIZE=1 ./run_qemu.sh
# serial: qemu-serial.log
# pid:    qemu.pid
# ssh:    root@localhost -p 10022
```

Guest 使用 Buildroot，不包含编译器，也不包含 syzkaller executors（`syz-execprog`/`syz-executor`），因此我们在 host 上构建 ReproC 二进制，并通过 scp 拷贝进 guest：

```bash
# host build (static)
gcc -O2 -static -pthread -o repro repro.c

# copy to guest
scp -P 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null repro root@localhost:/root/

# run inside guest (example)
ssh -p 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@localhost '/root/repro & echo REPRO_PID=$!'
```

## 观察

在 repro 运行过程中，串口日志捕获到了 RCU stall 报告。关键点：

- `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:`
- 随后是 NMI backtraces，以及 RCU GP kthread 饥饿报告（`rcu_preempt kthread starved ...`）。
- 不久后，SSH 变得不可用（banner exchange timeout）。QEMU 进程仍存活，但除了 stall 堆栈外，串口输出没有明显继续推进。

`qemu-serial.log` 片段（已裁剪）：

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

### 备注

- 此次运行在串口日志中 **没有** 出现 `br_handle_frame`（简单字符串搜索没有匹配）。
- 即使缺少精确的 `br_handle_frame` 特征，repro 仍然看起来在施压 networking/bridge 路径（stall 之前能看到大量虚拟网卡相关的 setup）。

## 下一步

尝试用更多资源重跑，以减少调度饥饿的影响：

```bash
cd repro/f8850bc3986562f79619
SMP=4 MEM=4096 DAEMONIZE=1 SERIAL_LOG=$PWD/qemu-serial-2cpu4g.log PIDFILE=$PWD/qemu-2cpu4g.pid ./run_qemu.sh
```

然后重复相同的 ReproC 步骤，并再次检查 stall 堆栈里是否出现 `br_handle_frame`。

## 额外重跑（同日）

### run2 / run3（SMP=4 MEM=4096）

尝试 `SMP=4 MEM=4096` 后，早期启动不稳定性增加：两次都出现 KASAN `int3`，随后在启动到 sshd 之前就触发：

`Kernel panic - not syncing: Fatal exception in interrupt`

产物：

- `repro/f8850bc3986562f79619/qemu-serial-run2.log`
- `repro/f8850bc3986562f79619/qemu-serial-run3.log`

### run4（SMP=2 MEM=4096）

使用 2 个 vCPU（保持与原始一致）但增加内存后，可以启动到 sshd、启动 repro，并触发 stall + watchdog panic：

- `/root/repro` 启动后不久 SSH 变得不可用。
- 串口日志中先出现 `rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:`，之后出现
  `Kernel panic - not syncing: softlockup: hung tasks`。

产物：

- `repro/f8850bc3986562f79619/qemu-serial-run4.log`

备注：

- 捕获到的串口输出里，`br_handle_frame` 仍然没有以字符串形式出现。
