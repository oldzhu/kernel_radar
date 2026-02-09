# 2026-01-11：issue #3（vhost_worker_killed）复现进展

[English](2026-01-11-issue3-repro-progress.md)

目标问题：

- extid: `a9528028ab4ca83e8bac`
- bug 页面: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac

背景：

- 参考前一日记录：`docs/2026-01-10-issue3-repro-progress.md`。
- 主要目标仍是在线复现 `vhost_worker_killed()` 相关 hung-task 特征（不仅限于 syzbot 保存的 `crash.report`）。

## 今天发生了什么

### A) 观察到另一次早期启动 Oops/panic（不涉及 9p）

在用户态启动后不久（约 udev 阶段），出现可复现的启动崩溃：

- `Oops: int3: 0000 [#1] SMP KASAN NOPTI`
- `RIP: kmem_cache_alloc_noprof+0x9c/0x710`
- 例子任务：`Comm: udevd`
- 随后：`Kernel panic - not syncing: Fatal exception in interrupt`

该次尝试中 SSH 无法启动（helper 等待 SSH 超时）。

我们保存了串口日志片段以备对照（bundle 本地、git 忽略）：

- `repro/a9528028ab4ca83e8bac/qemu-serial.bootpanic.20260111-154335.log`

### B) 修复 helper 脚本的误用：`--clean` 触发新启动

我们在清理时误触发了新的 QEMU 启动。
原因：helper 把 `--clean` 当作参数，但默认 ACTION=start。

修复（见“代码改动”）：

- `--clean` 必须与 `--stop` 一起使用（`--stop --clean`）。

### C) 启动低并发运行以避开早期崩溃

我们用较低并发启动新一轮：

```bash
cd /home/oldzhu/mylinux/kernel_radar
SMP=1 SSH_WAIT_SECS=240 EXECPROG_PROCS=1 EXECPROG_THREADED=0 EXECPROG_REPEAT=0 \
  tools/run_issue3_manual.sh
```

备注：

- SSH 大约 151 秒后可用。
- `syz-execprog` 在 guest 中启动并持续推进。

即便 guest 用户态非常精简（BusyBox）且缺少 `pgrep`，我们仍通过 `execprog.out` 确认进展：

```bash
ssh -p 10022 root@127.0.0.1 'tail -n 5 /root/repro/execprog.out'
# shows "executed programs: N" increasing over time
```

同时使用 /proc 扫描替代 `pgrep`：

```bash
ssh -p 10022 root@127.0.0.1 \
  'for p in /proc/[0-9]*; do comm=$(cat $p/comm 2>/dev/null || true); \
    case "$comm" in syz-execprog|syz-executor) echo "pid=${p##*/} comm=$comm";; esac; \
  done'
```

### D) 低并发运行中仍未出现 hung-task

在该运行中：

- `watch_patterns.log` 仍为空（没有 `INFO: task ... blocked` 或 `vhost_worker_killed`）。
- 串口日志持续增长并包含典型 fuzz 噪声（例如 NILFS 消息），说明 guest 仍存活。

假设：

- 目标 hang 可能与时序相关，需要更高并发（更多 `-procs` 和/或更多 vCPU）。
- 但更高并发此前又与早期启动 panic 相关。

下一次计划：

- 逐步增加并发：`SMP=2` + `EXECPROG_PROCS=2`，再到 `4`，观察早期 Oops/panic 是否回归。

## 今日代码改动

### 1) `tools/run_issue3_manual.sh`

改动：

- 提高默认 SSH 等待：`SSH_WAIT_SECS` 从 `120` → `240`。
- 增加 guest 负载可调参数：
  - `EXECPROG_SANDBOX`（默认 `none`）
  - `EXECPROG_PROCS`（默认 `6`）
  - `EXECPROG_THREADED`（默认 `1`）
  - `EXECPROG_REPEAT`（默认 `0`）
  - `EXECPROG_EXTRA_ARGS`（默认空）
- 安全性：`--clean` 必须与 `--stop` 一起使用。

### 2) `tools/monitor_issue3_watch.sh`

新增一个适合终端的轮询脚本：

- 持续打印 `watch_patterns.log` 的 `wc -l` + `tail`。
- 一旦 watcher 捕获到任何模式就立即退出。
- 输出捕获到的模式行，并附上 `qemu-serial.log` 的 tail。

用法示例：

```bash
cd /home/oldzhu/mylinux/kernel_radar
INTERVAL=1 TAIL_N=20 tools/monitor_issue3_watch.sh repro/a9528028ab4ca83e8bac
```

## 今日结束时的状态

- 在低并发下，`syz-execprog` 可长期运行而不出现早期启动崩溃。
- 尚未在线复现目标 hung-task 特征（`vhost_worker_killed`、`INFO: task ... blocked`）。
- 下一次尝试需逐步提高并发，以提升命中率，同时观察启动 panic 是否回归。
