# 2026-01-10：issue #3（vhost_worker_killed）复现进展

[English](2026-01-10-issue3-repro-progress.md)

本文记录今日进展，便于后续快速续上。

目标问题：

- extid: `a9528028ab4ca83e8bac`
- bug 页面: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac

## 今日结束时的状态

- 可以使用本地 bundle 在 QEMU 中启动 syzbot 提供的内核+磁盘。
- 之前缺失的是 `syz-execprog` + `syz-executor` 二进制，用于运行 `repro.syz`。
- 这两个二进制已在 host 上构建完成（见下文）。

## 关键文件/目录

- Repro bundle（git 忽略）：
  - `repro/a9528028ab4ca83e8bac/`
  - 包含 `bzImage`、`disk.raw`、`repro.syz`、`run_qemu.sh`、日志等。
- syzkaller checkout（host）：
  - `/home/oldzhu/mylinux/syzkaller/`

## QEMU runner 改进

QEMU runner 由以下脚本生成：

- `tools/syzbot_prepare_qemu_repro.py`

`run_qemu.sh` 现在支持两个可选“质量提升”功能：

1) **守护进程模式（不占用终端）**

- `DAEMONIZE=1 ./run_qemu.sh`
- 串口输出写入 `qemu-serial.log`，PID 写入 `qemu.pid`。

2) **可选 host↔guest 共享目录（9p）**

- `SHARE_DIR=$PWD SHARE_MOUNT=/mnt/host ./run_qemu.sh`
- 在 guest 内挂载：
  - `mkdir -p /mnt/host`
  - `mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host`

这有助于在不依赖 SSH 的情况下把 `syz-execprog`/`syz-executor` 复制进 VM。

## syzkaller 运行二进制（host 侧）

系统 APT 没有 `syzkaller` 包，所以我们从源码构建。

### 1) clone syzkaller

- checkout 路径：`/home/oldzhu/mylinux/syzkaller`

为了应对网络不稳定，使用了浅克隆并减少 blob 传输。

### 2) Go 工具链要求

拉取的 syzkaller 仓库在 `go.mod` 中声明：

- `go 1.24.4`

而 host 的 Go 版本是：

- `go1.22.2`

因此我们下载了本地 Go 工具链（不替换系统版本）：

- 安装路径：`/home/oldzhu/.local/go1.24.4/go/bin/go`

### 3) 构建所需的两个二进制

产物路径：

- `/home/oldzhu/mylinux/syzkaller/bin/linux_amd64/syz-execprog`
- `/home/oldzhu/mylinux/syzkaller/bin/linux_amd64/syz-executor`

我们直接构建 `syz-execprog`：

- `GOOS=linux GOARCH=amd64 go build ... github.com/google/syzkaller/tools/syz-execprog`

并通过 `make execprog executor` 构建 `syz-executor`（executor 为 C++ 构建）。

注意：

- `make` 可能会尝试下载其他云/看板依赖；我们只需要这两个二进制。

## 下一步（恢复时）

1) 用共享目录启动 VM：

- `cd repro/a9528028ab4ca83e8bac`
- `SHARE_DIR=/home/oldzhu/mylinux SHARE_MOUNT=/mnt/host DAEMONIZE=1 ./run_qemu.sh`

2) 在 guest 内挂载共享目录并运行 repro：

- `mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host`
- 将二进制复制到可写目录（如 `/root/repro`），然后运行：
  - `./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz`

3) 捕获复现证据：

- `dmesg -wT`
- 挂起时执行：`echo t > /proc/sysrq-trigger`

参考复现预期：

- `docs/repro-syzbot-issue3-vhost-worker-killed.md`

## 额外实验 / 调试记录（之前未写入）

此处记录我们在实际复现过程中碰到的额外命令与失败模式，便于后续对照。

### A) 确认 syzbot “预期症状”来自已保存工件

bundle 中已经包含 syzbot 的目标 hung-task 报告：

- `repro/a9528028ab4ca83e8bac/crash.report`
  - `INFO: task vhost-... blocked for more than 143 seconds`
  - 调用栈包含 `vhost_worker_killed()`（`drivers/vhost/vhost.c:476`）。

### B) QEMU/SSH “是否存活”检查

Host 侧检查：

```bash
cd repro/a9528028ab4ca83e8bac

ls -l qemu.pid
ps -p "$(cat qemu.pid)" -o pid,cmd

# confirm the hostfwd is active
ss -ltnp | grep ':10022'
```

Guest 可达性/快速检查：

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'uname -a; echo ---cmdline---; cat /proc/cmdline'
```

注意：guest 镜像是 BusyBox；部分常用选项缺失，例如：

- `ps -p ...` 不支持（BusyBox `ps` 没有 `-p`）。
- `who -b` 不支持（BusyBox `who` 仅支持 `-aH`）。

### C) 将 `syz-execprog`/`syz-executor` + `repro.syz` 放入 guest

我们使用 **scp** 作为最可靠的基础方案：

```bash
SYZ=/home/oldzhu/mylinux/syzkaller/bin/linux_amd64
BUNDLE=/home/oldzhu/mylinux/kernel_radar/repro/a9528028ab4ca83e8bac

ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 'mkdir -p /root/repro'
scp -P 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$SYZ/syz-execprog" "$SYZ/syz-executor" "$BUNDLE/repro.syz" \
  root@127.0.0.1:/root/repro/
```

为了确认 executor 是预期构建（带 revision），我们检查字符串：

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'strings /root/repro/syz-executor | grep -i -E "rev|revision|bc54aa9f" | head -n 20'
```

预期输出包含 syzkaller 的 git revision（我们看到的示例）：

- `bc54aa9fe40d6d1ffa6f80a1e04a18689ddbc54c`

### D) 在 guest 内运行 repro（后台）

我们把 `syz-execprog` 放到后台运行，方便保持 SSH 会话较短：

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'set -e; cd /root/repro; rm -f execprog.out; \
   nohup ./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz \
     >execprog.out 2>&1 & echo execprog_pid=$!'

ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'tail -n 10 /root/repro/execprog.out'
```

我们通过 “executed programs: N” 行确认持续进展。

### E) 失败模式 1：启用 9p 时出现早期 KASAN panic

当使用 `run_qemu.sh` 启用 9p（设置 `SHARE_DIR=...`）启动 QEMU 时，观察到 guest 在 userspace 启动不久出现 **早期 KASAN Oops + panic**：

- `Oops: int3: 0000 [#1] SMP KASAN NOPTI`
- `RIP: kmem_cache_alloc_noprof+0x9c/0x710`
- 调用栈包含 `vm_area_alloc -> mmap_region -> do_mmap -> __x64_sys_mmap`
- `PID: ... Comm: dhcpcd-run-hook`
- `Kernel panic - not syncing: Fatal exception in interrupt`

该信息出现在串口输出：

- `repro/a9528028ab4ca83e8bac/qemu-serial.log`

我们用以下命令保存相关片段：

```bash
cd repro/a9528028ab4ca83e8bac
grep -n 'Kernel panic' qemu-serial.log
sed -n '2180,2310p' qemu-serial.log
```

由于 panic 发生在启动期间或刚进入 userspace，SSH 往往重置或无法使用。

### F) 失败模式 2：SSH 失联但串口仍继续输出

在 **不启用 9p** 的运行中，guest 能启动并可 SSH。运行 `syz-execprog` 一段时间后，SSH 开始报错：

- `Connection timed out during banner exchange`

同时：

- QEMU 仍存活（host 上 `ps` 显示 qemu pid 仍在）
- host 端口转发仍监听（`ss -ltnp | grep :10022`）
- `qemu-serial.log` 继续输出内核消息（guest 未彻底死掉）

我们用以下命令尝试捕获 vhost hung-task 特征：

```bash
cd repro/a9528028ab4ca83e8bac
grep -n -E 'INFO: task vhost|vhost_worker_killed|blocked for more than' qemu-serial.log

ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'dmesg | grep -E "INFO: task vhost|vhost_worker_killed|blocked for more than" | tail -n 20 || true'
```

在这些运行中，SSH 失联之前串口日志 **没有** 出现 hung-task 行。

### G) 观察到 guest 时间异常

我们注意到 `/proc/uptime` 可能非常大，而 dmesg 时间戳仍较小/正常。示例：

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'cat /proc/uptime; dmesg | tail -n 1'
```

这可能与启动时 clocksource 信息（例如 tsc 被标记为 unstable）有关，但尚未深入。

### H) 每次尝试间的 QEMU 清理重启

我们频繁重启 QEMU 以获得干净的运行与日志：

```bash
cd repro/a9528028ab4ca83e8bac
PID=$(cat qemu.pid)
kill "$PID" || true
```
