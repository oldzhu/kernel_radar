# 2026-02-09 每日报告（各领域最新 5 条提交）

[English](2026-02-09-daily-report.md)

范围：上游 Linux（master），基于路径的领域过滤，包含 merge。

## 调度器

- [dda5df982363](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=dda5df9823630a26ed24ca9150b33a7f56ba4546) Merge tag 'sched-urgent-2026-02-07' of git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip（Linus Torvalds，2026-02-07）
- [3c7b4d1994f6](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=3c7b4d1994f63d6fa3984d7d5ad06dbaad96f167) Merge tag 'sched_ext-for-6.19-rc8-fixes' of git://git.kernel.org/pub/scm/linux/kernel/git/tj/sched_ext（Linus Torvalds，2026-02-04）
- [0eca95cba2b7](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=0eca95cba2b7bf7b7b4f2fa90734a85fcaa72782) sched_ext: Short-circuit sched_class operations on dead tasks（Tejun Heo，2026-02-04）
- [4463c7aa11a6](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=4463c7aa11a6e67169ae48c6804968960c4bffea) sched/mmcid: Optimize transitional CIDs when scheduling out（Thomas Gleixner，2026-02-02）
- [007d84287c74](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=007d84287c7466ca68a5809b616338214dc5b77b) sched/mmcid: Drop per CPU CID immediately when switching to per task mode（Thomas Gleixner，2026-02-02）

## Cgroup

- [99a2ef500906](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=99a2ef500906138ba58093b9893972a5c303c734) cgroup/dmem: avoid pool UAF（Chen Ridong，2026-02-02）
- [592a68212c56](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=592a68212c5664bcaa88f24ed80bf791282790fe) cgroup/dmem: avoid rcu warning when unregister region（Chen Ridong，2026-02-02）
- [43151f812886](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=43151f812886be1855d2cba059f9c93e4729460b) cgroup/dmem: fix NULL pointer dereference when setting max（Chen Ridong，2026-02-02）
- [84697bf55329](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=84697bf5532923f70ac99ea9784fab325c560df0) kernel: cgroup: Add LGPL-2.1 SPDX license ID to legacy_freezer.c（Tim Bird，2026-01-14）
- [a1b3421a023e](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=a1b3421a023e920b006d9a55eac334b14d115687) kernel: cgroup: Add SPDX-License-Identifier lines（Tim Bird，2026-01-14）

## 命名空间

- [cefd55bd2159](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=cefd55bd2159f427228d44864747243946296739) nsproxy: fix free_nsproxy() and simplify create_new_namespaces()（Christian Brauner，2025-11-11）
- [a657bc8a75cf](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=a657bc8a75cf40c3d0814fe6488ba4af56528f42) nstree: switch to new structures（Christian Brauner，2025-11-10）
- [1c64fb02ac46](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=1c64fb02ac46f5ca93ac9f5470f124921b4713b7) nstree: move nstree types into separate header（Christian Brauner，2025-11-10）
- [2b9a0f21fbb8](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=2b9a0f21fbb8a3b7df7faa5b7534897a86c44b98) ns: move namespace types into separate header（Christian Brauner，2025-11-10）
- [3a18f809184b](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=3a18f809184bc5a1cfad7cde5b8b026e2ff61587) ns: add active reference count（Christian Brauner，2025-10-29）

## GPU（DRM）

- [7ef92d2ecef7](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=7ef92d2ecef7486d46eda0f911dc53b873fdf567) Merge tag 'amd-drm-fixes-6.19-2026-02-05' of https://gitlab.freedesktop.org/agd5f/linux into drm-fixes（Dave Airlie，2026-02-06）
- [cb8455cbf343](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=cb8455cbf343791eea3c9fa142807a99c186b323) Merge tag 'drm-xe-fixes-2026-02-05' of https://gitlab.freedesktop.org/drm/xe/kernel into drm-fixes（Dave Airlie，2026-02-06）
- [4e3b2f0db48e](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=4e3b2f0db48ebc277855dace4b4b746f166fecb3) Merge tag 'drm-misc-fixes-2026-02-05' of https://gitlab.freedesktop.org/drm/misc/kernel into drm-fixes（Dave Airlie，2026-02-06）
- [4cb1b327135d](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=4cb1b327135dddf3d0ec2544ea36ed05ba2252bc) drm/xe/guc: Fix CFI violation in debugfs access.（Daniele Ceraolo Spurio，2026-01-29）
- [40b24d9cdd41](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=40b24d9cdd4141ef43eeaa7e57c3efc07a567473) drm/bridge: imx8mp-hdmi-pai: enable PM runtime（Shengjiu Wang，2026-01-30）

## AMD GPU（DRM）

- [6b61a54e6840](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=6b61a54e684006ca0d92d684a1d3c3a00f077d8f) drm/amdgpu: Fix double deletion of validate_list（Harish Kasiviswanathan，2026-01-09）
- [84962445cd8a](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=84962445cd8a83dc5bed4c8ad5bbb2c1cdb249a0) drm/amd/display: remove assert around dpp_base replacement（Melissa Wen，2026-01-16）
- [d25b32aa829a](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=d25b32aa829a3ed5570138e541a71fb7805faec3) drm/amd/display: extend delta clamping logic to CM3 LUT helper（Melissa Wen，2025-12-08）
- [8f959d37c1f2](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=8f959d37c1f2efec6dac55915ee82302e98101fb) drm/amd/display: fix wrong color value mapping on MCM shaper LUT（Melissa Wen，2026-01-22）
- [243b467dea17](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=243b467dea1735fed904c2e54d248a46fa417a2d) Revert "drm/amd: Check if ASPM is enabled from PCIe subsystem"（Bert Karwatzki，2026-02-01）

## NVIDIA GPU（DRM nouveau）

- [4e3b2f0db48e](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=4e3b2f0db48ebc277855dace4b4b746f166fecb3) Merge tag 'drm-misc-fixes-2026-02-05' of https://gitlab.freedesktop.org/drm/misc/kernel into drm-fixes（Dave Airlie，2026-02-06）
- [8302d0afeaec](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=8302d0afeaec0bc57d951dd085e0cffe997d4d18) nouveau/gsp: fix suspend/resume regression on r570 firmware（Dave Airlie，2026-02-03）
- [8f8a4dce6401](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=8f8a4dce64013737701d13565cf6107f42b725ea) nouveau: add a third state to the fini handler.（Dave Airlie，2026-02-03）
- [90caca3b7264](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=90caca3b7264cc3e92e347b2004fff4e386fc26e) nouveau/gsp: use rpc sequence numbers properly.（Dave Airlie，2026-02-03）
- [6c65db809796](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=6c65db809796717f0a96cf22f80405dbc1a31a4b) Revert "drm/nouveau/disp: Set drm_mode_config_funcs.atomic_(check|commit)"（John Ogness，2026-01-30）
