# Repro setup: syzbot issue #3 (vhost_worker_killed hung task)

This doc records an end-to-end “use syzbot artifacts first” repro setup for:
- extid: `a9528028ab4ca83e8bac`
- bug page: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac

The point is to quickly get a reproducer running under QEMU so we can gather
useful evidence (stacks, lock holders) before attempting a fix.

## 0) Prereqs

- QEMU (host): `qemu-system-x86_64`
  - Debian/Ubuntu: `sudo apt-get update && sudo apt-get install -y qemu-system-x86`

This repo tool does **not** install QEMU for you.

## 1) Prepare the bundle (download + unpack)

From the `kernel_radar` repo root:

- `./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac`

This creates a local directory:
- `repro/a9528028ab4ca83e8bac/`

…and writes:
- `bzImage` / `bzImage.xz`
- `disk.raw` / `disk.raw.xz`
- `vmlinux` / `vmlinux.xz` (if present on the bug page)
- `kernel.config` (KernelConfig)
- `repro.syz` (ReproSyz)
- `crash.log`, `repro.log`, `crash.report` (if present)
- `run_qemu.sh`

The `repro/` directory is ignored by git so you don’t accidentally commit large binaries.

### How the tool works (for later reference)

The helper script is:
- [tools/syzbot_prepare_qemu_repro.py](../tools/syzbot_prepare_qemu_repro.py)

Internally it:
1) Fetches the syzbot bug HTML page.
2) Scrapes attachment links like `/text?tag=KernelConfig` and `/text?tag=ReproSyz`.
3) Scrapes large artifact links hosted under `https://storage.googleapis.com/syzbot-assets/` (disk + kernel image).
4) Streams downloads to disk using `*.part` temporary files then renames.
5) Decompresses `*.xz` into the exact filenames expected by the generated QEMU runner (`bzImage`, `disk.raw`).
6) Writes `run_qemu.sh` as a minimal boot helper (and refuses to run if `qemu-system-x86_64` is missing).

Safety behaviors:
- It will not overwrite existing files unless you pass `--force`.
- It keeps the original `*.xz` files so you can re-decompress without re-downloading.

## 2) Boot QEMU

- `cd repro/a9528028ab4ca83e8bac`
- `./run_qemu.sh`

Notes:
- The script uses `-snapshot` by default (disk changes are not persisted).
  - To persist: `PERSIST=1 ./run_qemu.sh`
- You can change VM resources:
  - `MEM=4096 SMP=4 ./run_qemu.sh`

## 3) Run the syzkaller repro inside the VM

syzbot disk images usually include syzkaller runner binaries (commonly named
`syz-execprog` and `syz-executor`), but locations can vary.

Typical workflow after you get a root shell:

- Find the binaries:
  - `ls / | grep syz`
  - `find / -maxdepth 2 -name 'syz-execprog' -o -name 'syz-executor' 2>/dev/null`

- Run the reproducer:
  - `syz-execprog -executor=syz-executor -procs=1 -repeat=0 repro.syz`

If the binaries are under `/`, try:
- `/syz-execprog -executor=/syz-executor -procs=1 -repeat=0 repro.syz`

## 4) What to capture when it reproduces

For this issue, the goal is to capture evidence around the hung task / mutex
ownership. Useful data to post back to the thread includes:

- full console output up to the hang
- `sysrq` task dumps (if enabled): `echo t > /proc/sysrq-trigger`
- `dmesg` output from the VM

## 5) Related thread review

See the earlier mail-thread summary:
- `docs/review-syzbot-issue3-vhost-worker-killed-thread.md`


## Troubleshooting: very slow network

If downloads are slow/unreliable, you can:
- Run the tool once and let it partially download (it writes `*.part` files), then rerun with the same command.
- Prefer doing the big downloads later; the script still writes `meta.txt` first so you keep the exact URLs.
- Use `--force` only if you want to discard partial/cached files.
