# 2026-01-19 — Progress note (network slow; scheduler picking)

## What we tried

Goal today:
- pick **3 recently reported** issues with a **repro**, that are **not fixed/dup**, and appear **unclaimed** (no linked lore thread subject containing `[PATCH`).
- focus on scheduler-adjacent symptoms (hung tasks / lockups / RCU stalls / workqueue).

## Observations

### 1) Network instability blocks the “scan many bug pages” workflow

- The picker scripts rely on per-bug HTML fetches from syzkaller.
- With slow/unstable network, runs often stall on TLS handshake / reads.
- This makes “scan-limit in the thousands” impractical interactively.

### 2) Scheduler is not a first-class syzkaller upstream subsystem label

- `https://syzkaller.appspot.com/upstream?json=1` only contains `{title, link}`.
- The upstream subsystem filter list on `https://syzkaller.appspot.com/upstream` didn’t show obvious scheduler labels.
- We found we can at least use `kernel` as a broad area (`/upstream/s/kernel`), and then rely on title keywords to narrow.

### 3) The existing “kernel scheduler-adjacent” shortlist we saw was older

When we fell back to `tools/syzbot_pick_top3.py` (ignores unclaimed/freshness constraints), it returned:

- `ed53e35a1e9dde289579` — INFO: task hung in `p9_fd_close (3)`
- `68c586d577defab7485e` — INFO: task hung in `vmci_qp_broker_detach`
- `a50479d6d26ffd27e13b` — INFO: task hung in `worker_attach_to_pool (3)`

But these are not “just reported” (reported in 2025/08–10) and at least one has a dup signal.

### 4) In-progress/fix signals check

- `tools/syzbot_check_in_progress.py ed53e35a1e9dde289579` showed a dup signal (bug page contains “closed as dup ...”).
- The other two above did not obviously show patch-like lore subjects in the first quick check output.

## Result

We did **not** reliably produce 3 “fresh + unclaimed + scheduler-area” candidates today due to network slowness.

## Next attempt (tomorrow)

Suggested low-network approach:

1) Use a smaller candidate list first (e.g. from `https://syzkaller.appspot.com/upstream/s/kernel`) to reduce scanning.
2) Apply strict recency filter in the picker:

```bash
./tools/syzbot_pick_unclaimed.py \
  --count 3 --reported-after 2026/01/01 \
  --scan-limit 200 --timeout 10 --sleep 0.05 \
  --include-subsystem kernel \
  --include-title-re 'rcu|stall|hung|soft lockup|lockup|scheduling|preempt|watchdog|workqueue|kthread'
```

If this still returns nothing, relax in this order:
- widen date window (use `--max-age-days 60`)
- drop `--include-subsystem kernel` (keep title regex)
- temporarily drop the scheduler-adjacent regex and just pick 3 fresh unclaimed issues, then choose one closer to scheduler.
