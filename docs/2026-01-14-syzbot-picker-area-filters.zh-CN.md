# 2026-01-14 — Area-focused syzbot picking（简体中文）

[English](2026-01-14-syzbot-picker-area-filters.md)

> 说明：本简体中文版本包含中文导读 + 英文原文（便于准确对照命令/日志/代码符号）。

## 中文导读（章节列表）

- What changed
- Usage examples
- Notes

## English 原文

# 2026-01-14 — Area-focused syzbot picking

[简体中文](2026-01-14-syzbot-picker-area-filters.zh-CN.md)

Today we improved the “pick candidates” workflow so we can intentionally target specific kernel areas (e.g. cgroup, namespaces, scheduler, GPU/DRM) instead of only relying on generic “starter” heuristics.

## What changed

### 1) Dynamic filters in the picker scripts

Both pickers now support:

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

### 2) Output includes `extid`

Picker output prints `extid: ...` when present, so we can immediately:
- check lore status with `tools/syzbot_check_in_progress.py --extid <extid>`
- scaffold a QEMU repro bundle via `tools/syzbot_prepare_qemu_repro.py --extid <extid>`

## Usage examples

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

## Notes

- Subsystem names are whatever syzbot labels on the bug page; if you get no hits, try the title regex approach.
- For GPU bugs: upstream coverage is typically DRM + open drivers (e.g. `amdgpu`, `nouveau`). Proprietary `nvidia` driver issues usually won’t appear as upstream syzbot subsystems.
