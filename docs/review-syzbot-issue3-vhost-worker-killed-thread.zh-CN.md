# Review notes：syzbot 问题 #3（vhost_worker_killed hung task）thread

[English](review-syzbot-issue3-vhost-worker-killed-thread.md)

本文记录我们如何回顾此前“top 3” syzbot shortlist 中 **issue #3** 的 lore 邮件线程。

- Bug (syzbot): https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac
- Lore thread (all): https://lore.kernel.org/all/695b796e.050a0220.1c9965.002a.GAE@google.com/T/


## 目标

- 理解维护者讨论的核心（根因 vs. 锁设计）
- 判断是否已经有人在积极推进
- 找到一个具体、初学者友好的贡献点（分析、复现、插桩或小补丁）


## 如何稳定地获取线程内容

我们避免使用 lore 的 HTML 搜索页（有时会有 bot 保护），改用脚本直接读取 thread mbox：

- 脚本：[tools/lore_thread_followups.py](../tools/lore_thread_followups.py)

命令：

```bash
./tools/lore_thread_followups.py \
  --list all \
  --mid 695b796e.050a0220.1c9965.002a.GAE@google.com \
  --show-bodies 5
```

输出内容包括：

- 消息数量
- 每条消息的 From/Date/Subject/Message-ID/In-Reply-To
- 最多 N 条回复的正文（不含第一封 syzbot 报告）


## 线程讨论概要（高层）

报告的症状是 **hung task**，涉及 vhost 线程的 teardown / kill 路径。
syzbot 报告中的堆栈显示 vhost 内核线程阻塞在：

- `vhost_worker_killed()` 里尝试锁 `vq->mutex`（virtqueue mutex）

讨论焦点是：在 kill/teardown 路径中获取 `vq->mutex` 是否安全。


## 逐条消息摘要

当前线程总共 **5 条消息**（syzbot 报告 + 4 条人工回复）。

1) syzbot 报告
- 提供：kernel commit、config、repro 链接，以及 hung task 的栈信息。
- 关键线索是 `vhost_worker_killed()` 在等待 `vq->mutex`。

2) Michael S. Tsirkin (mst)
- 指出在 kill handler 中拿 `vq->mutex` 很可能是不合适的。
- 建议为 worker 分配/teardown 引入单独的锁。

3) Hillf Danton
- 提醒不要在尚未确认根因的情况下“盲目”添加新锁。

4) Michael S. Tsirkin 继续说明
- 解释更广泛的担忧：`vq->mutex` 可能会在与用户空间相关的操作期间被持有。
- 如果 vhost 线程在持锁时进入不可中断睡眠，其他持锁路径也会变得不可中断。
- 这不是新问题，但在新的 vhost 线程管理机制下更容易暴露。
- 不希望在 datapath 上增加额外锁。

5) Mike Christie
- 询问进一步澄清，因为 lockdep 只显示 kill handler 在等待 `vq->mutex`。
- 怀疑是否存在用户态 ioctl 线程参与，但未在输出中体现。
- 提到历史锁设计：曾用 `vhost_dev->mutex`，之后引入 `vhost_worker->mutex` 以避免 ioctl flush 交互。
- 如果确认 `vq->mutex` 是问题，愿意接受补丁。


## 是否已经有人在推进？

- 有讨论，但 **尚未看到明显的修复补丁**（检查时主题中没有 `[PATCH]`）。
- 这通常意味着仍处在“调查/诊断”阶段。


## 实用贡献建议（低风险）

此处更适合初学者的贡献是 **补充证据**，以帮助维护者推进：

1) 复现并确认“是谁持有 `vq->mutex`”
- 在 VM 中运行 syz repro（见下文）。
- 触发 hung-task 时捕获相关任务的堆栈。
- 尽可能确认是否有用户态 ioctl 线程持有 `vq->mutex`。

2) 诊断用的临时插桩补丁
- 在 vhost 路径中围绕 `vq->mutex` 的获取加入 debug prints / tracepoints。
- 记录持锁者（PID/comm）以及是否在持锁期间进入不可中断睡眠。
- 将结果回复到邮件线程（即使没有最终修复补丁）。

3) 若证据支持，再提出小的锁改动
- 避免在 `vhost_worker_killed()` 中直接拿 `vq->mutex`，改为重构 teardown 或引入专用锁。
- 必须以证据驱动（回应线程中的担忧）。


## Repro 环境说明

syzbot 提供的资产（内核镜像 + 磁盘镜像）可直接用于 QEMU 复现，无需自行编译内核。
但若要验证修复，一般还是需要编译带补丁的内核，并在 QEMU 中使用同一磁盘/repro 启动。

