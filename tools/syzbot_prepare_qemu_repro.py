#!/usr/bin/env python3
"""Prepare a local QEMU repro bundle from a syzbot bug page.

This downloads the syzbot-provided kernel image + disk image and writes a small
"bundle" directory containing:
- bzImage
- disk.raw
- vmlinux (optional; if present on the bug page)
- kernel.config (KernelConfig text)
- repro.syz (ReproSyz program)
- crash.log / repro.log / crash.report (if present)
- run_qemu.sh (a ready-to-run QEMU command)

The goal is to let you reproduce quickly using syzbot artifacts first; build your
own kernel later when validating a fix.

Usage
-----
  ./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac
  ./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac --out repro/issue3

Notes
-----
- This tool only uses stdlib.
- QEMU is not installed by this tool.
- Large assets are downloaded by streaming to disk and written via a temporary
    `.part` file first, then atomically renamed.
- Existing files are not overwritten unless you pass `--force`.
"""

from __future__ import annotations

import argparse
import lzma
import os
import re
import sys
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "https://syzkaller.appspot.com"
UA = {"User-Agent": "kernel_radar/0.1 (+local)"}


@dataclass(frozen=True)
class BugLinks:
    bug_url: str
    disk_xz: str | None
    bzimage_xz: str | None
    vmlinux_xz: str | None
    kernel_config: str | None
    repro_syz: str | None
    repro_log: str | None
    crash_log: str | None
    crash_report: str | None


def http_get_bytes(url: str) -> bytes:
    if url.startswith("/"):
        url = BASE + url
    req = urllib.request.Request(url, headers=UA)
    # For small resources (HTML pages and /text?tag=... attachments).
    # Large assets are streamed via `download_stream`.
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def http_get_text(url: str) -> str:
    return http_get_bytes(url).decode("utf-8", "replace")


def html_unescape_amp(s: str) -> str:
    return s.replace("&amp;", "&")


def scrape_bug_page(extid: str) -> BugLinks:
    bug_url = f"{BASE}/bug?extid={extid}"
    html = http_get_text(bug_url)

    # /text?tag=...&x=... links
    text_links = [html_unescape_amp(x) for x in re.findall(r"(/text\?tag=[^\"\s<>]+)", html)]

    def pick_text(tag: str) -> str | None:
        for lnk in text_links:
            if f"tag={tag}" in lnk:
                return BASE + lnk
        return None

    # syzbot assets are hosted on storage.googleapis.com
    # We allow both http and https to be safe.
    asset_links = re.findall(r"https?://storage\.googleapis\.com/syzbot-assets/[^\"\s<>]+", html)

    def pick_asset(prefix: str, suffix: str) -> str | None:
        for lnk in asset_links:
            if "/" + prefix in lnk and lnk.endswith(suffix):
                return lnk
        return None

    return BugLinks(
        bug_url=bug_url,
        disk_xz=pick_asset("disk-", ".raw.xz"),
        bzimage_xz=pick_asset("bzImage-", ".xz"),
        vmlinux_xz=pick_asset("vmlinux-", ".xz"),
        kernel_config=pick_text("KernelConfig"),
        repro_syz=pick_text("ReproSyz"),
        repro_log=pick_text("ReproLog"),
        crash_log=pick_text("CrashLog"),
        crash_report=pick_text("CrashReport"),
    )


def download_stream(url: str, out_path: Path, *, force: bool, timeout: int = 600) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return

    tmp = out_path.with_suffix(out_path.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r, tmp.open("wb") as f:
        while True:
            chunk = r.read(4 * 1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(out_path)


def decompress_xz(in_path: Path, out_path: Path, *, force: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return

    # Stream decompression to avoid holding large images in memory.
    tmp = out_path.with_suffix(out_path.suffix + ".part")
    with lzma.open(in_path, "rb") as fin, tmp.open("wb") as fout:
        while True:
            chunk = fin.read(4 * 1024 * 1024)
            if not chunk:
                break
            fout.write(chunk)
    tmp.replace(out_path)


def write_text(out_path: Path, content: str, *, force: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return
    out_path.write_text(content, encoding="utf-8")


def write_run_qemu_sh(out_dir: Path, *, force: bool) -> None:
    run_sh = out_dir / "run_qemu.sh"
    if run_sh.exists() and not force:
        return

    script = """#!/usr/bin/env bash
set -euo pipefail

DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
QEMU_BIN=${QEMU_BIN:-qemu-system-x86_64}

if ! command -v "$QEMU_BIN" >/dev/null 2>&1; then
  echo "Missing $QEMU_BIN." >&2
  echo "Install (Debian/Ubuntu): sudo apt-get update && sudo apt-get install -y qemu-system-x86" >&2
  exit 1
fi

MEM=${MEM:-2048}
SMP=${SMP:-2}
HOSTFWD_PORT=${HOSTFWD_PORT:-10022}
PERSIST=${PERSIST:-0}

snapshot_args=()
if [[ "$PERSIST" != "1" ]]; then
  snapshot_args+=( -snapshot )
fi

exec "$QEMU_BIN" \
  -m "$MEM" -smp "$SMP" \
  -kernel "$DIR/bzImage" \
  -append "console=ttyS0 root=/dev/vda earlyprintk=serial net.ifnames=0" \
  -drive "file=$DIR/disk.raw,format=raw,if=virtio" \
  -net nic,model=e1000 -net "user,hostfwd=tcp::${HOSTFWD_PORT}-:22" \
  -nographic \
  "${snapshot_args[@]}"
"""

    run_sh.write_text(script, encoding="utf-8")
    try:
        os.chmod(run_sh, 0o755)
    except OSError:
        # Best-effort; not fatal in some environments.
        pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Prepare a local QEMU repro bundle from a syzbot extid.

            Example:
              ./tools/syzbot_prepare_qemu_repro.py --extid a9528028ab4ca83e8bac
            """
        ),
    )
    ap.add_argument("--extid", required=True, help="syzbot extid (from bug?extid=...)")
    ap.add_argument(
        "--out",
        default=None,
        help="output directory (default: repro/<extid>)",
    )
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    args = ap.parse_args(argv)

    out_dir = Path(args.out or f"repro/{args.extid}")
    out_dir.mkdir(parents=True, exist_ok=True)

    links = scrape_bug_page(args.extid)

    # Save metadata for debugging / provenance.
    meta = (out_dir / "meta.txt")
    meta_txt = "\n".join(
        [
            f"bug_url={links.bug_url}",
            f"disk_xz={links.disk_xz or ''}",
            f"bzimage_xz={links.bzimage_xz or ''}",
            f"vmlinux_xz={links.vmlinux_xz or ''}",
            f"kernel_config={links.kernel_config or ''}",
            f"repro_syz={links.repro_syz or ''}",
            f"repro_log={links.repro_log or ''}",
            f"crash_log={links.crash_log or ''}",
            f"crash_report={links.crash_report or ''}",
        ]
    )
    write_text(meta, meta_txt + "\n", force=args.force)

    if not links.disk_xz or not links.bzimage_xz:
        print("Bug page did not expose required assets (disk and bzImage).", file=sys.stderr)
        print(f"bug: {links.bug_url}", file=sys.stderr)
        return 2

    # Download compressed assets.
    disk_xz_path = out_dir / "disk.raw.xz"
    bz_xz_path = out_dir / "bzImage.xz"
    print(f"Downloading: {links.disk_xz}")
    download_stream(links.disk_xz, disk_xz_path, force=args.force)
    print(f"Downloading: {links.bzimage_xz}")
    download_stream(links.bzimage_xz, bz_xz_path, force=args.force)

    if links.vmlinux_xz:
        vmlinux_xz_path = out_dir / "vmlinux.xz"
        print(f"Downloading: {links.vmlinux_xz}")
        download_stream(links.vmlinux_xz, vmlinux_xz_path, force=args.force)

    # Decompress to the filenames the run script expects.
    decompress_xz(bz_xz_path, out_dir / "bzImage", force=args.force)
    decompress_xz(disk_xz_path, out_dir / "disk.raw", force=args.force)

    if (out_dir / "vmlinux.xz").exists():
        decompress_xz(out_dir / "vmlinux.xz", out_dir / "vmlinux", force=args.force)

    # Fetch text attachments.
    if links.kernel_config:
        write_text(out_dir / "kernel.config", http_get_text(links.kernel_config), force=args.force)
    if links.repro_syz:
        write_text(out_dir / "repro.syz", http_get_text(links.repro_syz), force=args.force)
    if links.repro_log:
        write_text(out_dir / "repro.log", http_get_text(links.repro_log), force=args.force)
    if links.crash_log:
        write_text(out_dir / "crash.log", http_get_text(links.crash_log), force=args.force)
    if links.crash_report:
        write_text(out_dir / "crash.report", http_get_text(links.crash_report), force=args.force)

    write_run_qemu_sh(out_dir, force=args.force)

    print(f"Prepared bundle: {out_dir}")
    print("Next:")
    print(f"  cd {out_dir}")
    print("  ./run_qemu.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
