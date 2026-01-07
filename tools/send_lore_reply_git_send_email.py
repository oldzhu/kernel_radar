#!/usr/bin/env python3
"""Send a short lore.kernel.org reply using `git send-email`.

Why
---
Direct SMTP from WSL/VMs can fail due to networking/routing restrictions.
This tool instead:
1) Fetches the message you want to reply to from lore (/raw)
2) Generates a small RFC822 reply file (.eml)
3) Sends it using `git send-email --in-reply-to ...`

It also tries to avoid VS Code askpass helpers by clearing common askpass
environment variables for the subprocess.

Example (LKML)
-------------
./tools/send_lore_reply_git_send_email.py \
  --lore-list lkml \
  --reply-to-mid 20260106094433.GW3707891@noisy.programming.kicks-ass.net \
  --from-name oldzhu \
  --from-email oldrunner999@gmail.com \
  --body "Thanks, noted about generated files; I’ll include them next time." \
  --send

Notes
-----
- Message-IDs must be provided without surrounding <>.
- This assumes your `git send-email` is already configured (SMTP server,
  credentials method, etc.).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from email.utils import getaddresses, formataddr
from email.message import EmailMessage
from email import policy
import email

UA = {"User-Agent": "kernel_radar/0.1 (+local)"}


def lore_raw_url(list_name: str, mid: str) -> str:
    mid = mid.strip()
    if mid.startswith("<") and mid.endswith(">"):
        mid = mid[1:-1]
    mid = urllib.parse.quote(mid, safe="@._-+")
    return f"https://lore.kernel.org/{list_name}/{mid}/raw"


def fetch_lore_message(list_name: str, mid: str, timeout: int) -> email.message.EmailMessage:
    url = lore_raw_url(list_name, mid)
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    lines = raw.splitlines()
    if lines and lines[0].startswith("From "):
        raw = "\n".join(lines[1:])
    return email.message_from_string(raw, policy=policy.default)


def _strip_and_wrap_mid(mid: str) -> str:
    mid = (mid or "").strip()
    if not mid:
        return ""
    if mid.startswith("<") and mid.endswith(">"):
        return mid
    return f"<{mid}>"


def _dedup_addrs(pairs: list[tuple[str, str]]) -> list[str]:
    dedup: dict[str, tuple[str, str]] = {}
    for name, addr in pairs:
        addr = (addr or "").strip()
        if not addr:
            continue
        dedup.setdefault(addr.lower(), (name, addr))
    return [formataddr(dedup[k]) for k in sorted(dedup.keys())]


def _discover_list_addr(list_name: str, present_addrs: list[str]) -> str | None:
    present = {a.lower() for a in present_addrs}
    known_list_map = {
        "lkml": "linux-kernel@vger.kernel.org",
    }
    a = known_list_map.get(list_name)
    if a and a.lower() in present:
        return a

    candidate = f"{list_name}@vger.kernel.org"
    if candidate.lower() in present:
        return candidate

    for addr in present_addrs:
        al = addr.lower()
        if al.endswith("@vger.kernel.org"):
            return addr
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lore-list", required=True, help="lore list name, e.g. lkml")
    ap.add_argument("--reply-to-mid", required=True, help="Message-ID to reply to (no <>)")
    ap.add_argument("--from-name", required=True)
    ap.add_argument("--from-email", required=True)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--body", required=True, help="plain text body")
    ap.add_argument("--subject", help="override Subject (otherwise derived from replied-to email)")
    ap.add_argument("--dry-run", action="store_true", help="print composed headers, do not send")
    ap.add_argument("--out", help="write the generated .eml to this path")
    ap.add_argument("--send", action="store_true", help="run git send-email to send the reply")
    ap.add_argument("--git", default="git", help="path to git executable")
    ap.add_argument(
        "--cc-self",
        action="store_true",
        help="include your own address in Cc (useful to keep a copy)",
    )
    args = ap.parse_args(argv)

    original = fetch_lore_message(args.lore_list, args.reply_to_mid, timeout=args.timeout)

    orig_subj = original.get("Subject", "").strip()
    if args.subject:
        subject = args.subject
    else:
        subject = orig_subj if orig_subj.lower().startswith("re:") else f"Re: {orig_subj}"

    orig_mid = original.get("Message-ID", "").strip() or args.reply_to_mid
    orig_refs = original.get("References", "").strip()

    msg = EmailMessage()
    msg["From"] = f"{args.from_name} <{args.from_email}>"

    orig_from = getaddresses([original.get("From", "")])
    orig_to = getaddresses([original.get("To", "")])
    orig_cc = getaddresses([original.get("Cc", "")])

    present_addrs = [addr.strip() for _, addr in (orig_to + orig_cc) if (addr or "").strip()]
    list_addr = _discover_list_addr(args.lore_list, present_addrs)

    # For replies, we typically address the author directly and CC the list.
    to_list = _dedup_addrs(orig_from)
    msg["To"] = ", ".join(to_list) if to_list else original.get("From", "")

    cc_pairs: list[tuple[str, str]] = []
    cc_pairs.extend(orig_cc)
    cc_pairs.extend(orig_to)
    if list_addr:
        cc_pairs.append(("", list_addr))
    if args.cc_self:
        cc_pairs.append(("", args.from_email))

    # Dedup CC, but drop the primary To address(es).
    to_addrs_l = {addr.lower() for _, addr in getaddresses([msg.get("To", "")]) if addr}
    cc_list = []
    for formatted in _dedup_addrs(cc_pairs):
        _, addr = getaddresses([formatted])[0]
        if addr and addr.lower() in to_addrs_l:
            continue
        cc_list.append(formatted)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    msg["Subject"] = subject

    wrapped_mid = _strip_and_wrap_mid(orig_mid)
    if wrapped_mid:
        msg["In-Reply-To"] = wrapped_mid
        msg["References"] = (orig_refs + " " + wrapped_mid).strip() if orig_refs else wrapped_mid

    msg["Link"] = f"https://patch.msgid.link/{args.reply_to_mid}"
    msg.set_content(args.body.strip() + "\n")

    if args.dry_run:
        print("--- composed headers ---")
        for k, v in msg.items():
            print(f"{k}: {v}")
        print("--- body ---")
        print(msg.get_content())
        return 0

    out_path: Path
    if args.out:
        out_path = Path(args.out).expanduser()
    else:
        safe_mid = args.reply_to_mid.replace("/", "%2F")
        out_path = Path("outbox") / f"reply-{safe_mid}.eml"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(msg.as_string(), encoding="utf-8")

    cmd = [
        args.git,
        "send-email",
        f"--in-reply-to={args.reply_to_mid}",
    ]

    # Always pass --to/--cc explicitly.
    to_addrs = [addr for _, addr in getaddresses([msg.get("To", "")]) if addr]
    for a in to_addrs:
        cmd.append(f"--to={a}")

    cc_addrs = [addr for _, addr in getaddresses([msg.get("Cc", "")]) if addr]
    for a in cc_addrs:
        cmd.append(f"--cc={a}")

    cmd.append(str(out_path))

    if not args.send:
        print("Wrote", out_path)
        print("To send, run:")
        print(" \\\n  ".join(cmd))
        return 0

    env = os.environ.copy()
    # Avoid VS Code askpass helpers; require TTY prompting if needed.
    env.pop("GIT_ASKPASS", None)
    env.pop("SSH_ASKPASS", None)
    env.pop("ASKPASS", None)
    env["GIT_TERMINAL_PROMPT"] = "1"

    subprocess.run(cmd, check=True, env=env)
    print("Sent reply (git send-email):", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
