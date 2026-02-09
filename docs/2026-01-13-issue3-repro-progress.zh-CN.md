# 2026-01-13 — syzbot issue #3 复现进展（extid a9528028ab4ca83e8bac）

[English](2026-01-13-issue3-repro-progress.md)

背景：继续使用 `kernel_radar` 的 QEMU + `syz-execprog` 流程本地复现 issue #3 的 vhost/vsock hang（期望出现 `vhost_worker_killed()`/hung-task 特征）。

## 变更/关键结论

- 确认前一阶段的阻塞 **不是 vhost**：重复发生的致命失败是 `Oops: int3`，随后 `Kernel panic - not syncing: Fatal exception in interrupt`。
- 观察到两类不同的 “int3 in kmalloc” 失败模式：
  - **启动时的 tracing 初始化路径**（workqueue `eval_map_wq` / `tracer_init_tracefs_work_func`）。
  - **运行时的 udevd/sysfs 路径**（PID `udevd`，栈内有 `uevent_show()`）。
- 本地插桩内核不稳定，根因是 `__kmalloc_cache_noprof` 在 `arch_static_branch` 位置触发 `int3`；通过关闭 jump labels（`CONFIG_JUMP_LABEL=n`）进行缓解。
- 重新构建后，本地内核能稳定启动，`syz-execprog` 持续推进（execprog stream 计数持续增长），从而继续尝试触发目标 vhost hang。

## 今日使用的 runner / 脚本

以下内容均在 `kernel_radar` 工作区内。

### 生成替代 repro（禁用 wifi + ieee802154）

我们创建了一个替代 repro 文件，仅修改 JSON options 行（保留 syzbot bundle 不变）：

- 脚本：`tools/make_issue3_repro_local.sh`
- 输出：`repro/a9528028ab4ca83e8bac/repro.local.syz`

命令：

- `cd /home/oldzhu/mylinux/kernel_radar && tools/make_issue3_repro_local.sh`

### 使用替代 repro 运行 QEMU + syz-execprog

通过 `REPRO_SYZ=...` 选择替代 repro 文件。

- 脚本：`tools/run_issue3_manual.sh`

典型命令（本地内核）：

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac \
  USE_LOCALIMAGE=1 \
  REPRO_SYZ=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/repro.local.syz \
  APPEND_EXTRA='ip=dhcp panic_on_warn=0 panic_on_oops=0' \
  FTRACE_DUMP_ON_OOPS=1 TRACE_BUF_SIZE_KB=4096 \
  CAPTURE_EXECPROG=1 SSH_WAIT_SECS=360 \
  tools/run_issue3_manual.sh`

A/B 运行（bundle 内核）：

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac \
  USE_LOCALIMAGE=0 \
  REPRO_SYZ=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/repro.local.syz \
  APPEND_EXTRA='ip=dhcp panic_on_warn=0 panic_on_oops=0' \
  FTRACE_DUMP_ON_OOPS=1 TRACE_BUF_SIZE_KB=4096 \
  CAPTURE_EXECPROG=1 SSH_WAIT_SECS=360 \
  tools/run_issue3_manual.sh`

运行间的 stop/clean：

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac tools/run_issue3_manual.sh --stop --clean`

### 为该问题构建/重建本地内核

我们从 `~/mylinux/linux` 构建到 `repro/<extid>/localimage/build/`，并在 `repro/<extid>/localimage/` 生成产物。

- 脚本：`tools/build_issue3_local_kernel.sh`

命令：

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac tools/build_issue3_local_kernel.sh`

配置片段说明：

- 片段已纳入仓库：`tools/issue3_localimage.fragment.config`。
- 其中包含 `CONFIG_JUMP_LABEL=n`，用于规避 `arch_static_branch` 的 `int3`。

## 今日调试命令（排障）

串口/监视器快速查看：

- `tail -n 200 repro/a9528028ab4ca83e8bac/qemu-serial.log`
- `tail -n 120 repro/a9528028ab4ca83e8bac/watch_patterns.log`
- `tail -n 50 repro/a9528028ab4ca83e8bac/execprog_stream.log`

本地内核地址到源码定位（诊断 `__kmalloc_cache_noprof+0x97/0x790`）：

- `nm -n repro/a9528028ab4ca83e8bac/localimage/vmlinux | grep __kmalloc_cache_noprof`
- `addr2line -e repro/a9528028ab4ca83e8bac/localimage/vmlinux -f -p <addr>`
- `objdump -d --no-show-raw-insn --start-address=<addr> --stop-address=<addr> repro/a9528028ab4ca83e8bac/localimage/vmlinux`

## 当前状态（收工时）

- 使用新的 fragment，本地内核稳定启动，SSH 可用。
- `syz-execprog` 正在持续执行（execprog stream 计数持续上升）。
- 尚未捕获 vhost hung-task 特征；继续监控 `watch_patterns.log` 中的 `hung task`、`blocked for more than`、`vhost_worker_killed`。

## vhost_worker_killed 锁顺序：提交、本地补丁与 bundle 证明

### 引入 vhost_worker_killed() 的上游提交

在 `~/mylinux/linux` 中，vhost SIGKILL 路径（以及 `vhost_worker_killed()` 回调）由以下提交引入：

- Commit: `db5247d9bf5c6ade9fd70b4e4897441e0269b233`
- Subject: `vhost_task: Handle SIGKILL by flushing work and exiting`
- Author: Mike Christie `<michael.christie@oracle.com>`
- Files: `drivers/vhost/vhost.c`, `drivers/vhost/vhost.h`, `include/linux/sched/vhost_task.h`, `kernel/vhost_task.c`

该提交的原始实现中，`vhost_worker_killed()` 会持有 `worker->mutex` 并遍历 `dev->vqs[]`，对每个 `vq` 再获取 `vq->mutex`。这会与“先持 `vq->mutex` 再需要 `worker->mutex`”的路径形成 AB/BA 死锁风险，符合我们追踪的 syzbot hung-task 特征。

在本地源码中验证：

- `cd ~/mylinux/linux && git show db5247d9bf5c6ade9fd70b4e4897441e0269b233 -- drivers/vhost/vhost.c`

### ~/mylinux/linux 中 “重构” 状态：当前为本地未提交补丁

我们讨论过的“在拿 `vq->mutex` 前释放 `worker->mutex`，并在 post-RCU 后再重新获取以更新计数”的行为，目前 **并未** 作为已提交变更出现在 `~/mylinux/linux` 的历史中。它只存在于 **本地未提交的工作树补丁**（可能是在调试期间加入，并伴随 `trace_printk` 的锁跟踪）。

验证本地补丁是否存在：

- `cd ~/mylinux/linux && git diff -- drivers/vhost/vhost.c | less`
- `cd ~/mylinux/linux && git blame -L 475,521 drivers/vhost/vhost.c`

### 证明下载的 syzbot bundle 内核仍为“旧行为”（二进制层面）

由于从 `bzImage` 提取的 ELF 是 stripped，我们通过 **运行时地址** 反汇编 `vhost_worker_killed()`：

1) 启动 bundle 内核（A/B 模式）：

- `cd ~/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac USE_LOCALIMAGE=0 tools/run_issue3_manual.sh`

2) 在 guest 中获取函数运行时地址：

- `ssh -p 10022 root@127.0.0.1 'grep -m1 -w vhost_worker_killed /proc/kallsyms'`

3) 从 `bzImage` 提取 vmlinux（host 侧）并按地址反汇编：

- `cd repro/a9528028ab4ca83e8bac && ~/mylinux/linux/scripts/extract-vmlinux bzImage > vmlinux.from_bzImage`
- `objdump -d --no-show-raw-insn --start-address=<addr> --stop-address=$((<addr>+0x1200)) vmlinux.from_bzImage > tmp_disas_vhost_worker_killed_full.txt`

4) 在反汇编结果中确认锁顺序：

- 可以看到 `mutex_lock_nested(&worker->mutex)`，随后 `mutex_lock_nested(&vq->mutex)` 在释放 worker mutex 之前发生。

保存的产物：

- `repro/a9528028ab4ca83e8bac/tmp_disas_vhost_worker_killed_full.txt`

为了方便复用，已脚本化：

- `tools/disassemble_issue3_bundle_vhost_worker_killed.sh`

## 会话后期更新（自动归档 + 更高并发）

### 新增自动归档（命中即归档）

目标：第一次出现 `hung task` / `vhost_worker_killed` / `Oops` / `panic` 时，立即在 `repro/<extid>/runs/` 下做快照保存。

- 新工具：`tools/archive_repro_run.sh`
  - 创建 `repro/<extid>/runs/<timestamp>[-tag]/`。
  - 复制核心日志（`qemu-serial.log`、`watch_patterns.log`、`execprog_stream.log`），以及 `kernel.config`、`repro.syz`，若存在则包含 localimage 内核产物。
  - 明确避免复制 `disk.raw` 等大文件。
- runner 接入：`tools/run_issue3_manual.sh`
  - 新参数：`AUTO_ARCHIVE_ON_HIT=1`、`ARCHIVE_TAG=...`、`STOP_ON_HIT=1`。
  - 第一次 watcher 命中后自动归档，并可选停止 VM。

提交：

- `81c14b2` tools: auto-archive repro run on watcher hit

### watcher 稳健性修复

迭代中落地了两个小但关键的修复：

- 在 clean start 时重置 `.auto_archived_once`，确保自动归档在重复运行中可正常触发。
- 确保默认 `WATCH_PATTERNS` 不包含意外的换行，避免匹配噪音与奇怪行为。

提交：

- `84db349` tools: reset auto-archive state each run
- `a34595a` tools: prevent watcher newline pattern

### 高并发运行（尝试更快复现）

通过提高 `syz-execprog -procs` 来提升负载并发。

命令（本地内核 + repro.local.syz，procs=12）：

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac \
  USE_LOCALIMAGE=1 \
  REPRO_SYZ=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/repro.local.syz \
  MEM=4096 SMP=4 TRACE_BUF_SIZE_KB=16384 SSH_WAIT_SECS=600 \
  CAPTURE_EXECPROG=1 \
  EXECPROG_PROCS=12 EXECPROG_THREADED=1 EXECPROG_REPEAT=0 \
  AUTO_ARCHIVE_ON_HIT=1 STOP_ON_HIT=1 ARCHIVE_TAG=issue3-procs12 \
  tools/run_issue3_manual.sh`

状态检查命令：

- `cd /home/oldzhu/mylinux/kernel_radar && EXTID=a9528028ab4ca83e8bac tools/run_issue3_manual.sh --status`
- `tail -n 30 repro/a9528028ab4ca83e8bac/execprog_stream.log`
- `tail -f repro/a9528028ab4ca83e8bac/watch_patterns.log`

### 一次性清理：遗留 watcher 管线

我们发现进程表中残留多条旧的 `tail -F .../qemu-serial.log | egrep | tee -a .../watch_patterns.log` 管线。这些不受当前 `watcher.pid` 管理，会导致状态混乱。

清理命令：

- `pkill -f 'tail -n 0 -F /home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/qemu-serial\.log' || true`
- `pkill -f 'tee -a /home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac/watch_patterns\.log' || true`
- `pkill -f 'egrep --line-buffered' || true`

## 明日（2026-01-14）— 选择 3 个新问题清单

目标：高效切换到 3 个新 syzbot 问题，避免在已修复报告上浪费时间。

1) 选择候选

- 使用挑选指南：
  - `docs/how-we-picked-top-3-syzbot-issues.md`
  - `docs/how-we-picked-unclaimed-syzbot-issues.md`
  - `docs/how-to-check-if-an-issue-is-already-being-worked.md`

2) 为每个 extid 建立 repro 目录与 runner

- 创建 `repro/<extid>/`，包含 syzbot bundle 工件（`disk.raw`、`bzImage`、`repro.syz` 等）。
- 复用 issue-3 runner 模式：
  - `tools/run_issue3_manual.sh`（必要时改为 `tools/run_issueX_manual.sh`）
  - 保持自动归档 watcher 命中功能开启。

3) “是否已修复？”快速确认

- 优先启动 **bundle** 内核。
- 若符号缺失/剥离，按同样的“地址反汇编”流程：
  - `ssh ... 'grep -m1 <symbol> /proc/kallsyms'`
  - `scripts/extract-vmlinux bzImage > vmlinux.from_bzImage`
  - `objdump --start-address/--stop-address ...`

4) 以稳定为先的起步参数

- 若早期崩溃出现，可在 `repro.local.syz` 中禁用无关子系统（如 wifi/ieee802154）。
- 除非确有必要，保持 `panic_on_oops=0 panic_on_warn=0`。
