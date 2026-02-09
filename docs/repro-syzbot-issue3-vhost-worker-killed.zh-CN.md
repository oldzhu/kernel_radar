# Repro 设置：syzbot issue #3（vhost_worker_killed hung task）

[English](repro-syzbot-issue3-vhost-worker-killed.md)

本文记录一个端到端的“先用 syzbot 工件”复现流程：

- extid: `a9528028ab4ca83e8bac`
- bug 页面: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac

目标是尽快在 QEMU 中跑起 reproducer，以便在尝试修复之前先收集有价值的证据（堆栈、锁持有者）。

## 状态（2026-01-12）

此前已用 syzbot 内核成功复现：

- `INFO: task vhost-... blocked for more than ... seconds`
- 堆栈包含 `vhost_worker_killed()`
- 最终升级为 `Kernel panic - not syncing: hung_task: blocked tasks`

今日工作重心：从“能复现一次”推进到可重复的 **可插桩** 工作流：

- 新增本地内核构建流程（来自 `~/mylinux/linux`），产物放在 `repro/<extid>/localimage/`。
- 启用 lockdep + ftrace dump-on-oops，并添加 vhost 锁的定点跟踪（在 `~/mylinux/linux` 的内核树中，不在本仓库）。
- 在本地 fragment 中禁用 `CONFIG_NILFS2_FS` 和 `CONFIG_NETDEVSIM` 以减少无关噪音/崩溃。

当前本地内核的阻塞点：

- VM 在 `kmem_cache_alloc_noprof()` 里触发 `Oops: int3` 并 panic（SSH 重置）。
- ftrace dump 里能看到 `vhost_lock:` tracepoints，说明插桩生效。
- runner 现在会在启动 `syz-execprog` 前，通过 sysctl 关闭 panic-on-oops/panic-on-warn。

该次运行的 bundle 目录中有时间戳归档，例如：

- `qemu-serial.panic.<timestamp>.log`
- `watch_patterns.panic.<timestamp>.log`
- `execprog_stream.tail.<timestamp>.log`（小尾部；可安全分享）

## 0.1) 今日变更（摘要）

仓库内新增/更新脚本：

- `tools/build_issue3_local_kernel.sh`：从 `~/mylinux/linux` 构建本地内核，使用 `kernel.config` + fragment，产物放到 `repro/<extid>/localimage/`。
- `tools/run_issue3_manual.sh`：支持 A/B 内核选择和额外跟踪参数；同时设置 guest sysctl 以降低 “oops → 立即 panic”。

本地内核树（非仓库）改动：

- 在 `~/mylinux/linux/drivers/vhost/vhost.c` 中添加了定点 `trace_printk()`。
- 这些改动不会提交到此仓库（该仓库只保留自动化工具和文档）。

## 2.2) 本地内核（A/B 启动）+ 跟踪开关

我们保持原始 syzbot bundle 不变，本地产物放在：

- `repro/a9528028ab4ca83e8bac/localimage/`

### 构建本地内核

在仓库根目录执行：

```bash
tools/build_issue3_local_kernel.sh
```

使用：

- base: `repro/a9528028ab4ca83e8bac/kernel.config`
- fragment: `repro/a9528028ab4ca83e8bac/localimage/lockdep-trace-nonilfs.config`
- 内核树: `~/mylinux/linux`

产物输出到 `repro/a9528028ab4ca83e8bac/localimage/`：

- `bzImage`（QEMU 用）
- `vmlinux`（符号化用）
- `System.map`、`config`（调试参考）

### 启动本地内核并运行负载

示例（更激进负载 + 更大 ftrace buffer）：

```bash
USE_LOCALIMAGE=1 \
TRACE_BUF_SIZE_KB=8192 \
FTRACE_DUMP_ON_OOPS=1 \
APPEND_EXTRA='panic_on_warn=0 oops=continue' \
EXECPROG_PROCS=8 \
EXECPROG_REPEAT=1 \
CAPTURE_EXECPROG=1 \
tools/run_issue3_manual.sh
```

注意：

- `panic_on_oops=0` **不是** 支持的内核 cmdline 参数；内核会打印 unknown。
- 为避免 “oops → 立即 panic”，runner 现在会尝试：
  - `sysctl -w kernel.panic_on_oops=0` 和 `kernel.panic_on_warn=0`
  - 以及（fallback）写入 `/proc/sys/kernel/panic_on_oops` / `/proc/sys/kernel/panic_on_warn`

## 6) 已知失败模式（目前观察到的）

## 0) 前置条件

- QEMU（host）：`qemu-system-x86_64`
  - Debian/Ubuntu：`sudo apt-get update && sudo apt-get install -y qemu-system-x86`

该仓库工具 **不会** 自动安装 QEMU。

## 1) 准备 bundle（下载 + 解包）

在 `kernel_radar` 仓库根目录执行：

- `./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac`

会创建目录：

- `repro/a9528028ab4ca83e8bac/`

并写入：

- `bzImage` / `bzImage.xz`
- `disk.raw` / `disk.raw.xz`
- `vmlinux` / `vmlinux.xz`（若 bug 页面提供）
- `kernel.config`（KernelConfig）
- `repro.syz`（ReproSyz）
- `crash.log`、`repro.log`、`crash.report`（若存在）
- `run_qemu.sh`

`repro/` 目录被 git 忽略，避免误提交大文件。

### 工具工作原理（便于后续参考）

辅助脚本：

- [tools/syzbot_prepare_qemu_repro.py](../tools/syzbot_prepare_qemu_repro.py)

内部流程：

1) 抓取 syzbot bug HTML 页面。
2) 解析附件链接，如 `/text?tag=KernelConfig`、`/text?tag=ReproSyz`。
3) 解析 `https://storage.googleapis.com/syzbot-assets/` 下的大工件链接（disk + kernel image）。
4) 使用 `*.part` 临时文件流式下载后再 rename。
5) 解压 `*.xz` 到生成的 QEMU runner 期望的文件名（`bzImage`、`disk.raw`）。
6) 写出最小化 `run_qemu.sh`（并在缺少 `qemu-system-x86_64` 时拒绝运行）。

安全行为：

- 不会覆盖已有文件，除非传入 `--force`。
- 如只想刷新 `run_qemu.sh`（例如我们调整了 QEMU 参数），可用 `--regen-runner` 避免下载/解压。
- 保留原始 `*.xz`，便于无需重新下载即可再解压。

仅更新 runner 示例：

```bash
./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac --regen-runner
```

## 2) 启动 QEMU

- `cd repro/a9528028ab4ca83e8bac`
- `./run_qemu.sh`

说明：

- 默认使用 `-snapshot`（磁盘改动不持久化）。
  - 若需持久化：`PERSIST=1 ./run_qemu.sh`
- 可调整 VM 资源：
  - `MEM=4096 SMP=4 ./run_qemu.sh`

### 可选：后台运行 QEMU（保留终端）

默认 VM 在前台运行并占用终端。

若希望 VM 脱离运行（便于同一终端执行 `ssh`/`scp`），使用：

- `DAEMONIZE=1 ./run_qemu.sh`

说明：后台模式为纯 headless（无 `-nographic`）；控制台输出写入 `qemu-serial.log`。

会写入：

- `qemu-serial.log`（串口输出）
- `qemu.pid`（QEMU PID）

### 可选：host↔guest 共享目录（9p）

如果想不依赖 SSH/scp 简化文件传输，可通过 9p 把 host 目录映射进 VM：

- `SHARE_DIR=$PWD SHARE_MOUNT=/mnt/host ./run_qemu.sh`

在 guest 内执行：

- `mkdir -p /mnt/host`
- `mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host`

之后 host 的 `$PWD` 会出现在 VM 的 `/mnt/host`。

### 如果出现 “Unable to mount root fs”

syzbot 的磁盘镜像通常有分区。若看到类似：
`VFS: Unable to mount root fs`，通常是 cmdline 的 root 设备不对。

本仓库生成器设置为：

- `root=/dev/vda1 rootwait rw`

若你修改过旧版本 `run_qemu.sh`，请确认使用 `/dev/vda1`（不是 `/dev/vda`）。

## 2.1) 手动运行清单（host 侧）

本节为可直接复制的“手工流程”清单，便于反复跑 repro。

可选 helper 脚本（执行同样步骤，但保持透明）：

- `tools/run_issue3_manual.sh`

在仓库根目录运行：

```bash
tools/run_issue3_manual.sh
```

后续检查/停止：

```bash
tools/run_issue3_manual.sh --status
tools/run_issue3_manual.sh --stop
```

可选：将 guest 的 `execprog.out` 拉回 host（默认限制大小）：

```bash
CAPTURE_EXECPROG=1 tools/run_issue3_manual.sh
```

参数：

- `EXECPROG_STREAM_MAX_BYTES`（默认 5MiB；设为 `0` 关闭裁剪）
- `EXECPROG_STREAM_TRIM_SECS`（默认 5）

### A) 干净停止 + 重启 QEMU（建议 daemon 模式）

在 bundle 目录：

```bash
cd repro/a9528028ab4ca83e8bac

# stop an existing VM if present
if [[ -f qemu.pid ]]; then
  kill "$(cat qemu.pid)" || true
  sleep 1
  kill -9 "$(cat qemu.pid)" || true
fi

rm -f qemu.pid qemu-serial.log

# start detached (keeps your terminal)
DAEMONIZE=1 ./run_qemu.sh
```

你应看到：

- 出现 `qemu.pid`（qemu 的 PID）
- `qemu-serial.log` 持续增长

### B) 在串口日志中监控目标特征

在 host 上执行以下任一命令：

```bash
cd repro/a9528028ab4ca83e8bac

# quick grep (useful after-the-fact)
egrep -n 'INFO: task|blocked for more than|hung task|vhost_worker_killed|vhost-' qemu-serial.log | tail -n 50

# live watcher (best when SSH dies)
rm -f watch_patterns.log
(stdbuf -oL tail -n 0 -F qemu-serial.log | \
  stdbuf -oL egrep --line-buffered 'INFO: task|blocked for more than|hung task|vhost_worker_killed|BUG:|KASAN:|panic|Oops' | \
  tee -a watch_patterns.log)
```

### C) 验证 SSH 端口转发可用（避免命令卡死）

host `127.0.0.1:10022` → guest `:22` 的转发已经设置。

```bash
cd repro/a9528028ab4ca83e8bac

# host-side: make sure the port is listening
ss -ltnp | grep ':10022' || true

# guest-side probe (hard timeout so it never blocks)
timeout 8s ssh -o BatchMode=yes \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=5 -p 10022 root@127.0.0.1 true \
  && echo SSH_OK || echo SSH_FAIL
```

若显示 `SSH_FAIL` 但 `qemu-serial.log` 仍在增长，可视为 VM 存活，改用串口日志驱动的监控。

## 3) 在 VM 内运行 syzkaller repro

重要：`repro.syz` 是 **syz program**（不是 shell 脚本）。运行它需要：

- 可直接编译/运行的 C reproducer（`ReproC`），或
- syzkaller 运行器二进制：`syz-execprog` + `syz-executor`。

部分 syzbot 镜像内含 `syz-execprog`/`syz-executor`，但也有不包含的情况。

典型流程（拿到 root shell 后）：

- 查找二进制：
  - `ls / | grep syz`
  - `find / -maxdepth 2 -name 'syz-execprog' -o -name 'syz-executor' 2>/dev/null`

- 运行 reproducer：
  - `syz-execprog -executor=syz-executor -procs=1 -repeat=0 repro.syz`

若二进制在 `/` 下，可尝试：

- `/syz-execprog -executor=/syz-executor -procs=1 -repeat=0 repro.syz`

### 若 VM 中没有 `syz-execprog` / `syz-executor`

需要在 host 安装/构建 syzkaller，并将两个二进制复制/共享到 VM。最简单的方案：

- **host→guest 传输**（QEMU 9p 共享目录，或 SSH 可用时 scp）
- **在 VM 内构建**（更慢，需要 Go 工具链）

将二进制放入 VM 后，再运行上面的命令。

## 3.2) 手动流程（SSH + scp）— 最可靠的基线方式

我们发现这是最稳定的入门方式。SSH 通常在 `syz-execprog` 运行一段时间后变得不稳定，因此关键是 **缩短 SSH 会话** 并将负载后台化。

### 在 host 上

```bash
cd repro/a9528028ab4ca83e8bac

SYZ=/home/oldzhu/mylinux/syzkaller/bin/linux_amd64

# wait for SSH to become reachable (simple polling loop)
for i in $(seq 1 120); do
  if timeout 2s ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=2 -p 10022 root@127.0.0.1 true; then
    echo "ssh_up_after_seconds=$i"; break
  fi
  sleep 1
done

# stage files
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 'mkdir -p /root/repro'
scp -P 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$SYZ/syz-execprog" "$SYZ/syz-executor" repro.syz \
  root@127.0.0.1:/root/repro/

# start the repro in the background
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'set -e; cd /root/repro; chmod +x syz-execprog syz-executor; rm -f execprog.out; \
   nohup ./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz \
     >execprog.out 2>&1 & echo execprog_pid=$!'

# optional: try to fetch a small tail (may fail later if SSH starts timing out)
timeout 8s ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
  -p 10022 root@127.0.0.1 'tail -n 20 /root/repro/execprog.out' || true
```

如果 SSH 开始报 `Connection timed out during banner exchange`，请改用 `qemu-serial.log` + watcher（见 2.1B）。

## 3.1) 推荐的“无 scp”流程（使用共享目录）

这是不依赖 guest SSH 的最快方式。

### 在 host 上

1) 确保 host 上已有构建好的 runner 二进制：

- `~/mylinux/syzkaller/bin/linux_amd64/syz-execprog`
- `~/mylinux/syzkaller/bin/linux_amd64/syz-executor`

2) 使用 9p 共享目录启动 VM，指向 `~/mylinux`：

- `cd repro/a9528028ab4ca83e8bac`
- `SHARE_DIR=/home/oldzhu/mylinux SHARE_MOUNT=/mnt/host ./run_qemu.sh`

提示：若需后台运行：

- `SHARE_DIR=/home/oldzhu/mylinux SHARE_MOUNT=/mnt/host DAEMONIZE=1 ./run_qemu.sh`

### 在 guest 内

1) 挂载共享目录：

- `mkdir -p /mnt/host`
- `mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host`

2) 将二进制与 reproducer 拷贝到 guest 可写目录：

- `mkdir -p /root/repro`
- `cp /mnt/host/syzkaller/bin/linux_amd64/syz-execprog /root/repro/`
- `cp /mnt/host/syzkaller/bin/linux_amd64/syz-executor /root/repro/`
- `cp /mnt/host/kernel_radar/repro/a9528028ab4ca83e8bac/repro.syz /root/repro/`
- `chmod +x /root/repro/syz-execprog /root/repro/syz-executor`

3) 运行 reproducer：

- `cd /root/repro`
- `dmesg -wT &`
- `./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz`

若按预期卡住，记得抓取任务转储：

- `echo t > /proc/sysrq-trigger`

### “复现成功”的表现

该问题通常表现为与 vhost 相关的 hang/hung task，例如：

- `INFO: task ... blocked for more than ... seconds`
- `hung_task: blocked tasks`
- 堆栈中出现 `vhost*`（包含 vhost worker 路径）

## 4) 复现时需要捕获什么

该问题重点是收集 hung task / mutex 持有信息，建议回帖的数据包括：

- hang 之前的完整控制台输出
- `sysrq` 任务转储（若启用）：`echo t > /proc/sysrq-trigger`
- VM 中的 `dmesg` 输出

## 6) 已知失败模式（目前观察到的）

### A) 运行中 SSH 失效，但串口仍有输出

症状（host 侧）：

- `Connection timed out during banner exchange`

处理建议：

- 不再依赖 SSH，改为：
  - 使用 `qemu-serial.log` + `watch_patterns.log` 检测 hung-task 特征
  - 继续检查 `qemu-serial.log` 是否增长（`wc -l qemu-serial.log`、`tail -n 50 qemu-serial.log`）

### B) 启用 9p 共享时出现早期 KASAN Oops/panic

在 `SHARE_DIR=...`（virtio-9p）时，部分运行在 userspace 期间/之后出现早期 KASAN Oops/panic。

建议：

- 若目标是复现 hung-task，优先使用 SSH+scp 流程。
- 仅在需要“无 scp”时使用 9p，并注意它可能改变时序/行为。

### C) 本地内核：`Oops: int3` 随后 panic（SSH 重置）

症状：

- `Oops: int3`，RIP 位于 `kmem_cache_alloc_noprof()`
- 随后 `Kernel panic - not syncing: Fatal exception in interrupt`

说明：

- 这是与 vhost hung-task 不同的崩溃特征，可能阻碍达到目标。
- ftrace dump 仍能看到 `vhost_lock:` 跟踪，说明 vhost 路径被走到。
- 缓解尝试：通过 sysctl 关闭 panic-on-oops/panic-on-warn（已在 `tools/run_issue3_manual.sh` 自动执行）。

## 5) 相关线程回顾

参见此前邮件线程摘要：

- `docs/review-syzbot-issue3-vhost-worker-killed-thread.md`

## 故障排查：网络极慢

如果下载很慢/不稳定，可考虑：

- 先运行一次让其部分下载（写 `*.part`），随后用同样命令继续。
- 大文件可晚点下载；脚本会先写 `meta.txt` 以保留精确 URL。
- 仅在想丢弃 partial/cached 文件时使用 `--force`。
