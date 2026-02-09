# 如何列出“无人认领”的 syzbot 问题（没有补丁在路上）

[English](how-we-picked-unclaimed-syzbot-issues.md)

本文记录了我们在挑选问题时使用的工作流与脚本，目标是选择一个：

- 可复现（最好有 C reproducer）
- 不需要特殊硬件
- **没有已经发布修复补丁**（避免重复劳动）


## “无人认领”的定义（启发式规则）

内核工作通过公开邮件协作，但没有一个完美的“锁”。
因此我们采用一个可观察、可执行的启发式规则：

> 只有当 syzbot bug 页面链接到某个 lore thread（`.../T/`），且该 thread 的主题包含 `[PATCH` 时，我们才认为该问题 **已在推进**。

如果关联的 lore thread 主题只是 `[syzbot] ...`，那是报告线程，并不是已发布修复补丁的线程。

局限性：

- 有人可能私下在做，或者在其它邮件列表中推进，但 syzbot 还没链接上。
- 修复可能已在子系统维护者树中，但尚未进入主线。

尽管如此，这一规则能避免最常见的重复：**修复补丁已经公开发布** 的情况。


## 数据来源

- syzbot upstream 列表（最小化 JSON）：
  - https://syzkaller.appspot.com/upstream?json=1

- 单个 bug 的 HTML 页面：
  - `https://syzkaller.appspot.com/bug?extid=...`

- 关联 thread 的 lore 页面：
  - `https://lore.kernel.org/.../T/`


## 新增脚本

我们把筛选逻辑保存成一个可运行的工具：

- [tools/syzbot_pick_unclaimed.py](../tools/syzbot_pick_unclaimed.py)

它的主要流程：
1) 拉取 upstream 列表 JSON（`/upstream?json=1`）。
2) 对每个 bug 抓取其 HTML 页面。
3) 仅保留包含 `ReproC` 或 `ReproSyz` 链接的 bug。
4) 过滤明显偏硬件的标题（USB/WiFi/BT/DRM 等）。
5) 跟进所有 lore `.../T/` 链接，从 `<u id=u>...</u>` 提取主题。
6) 若任何关联 thread 主题包含 `[PATCH`，则排除。

示例命令：

```bash
./tools/syzbot_pick_unclaimed.py
./tools/syzbot_pick_unclaimed.py --count 5 --scan-limit 2000
```

定向筛选特定领域（cgroup/namespaces/scheduler/GPU）：

```bash
# 尽量优先使用 syzbot subsystem 标签：
./tools/syzbot_pick_unclaimed.py --count 3 --include-subsystem cgroup
./tools/syzbot_pick_unclaimed.py --count 3 --include-subsystem scheduler
./tools/syzbot_pick_unclaimed.py --count 3 --include-subsystem namespaces

# 或者对 subsystem 标签做正则：
./tools/syzbot_pick_unclaimed.py --count 3 --include-subsystem-re '^(cgroup|memcg)$'

# 或者对标题关键词做正则（当 subsystem 标签不直观时很有用）：
./tools/syzbot_pick_unclaimed.py --count 3 --include-title-re 'cgroup|memcg'
./tools/syzbot_pick_unclaimed.py --count 3 --include-title-re 'namespace|setns|unshare|nsfs'
./tools/syzbot_pick_unclaimed.py --count 3 --include-title-re 'sched|scheduler|cfs|rtmutex'

# GPU/DRM 说明：默认标题排除包含 drm/amdgpu/nouveau。
# 如果明确要 GPU 相关问题，请关闭默认排除：
./tools/syzbot_pick_unclaimed.py --count 3 --no-exclude-title --include-title-re 'drm|amdgpu|nouveau'
```


## 与现有脚本的关系

- [tools/syzbot_check_in_progress.py](../tools/syzbot_check_in_progress.py)
  - 回答：“这个问题是否已经有人在做？”
  - 我们修正了判断逻辑：只有当 lore 主题包含 `[PATCH` 才算“有补丁在路上”。

- [tools/syzbot_pick_top3.py](../tools/syzbot_pick_top3.py)
  - 早期的“挑 3 个入门问题”脚本。
  - 它不判断“是否无人认领”，只做可复现性 + 排除硬件类标题。


## 关于速度/可靠性的说明

- syzbot 的 JSON 列表很简洁，因此必须抓取 HTML 页面。
- 这会带来大量 HTTP 请求；脚本使用了超时和小 sleep 来避免卡死。
- 如果结果为 0，尝试提高 `--scan-limit` 或放宽硬件类标题过滤条件。
