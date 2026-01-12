# Repro setup: syzbot issue #3 (vhost_worker_killed hung task)

This doc records an end-to-end “use syzbot artifacts first” repro setup for:
- extid: `a9528028ab4ca83e8bac`
- bug page: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac

The point is to quickly get a reproducer running under QEMU so we can gather
useful evidence (stacks, lock holders) before attempting a fix.

## Status (2026-01-12)

We observed the target signature in the VM serial log:
- `INFO: task vhost-... blocked for more than ... seconds`
- stack including `vhost_worker_killed()`
- escalated to `Kernel panic - not syncing: hung_task: blocked tasks`

For that run, the bundle directory contains timestamped archives like:
- `qemu-serial.panic.<timestamp>.log`
- `watch_patterns.panic.<timestamp>.log`
- `execprog_stream.tail.<timestamp>.log` (small tail; safe to share)

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

Note: daemonized mode is fully headless (no `-nographic`); console output is written to `qemu-serial.log`.

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

## 2.1) Manual runbook (host-side)

This section is a copy/paste-friendly “manual ops” checklist for running the repro repeatedly.

Optional helper script (runs these same steps, but keeps everything transparent):

- `tools/run_issue3_manual.sh`

From the repo root:

```bash
tools/run_issue3_manual.sh
```

To check/stop later:

```bash
tools/run_issue3_manual.sh --status
tools/run_issue3_manual.sh --stop
```

Optional: capture the guest `execprog.out` to the host (bounded size by default):

```bash
CAPTURE_EXECPROG=1 tools/run_issue3_manual.sh
```

Knobs:
- `EXECPROG_STREAM_MAX_BYTES` (default: 5MiB; set `0` to disable trimming)
- `EXECPROG_STREAM_TRIM_SECS` (default: 5)

### A) Clean stop + restart QEMU (daemon mode recommended)

From the bundle directory:

```bash
cd repro/a9528028ab4ca83e8bac

# stop an existing VM if present
if [[ -f qemu.pid ]]; then
  kill "$(cat qemu.pid)" || true
  sleep 1
  kill -9 "$(cat qemu.pid)" || true
fi

rm -f qemu.pid qemu-serial.log

# start detached (keeps your terminal)
DAEMONIZE=1 ./run_qemu.sh
```

What you should see:
- `qemu.pid` appears (PID of qemu)
- `qemu-serial.log` grows over time

### B) Watch for the target signature in the serial log

Run one of these on the host:

```bash
cd repro/a9528028ab4ca83e8bac

# quick grep (useful after-the-fact)
egrep -n 'INFO: task|blocked for more than|hung task|vhost_worker_killed|vhost-' qemu-serial.log | tail -n 50

# live watcher (best when SSH dies)
rm -f watch_patterns.log
(stdbuf -oL tail -n 0 -F qemu-serial.log | \
  stdbuf -oL egrep --line-buffered 'INFO: task|blocked for more than|hung task|vhost_worker_killed|BUG:|KASAN:|panic|Oops' | \
  tee -a watch_patterns.log)
```

### C) Verify the forwarded SSH port is up (don’t let commands hang)

We forward host `127.0.0.1:10022` → guest `:22`.

```bash
cd repro/a9528028ab4ca83e8bac

# host-side: make sure the port is listening
ss -ltnp | grep ':10022' || true

# guest-side probe (hard timeout so it never blocks)
timeout 8s ssh -o BatchMode=yes \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=5 -p 10022 root@127.0.0.1 true \
  && echo SSH_OK || echo SSH_FAIL
```

If `SSH_FAIL` but `qemu-serial.log` is still growing, treat the VM as alive and switch to serial-log-driven monitoring.

## 3) Run the syzkaller repro inside the VM

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

## 3.2) Manual workflow (SSH + scp) — baseline reliable method

We found this to be the most reliable way to get started. SSH may become unstable *after* `syz-execprog`
runs for a while, so the trick is to keep SSH sessions short and background the workload.

### On the host

```bash
cd repro/a9528028ab4ca83e8bac

SYZ=/home/oldzhu/mylinux/syzkaller/bin/linux_amd64

# wait for SSH to become reachable (simple polling loop)
for i in $(seq 1 120); do
  if timeout 2s ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=2 -p 10022 root@127.0.0.1 true; then
    echo "ssh_up_after_seconds=$i"; break
  fi
  sleep 1
done

# stage files
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 'mkdir -p /root/repro'
scp -P 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$SYZ/syz-execprog" "$SYZ/syz-executor" repro.syz \
  root@127.0.0.1:/root/repro/

# start the repro in the background
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 10022 root@127.0.0.1 \
  'set -e; cd /root/repro; chmod +x syz-execprog syz-executor; rm -f execprog.out; \
   nohup ./syz-execprog -executor=./syz-executor -sandbox=none -procs=6 -threaded=1 -repeat=0 repro.syz \
     >execprog.out 2>&1 & echo execprog_pid=$!'

# optional: try to fetch a small tail (may fail later if SSH starts timing out)
timeout 8s ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
  -p 10022 root@127.0.0.1 'tail -n 20 /root/repro/execprog.out' || true
```

If SSH starts failing with `Connection timed out during banner exchange`, rely on `qemu-serial.log` + the watcher (section 2.1B).

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

## 6) Known failure modes (what we’ve seen so far)

### A) SSH becomes unusable mid-run while serial output continues

Symptom (host-side):
- `Connection timed out during banner exchange`

What to do:
- Stop relying on SSH, and instead:
  - use `qemu-serial.log` + `watch_patterns.log` to detect the hung-task signature
  - keep checking whether `qemu-serial.log` is still growing (`wc -l qemu-serial.log`, `tail -n 50 qemu-serial.log`)

### B) Early KASAN Oops/panic when 9p sharing is enabled

In some runs with `SHARE_DIR=...` (virtio-9p), we observed an early KASAN Oops/panic during/soon after userspace.

Practical advice:
- If your goal is reproducing the hung-task, prefer the SSH+scp workflow first.
- Use 9p only if you specifically want scp-free staging, and be aware it may change timing/behavior.


## 5) Related thread review

See the earlier mail-thread summary:
- `docs/review-syzbot-issue3-vhost-worker-killed-thread.md`


## Troubleshooting: very slow network

If downloads are slow/unreliable, you can:
- Run the tool once and let it partially download (it writes `*.part` files), then rerun with the same command.
- Prefer doing the big downloads later; the script still writes `meta.txt` first so you keep the exact URLs.
- Use `--force` only if you want to discard partial/cached files.
