#!/usr/bin/env python3
"""Boot a syzbot QEMU bundle and run ./repro via the serial console.

This is intended to be used with syzbot repro bundles prepared under:
  kernel_radar/repro/<extid>/

The bundle directory must contain at least:
- run_qemu.sh
- repro
- repro.c
- repro.syz

It will:
- boot QEMU (optionally with KVM)
- wait for a root shell on the serial console
- mount the bundle directory into the guest via 9p
- execute ./repro inside the guest
- watch for common crash/stall patterns

Example:
  python3 tools/run_repro_serial.py --bundle-dir repro/f8850bc3986562f79619 --kvm --cpu host

Dependencies:
- pexpect (python package)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

try:
    import pexpect
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pexpect. Install with: pip install -r requirements.txt"
    ) from exc


def _wait_for_shell(child: pexpect.spawn, timeout_s: int) -> None:
    deadline = time.time() + timeout_s

    login_re = r"(?i)login:\s*$"
    password_re = r"(?i)password:\s*$"
    shell_re = r"(?m)^[^\n]*[#]\s*$"

    while True:
        remaining = max(1, int(deadline - time.time()))
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for guest shell prompt")

        idx = child.expect(
            [shell_re, login_re, password_re, pexpect.EOF, pexpect.TIMEOUT], timeout=remaining
        )
        if idx == 0:
            return
        if idx == 1:
            child.sendline("root")
            continue
        if idx == 2:
            child.sendline("")
            continue
        if idx == 3:
            raise RuntimeError("QEMU exited before reaching a shell")
        # TIMEOUT: loop until deadline


def _run_cmd(child: pexpect.spawn, cmd: str, timeout_s: int) -> None:
    shell_re = r"(?m)^[^\n]*[#]\s*$"
    child.sendline(cmd)
    child.expect(shell_re, timeout=timeout_s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bundle-dir",
        default=".",
        help="Path to the syzbot repro bundle directory (contains run_qemu.sh, repro, disk image).",
    )
    ap.add_argument("--timeout", type=int, default=420, help="Wait for trigger (seconds).")
    ap.add_argument("--boot-timeout", type=int, default=240, help="Wait for boot/login (seconds).")
    ap.add_argument(
        "--post-trigger-wait",
        type=int,
        default=15,
        help="After detecting a trigger, wait to capture more console output (seconds).",
    )
    ap.add_argument("--kvm", action="store_true", help="Enable KVM acceleration (requires /dev/kvm).")
    ap.add_argument("--cpu", default="", help="QEMU -cpu argument when --kvm is enabled (e.g. 'host').")
    ap.add_argument("--mem", type=int, default=2048, help="Guest memory in MB (MEM env for run_qemu.sh).")
    ap.add_argument("--smp", type=int, default=2, help="Guest vCPU count (SMP env for run_qemu.sh).")
    args = ap.parse_args()

    bundle_dir = os.path.abspath(args.bundle_dir)
    run_qemu = os.path.join(bundle_dir, "run_qemu.sh")
    if not os.path.exists(run_qemu):
        print(f"Missing runner: {run_qemu}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["MEM"] = str(args.mem)
    env["SMP"] = str(args.smp)
    env["SHARE_DIR"] = bundle_dir
    env["SHARE_TAG"] = "hostshare"
    env["SHARE_MOUNT"] = "/mnt/host"

    if args.kvm:
        env["ENABLE_KVM"] = "1"
        if args.cpu:
            env["CPU"] = args.cpu

    log_path = os.path.join(bundle_dir, "qemu-serial-auto.log")
    with open(log_path, "w", encoding="utf-8", errors="ignore") as log_fp:
        print(f"[+] Starting QEMU (log: {log_path})")
        child = pexpect.spawn(
            run_qemu,
            cwd=bundle_dir,
            env=env,
            encoding="utf-8",
            codec_errors="ignore",
        )
        child.logfile_read = log_fp

        try:
            _wait_for_shell(child, timeout_s=args.boot_timeout)

            _run_cmd(child, "mkdir -p /mnt/host", timeout_s=30)
            _run_cmd(child, "modprobe 9pnet_virtio 2>/dev/null || true", timeout_s=30)
            _run_cmd(
                child,
                "mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt/host || true",
                timeout_s=30,
            )
            _run_cmd(child, "ls -l /mnt/host/repro /mnt/host/repro.c /mnt/host/repro.syz", timeout_s=30)

            print("[+] Running /mnt/host/repro inside guest")
            child.sendline("cd /mnt/host && chmod +x repro && ./repro")

            crash_patterns = [
                r"BUG: soft lockup",
                r"rcu:.*stall",
                r"INFO: rcu detected stall",
                r"Kernel panic",
                r"KASAN:",
                pexpect.EOF,
                pexpect.TIMEOUT,
            ]
            idx = child.expect(crash_patterns, timeout=args.timeout)
            if idx in (0, 1, 2, 3, 4):
                print(f"[!] Triggered: matched pattern: {crash_patterns[idx]}")
                if args.post_trigger_wait > 0:
                    time.sleep(args.post_trigger_wait)
                return 0
            if idx == 5:
                print("[!] QEMU exited (EOF) while waiting")
                return 1

            print("[-] Timeout waiting for crash/stall; no repro observed")
            return 1
        finally:
            try:
                child.sendcontrol("a")
                child.send("x")
                child.expect(pexpect.EOF, timeout=10)
            except Exception:
                try:
                    child.close(force=True)
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
