#!/usr/bin/env python3
"""Pick reproducible syzbot issues that don't appear to have a fix posted yet.

Context
-------
We want issues suitable for a first real upstream patch:
- reproducible (prefer C repro; syz repro acceptable)
- no special hardware
- *not already being worked on*, approximated as:
    "syzbot bug page does NOT link to any lore /T/ thread whose subject contains
     '[PATCH]'"

Important limitation
--------------------
This only answers "no patch thread linked from the syzbot page".
It cannot guarantee nobody is working on it privately or on another list.
Still, it's a good practical heuristic for avoiding obvious duplicates.

Data sources
------------
- https://syzkaller.appspot.com/upstream?json=1
  Minimal JSON list: [{title, link}, ...]

- https://syzkaller.appspot.com/bug?extid=...
  HTML page with attachment links:
    /text?tag=ReproC, /text?tag=ReproSyz, /text?tag=KernelConfig, /text?tag=CrashReport
  plus sometimes lore links.

- lore thread pages (if linked):
  https://lore.kernel.org/.../T/
  We fetch the thread subject from <u id=u>...</u> and treat it as "in progress"
  only if subject contains '[PATCH'.

Usage
-----
  ./tools/syzbot_pick_unclaimed.py
  ./tools/syzbot_pick_unclaimed.py --count 5 --scan-limit 2000

Output
------
Prints a shortlist with:
- bug URL
- status, subsystems
- repro/config links
- lore thread link(s) if present (usually the syzbot report thread)
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape

BASE = "https://syzkaller.appspot.com"
UA = {"User-Agent": "kernel_radar/0.1 (+local)"}

# Heuristic: avoid obvious hardware-ish bugs by title.
HARDWARE_TITLE_RE = re.compile(
    r"usb|bluetooth|wifi|iwlwifi|ath|drm|amdgpu|nouveau|sound|snd_|nvme|scsi|mmc|rtc|i2c|spi|hid",
    re.I,
)


@dataclass(frozen=True)
class Candidate:
    title: str
    bug_url: str
    extid: str | None
    status: str | None
    subsystems: list[str]
    kernel_config: str | None
    repro_c: str | None
    repro_syz: str | None
    crash_report: str | None
    status_thread: str | None
    lore_threads: list[str]


def http_get_text(url: str, timeout: int) -> str:
    if url.startswith("/"):
        url = BASE + url
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def html_unescape_amp(s: str) -> str:
    return s.replace("&amp;", "&")


def lore_thread_subject(thread_url: str, timeout: int) -> str | None:
    """Best-effort extract of a lore /T/ thread subject."""
    try:
        html = http_get_text(thread_url, timeout=timeout)
    except Exception:
        return None
    m = re.search(r"<u\s+id=u>(.*?)</u>", html, re.I | re.S)
    if not m:
        return None
    return unescape(m.group(1)).strip()


def scrape_bug_page(link: str, timeout: int) -> dict[str, object]:
    html = http_get_text(link, timeout=timeout)

    m = re.search(r"<b>(.*?)</b><br>", html, re.I | re.S)
    title = unescape(m.group(1)).strip() if m else None

    m = re.search(r"Status:\s*<a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a>", html, re.I)
    status_text = unescape(m.group(2)).strip() if m else None
    status_thread = unescape(m.group(1)) if m else None

    subsystems: list[str] = []
    m = re.search(r"Subsystems:\s*(.*?)<br", html, re.I | re.S)
    if m:
        block = m.group(1)
        subsystems = [
            s.strip()
            for s in re.findall(r"/upstream/s/[^\"]+\">([^<]+)</a>", block)
            if s.strip()
        ]

    text_links = [
        html_unescape_amp(x) for x in re.findall(r"(/text\?tag=[^\"\s<>]+)", html)
    ]

    def pick(tag: str) -> str | None:
        for lnk in text_links:
            if f"tag={tag}" in lnk:
                return BASE + lnk
        return None

    hrefs = [unescape(x) for x in re.findall(r"href=\"([^\"]+)\"", html)]
    lore_threads = [h for h in hrefs if "lore.kernel.org" in h and re.search(r"/T/\s*$", h)]

    patch_threads: list[str] = []
    for t in lore_threads[:6]:
        subj = lore_thread_subject(t, timeout=timeout)
        if subj and "[PATCH" in subj.upper():
            patch_threads.append(t)

    return {
        "title": title,
        "status": status_text,
        "status_thread": status_thread,
        "subsystems": subsystems,
        "kernel_config": pick("KernelConfig"),
        "repro_c": pick("ReproC"),
        "repro_syz": pick("ReproSyz"),
        "crash_report": pick("CrashReport"),
        "lore_threads": lore_threads,
        "patch_threads": patch_threads,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--scan-limit", type=int, default=1500)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--sleep", type=float, default=0.1)
    ap.add_argument(
        "--include-title-re",
        default=None,
        help="only consider bugs whose title matches this regex (case-insensitive)",
    )
    ap.add_argument(
        "--exclude-title-re",
        default=None,
        help=(
            "exclude bugs whose title matches this regex (case-insensitive); "
            "default is a hardware-ish filter"
        ),
    )
    ap.add_argument(
        "--no-exclude-title",
        action="store_true",
        help="do not apply the default title exclusion filter",
    )
    ap.add_argument(
        "--include-subsystem",
        action="append",
        default=[],
        help="only consider bugs whose syzbot subsystems include this (repeatable; case-insensitive)",
    )
    ap.add_argument(
        "--exclude-subsystem",
        action="append",
        default=[],
        help="exclude bugs whose syzbot subsystems include this (repeatable; case-insensitive)",
    )
    ap.add_argument(
        "--include-subsystem-re",
        default=None,
        help="only consider bugs whose syzbot subsystems match this regex (case-insensitive)",
    )
    ap.add_argument(
        "--exclude-subsystem-re",
        default=None,
        help="exclude bugs whose syzbot subsystems match this regex (case-insensitive)",
    )
    args = ap.parse_args(argv)

    include_re = re.compile(args.include_title_re, re.I) if args.include_title_re else None
    if args.no_exclude_title:
        exclude_re = None
    else:
        exclude_re = re.compile(args.exclude_title_re, re.I) if args.exclude_title_re else HARDWARE_TITLE_RE

    include_subsystems = {s.strip().lower() for s in args.include_subsystem if s and s.strip()}
    exclude_subsystems = {s.strip().lower() for s in args.exclude_subsystem if s and s.strip()}
    include_subsystem_re = (
        re.compile(args.include_subsystem_re, re.I) if args.include_subsystem_re else None
    )
    exclude_subsystem_re = (
        re.compile(args.exclude_subsystem_re, re.I) if args.exclude_subsystem_re else None
    )

    upstream_json = http_get_text(BASE + "/upstream?json=1", timeout=args.timeout)
    data = json.loads(upstream_json)
    bugs = data.get("Bugs")
    if not isinstance(bugs, list):
        raise SystemExit("Unexpected upstream JSON schema")

    picked: list[Candidate] = []
    seen_titles: set[str] = set()

    for bug in bugs[: args.scan_limit]:
        title = str(bug.get("title", "")).strip()
        link = str(bug.get("link", "")).strip()
        if not title or not link:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)

        if include_re and not include_re.search(title):
            continue

        if exclude_re and exclude_re.search(title):
            continue

        try:
            scraped = scrape_bug_page(link, timeout=args.timeout)
        except Exception:
            continue

        subsystems = list(scraped.get("subsystems") or [])
        subsystems_lc = [s.strip().lower() for s in subsystems if isinstance(s, str) and s.strip()]

        if include_subsystems and not any(s in include_subsystems for s in subsystems_lc):
            continue

        if include_subsystem_re and not any(include_subsystem_re.search(s) for s in subsystems_lc):
            continue

        if exclude_subsystems and any(s in exclude_subsystems for s in subsystems_lc):
            continue

        if exclude_subsystem_re and any(exclude_subsystem_re.search(s) for s in subsystems_lc):
            continue

        # must have repro
        if not scraped.get("repro_c") and not scraped.get("repro_syz"):
            continue

        status_text = str(scraped.get("status") or "")
        if any(x in status_text.lower() for x in ["fixed", "invalid", "dup"]):
            continue

        # exclude if any linked lore /T/ subject contains [PATCH]
        if scraped.get("patch_threads"):
            continue

        picked.append(
            Candidate(
                title=str(scraped.get("title") or title),
                bug_url=BASE + link if link.startswith("/") else link,
                extid=(
                    urllib.parse.parse_qs(urllib.parse.urlparse(BASE + link).query)
                    .get("extid", [None])[0]
                    if link.startswith("/")
                    else urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("extid", [None])[0]
                ),
                status=scraped.get("status") if isinstance(scraped.get("status"), str) else None,
                subsystems=subsystems,
                kernel_config=scraped.get("kernel_config") if isinstance(scraped.get("kernel_config"), str) else None,
                repro_c=scraped.get("repro_c") if isinstance(scraped.get("repro_c"), str) else None,
                repro_syz=scraped.get("repro_syz") if isinstance(scraped.get("repro_syz"), str) else None,
                crash_report=scraped.get("crash_report") if isinstance(scraped.get("crash_report"), str) else None,
                status_thread=scraped.get("status_thread") if isinstance(scraped.get("status_thread"), str) else None,
                lore_threads=list(scraped.get("lore_threads") or []),
            )
        )

        if len(picked) >= args.count:
            break

        time.sleep(args.sleep)

    for c in picked:
        print(f"\n- {c.title}")
        if c.extid:
            print(f"  extid: {c.extid}")
        print(f"  bug: {c.bug_url}")
        if c.status:
            print(f"  status: {c.status}")
        if c.subsystems:
            print(f"  subsystems: {', '.join(c.subsystems)}")
        if c.kernel_config:
            print(f"  KernelConfig: {c.kernel_config}")
        if c.repro_c:
            print(f"  ReproC: {c.repro_c}")
        if c.repro_syz:
            print(f"  ReproSyz: {c.repro_syz}")
        if c.crash_report:
            print(f"  CrashReport: {c.crash_report}")
        if c.status_thread:
            print(f"  status thread: {c.status_thread}")
        if c.lore_threads:
            print(f"  lore thread: {c.lore_threads[0]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
