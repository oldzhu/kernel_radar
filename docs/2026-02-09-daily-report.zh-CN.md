# 2026-02-09 每日报告（各领域最新 5 条提交）

[English](2026-02-09-daily-report.md)

范围：上游 Linux（当前分支），基于路径的领域过滤。

## 调度器

- dda5df982363 Merge tag 'sched-urgent-2026-02-07' of git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip（Linus Torvalds，2026-02-07）
- 3c7b4d1994f6 Merge tag 'sched_ext-for-6.19-rc8-fixes' of git://git.kernel.org/pub/scm/linux/kernel/git/tj/sched_ext（Linus Torvalds，2026-02-04）
- 0eca95cba2b7 sched_ext: Short-circuit sched_class operations on dead tasks（Tejun Heo，2026-02-04）
- 4463c7aa11a6 sched/mmcid: Optimize transitional CIDs when scheduling out（Thomas Gleixner，2026-02-02）
- 007d84287c74 sched/mmcid: Drop per CPU CID immediately when switching to per task mode（Thomas Gleixner，2026-02-02）

## Cgroup

- 99a2ef500906 cgroup/dmem: avoid pool UAF（Chen Ridong，2026-02-02）
- 592a68212c56 cgroup/dmem: avoid rcu warning when unregister region（Chen Ridong，2026-02-02）
- 43151f812886 cgroup/dmem: fix NULL pointer dereference when setting max（Chen Ridong，2026-02-02）
- 84697bf55329 kernel: cgroup: Add LGPL-2.1 SPDX license ID to legacy_freezer.c（Tim Bird，2026-01-14）
- a1b3421a023e kernel: cgroup: Add SPDX-License-Identifier lines（Tim Bird，2026-01-14）

## 命名空间

- cefd55bd2159 nsproxy: fix free_nsproxy() and simplify create_new_namespaces()（Christian Brauner，2025-11-11）
- a657bc8a75cf nstree: switch to new structures（Christian Brauner，2025-11-10）
- 1c64fb02ac46 nstree: move nstree types into separate header（Christian Brauner，2025-11-10）
- 2b9a0f21fbb8 ns: move namespace types into separate header（Christian Brauner，2025-11-10）
- 3a18f809184b ns: add active reference count（Christian Brauner，2025-10-29）

## GPU（DRM）

- 7ef92d2ecef7 Merge tag 'amd-drm-fixes-6.19-2026-02-05' of https://gitlab.freedesktop.org/agd5f/linux into drm-fixes（Dave Airlie，2026-02-06）
- cb8455cbf343 Merge tag 'drm-xe-fixes-2026-02-05' of https://gitlab.freedesktop.org/drm/xe/kernel into drm-fixes（Dave Airlie，2026-02-06）
- 4e3b2f0db48e Merge tag 'drm-misc-fixes-2026-02-05' of https://gitlab.freedesktop.org/drm/misc/kernel into drm-fixes（Dave Airlie，2026-02-06）
- 4cb1b327135d drm/xe/guc: Fix CFI violation in debugfs access.（Daniele Ceraolo Spurio，2026-01-29）
- 40b24d9cdd41 drm/bridge: imx8mp-hdmi-pai: enable PM runtime（Shengjiu Wang，2026-01-30）

## AMD GPU（DRM）

- 6b61a54e6840 drm/amdgpu: Fix double deletion of validate_list（Harish Kasiviswanathan，2026-01-09）
- 84962445cd8a drm/amd/display: remove assert around dpp_base replacement（Melissa Wen，2026-01-16）
- d25b32aa829a drm/amd/display: extend delta clamping logic to CM3 LUT helper（Melissa Wen，2025-12-08）
- 8f959d37c1f2 drm/amd/display: fix wrong color value mapping on MCM shaper LUT（Melissa Wen，2026-01-22）
- 243b467dea17 Revert "drm/amd: Check if ASPM is enabled from PCIe subsystem"（Bert Karwatzki，2026-02-01）

## NVIDIA GPU（DRM nouveau）

- 4e3b2f0db48e Merge tag 'drm-misc-fixes-2026-02-05' of https://gitlab.freedesktop.org/drm/misc/kernel into drm-fixes（Dave Airlie，2026-02-06）
- 8302d0afeaec nouveau/gsp: fix suspend/resume regression on r570 firmware（Dave Airlie，2026-02-03）
- 8f8a4dce6401 nouveau: add a third state to the fini handler.（Dave Airlie，2026-02-03）
- 90caca3b7264 nouveau/gsp: use rpc sequence numbers properly.（Dave Airlie，2026-02-03）
- 6c65db809796 Revert "drm/nouveau/disp: Set drm_mode_config_funcs.atomic_(check|commit)"（John Ogness，2026-01-30）
