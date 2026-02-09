# 2026-01-14 — 面向特定领域的 syzbot 候选挑选

[English](2026-01-14-syzbot-picker-area-filters.md)

今天我们改进了“挑选候选问题（pick candidates）”的工作流：可以 **有意识地** 针对特定内核领域（例如 cgroup、namespaces、scheduler、GPU/DRM）进行筛选，而不是只依赖通用的“入门问题（starter）”启发式规则。

## 变更内容

### 1) picker 脚本支持动态过滤

两个 picker 现在都支持：

- `--include-title-re` / `--exclude-title-re`
  - Regex match against the syzbot bug title (case-insensitive).
- `--no-exclude-title`
  - Disables the default “hardware-ish” title exclusion.
  - This is required if you intentionally want GPU/DRM issues (default excludes include `drm`, `amdgpu`, `nouveau`, etc.).
- `--include-subsystem` / `--exclude-subsystem`
  - Match exact syzbot “Subsystems” labels (case-insensitive). Repeatable.
- `--include-subsystem-re` / `--exclude-subsystem-re`
  - Regex match against syzbot “Subsystems” labels (case-insensitive).

Scripts:
- `tools/syzbot_pick_top3.py`
- `tools/syzbot_pick_unclaimed.py`

### 2) 输出包含 `extid`

当页面上存在 extid 时，picker 输出会打印 `extid: ...`，这样我们可以立刻：
- check lore status with `tools/syzbot_check_in_progress.py --extid <extid>`
- scaffold a QEMU repro bundle via `tools/syzbot_prepare_qemu_repro.py --extid <extid>`

## 用法示例

Pick unclaimed issues (repro required, and skip ones with linked `[PATCH]` threads):

```bash
# cgroup / memcg
./tools/syzbot_pick_unclaimed.py --count 3 --include-subsystem cgroup
./tools/syzbot_pick_unclaimed.py --count 3 --include-title-re 'cgroup|memcg'

# namespaces
./tools/syzbot_pick_unclaimed.py --count 3 --include-title-re 'namespace|setns|unshare|nsfs'

# scheduler
./tools/syzbot_pick_unclaimed.py --count 3 --include-title-re 'sched|scheduler|cfs|rtmutex'

# GPU / DRM (intentionally)
./tools/syzbot_pick_unclaimed.py --count 3 --no-exclude-title --include-title-re 'drm|amdgpu|nouveau'
```

Pick “starter-friendly” issues (repro required, doesn’t check lore in-progress):

```bash
./tools/syzbot_pick_top3.py --count 3 --include-subsystem cgroup
./tools/syzbot_pick_top3.py --count 3 --include-subsystem-re '(cgroup|memcg|namespaces|scheduler)'
```

## 备注

- Subsystem 名称以 syzbot bug 页面上的标签为准；如果筛不到结果，尝试改用标题正则的方式。
- 对于 GPU 相关问题：upstream 覆盖通常是 DRM + 开源驱动（例如 `amdgpu`、`nouveau`）。闭源的 `nvidia` 驱动问题通常不会以 upstream syzbot subsystem 的形式出现。
