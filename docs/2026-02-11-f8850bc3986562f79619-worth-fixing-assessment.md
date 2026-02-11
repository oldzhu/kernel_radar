# 2026-02-11 — f8850bc3986562f79619: worth-fixing assessment

[简体中文](2026-02-11-f8850bc3986562f79619-worth-fixing-assessment.zh-CN.md)

## Question

Is the issue worth fixing when considering cost and impact? If yes, proceed to test on latest upstream kernel.

## Impact (why it matters)

- The symptom is RCU stalls / softlockups triggered by TAPRIO schedule handling. This is a system-wide liveness failure, not a benign bug.
- The reproducer is automated (syzbot), so the trigger is reachable via netlink inputs and can be used as a robustness/DoS vector.
- The stack traces point into TAPRIO + hrtimer logic, which is real-time scheduling territory with user-facing impact.

## Cost / risk (why it might not be worth it)

- Fixing scheduling logic can be risky for real-time users; small timing changes can have subtle effects.
- Some fixes (e.g., clamping a minimum interval) may be seen as behavioral changes and require justification.
- The issue may be narrow in scope (software mode + tiny intervals), which is good for a targeted fix but still needs careful validation.

## Net assessment

The issue is worth fixing if we keep the mitigation low-risk and tightly scoped (e.g., validate/guard pathological inputs or bound catch-up behavior). The liveness impact is serious enough to justify it.

## Next step

Proceed to rebuild and repro on the latest upstream kernel:

- Kernel tree: `~/mylinux/linux`
- Config: syzbot `kernel.config`

If it still reproduces, pick a fix strategy from the three options.
