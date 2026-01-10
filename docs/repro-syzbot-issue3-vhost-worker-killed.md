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
- If you only want to refresh `run_qemu.sh` (for example after we tweak QEMU args in the generator), use `--regen-runner` to avoid any downloads/decompression.
- It keeps the original `*.xz` files so you can re-decompress without re-downloading.

Runner-only update example:

```bash
./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac --regen-runner
```

## 2) Boot QEMU

- `cd repro/a9528028ab4ca83e8bac`
- `./run_qemu.sh`

Notes:
- The script uses `-snapshot` by default (disk changes are not persisted).
  - To persist: `PERSIST=1 ./run_qemu.sh`
- You can change VM resources:
  - `MEM=4096 SMP=4 ./run_qemu.sh`

### Optional: run QEMU in the background (keep your terminal)

By default the VM runs in the foreground and takes over your terminal.

If you want the VM detached (so you can run `ssh`/`scp` from the same shell), use:
- `DAEMONIZE=1 ./run_qemu.sh`

It will write:
- `qemu-serial.log` (serial console output)
- `qemu.pid` (QEMU PID)

### Optional: host↔guest shared folder (9p)

If you want a simple file transfer path without relying on SSH/scp, you can pass a host directory
to the VM via 9p:

- `SHARE_DIR=$PWD SHARE_MOUNT=/mnt/host ./run_qemu.sh`

Then inside the guest:

- `mkdir -p /mnt/host`
- `mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host`

After that, files you put in `$PWD` on the host will appear under `/mnt/host` in the VM.

### If you hit “Unable to mount root fs”

syzbot disk images are typically partitioned. If you see a panic like:
`VFS: Unable to mount root fs`, it usually means the kernel cmdline root device
is wrong.

This repo’s generator sets:
- `root=/dev/vda1 rootwait rw`

If you’ve edited an older `run_qemu.sh`, ensure it uses `/dev/vda1` (not `/dev/vda`).

## 3) Run the syzkaller repro inside the VM

Important: `repro.syz` is a **syz program** (not a shell script). To run it you
need either:
- a C reproducer (`ReproC`) that you can compile/run directly, or
- syzkaller runner binaries: `syz-execprog` + `syz-executor`.

Some syzbot images include `syz-execprog`/`syz-executor`, but some do not.

Typical workflow after you get a root shell:

- Find the binaries:
  - `ls / | grep syz`
  - `find / -maxdepth 2 -name 'syz-execprog' -o -name 'syz-executor' 2>/dev/null`

- Run the reproducer:
  - `syz-execprog -executor=syz-executor -procs=1 -repeat=0 repro.syz`

If the binaries are under `/`, try:
- `/syz-execprog -executor=/syz-executor -procs=1 -repeat=0 repro.syz`

### If the VM does not contain `syz-execprog` / `syz-executor`

You will need to install/build syzkaller on the host, then copy/share the two
binaries into the VM. Easiest approaches:

- **Host→guest file transfer** (e.g. QEMU 9p shared folder, or scp once SSH works)
- **Build inside the VM** (slower; needs Go toolchain)

Once you have the two binaries inside the VM, re-run the command above.

## 3.1) Recommended “scp-free” workflow (use the shared folder)

This is the quickest way to run `repro.syz` without depending on guest SSH.

### On the host

1) Ensure you have the built runner binaries on the host:
- `~/mylinux/syzkaller/bin/linux_amd64/syz-execprog`
- `~/mylinux/syzkaller/bin/linux_amd64/syz-executor`

2) Boot the VM with a 9p shared folder that points at `~/mylinux`:

- `cd repro/a9528028ab4ca83e8bac`
- `SHARE_DIR=/home/oldzhu/mylinux SHARE_MOUNT=/mnt/host ./run_qemu.sh`

Tip: add `DAEMONIZE=1` if you want QEMU detached:
- `SHARE_DIR=/home/oldzhu/mylinux SHARE_MOUNT=/mnt/host DAEMONIZE=1 ./run_qemu.sh`

### In the guest

1) Mount the shared folder:

- `mkdir -p /mnt/host`
- `mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host`

2) Copy the binaries and reproducer into a writable guest directory:

- `mkdir -p /root/repro`
- `cp /mnt/host/syzkaller/bin/linux_amd64/syz-execprog /root/repro/`
- `cp /mnt/host/syzkaller/bin/linux_amd64/syz-executor /root/repro/`
- `cp /mnt/host/kernel_radar/repro/a9528028ab4ca83e8bac/repro.syz /root/repro/`
- `chmod +x /root/repro/syz-execprog /root/repro/syz-executor`

3) Run the reproducer:

- `cd /root/repro`
- `dmesg -wT &`
- `./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz`

If it hangs as expected, capture a task dump too:
- `echo t > /proc/sysrq-trigger`

### What “reproduced” looks like

For this issue, reproduction usually manifests as a hang/hung task involving vhost,
e.g. messages like:
- `INFO: task ... blocked for more than ... seconds`
- `hung_task: blocked tasks`
- call traces mentioning `vhost*` (including the vhost worker path)

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
