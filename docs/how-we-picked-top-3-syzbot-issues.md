# How we picked the “top 3” starter kernel issues (syzbot)

This doc records exactly how we selected 3 real kernel issues for a “first real bugfix patch” round.

**Goal constraints** (what we optimized for)
- **Real upstream issues** (mainline-facing, not private).
- **Reproducible**: ideally a **C reproducer**, otherwise a syz repro.
- **No special hardware** (should run in QEMU/VM).
- **Not too complex** (localized warning/OOB, clear file/line, smaller blast radius).

We used **syzbot/syzkaller upstream bug list** as the primary source because it provides:
- a public bug tracker page per issue
- attachments for reproducers (`ReproC`, `ReproSyz`)
- a syzbot-tested kernel config (`KernelConfig`)


## Data sources used

### 1) syzbot upstream list (JSON)
- URL: https://syzkaller.appspot.com/upstream?json=1
- Schema note: this endpoint is intentionally minimal; each entry is mostly:
  - `title`
  - `link` (usually relative, like `/bug?extid=...`)

So the JSON alone is **not enough** to know whether a bug has a reproducer.

### 2) Bug detail page (HTML)
- Example: https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9
- The HTML page includes links to attachments like:
  - `/text?tag=ReproC&x=...`
  - `/text?tag=ReproSyz&x=...`
  - `/text?tag=KernelConfig&x=...`
  - `/text?tag=CrashReport&x=...`

We scraped those links to decide if a bug is reproducible and “starter-friendly”.

### 3) lore.kernel.org `syzbot` list (initial exploration)
We also explored lore feeds to see if recent syzbot bug mail could be mined directly:
- Atom: https://lore.kernel.org/syzbot/new.atom

However, in the slice we looked at, a lot of entries were **CI/moderation** and some “Email from syzbot” threads were essentially empty bodies when retrieved as mbox. That’s why we pivoted to scraping syzkaller bug pages instead.


## Selection approach (high level)

1. Pull upstream bug list JSON from syzkaller.
2. For each bug, open its bug page.
3. **Keep** it only if it has a **ReproC** or **ReproSyz** attachment link.
4. Apply a simple “no special hardware” heuristic by excluding titles mentioning common hardware drivers.
5. Stop once we have 3 candidates.

This yields a shortlist suitable for the next phase: reproduce → minimize → patch → send to upstream.


## Scripts used (with explanation)

### A) Quick look at lore’s `syzbot` Atom feed
Purpose: sanity-check whether lore `syzbot` feed contains actual bug threads.

```bash
python3 - <<'PY'
import urllib.request, xml.etree.ElementTree as ET, re
UA={'User-Agent':'kernel_radar/0.1 (+local)'}

def fetch(url):
  req=urllib.request.Request(url, headers=UA)
  with urllib.request.urlopen(req, timeout=30) as r:
    return r.read().decode('utf-8','replace')

def entries(atom_xml):
  root=ET.fromstring(atom_xml)
  ns={'a':root.tag.split('}',1)[0][1:]} if root.tag.startswith('{') else {}
  es=root.findall('a:entry', ns) if ns else root.findall('entry')
  for e in es:
    t=(e.findtext('a:title',default='',namespaces=ns) if ns else e.findtext('title',''))
    l=''
    for ln in (e.findall('a:link',ns) if ns else e.findall('link')):
      if ln.attrib.get('rel','') in ('alternate',''):
        l=ln.attrib.get('href','')
        if l: break
    yield (t or '').strip(), l

a=fetch('https://lore.kernel.org/syzbot/new.atom')
count=0
for title, link in entries(a):
  if re.search(r'syzbot|syzkaller|KASAN|BUG:|WARNING:', title, re.I):
    print('-', title)
    print(' ', link)
    count += 1
    if count>=30:
      break
print('printed', count)
PY
```

Outcome: mostly CI/moderation-type threads in the sample; not a straightforward bug shortlist.


### B) Lore raw message probing
Purpose: confirm which “raw” URLs return RFC822/mbox vs HTML.

Key finding for lore:
- `.../raw` returns mbox-like content
- `...?raw=1` returns HTML (not the raw message)

Example probe:

```bash
python3 - <<'PY'
import urllib.request
base='https://lore.kernel.org/syzbot/20251229085057.5B6A8C4CEF7@smtp.kernel.org/'
for suffix in ['raw','?raw=1','?x=raw','?format=raw','?x=mbox']:
  url=base+suffix
  try:
    req=urllib.request.Request(url, headers={'User-Agent':'kernel_radar/0.1 (+local)'})
    data=urllib.request.urlopen(req, timeout=30).read(200)
    print(suffix, '->', data[:60].replace(b'\n',b'\\n'))
  except Exception as e:
    print(suffix, '-> ERR', e)
PY
```

This investigation led us to prefer **syzkaller bug pages** as the canonical source for repro/config.


### C) The actual “pick top 3” script (re-runnable)
We turned the final selection logic into a small script you can rerun later:

- Script: [tools/syzbot_pick_top3.py](../tools/syzbot_pick_top3.py)

What it does:
- fetches https://syzkaller.appspot.com/upstream?json=1
- walks bugs until it finds `ReproC`/`ReproSyz` links
- filters out obvious hardware-ish titles (USB/WiFi/BT/DRM/etc.)
- prints a shortlist with bug URL, status/subsystems, and attachment links

Run it from the repo root:

```bash
./tools/syzbot_pick_top3.py
# or:
./tools/syzbot_pick_top3.py --scan-limit 800 --count 3
```


### D) Preview a C reproducer quickly
Purpose: confirm a repro doesn’t require special hardware and is “normal syscalls”.

```bash
python3 - <<'PY'
import urllib.request
UA={'User-Agent':'kernel_radar/0.1 (+local)'}
url='https://syzkaller.appspot.com/text?tag=ReproC&x=16e6089a580000'
req=urllib.request.Request(url, headers=UA)
text=urllib.request.urlopen(req, timeout=30).read().decode('utf-8','replace')
print('\n'.join(text.splitlines()[:80]))
PY
```


## The 3 selected issues (snapshot)

This was the shortlist at the time of selection (2026-01-06):

1) WARNING in `skb_attempt_defer_free` (net)
- Bug: https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a11e0f726bfb6765
- ReproC: https://syzkaller.appspot.com/text?tag=ReproC&x=16e6089a580000
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=1545c89a580000

2) KASAN: slab-out-of-bounds Read in `strnchr` (bpf)
- Bug: https://syzkaller.appspot.com/bug?extid=2c29addf92581b410079
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a94030c847137a18
- ReproC: https://syzkaller.appspot.com/text?tag=ReproC&x=16de569a580000
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=10c82e22580000

3) INFO: task hung in `vhost_worker_killed` (workqueue/vhost-ish)
- Bug: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a94030c847137a18
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=13a67222580000


## Notes / limitations
- The “no special hardware” filter is heuristic and based on the **title**; it can be refined.
- Some issues may still require special kernel config / debugging options; the script prints the syzbot `KernelConfig` link for that reason.
- For deeper prioritization you could additionally scrape:
  - whether a bug is already fixed
  - whether there is a cause/fix bisection
  - how frequently it reproduces

But for a first real patch, **reproducer availability + clear crash site** is usually the best ROI.
