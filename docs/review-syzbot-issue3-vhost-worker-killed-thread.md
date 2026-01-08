# Review notes: syzbot issue #3 (vhost_worker_killed hung task) thread

This doc records how we reviewed the lore mail thread for **issue #3** from our previously-picked “top 3” syzbot shortlist.

- Bug (syzbot): https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac
- Lore thread (all): https://lore.kernel.org/all/695b796e.050a0220.1c9965.002a.GAE@google.com/T/


## Goal

- Understand what maintainers are discussing (root cause vs. locking design)
- Decide whether it’s already being actively worked on
- Identify a concrete, beginner-friendly contribution (analysis, repro, instrumentation, or a small patch)


## How we extracted the thread reliably

We avoided lore HTML search pages (sometimes bot-protected) and instead used the thread mbox endpoints via our helper script:

- Script: [tools/lore_thread_followups.py](../tools/lore_thread_followups.py)

Command used:

```bash
./tools/lore_thread_followups.py \
  --list all \
  --mid 695b796e.050a0220.1c9965.002a.GAE@google.com \
  --show-bodies 5
```

This prints:
- message count
- From/Date/Subject/Message-ID/In-Reply-To for each message
- bodies of up to N replies (excluding the first syzbot report)


## What the thread is about (high level)

The reported symptom is a **hung task** involving vhost thread teardown / kill path.
The stack in the syzbot report shows the vhost kernel thread blocked in:
- `vhost_worker_killed()` while trying to lock `vq->mutex` (virtqueue mutex)

The discussion focuses on whether taking `vq->mutex` in this kill/teardown path is safe.


## Message-by-message summary

The thread currently contains **5 messages total** (syzbot report + 4 human replies).

1) syzbot report
- Provides: kernel commit, config, repro link, and the hung task stack trace.
- The key signal is `vhost_worker_killed()` waiting on `vq->mutex`.

2) Michael S. Tsirkin (mst)
- Notes that taking `vq->mutex` inside a kill handler is likely a bad idea.
- Suggests using a separate lock specifically for worker assignment/teardown.

3) Hillf Danton
- Cautions against adding a new lock “blindly” without proving the root cause of the hang.

4) Michael S. Tsirkin follow-up
- Explains a broader concern: `vq->mutex` can be held around userspace-related operations.
- If a vhost thread sleeps uninterruptibly while holding it, other code taking the mutex can also become uninterruptible.
- Says this isn’t new but is more visible with newer vhost thread management.
- Does not want to add extra locking on the datapath.

5) Mike Christie
- Asks for clarification because lockdep output only shows the kill handler waiting for `vq->mutex`.
- Questions whether a userspace thread (ioctl path) is involved but not shown.
- Mentions prior locking: used `vhost_dev->mutex` then introduced `vhost_worker->mutex` to avoid ioctl flush interactions.
- Open to a patch if `vq->mutex` is confirmed to be the issue.


## Is it already being worked on?

- There is discussion, but **no obvious fix patch posted in this thread yet** (no `[PATCH]` in the subjects at the time we checked).
- That usually means it’s still in “investigation/diagnosis” stage.


## Practical contribution ideas (low-risk)

Good beginner-friendly contributions here are **evidence gathering** steps that unblock maintainers:

1) Reproduce and capture “who holds `vq->mutex`” during the hang
- Run the syz repro under a VM (see below).
- When hung-task triggers, capture stack traces of the involved tasks.
- If possible, confirm whether a userspace ioctl thread is holding `vq->mutex`.

2) Temporary instrumentation patch (for diagnosis)
- Add debug prints / tracepoints around acquisition of `vq->mutex` in vhost paths.
- Log the owner (PID/comm), and whether it goes uninterruptible while holding the lock.
- Send results to the thread (even without a final fix patch).

3) If evidence supports it, propose a small locking change
- Avoid taking `vq->mutex` in `vhost_worker_killed()` by restructuring teardown or using a dedicated lock.
- This should be driven by evidence (matches concerns raised in the thread).


## Repro environment note

syzbot provides assets (kernel image + disk image) suitable for QEMU, which lets you reproduce without building a kernel.
However, to validate a fix, you typically build your own kernel with the patch and boot it in QEMU using the same disk/repro.

