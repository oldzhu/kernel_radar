# Tools index

This is the “what tool do I use for X?” entry point.

## Session checklist

Before ending a work session:

- Update or add a dated progress note under `docs/` (what we tried/learned/next).
- Save any ad-hoc snippet as a reusable script under `tools/`.
- Update this tools index if tooling/flags/workflows changed.
- Commit docs/tools changes in a coherent commit.

Standing collaboration rules and project goal live in `.github/copilot-instructions.md`.

## Picking issues

- Pick reproducible starter issues (no lore checks):
  - `./tools/syzbot_pick_top3.py --count 3`

- Pick reproducible issues that appear unclaimed (no linked `[PATCH` thread):
  - `./tools/syzbot_pick_unclaimed.py --count 3`

- Pick recently reported unclaimed issues:
  - `./tools/syzbot_pick_unclaimed.py --count 3 --reported-after 2026/01/01`
  - `./tools/syzbot_pick_unclaimed.py --count 3 --max-age-days 14`

- Target specific areas:
  - Subsystems: `--include-subsystem X` / `--include-subsystem-re 're'`
  - Titles: `--include-title-re 're'`
  - GPU note: add `--no-exclude-title` if you intentionally want DRM/GPU

## Checking “in progress” / fixed

- Check a single extid for lore links and patch-like threads:
  - `./tools/syzbot_check_in_progress.py <extid>`

## Summarizing bugs for tracking notes

- Generate a copy/paste Markdown summary for one or more extids:
  - `./tools/syzbot_bug_summary.py --markdown <extid1> <extid2> ...`

## Preparing repro

- Create a local QEMU repro bundle:
  - `./tools/syzbot_prepare_qemu_repro.py --extid <extid>`
  - Output: `repro/<extid>/run_qemu.sh`

## Lore thread followups

- Summarize a lore thread (follow-ups):
  - `./tools/lore_thread_followups.py --help`

## Notes

- If you add or change a tool/flag, update this file and add a short dated note under `docs/`.
