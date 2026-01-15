# 2026-01-15 — “Recently reported” + stronger not-fixed filtering

Network was slow today, so we focused on making the picker more deterministic for “fresh work” selection:

Goal:
- pick issues that were **recently reported with a repro**
- avoid issues that are **already fixed / dup / resolved**
- avoid issues with **patches in flight** (heuristic: linked lore thread subject contains `[PATCH`)

## Changes

Updated script: `tools/syzbot_pick_unclaimed.py`

### 1) Report recency filters

New CLI flags:

- `--reported-after YYYY/MM/DD`
  - Keep only bugs whose syzbot status line contains a parseable “reported … on YYYY/MM/DD” date **on/after** this date.
- `--max-age-days N`
  - Keep only bugs reported within the last `N` days.
  - Requires the status line to contain a parseable “reported … on …” date.

These are meant to support “just reported” triage instead of older backlog.

### 2) Stronger “not fixed / not dup” exclusion

Even if the status text is not explicit, the syzbot bug page may include fix-ish signals.
The unclaimed picker now excludes a candidate if the bug page contains any of:

- `upstream: fixed`
- `fixed:`
- `Fix commit` / `Fixing commit`
- `Resolved`
- `dup`

This mirrors the quick signals printed by `tools/syzbot_check_in_progress.py`.

## Example commands

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
