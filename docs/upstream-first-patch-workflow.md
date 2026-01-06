# Upstream Linux: first patch workflow (email-based)

This document captures the **manual workflow** we used to send the first upstream Linux kernel patch via email, end-to-end.

It’s written so we can later automate parts of it with the `kernel_radar` AI agent.

## Scope

- Target: **upstream mainline** (kernel.org) via the standard **email** workflow (not GitHub PRs).
- Example patch: small typo fix in `scripts/atomic/kerneldoc/try_cmpxchg`.
- Mail transport: **Gmail SMTP**, sending as `oldrunner999@gmail.com` from the host.

## Preconditions

- You have a clone of upstream Linux (example path used here): `~/mylinux/linux`
- You have a working `git` identity (name/email).
- You can send email via SMTP.

## 0) Clone upstream Linux

From your projects directory:

- `cd ~/mylinux`
- `git clone https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git`

## 1) Create a topic branch

- `cd ~/mylinux/linux`
- `git checkout -b oldzhu/atomic-kerneldoc-spelling`

## 2) Make a tiny change

We fixed a typo in a kerneldoc template:

- File: `scripts/atomic/kerneldoc/try_cmpxchg`
- Change: `occured` → `occurred`

Edit the file, then confirm the diff:

- `git diff`

## 3) Commit with kernel conventions

Kernel expectations:
- A short subject line with subsystem prefix (`scripts/atomic: ...`)
- A brief body explaining the change
- A `Signed-off-by:` line (use `-s`)

We also decided to send using Gmail (`oldrunner999@gmail.com`) as the From address.

Set per-repo identity (safe; doesn’t affect other repos):

- `git config user.name "oldzhu"`
- `git config user.email "oldrunner999@gmail.com"`

Commit:

- `git commit -s -am "scripts/atomic: fix kerneldoc spelling in try_cmpxchg"`

If you need to fix the message/body or author later:

- `git commit --amend --reset-author -s`

(We used amend to ensure there was exactly one `Signed-off-by:` line for the Gmail address and that `checkpatch.pl` was clean.)

## 4) Run checkpatch

- `./scripts/checkpatch.pl -g HEAD`

Goal: ideally **0 errors, 0 warnings**.

If there are issues, fix them and amend, then re-run checkpatch.

## 5) Determine recipients (maintainers + lists)

- `./scripts/get_maintainer.pl -f scripts/atomic/kerneldoc/try_cmpxchg`

Example output included:
- maintainers/reviewers for atomic infrastructure
- `linux-kernel@vger.kernel.org`

These become your `--to` / `--cc` recipients.

## 6) Generate the patch file

Create an `outgoing/` folder and generate a `0001-...patch` file:

- `mkdir -p outgoing`
- `git format-patch -1 --output-directory outgoing HEAD`

Preview the patch header:

- `sed -n '1,60p' outgoing/*.patch`

## 7) Install and configure git-send-email (host)

We send from the **host** (not inside the container) to keep credentials simpler.

Install the tool:

- `sudo apt-get update -y`
- `sudo apt-get install -y git-email`

Configure Gmail SMTP:

- `git config --global sendemail.smtpserver smtp.gmail.com`
- `git config --global sendemail.smtpserverport 587`
- `git config --global sendemail.smtpencryption tls`
- `git config --global sendemail.smtpuser oldrunner999@gmail.com`
- `git config --global sendemail.from "oldzhu <oldrunner999@gmail.com>"`

Inspect the config:

- `git config --global --get-regexp '^sendemail\.'`

### Gmail App Password

Gmail SMTP generally requires an **App Password**:
- enable Google 2FA
- create an App Password for something like “git-send-email”

Do **not** paste the App Password into chat.

## 8) Dry-run send (recommended)

This does **not** send anything:

- `git send-email --dry-run outgoing/0001-*.patch --to will@kernel.org --cc ... --confirm=always`

Use this to verify recipients and headers.

## 9) Send for real

We hit a VS Code askpass issue where the password prompt didn’t behave well.

The fix was to force a real terminal prompt and bypass askpass:

- `env -u GIT_ASKPASS -u SSH_ASKPASS GIT_TERMINAL_PROMPT=1 \
  git send-email outgoing/0001-*.patch \
    --to will@kernel.org \
    --cc peterz@infradead.org \
    --cc boqun.feng@gmail.com \
    --cc mark.rutland@arm.com \
    --cc gary@garyguo.net \
    --cc linux-kernel@vger.kernel.org \
    --confirm=always`

When prompted:
- username: `oldrunner999@gmail.com`
- password: your **Gmail App Password**

Successful send output includes an `OK` status and a `Message-ID`.

Example `Message-ID` from our first send:
- `<20260106040158.31461-1-oldrunner999@gmail.com>`

## 10) Confirm it appears on lore

Wait a few minutes, then search lore:

- By Message-ID (URL-encoded):
  - `https://lore.kernel.org/lkml/?q=20260106040158.31461-1-oldrunner999%40gmail.com`

- By subject keywords:
  - `https://lore.kernel.org/lkml/?q=scripts%2Fatomic%3A+fix+kerneldoc+spelling+in+try_cmpxchg`

## 11) Handling review (v2 / threading)

If reviewers request changes:

1) Make the change
2) `git commit --amend -s`
3) Regenerate a v2 patch:
- `rm -f outgoing/*.patch`
- `git format-patch -1 -v2 --output-directory outgoing HEAD`

4) Send v2 in the same thread (keep continuity):
- `git send-email --in-reply-to <MESSAGE_ID_FROM_V1> outgoing/0001-*.patch ...`

## Notes for future automation

An agent can help automate/summarize:
- pick low-risk candidate patches/bugs
- run `checkpatch.pl` and summarize failures
- run `get_maintainer.pl` and build a send command
- generate the patch and a “ready to send” checklist

But:
- never auto-send email without explicit human approval
- never store SMTP credentials in repo
