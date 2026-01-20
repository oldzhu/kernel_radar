#!/usr/bin/env python3
"""Fetch and print a compact summary for syzbot extids.

This is a small, reusable helper for turning a list of extids into
copy/paste-able tracking notes.

It scrapes the syzkaller bug page:
  https://syzkaller.appspot.com/bug?extid=<extid>

and extracts:
- title
- status text + status link
- subsystems
- KernelConfig / ReproC / ReproSyz / CrashReport links
- lore.kernel.org thread links ending in /T/

Usage examples:
  ./tools/syzbot_bug_summary.py f8850bc3986562f79619
  ./tools/syzbot_bug_summary.py --markdown aa... f8... 06...
  ./tools/syzbot_bug_summary.py --file extids.txt --markdown
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape

BASE = "https://syzkaller.appspot.com"
UA = {"User-Agent": "kernel_radar/0.1 (+local)"}


@dataclass(frozen=True)
class BugSummary:
    extid: str
    bug_url: str
    title: str | None
    status: str | None
    status_thread: str | None
    subsystems: list[str]
    kernel_config: str | None
    repro_c: str | None
    repro_syz: str | None
    crash_report: str | None
    lore_threads: list[str]


def http_get_text(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def html_unescape_amp(s: str) -> str:
    return s.replace("&amp;", "&")


def scrape_bug(extid: str, timeout: int) -> BugSummary:
    bug_url = f"{BASE}/bug?extid={urllib.parse.quote(extid)}"
    html = http_get_text(bug_url, timeout=timeout)

    m = re.search(r"<b>(.*?)</b><br>", html, re.I | re.S)
    title = unescape(m.group(1)).strip() if m else None

    m = re.search(r"Status:\s*<a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a>", html, re.I)
    status_thread = unescape(m.group(1)) if m else None
    status = unescape(m.group(2)).strip() if m else None

    subsystems: list[str] = []
    m = re.search(r"Subsystems:\s*(.*?)<br", html, re.I | re.S)
    if m:
        block = m.group(1)
        subsystems = [
            s.strip()
            for s in re.findall(r"/upstream/s/[^\"]+\">([^<]+)</a>", block)
            if s.strip()
        ]

    text_links = [html_unescape_amp(x) for x in re.findall(r"(/text\?tag=[^\"\s<>]+)", html)]

    def pick(tag: str) -> str | None:
        for lnk in text_links:
            if f"tag={tag}" in lnk:
                return BASE + lnk
        return None

    hrefs = [unescape(x) for x in re.findall(r'href="([^"]+)"', html)]
    lore_threads = [h for h in hrefs if "lore.kernel.org" in h and re.search(r"/T/\s*$", h)]

    return BugSummary(
        extid=extid,
        bug_url=bug_url,
        title=title,
        status=status,
        status_thread=status_thread,
        subsystems=subsystems,
        kernel_config=pick("KernelConfig"),
        repro_c=pick("ReproC"),
        repro_syz=pick("ReproSyz"),
        crash_report=pick("CrashReport"),
        lore_threads=lore_threads,
    )


def read_extids_from_file(path: str) -> list[str]:
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out


def print_text(b: BugSummary) -> None:
    print(f"EXTID {b.extid}")
    if b.title:
        print("TITLE", b.title)
    if b.status:
        print("STATUS", b.status)
    if b.subsystems:
        print("SUBSYSTEMS", ", ".join(b.subsystems))
    print("BUG", b.bug_url)
    if b.status_thread:
        print("STATUS_THREAD", b.status_thread)
    if b.lore_threads:
        print("LORE", b.lore_threads[0])
        for i, t in enumerate(b.lore_threads[1:3], start=2):
            print(f"LORE{i}", t)
    for k, v in (
        ("KERNELCONFIG", b.kernel_config),
        ("REPROC", b.repro_c),
        ("REPROSYZ", b.repro_syz),
        ("CRASHREPORT", b.crash_report),
    ):
        if v:
            print(k, v)


def print_markdown(b: BugSummary) -> None:
    title = b.title or "(unknown title)"
    print(f"### {b.extid}")
    print("")
    print(f"- Title: {title}")
    print(f"- Bug: {b.bug_url}")
    if b.status:
        print(f"- Status: {b.status}")
    if b.subsystems:
        print(f"- Subsystems: {', '.join(b.subsystems)}")
    if b.kernel_config:
        print(f"- KernelConfig: {b.kernel_config}")
    if b.repro_c:
        print(f"- ReproC: {b.repro_c}")
    if b.repro_syz:
        print(f"- ReproSyz: {b.repro_syz}")
    if b.crash_report:
        print(f"- CrashReport: {b.crash_report}")
    if b.status_thread:
        print(f"- Status thread: {b.status_thread}")
    if b.lore_threads:
        print(f"- Lore thread: {b.lore_threads[0]}")
        for t in b.lore_threads[1:3]:
            print(f"- Lore thread: {t}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("extid", nargs="*", help="syzbot extid(s)")
    ap.add_argument("--file", help="read extids from file (one per line; # comments ok)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--markdown", action="store_true", help="print in Markdown format")
    args = ap.parse_args(argv)

    extids: list[str] = []
    if args.file:
        extids.extend(read_extids_from_file(args.file))
    extids.extend(args.extid)

    extids = [e.strip() for e in extids if e and e.strip()]
    if not extids:
        ap.error("need extid(s) or --file")

    for i, extid in enumerate(extids):
        if i:
            print("\n---\n") if args.markdown else print("---")
        b = scrape_bug(extid, timeout=args.timeout)
        if args.markdown:
            print_markdown(b)
        else:
            print_text(b)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
