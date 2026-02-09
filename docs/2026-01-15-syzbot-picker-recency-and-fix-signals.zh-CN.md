
# 2026-01-15 — “最近报告” + 更强的未修复过滤

[English](2026-01-15-syzbot-picker-recency-and-fix-signals.md)

今天网络较慢，因此我们把精力放在：让 picker 在选择“新鲜工作（fresh work）”时更确定、更可重复。

目标：
- 优先选择 **最近报告且带 repro** 的问题
- 排除 **已经修复 / dup / resolved** 的问题
- 排除 **正在流转补丁** 的问题（启发式：关联的 lore thread 标题包含 `[PATCH`）

## 变更

更新脚本：`tools/syzbot_pick_unclaimed.py`

### 1) “报告时间新鲜度”过滤

新增 CLI 参数：

- `--reported-after YYYY/MM/DD`
  - 仅保留 syzbot 状态行中包含可解析的 “reported … on YYYY/MM/DD” 且日期 **不早于** 该值的 bug。
- `--max-age-days N`
  - 仅保留在最近 `N` 天内报告的 bug。
  - 依赖状态行中存在可解析的 “reported … on …” 日期。

这些参数用于支持“刚报告（just reported）”的优先级分流，而不是从较老的 backlog 里捞。

### 2) 更强的 “未修复 / 非 dup” 排除

即使状态文本不够明确，syzkaller bug 页面本身也可能包含“已修复/已解决”的信号。
现在 unclaimed picker 会在 bug 页面包含以下任意关键词时排除候选：

- `upstream: fixed`
- `fixed:`
- `Fix commit` / `Fixing commit`
- `Resolved`
- `dup`

这与 `tools/syzbot_check_in_progress.py` 打印的快速信号保持一致。

## 示例命令

```bash
# Recently reported (since 2026/01/01), still unclaimed, reproducible:
./tools/syzbot_pick_unclaimed.py --count 3 --reported-after 2026/01/01

# Or: within last 14 days
./tools/syzbot_pick_unclaimed.py --count 3 --max-age-days 14

# Combine with area filters (example: kernel + scheduler-adjacent symptoms)
./tools/syzbot_pick_unclaimed.py \
  --count 3 --max-age-days 30 \
  --include-subsystem kernel \
  --include-title-re 'rcu|stall|hung|soft lockup|lockup|scheduling|preempt|watchdog|workqueue'
```

Notes:
- If your network is slow, reduce `--scan-limit` and/or `--timeout`.
- If a candidate is unexpectedly excluded, run `tools/syzbot_check_in_progress.py <extid>` to see the fix-ish signals and lore links.
