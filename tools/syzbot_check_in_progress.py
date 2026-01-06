#!/usr/bin/env python3
"""Check whether a syzbot issue already has an upstream patch in flight.

This script is meant to answer two questions quickly:
1) Is the issue already fixed / has a fix commit?
2) Is someone already working on it (patch posted / discussion thread)?

It does this by scraping the syzkaller bug page:
  https://syzkaller.appspot.com/bug?extid=<extid>

Signals we extract:
- Status line text
- Status link (often to syzkaller-bugs Google Groups msgid)
- lore.kernel.org thread links (if present)
- Any lore mail links that look like patches

Notes:
- This is intentionally heuristic and "best effort"; kernel work is coordinated
  over email, so the authoritative answer is always in the mail threads.

Usage:
  ./tools/syzbot_check_in_progress.py 3e68572cf2286ce5ebe9
  ./tools/syzbot_check_in_progress.py --bug-url "https://syzkaller.appspot.com/bug?extid=..."
"""

from __future__ import annotations

import argparse
import re
import urllib.parse
import urllib.request
from html import unescape

BASE = "https://syzkaller.appspot.com"
UA = {"User-Agent": "kernel_radar/0.1 (+local)"}


def http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("extid", nargs="?", help="syzbot extid (e.g. 3e68572c...)")
    ap.add_argument("--bug-url", help="full bug URL (overrides extid)")
    args = ap.parse_args()

    if args.bug_url:
        bug_url = args.bug_url
    else:
        if not args.extid:
            ap.error("need extid or --bug-url")
        bug_url = f"{BASE}/bug?extid={urllib.parse.quote(args.extid)}"

    html = http_get_text(bug_url)

    title = None
    m = re.search(r"<b>(.*?)</b><br>", html, re.I | re.S)
    if m:
        title = unescape(m.group(1)).strip()

    status_text = None
    status_link = None
    m = re.search(r"Status:\s*<a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a>", html, re.I)
    if m:
        status_link = unescape(m.group(1))
        status_text = unescape(m.group(2)).strip()

    print("Bug:", bug_url)
    if title:
        print("Title:", title)
    if status_text:
        print("Status:", status_text)
    if status_link:
        print("Status link:", status_link)

    # Extract lore links. syzkaller sometimes links directly to lore threads.
    hrefs = [unescape(x) for x in re.findall(r"href=\"([^\"]+)\"", html)]

    lore_links = []
    for h in hrefs:
        if "lore.kernel.org" in h:
            if h not in lore_links:
                lore_links.append(h)

    patch_like = []
    for h in lore_links:
        # Heuristic: /T/ thread pages with subjects including [PATCH]
        if re.search(r"/T/\s*$", h):
            patch_like.append(h)

    if lore_links:
        print("\nLore links:")
        for h in lore_links[:30]:
            print(" ", h)

    # Quick hint: if syzkaller already shows patch-like links, this is usually "in progress".
    if patch_like:
        print("\nPatch-like thread links (likely someone is already working on it):")
        for h in patch_like[:30]:
            print(" ", h)

    # Detect explicit "fixed" signals on page (not always present).
    fix_signals = []
    for kw in ["upstream: fixed", "fixed:", "Fix commit", "Fixing commit", "Patched", "Resolved", "dup"]:
        if kw.lower() in html.lower():
            fix_signals.append(kw)

    if fix_signals:
        print("\nFix-ish signals found on bug page:")
        print(" ", ", ".join(fix_signals))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
