# 2026-01-20 — Shortlist (RCU stall / scheduler-adjacent)

We shortlisted 3 **recently reported** syzbot issues that have a repro and appear **unclaimed** by our heuristic (no linked lore `/T/` thread subject containing `[PATCH`).

This note can be regenerated/updated using:

```bash
./tools/syzbot_bug_summary.py --markdown aa5520f7faf8d5438034 f8850bc3986562f79619 0604401cc084920f6c3d
```

## Shortlist (3)

### 1) aa5520f7faf8d5438034

- Title: INFO: rcu detected stall in `inotify_add_watch`
- Bug: https://syzkaller.appspot.com/bug?extid=aa5520f7faf8d5438034
- Status: upstream: reported syz repro on 2026/01/19 19:56
- Subsystems: modules
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=323fe5bdde2384a5
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=162c2dfc580000
- CrashReport: https://syzkaller.appspot.com/text?tag=CrashReport&x=14797d9a580000
- Status thread: https://groups.google.com/d/msgid/syzkaller-bugs/696e8c68.a70a0220.34546f.04b3.GAE@google.com
- Lore thread: https://lore.kernel.org/all/696e8c68.a70a0220.34546f.04b3.GAE@google.com/T/

### 2) f8850bc3986562f79619 (selected)

- Title: INFO: rcu detected stall in `br_handle_frame (6)`
- Bug: https://syzkaller.appspot.com/bug?extid=f8850bc3986562f79619
- Status: upstream: reported C repro on 2026/01/13 18:06
- Subsystems: bridge
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=4d8792ecb6308d0f
- ReproC: https://syzkaller.appspot.com/text?tag=ReproC&x=174fb934580000
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=102d3b62580000
- CrashReport: https://syzkaller.appspot.com/text?tag=CrashReport&x=16f4f642580000
- Status thread: https://groups.google.com/d/msgid/syzkaller-bugs/696689a1.a70a0220.2cc00b.0001.GAE@google.com
- Lore threads:
  - https://lore.kernel.org/all/696de90c.a70a0220.34546f.0435.GAE@google.com/T/
  - https://lore.kernel.org/all/696689a1.a70a0220.2cc00b.0001.GAE@google.com/T/

### 3) 0604401cc084920f6c3d

- Title: INFO: rcu detected stall in `cleanup_net (8)`
- Bug: https://syzkaller.appspot.com/bug?extid=0604401cc084920f6c3d
- Status: upstream: reported C repro on 2026/01/13 16:49
- Subsystems: kernfs
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a94030c847137a18
- ReproC: https://syzkaller.appspot.com/text?tag=ReproC&x=1406b992580000
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=13f9deb4580000
- CrashReport: https://syzkaller.appspot.com/text?tag=CrashReport&x=1006b992580000
- Status thread: https://groups.google.com/d/msgid/syzkaller-bugs/6966779c.050a0220.1a12f3.09f0.GAE@google.com
- Lore thread: https://lore.kernel.org/all/6966779c.050a0220.1a12f3.09f0.GAE@google.com/T/

## Next step (working issue)

We will work on extid `f8850bc3986562f79619`.

Commands:

```bash
./tools/syzbot_prepare_qemu_repro.py --extid f8850bc3986562f79619
# then:
./repro/f8850bc3986562f79619/run_qemu.sh
```
