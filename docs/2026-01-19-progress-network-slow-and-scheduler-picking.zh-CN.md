# 2026-01-19 — 进展记录（网络慢；选择调度相关问题）

[English](2026-01-19-progress-network-slow-and-scheduler-picking.md)

> 说明：本文为简体中文翻译版；命令、URL、日志片段与代码符号保持原样，便于精确对照。

## 今天尝试了什么

今日目标：
- 选择 **3 个最近报告**、带 **repro**、**未修复/非 dup**，并且看起来 **无人认领** 的问题（lore thread 标题中没有包含 `[PATCH` 的关联主题）。
- 重点关注“调度器相关/邻近”的症状（hung task / lockup / RCU stall / workqueue 等）。

## 观察

### 1) 网络不稳定会阻塞“批量扫很多 bug 页面”的工作流

- 选择器脚本对每个候选 bug 都依赖从 syzkaller 拉取 HTML 页面。
- 网络慢/不稳定时，经常卡在 TLS 握手或读取阶段。
- 这会让“scan-limit 上千”的交互式筛选基本不可用。

### 2) Scheduler 不是 syzkaller upstream 的一等 subsystem label

- `https://syzkaller.appspot.com/upstream?json=1` 的 JSON 只包含 `{title, link}`。
- `https://syzkaller.appspot.com/upstream` 的 upstream subsystem 过滤列表里没有明显的 scheduler 标签。
- 目前可行的折中是：先用 `kernel` 作为粗粒度区域（`/upstream/s/kernel`），再依靠标题关键词进一步收敛。

### 3) 现有“kernel + 调度相关”短名单偏旧

当退回使用 `tools/syzbot_pick_top3.py`（忽略“无人认领/新鲜度”约束）时，得到：

- `ed53e35a1e9dde289579` — INFO: task hung in `p9_fd_close (3)`
- `68c586d577defab7485e` — INFO: task hung in `vmci_qp_broker_detach`
- `a50479d6d26ffd27e13b` — INFO: task hung in `worker_attach_to_pool (3)`

但这些并非“刚报告”的问题（报告时间在 2025/08–10），且至少一个有 dup 信号。

### 4) in-progress / fix signals 检查

- `tools/syzbot_check_in_progress.py ed53e35a1e9dde289579` 显示了 dup 信号（bug 页面包含 “closed as dup ...”）。
- 另外两个在第一次快速检查输出中，没有明显看到类似补丁的 lore subject。

## 结果

由于网络较慢，今天 **没能稳定地** 产出 3 个“新鲜 + 无人认领 + 调度相关”的候选问题。

## 下一步（明天）

建议采用低网络消耗的方式：

1) 先用更小的候选集合（例如从 `https://syzkaller.appspot.com/upstream/s/kernel` 获取）来减少扫描量。
2) 在 picker 中启用更严格的“新鲜度”过滤：

```bash
./tools/syzbot_pick_unclaimed.py \
  --count 3 --reported-after 2026/01/01 \
  --scan-limit 200 --timeout 10 --sleep 0.05 \
  --include-subsystem kernel \
  --include-title-re 'rcu|stall|hung|soft lockup|lockup|scheduling|preempt|watchdog|workqueue|kthread'
```

如果仍然挑不出 3 个，按以下顺序放宽：
- 放宽日期窗口（使用 `--max-age-days 60`）
- 去掉 `--include-subsystem kernel`（保留标题正则）
- 暂时去掉“调度相关”正则：先挑 3 个新鲜、无人认领的问题，然后再从中选一个更接近调度器的。
