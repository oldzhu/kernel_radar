# How to check if a kernel issue is already being worked on（简体中文）

[English](how-to-check-if-an-issue-is-already-being-worked.md)

> 说明：本简体中文版本包含中文导读 + 英文原文（便于准确对照命令/日志/代码符号）。

## 中文导读（章节列表）

- The key idea
- Workflow we used (and why)
- The scripts/commands we used (record)
- What we found for issue #1 (example outcome)

## English 原文

# How to check if a kernel issue is already being worked on

[简体中文](how-to-check-if-an-issue-is-already-being-worked.zh-CN.md)

This doc records the workflow we used to answer:

1) **Is this issue already fixed?**
2) **Is someone else already working on it (patch in flight)?**

This is important so we don’t duplicate effort and so we can pivot to:
- testing an existing patch
- helping with root-cause analysis
- picking a different issue


## The key idea

Kernel collaboration happens primarily via **public email threads** (lore, mailing lists) plus trackers like **syzbot**.

So the most reliable signals are:
- a **patch** already posted to the relevant list (often `netdev`, `linux-mm`, `linux-fsdevel`, etc.)
- maintainer replies like “applied”, “queued”, “sent to net-next”, etc.
- a **fix commit** already merged (or queued in a subsystem tree)


## Workflow we used (and why)

### Step 1 — Check syzbot status + linked thread

For syzbot issues, start from the bug page:

- Example (issue #1 we checked):
  - https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9

What to look for:
- **Status:** line
  - If you see “fixed / dup / invalid”, it’s probably resolved.
  - If it says “reported …”, it might still be in progress or might already have a patch (syzbot often lags until it retests).
- The **status link** usually points to the original report thread (often Google Groups `syzkaller-bugs`) and sometimes lore.

Why this matters:
- This tells you whether syzbot *knows* about a fix.
- It also gives you the canonical report thread to follow.


### Step 2 — Follow the lore thread links (look for [PATCH])

On many syzbot pages, there are links to lore threads (example for #1):

- https://lore.kernel.org/all/20260105093630.1976085-1-edumazet@google.com/T/

If you see a lore subject like:
- `[PATCH net] ... skb_attempt_defer_free ...`

…then the issue is already being actively worked on.

Why this matters:
- It’s common (especially in active subsystems like net) for a maintainer to quickly post a patch that references the syzbot report.


### Step 3 — Fetch the patch mail (raw mbox) and confirm it really targets the report

We confirm by fetching the raw message for the patch email from lore.

Important lore detail we discovered:
- For a specific message URL like:
  - `https://lore.kernel.org/all/<message-id>/`
- The **raw mbox** is at:
  - `https://lore.kernel.org/all/<message-id>/raw`

`...?raw=1` often returns HTML, not RFC822.

After you fetch the raw message, check for:
- `Reported-by: syzbot+<extid>@...`
- `Closes: <link to the syzbot report thread>`
- `Fixes: <commit>`

If these exist and the diff touches the area in the crash, it’s a strong sign the issue is already covered.


### Step 4 — Optional: Git-side sanity checks

Even if a patch exists, it might already be merged.

Useful quick checks in your kernel tree:

- Look at recent changes to the crash site file:
  - `git log --oneline --max-count=50 -- <path>`

- Search for commits that touch a function name:
  - `git log -p -S 'function_name' -- <path>`

- If you have a known `Fixes:` commit hash from a patch, you can see if it’s in your tree:
  - `git show <hash>`

Why this matters:
- Sometimes a fix has landed but syzbot hasn’t retested yet.


## The scripts/commands we used (record)

### A) Scrape the syzbot bug page for status + thread links

This prints:
- Title
- Status text + status link
- lore links (including patch threads if present)

```bash
python3 - <<'PY'
import urllib.request, re
from html import unescape

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
BUG='https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9'

def get(url):
  req=urllib.request.Request(url, headers=UA)
  with urllib.request.urlopen(req, timeout=30) as r:
    return r.read().decode('utf-8','replace')

html=get(BUG)
print('Bug:', BUG)
# Title
m=re.search(r'<b>(.*?)</b><br>', html, re.I|re.S)
print('Title:', unescape(m.group(1)).strip() if m else '(unknown)')
# Status line
m=re.search(r'Status:\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.I)
if m:
  print('Status:', unescape(m.group(2)).strip())
  print('Status link:', unescape(m.group(1)))

hrefs=[unescape(x) for x in re.findall(r'href="([^"]+)"', html)]
print('\nLore links:')
for h in hrefs:
  if 'lore.kernel.org' in h:
    print(' ', h)
PY
```


### B) Fetch/parse the lore patch message as raw mbox

This confirms whether a posted patch is directly tied to the syzbot report:

```bash
python3 - <<'PY'
import urllib.request, email
from email import policy

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
url='https://lore.kernel.org/all/20260105093630.1976085-1-edumazet@google.com/raw'
req=urllib.request.Request(url, headers=UA)
mbox=urllib.request.urlopen(req, timeout=30).read().decode('utf-8','replace')
lines=mbox.splitlines()
if lines and lines[0].startswith('From '):
  mbox='\n'.join(lines[1:])
msg=email.message_from_string(mbox, policy=policy.default)

print('Subject:', msg.get('Subject'))
print('From:', msg.get('From'))
print('Message-ID:', msg.get('Message-ID'))

body = msg.get_body(preferencelist=('plain',))
text = body.get_content() if body else ''

for key in ['Fixes:', 'Reported-by:', 'Closes:', 'Link:', 'Signed-off-by:']:
  hits=[l for l in text.splitlines() if l.startswith(key)]
  if hits:
    print(key, hits[0])

print('\n--- first diff header ---')
for i,l in enumerate(text.splitlines()):
  if l.startswith('diff --git'):
    for x in text.splitlines()[i:i+30]:
      print(x)
    break
PY
```


### C) Small reusable helper script

We also saved a small helper script you can rerun:
- [tools/syzbot_check_in_progress.py](../tools/syzbot_check_in_progress.py)

Example:

```bash
./tools/syzbot_check_in_progress.py 3e68572cf2286ce5ebe9
```

What it outputs:
- syzbot title/status
- status link
- lore links found on the bug page (and “patch-like” thread links)


## What we found for issue #1 (example outcome)

Issue:
- https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9

Result:
- syzbot showed it as “reported”, but the bug page linked a lore thread containing:
  - `[PATCH net] udp: call skb_orphan() before skb_attempt_defer_free()`
- The patch email contained `Reported-by` and `Closes` pointing back to the syzbot report.

Conclusion:
- The issue was already being worked on (a fix patch was already posted).
