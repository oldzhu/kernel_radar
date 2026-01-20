# Copilot instructions (kernel_radar)

This file defines how the coding assistant should work in this repo.
Treat these as standing requirements for every chat/session.

## Project goal

Make monitoring and contribution to Linux kernel development easy and automated.

## Always do

### 1) Track progress in docs

- Maintain a dated progress note under `docs/` for each working day when we do non-trivial work.
- If the work is tied to a specific issue/extid, add a dated tracking note and link it from the progress note.
- Prefer short, factual notes: what we tried, what we learned, next steps.

### 2) Save new scripts/snippets as reusable tools

- If you write *any* new script (Python/shell) to help with picking, triage, repro, parsing lore, etc., save it under `tools/` (or `dev/` if clearly experimental) instead of leaving it as a one-off chat snippet.
- Add `--help` / usage examples in the script docstring.
- Keep dependencies minimal; prefer stdlib.
- Make scripts executable when appropriate.

### 3) Prefer existing tools; update instead of duplicating

- Before creating a new script, search for existing functionality in `tools/` and `docs/`.
- If an existing tool is close, extend it (add flags, improve output) rather than creating a near-duplicate.

### 4) Maintain a tools list and usage

- Keep `docs/tools-index.md` up to date when:
  - a new tool is added,
  - an existing tool gains new flags/features,
  - a workflow changes.
- The tools index should answer: “what tool do I use for X?” and provide 1–3 copy/paste commands.

### 5) Commit hygiene

- When adding docs/tools improvements, stage and commit them as coherent commits with descriptive messages.
- Keep commits scoped (avoid mixing unrelated refactors).

## Working conventions

- Use syzbot/syzkaller bug pages as the source of truth for repro/config links; use lore only via stable thread endpoints/links on bug pages.
- When network is slow/unreliable, prefer approaches that reduce per-bug HTTP fetches (smaller scan windows, shorter timeouts, cached artifacts if available).

## Checklist at the end of a session

- Did we write/update a dated doc under `docs/`?
- Did we save any ad-hoc snippet as a script under `tools/`?
- Did we update `docs/tools-index.md` if tooling changed?
- Is the working tree clean (or explicitly left dirty with a reason)?
