# How we listed “unclaimed” syzbot issues (no patch in flight)

This doc records the workflow and scripts used when we wanted to pick an issue that:
- is reproducible (preferably has a C reproducer)
- likely does not require special hardware
- **does not already have a fix patch posted** (to avoid duplicating effort)


## What “unclaimed” means (our heuristic)

Kernel work is coordinated over public email, but there is no perfect “lock”.
So we use a practical, observable heuristic:

> Treat a syzbot issue as **in progress** only if its syzbot bug page links to a lore thread (`.../T/`) whose subject contains `[PATCH`.

If the linked lore thread subject is just `[syzbot] ...`, that’s a report thread, not a posted fix.

Limitations:
- Someone could be working on it privately or on a different list without syzbot linking it yet.
- A fix might already be in a subsystem maintainer tree but not in mainline.

Still, this heuristic avoids the most common duplication: “a fix patch already posted to the public list”.


## Data sources

- syzbot upstream list (minimal JSON):
  - https://syzkaller.appspot.com/upstream?json=1

- per-bug HTML page:
  - `https://syzkaller.appspot.com/bug?extid=...`

- lore thread pages for linked threads:
  - `https://lore.kernel.org/.../T/`


## New script added

We saved the selection logic into a runnable tool:

- [tools/syzbot_pick_unclaimed.py](../tools/syzbot_pick_unclaimed.py)

What it does:
1) Fetch upstream list JSON (`/upstream?json=1`).
2) For each bug, fetch its bug page HTML.
3) Keep only bugs that have `ReproC` or `ReproSyz` links.
4) Filter out obvious hardware-ish titles (USB/WiFi/BT/DRM/etc.).
5) Follow any lore `.../T/` links and extract the subject from `<u id=u>...</u>`.
6) Exclude bugs where any linked thread subject contains `[PATCH`.

Run examples:

```bash
./tools/syzbot_pick_unclaimed.py
./tools/syzbot_pick_unclaimed.py --count 5 --scan-limit 2000
```


## Relationship to existing scripts

- [tools/syzbot_check_in_progress.py](../tools/syzbot_check_in_progress.py)
  - Answers: “is this one issue already being worked on?”
  - We fixed it to only treat a thread as patch-like if the lore subject contains `[PATCH`.

- [tools/syzbot_pick_top3.py](../tools/syzbot_pick_top3.py)
  - The earlier “pick 3 good starter issues” script.
  - It does not try to determine “unclaimed”; it only looks for reproducibility + avoids hardware-ish titles.


## Notes about speed/reliability

- The syzbot JSON list is minimal, so we must scrape HTML pages.
- That means many HTTP requests. The script uses timeouts and small sleeps.
- If you see 0 results, try increasing `--scan-limit` or relaxing the hardware-title filter.
