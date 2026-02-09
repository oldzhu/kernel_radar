# Tools index（简体中文）

[English](tools-index.md)

这里是“做 X 要用哪个工具？”的入口索引。

## 会话收尾清单

在结束一次工作会话前：

- 在 `docs/` 里更新或新增一条带日期的进展记录（尝试了什么/学到什么/下一步）。
- 把临时片段整理成可复用脚本，放到 `tools/`。
- 如果工具/参数/流程有变化，更新本索引。
- 把 docs/tools 的改动以清晰、完整的提交写入 git。

长期协作规则与项目目标见 `.github/copilot-instructions.md`。

## 选择问题

- 选择可复现的入门问题（不检查 lore）：
  - `./tools/syzbot_pick_top3.py --count 3`

- 选择看起来无人认领的可复现问题（没有关联的 `[PATCH` 线程）：
  - `./tools/syzbot_pick_unclaimed.py --count 3`

- 选择最近报告且无人认领的问题：
  - `./tools/syzbot_pick_unclaimed.py --count 3 --reported-after 2026/01/01`
  - `./tools/syzbot_pick_unclaimed.py --count 3 --max-age-days 14`

- 定向筛选特定领域：
  - Subsystems：`--include-subsystem X` / `--include-subsystem-re 're'`
  - 标题关键词：`--include-title-re 're'`
  - GPU 说明：如果明确要 DRM/GPU，添加 `--no-exclude-title`

## 检查 “in progress” / fixed

- 检查单个 extid 的 lore 链接与 patch 线索：
  - `./tools/syzbot_check_in_progress.py <extid>`

## 生成跟踪记录用的摘要

- 生成一个或多个 extid 的 Markdown 摘要（可直接复制）：
  - `./tools/syzbot_bug_summary.py --markdown <extid1> <extid2> ...`

## 准备 repro

- 创建本地 QEMU repro bundle：
  - `./tools/syzbot_prepare_qemu_repro.py --extid <extid>`
  - 输出：`repro/<extid>/run_qemu.sh`

Runner 环境变量（位于 `repro/<extid>/run_qemu.sh`）：

- `ENABLE_KVM=1` 启用 KVM 加速（需要 `/dev/kvm`）。
- `CPU=host` 选择 host CPU 模型（使用 KVM 时推荐）。

网络/鲁棒性参数：

- 默认启用 `.part` 续传（支持时使用 HTTP Range）
- 重试/退避：`--retries N`
- 超时：
  - `--timeout SECONDS`（bug 页面 + 小文本附件）
  - `--asset-timeout SECONDS`（大文件：disk/bzImage/vmlinux）
- 禁用续传（每次都从头下载）：`--no-resume`

## Lore 线程跟进

- 汇总 lore 线程（follow-ups）：
  - `./tools/lore_thread_followups.py --help`

## 备注

- 如果新增或修改了工具/参数，请更新本文件，并在 `docs/` 下补一条简短的带日期记录。
