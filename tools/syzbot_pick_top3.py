#!/usr/bin/env python3
"""Pick a small set of "good starter" syzbot issues from syzkaller.appspot.com.

Why this exists
--------------
We wanted 3 real kernel issues that:
- are in upstream (not a downstream tree)
- have a reproducer (preferably a C reproducer)
- do not require special hardware
- are not "too complex" for a first real bugfix patch

Data sources
------------
- https://syzkaller.appspot.com/upstream?json=1
  Returns a JSON list of upstream bugs with only {title, link}.
  The `link` is relative (e.g. "/bug?extid=...").

- https://syzkaller.appspot.com/bug?extid=...
  The HTML bug page includes links like:
    /text?tag=ReproC&x=...
    /text?tag=ReproSyz&x=...
    /text?tag=KernelConfig&x=...
  We scrape those links to detect whether an issue is reproducible.

Usage
-----
  ./tools/syzbot_pick_top3.py
  ./tools/syzbot_pick_top3.py --count 3 --scan-limit 400

Notes
-----
This is intentionally "dumb but transparent" scraping. It is good enough for
building a shortlist, and you can refine the keyword filters over time.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://syzkaller.appspot.com"
UA = {"User-Agent": "kernel_radar/0.1 (+local)"}


@dataclass(frozen=True)
class Candidate:
    extid: str | None
    title: str
    bug_url: str
    status: str | None
    subsystems: list[str]
    kernel_config_url: str | None
    repro_c_url: str | None
    repro_syz_url: str | None
    crash_report_url: str | None


def http_get_text(url: str) -> str:
    if url.startswith("/"):
        url = BASE + url
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def html_unescape_amp(s: str) -> str:
    # syzkaller HTML uses &amp; in hrefs; we only need to unescape that.
    return s.replace("&amp;", "&")


def scrape_bug_page(bug_url: str) -> dict[str, object]:
    html = http_get_text(bug_url)

    # Status line looks like:
    #   Status: <a ...>upstream: reported C repro on YYYY/MM/DD HH:MM</a><br>
    status = None
    m = re.search(r"Status:\s*<a[^>]*>([^<]+)</a>", html, re.I)
    if m:
        status = m.group(1).strip()

    # Subsystems block looks like:
    #   Subsystems: <span class="bug-label"><a href="/upstream/s/net">net</a></span>
    subsystems: list[str] = []
    m = re.search(r"Subsystems:\s*(.*?)<br", html, re.I | re.S)
    if m:
        block = m.group(1)
        subsystems = [
            s.strip()
            for s in re.findall(r"/upstream/s/[^\"]+\">([^<]+)</a>", block)
            if s.strip()
        ]

    # Reproducer/config/crash are linked via /text?tag=...&x=...
    text_links = [
        html_unescape_amp(x) for x in re.findall(r"(/text\?tag=[^\"\s<>]+)", html)
    ]

    def pick(tag: str) -> str | None:
        for lnk in text_links:
            if f"tag={tag}" in lnk:
                return BASE + lnk
        return None

    return {
        "status": status,
        "subsystems": subsystems,
        "kernel_config_url": pick("KernelConfig"),
        "repro_c_url": pick("ReproC"),
        "repro_syz_url": pick("ReproSyz"),
        "crash_report_url": pick("CrashReport"),
    }


def looks_hardware_specific(title: str) -> bool:
    # This is a heuristic. Tune it as needed.
    return bool(
        re.search(
            r"usb|bluetooth|wifi|iwlwifi|ath|drm|amdgpu|nouveau|sound|snd_|nvme|scsi|mmc|rtc|i2c|spi|hid",
            title,
            re.I,
        )
    )


def extract_extid(bug_url: str) -> str | None:
    try:
        u = urllib.parse.urlparse(bug_url)
        qs = urllib.parse.parse_qs(u.query)
        extids = qs.get("extid")
        if extids:
            return str(extids[0])
    except Exception:
        return None
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--scan-limit", type=int, default=400)
    ap.add_argument("--sleep", type=float, default=0.2, help="sleep between bug page fetches")
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
        exclude_re = (
            re.compile(args.exclude_title_re, re.I)
            if args.exclude_title_re
            else re.compile(
                r"usb|bluetooth|wifi|iwlwifi|ath|drm|amdgpu|nouveau|sound|snd_|nvme|scsi|mmc|rtc|i2c|spi|hid",
                re.I,
            )
        )

    include_subsystems = {s.strip().lower() for s in args.include_subsystem if s and s.strip()}
    exclude_subsystems = {s.strip().lower() for s in args.exclude_subsystem if s and s.strip()}
    include_subsystem_re = (
        re.compile(args.include_subsystem_re, re.I) if args.include_subsystem_re else None
    )
    exclude_subsystem_re = (
        re.compile(args.exclude_subsystem_re, re.I) if args.exclude_subsystem_re else None
    )

    upstream_json = http_get_text(BASE + "/upstream?json=1")
    data = json.loads(upstream_json)
    bugs = data.get("Bugs")
    if not isinstance(bugs, list):
        print("Unexpected upstream JSON schema", file=sys.stderr)
        return 2

    found: list[Candidate] = []

    for idx, bug in enumerate(bugs[: args.scan_limit]):
        title = str(bug.get("title", "")).strip()
        link = str(bug.get("link", "")).strip()
        if not title or not link:
            continue

        if include_re and not include_re.search(title):
            continue

        if exclude_re and exclude_re.search(title):
            continue

        # We only consider issues that have reproducers embedded on the bug page.
        try:
            scraped = scrape_bug_page(link)
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

        repro_c_url = scraped.get("repro_c_url")
        repro_syz_url = scraped.get("repro_syz_url")
        if not repro_c_url and not repro_syz_url:
            continue

        found.append(
            Candidate(
                extid=extract_extid(BASE + link if link.startswith("/") else link),
                title=title,
                bug_url=BASE + link if link.startswith("/") else link,
                status=scraped.get("status") if isinstance(scraped.get("status"), str) else None,
                subsystems=subsystems,
                kernel_config_url=scraped.get("kernel_config_url") if isinstance(scraped.get("kernel_config_url"), str) else None,
                repro_c_url=repro_c_url if isinstance(repro_c_url, str) else None,
                repro_syz_url=repro_syz_url if isinstance(repro_syz_url, str) else None,
                crash_report_url=scraped.get("crash_report_url") if isinstance(scraped.get("crash_report_url"), str) else None,
            )
        )

        if len(found) >= args.count:
            break

        time.sleep(args.sleep)

    for c in found:
        print(f"\n- {c.title}")
        if c.extid:
            print(f"  extid: {c.extid}")
        print(f"  bug: {c.bug_url}")
        if c.status:
            print(f"  status: {c.status}")
        if c.subsystems:
            print(f"  subsystems: {', '.join(c.subsystems)}")
        if c.kernel_config_url:
            print(f"  kernel config: {c.kernel_config_url}")
        if c.repro_c_url:
            print(f"  C repro: {c.repro_c_url}")
        if c.repro_syz_url:
            print(f"  syz repro: {c.repro_syz_url}")
        if c.crash_report_url:
            print(f"  crash report: {c.crash_report_url}")

    if not found:
        print("No candidates found; try increasing --scan-limit or relaxing filters.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
