# 上游 Linux：首个补丁工作流（邮件方式）

[English](upstream-first-patch-workflow.md)

本文记录我们通过邮件完成首个上游 Linux 内核补丁的 **手工流程**（端到端）。

写下它是为了后续能用 `kernel_radar` AI agent 自动化部分环节。

## 范围

- 目标：**上游主线**（kernel.org），标准 **邮件** 流程（不是 GitHub PR）。
- 示例补丁：`scripts/atomic/kerneldoc/try_cmpxchg` 的一个小拼写修复。
- 邮件发送：**Gmail SMTP**，从 host 以 `oldrunner999@gmail.com` 发送。

## 前置条件

- 你有 upstream Linux 的 clone（示例路径：`~/mylinux/linux`）。
- 你有可用的 `git` 身份（姓名/邮箱）。
- 你可以通过 SMTP 发送邮件。

## 0) 克隆 upstream Linux

在项目目录下：

- `cd ~/mylinux`
- `git clone https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git`

## 1) 创建主题分支

- `cd ~/mylinux/linux`
- `git checkout -b oldzhu/atomic-kerneldoc-spelling`

## 2) 做一个很小的改动

我们修复了 kerneldoc 模板中的拼写错误：

- 文件：`scripts/atomic/kerneldoc/try_cmpxchg`
- 改动：`occured` → `occurred`

编辑后确认 diff：

- `git diff`

## 3) 按内核规范提交

内核期望：

- 简短主题行，含子系统前缀（`scripts/atomic: ...`）
- 简要说明改动
- `Signed-off-by:` 行（用 `-s`）

我们决定使用 Gmail（`oldrunner999@gmail.com`）作为 From 地址发送。

设置仓库级身份（安全，不影响其他仓库）：

- `git config user.name "oldzhu"`
- `git config user.email "oldrunner999@gmail.com"`

提交：

- `git commit -s -am "scripts/atomic: fix kerneldoc spelling in try_cmpxchg"`

如需之后修正文案/作者：

- `git commit --amend --reset-author -s`

（我们使用 amend 来确保只有一条 `Signed-off-by:`，且 `checkpatch.pl` 通过。）

## 4) 运行 checkpatch

- `./scripts/checkpatch.pl -g HEAD`

目标：**0 errors, 0 warnings**。

如有问题，修复后 amend，再次运行 checkpatch。

## 5) 确定收件人（维护者 + 邮件列表）

- `./scripts/get_maintainer.pl -f scripts/atomic/kerneldoc/try_cmpxchg`

输出示例包括：

- atomic 基础设施相关维护者/评审
- `linux-kernel@vger.kernel.org`

这些将作为 `--to` / `--cc` 收件人。

## 6) 生成补丁文件

创建 `outgoing/` 并生成 `0001-...patch`：

- `mkdir -p outgoing`
- `git format-patch -1 --output-directory outgoing HEAD`

预览补丁头：

- `sed -n '1,60p' outgoing/*.patch`

## 7) 安装并配置 git-send-email（host）

我们在 **host** 侧发送（不在容器内），以便简化凭证处理。

安装工具：

- `sudo apt-get update -y`
- `sudo apt-get install -y git-email`

配置 Gmail SMTP：

- `git config --global sendemail.smtpserver smtp.gmail.com`
- `git config --global sendemail.smtpserverport 587`
- `git config --global sendemail.smtpencryption tls`
- `git config --global sendemail.smtpuser oldrunner999@gmail.com`
- `git config --global sendemail.from "oldzhu <oldrunner999@gmail.com>"`

检查配置：

- `git config --global --get-regexp '^sendemail\.'`

### Gmail App Password

Gmail SMTP 通常需要 **App Password**：

- 启用 Google 2FA
- 创建一个 App Password（例如用于 “git-send-email”）

**不要** 在聊天里粘贴 App Password。

## 8) 试运行发送（推荐）

该步骤 **不会** 发送邮件：

- `git send-email --dry-run outgoing/0001-*.patch --to will@kernel.org --cc ... --confirm=always`

用于确认收件人和邮件头是否正确。

## 9) 正式发送

我们遇到 VS Code 的 askpass 提示异常，导致密码输入不稳定。

解决办法：强制真实终端提示并绕过 askpass：

- `env -u GIT_ASKPASS -u SSH_ASKPASS GIT_TERMINAL_PROMPT=1 \
  git send-email outgoing/0001-*.patch \
    --to will@kernel.org \
    --cc peterz@infradead.org \
    --cc boqun.feng@gmail.com \
    --cc mark.rutland@arm.com \
    --cc gary@garyguo.net \
    --cc linux-kernel@vger.kernel.org \
    --confirm=always`

提示时输入：

- username: `oldrunner999@gmail.com`
- password: 你的 **Gmail App Password**

成功发送的输出会包含 `OK` 状态和 `Message-ID`。

我们首次发送的 `Message-ID` 示例：

- `<20260106040158.31461-1-oldrunner999@gmail.com>`

## 10) 确认出现在 lore

等待几分钟后在 lore 搜索：

- 按 Message-ID（URL 编码）：
  - `https://lore.kernel.org/lkml/?q=20260106040158.31461-1-oldrunner999%40gmail.com`

- 按主题关键词：
  - `https://lore.kernel.org/lkml/?q=scripts%2Fatomic%3A+fix+kerneldoc+spelling+in+try_cmpxchg`

## 11) 处理评审（v2 / threading）

若评审要求修改：

1) 修改内容
2) `git commit --amend -s`
3) 生成 v2 补丁：
   - `rm -f outgoing/*.patch`
   - `git format-patch -1 -v2 --output-directory outgoing HEAD`

4) 在同一线程发送 v2（保持上下文）：

- `git send-email --in-reply-to <MESSAGE_ID_FROM_V1> outgoing/0001-*.patch ...`

## 未来自动化的注意事项

agent 可帮助自动化/总结：

- 选择低风险候选补丁/bug
- 运行 `checkpatch.pl` 并总结失败点
- 运行 `get_maintainer.pl` 并生成发送命令
- 生成补丁并给出“可发送”清单

但：

- 未经明确人工许可，**不要** 自动发送邮件
- **不要** 在仓库中保存 SMTP 凭证
