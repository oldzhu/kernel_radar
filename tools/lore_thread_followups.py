#!/usr/bin/env python3
"""Fetch and summarize follow-ups for a lore.kernel.org thread.

Why
---
Sometimes lore HTML search pages are blocked by bot checks, but the thread feeds
and mbox downloads are still accessible. This tool uses those stable endpoints:
- Thread Atom feed:  https://lore.kernel.org/<list>/<message-id>/t.atom
- Thread mbox.gz:    https://lore.kernel.org/<list>/<message-id>/t.mbox.gz

It prints:
- number of messages in the thread
- From/Date/Subject/Message-ID/In-Reply-To for each message

Optionally, it can also fetch individual reply bodies using:
- Raw message: https://lore.kernel.org/<list>/<message-id>/raw

Usage
-----
  ./tools/lore_thread_followups.py --list lkml --mid 20260106040158.31461-1-oldrunner999@gmail.com
  ./tools/lore_thread_followups.py --list lkml --mid <mid> --show-bodies 2

Notes
-----
- Provide the Message-ID without surrounding <>.
- If the Message-ID contains '/', it must be URL-escaped as %2F (rare).
"""

from __future__ import annotations

import argparse
import email
import gzip
import re
import urllib.parse
import urllib.request
from email import policy

UA = {"User-Agent": "kernel_radar/0.1 (+local)"}


def http_get_bytes(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def normalize_mid(mid: str) -> str:
    mid = mid.strip()
    if mid.startswith("<") and mid.endswith(">"):
        mid = mid[1:-1]
    # Ensure any '/' in Message-ID is escaped for URLs.
    return urllib.parse.quote(mid, safe="@._-+")


def parse_mboxrd_messages(mbox_text: str) -> list[email.message.EmailMessage]:
    # lore mbox.gz uses mboxrd with a "From mboxrd@z" separator.
    raw_messages: list[str] = []
    cur: list[str] = []
    for line in mbox_text.splitlines(True):
        if line.startswith("From mboxrd@z "):
            if cur:
                raw_messages.append("".join(cur))
                cur = []
            continue
        cur.append(line)
    if cur:
        raw_messages.append("".join(cur))

    parsed: list[email.message.EmailMessage] = []
    for raw in raw_messages:
        msg = email.message_from_string(raw, policy=policy.default)
        parsed.append(msg)
    return parsed


def msg_line(msg: email.message.EmailMessage, key: str) -> str:
    v = msg.get(key)
    return v if v is not None else ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True, help="lore list name (e.g. lkml, netdev, linux-mm)")
    ap.add_argument("--mid", required=True, help="Message-ID without <> (e.g. 2026...@gmail.com)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument(
        "--show-bodies",
        type=int,
        default=0,
        help="Show up to N reply bodies (excluding the first message).",
    )
    args = ap.parse_args(argv)

    mid = normalize_mid(args.mid)
    base = f"https://lore.kernel.org/{args.list}/{mid}/"
    atom_url = base + "t.atom"
    mbox_url = base + "t.mbox.gz"

    atom = http_get_bytes(atom_url, timeout=args.timeout).decode("utf-8", "replace")
    # crude entry count without XML parsing dependencies
    entry_count = len(re.findall(r"<entry\b", atom))

    print("Thread base:", base)
    print("Atom:", atom_url)
    print("Mbox:", mbox_url)
    print("Atom entries:", entry_count)

    gz = http_get_bytes(mbox_url, timeout=args.timeout)
    mbox = gzip.decompress(gz).decode("utf-8", "replace")
    msgs = parse_mboxrd_messages(mbox)
    print("Messages in thread:", len(msgs))

    for i, msg in enumerate(msgs, 1):
        print(f"\n# {i}")
        print("From:", msg_line(msg, "From"))
        print("Date:", msg_line(msg, "Date"))
        print("Subject:", msg_line(msg, "Subject"))
        print("Message-ID:", msg_line(msg, "Message-ID"))
        print("In-Reply-To:", msg_line(msg, "In-Reply-To"))

    if args.show_bodies > 0:
        shown = 0
        for msg in msgs[1:]:  # skip original
            if shown >= args.show_bodies:
                break
            mid2 = msg_line(msg, "Message-ID").strip()
            if not mid2:
                continue
            mid2_norm = normalize_mid(mid2)
            raw_url = f"https://lore.kernel.org/{args.list}/{mid2_norm}/raw"
            raw = http_get_bytes(raw_url, timeout=args.timeout).decode("utf-8", "replace")
            lines = raw.splitlines()
            if lines and lines[0].startswith("From "):
                raw = "\n".join(lines[1:])
            msg2 = email.message_from_string(raw, policy=policy.default)
            body = msg2.get_body(preferencelist=("plain",))
            text = body.get_content() if body else msg2.get_content()

            print(f"\n==== Reply body: {msg_line(msg2, 'Message-ID')} ====")
            out = []
            for l in text.splitlines():
                if not out and not l.strip():
                    continue
                out.append(l.rstrip())
                if len(out) >= 80:
                    break
            print("\n".join(out))
            shown += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
