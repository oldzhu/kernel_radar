# kernel_radar

Small, local “radar” tool to monitor kernel mailing lists (via lore.kernel.org Atom feeds), tag items by area (scheduler / AMDGPU / cgroups / namespaces), and generate a Markdown digest you can triage.

## Why this exists
- Keep a daily/weekly queue of: patches, regressions, RFCs, and discussions.
- Provide just enough metadata (subject, author, list, date, link, tags) so you can quickly decide what to review/test/fix.
- Designed to be safe: **read-only monitoring**. Patch drafting/testing can be added later.

## Quick start

1) Create a venv and install deps:
- `sudo apt-get install -y python3-venv`
- `python3 -m venv .venv`
- `./.venv/bin/pip install -r requirements.txt`

2) Create a config (start from the example):
- `cp -n config.example.yaml config.yaml`

3) Run a digest (writes a date-stamped report into `reports/`):
- `./run.sh --since-hours 48`

4) Open the report:
- `ls -la reports/`
- `less reports/kernel-digest-YYYY-MM-DD.md`

## Notes
- Uses lore Atom feeds like `https://lore.kernel.org/linux-kernel/new.atom`.
- Deduping is supported via a local state file (JSON).
- `config.yaml` is intentionally local-only and ignored by git; commit changes to `config.example.yaml` when you want to share defaults.

## Optional: systemd user timer (repo-contained, opt-in)

This repo includes example user units in `systemd-user/`.

Install steps (you run these manually):
- `mkdir -p ~/.config/systemd/user`
- `cp systemd-user/kernel-radar.* ~/.config/systemd/user/`
- (If your repo location is not `~/mylinux/kernel_radar`, edit `~/.config/systemd/user/kernel-radar.service` and update `WorkingDirectory=` / `ExecStart=`)
- `systemctl --user daemon-reload`
- `systemctl --user enable --now kernel-radar.timer`

Logs:
- `journalctl --user -u kernel-radar.service -n 200 --no-pager`

## Optional: cron (repo-contained, opt-in)

If you prefer cron, use the example line in `cron/crontab.example` (edit paths as needed).

## Optional: containerized kernel dev env (repo-contained, opt-in)

If you want a clean, reproducible Ubuntu 24.04 environment for kernel build + tooling (while keeping **email sending on the host**), see:
- [dev/README.md](dev/README.md)

## Next steps (optional)
- Add Patchwork and syzbot/regzbot ingestion.
- Add a “fetch thread mbox + apply + build” assistant that *never sends email without approval*.
