# 如何判断一个内核问题是否已有人在处理

[English](how-to-check-if-an-issue-is-already-being-worked.md)

本文记录我们用于回答以下问题的工作流：

1) **这个问题是否已修复？**
2) **是否已有他人在推进（补丁在路上）？**

这一步很关键，可以避免重复劳动，并帮助我们尽快转向：

- 测试已有补丁
- 协助根因分析
- 改选其他问题


## 核心思路

内核协作主要通过 **公开邮件线程**（lore、邮件列表）以及 **syzbot** 等跟踪器完成。

因此，最可靠的信号包括：

- 已经向相关列表提交了 **补丁**（例如 `netdev`、`linux-mm`、`linux-fsdevel` 等）
- 维护者回复 “applied”、“queued”、“sent to net-next”等
- **修复提交** 已经合并（或在子系统维护者树中排队）


## 我们使用的流程（及原因）

### 步骤 1 — 查看 syzbot 状态与关联线程

对于 syzbot 问题，先从 bug 页面开始：

- 例子（我们检查的 issue #1）：
  - https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9

关注点：

- **Status：** 行
  - 如果看到 “fixed / dup / invalid”，通常说明已解决。
  - 如果是 “reported …”，可能还在推进，也可能已有补丁（syzbot 往往需要重新测试后才更新状态）。
- **status 链接** 通常指向原始报告线程（多为 Google Groups 的 `syzkaller-bugs`），有时也包含 lore 链接。

为什么重要：

- 这能判断 syzbot 是否 *知道* 有修复。
- 也能定位到规范的报告线程，方便后续跟进。


### 步骤 2 — 跟进 lore 线程链接（寻找 [PATCH]）

很多 syzbot 页面包含 lore 线程链接（以 #1 为例）：

- https://lore.kernel.org/all/20260105093630.1976085-1-edumazet@google.com/T/

如果看到类似的 lore 主题：
- `[PATCH net] ... skb_attempt_defer_free ...`

…那么说明该问题已有人在积极推进。

为什么重要：

- 在 net 等活跃子系统中，维护者很常见会快速发布引用 syzbot 报告的补丁。


### 步骤 3 — 拉取补丁邮件（raw mbox）并确认确实针对该报告

我们通过从 lore 拉取补丁邮件的 raw 消息来确认。

我们发现的 lore 细节：

- 对于某个消息 URL，例如：
  - `https://lore.kernel.org/all/<message-id>/`
- **raw mbox** 位于：
  - `https://lore.kernel.org/all/<message-id>/raw`

`...?raw=1` 往往返回 HTML，而不是 RFC822。

拉到 raw 消息后，检查是否包含：

- `Reported-by: syzbot+<extid>@...`
- `Closes: <link to the syzbot report thread>`
- `Fixes: <commit>`

如果这些标记存在且 diff 触及崩溃区域，基本可以确认该问题已被覆盖。


### 步骤 4 — 可选：Git 侧的健全性检查

即便补丁存在，也可能已经合并。

在你的内核树里可以快速检查：

- 查看崩溃文件的近期变更：
  - `git log --oneline --max-count=50 -- <path>`

- 搜索触及某个函数名的提交：
  - `git log -p -S 'function_name' -- <path>`

- 如果你已经知道补丁里有 `Fixes:` 的 commit hash，可检查它是否在你的树里：
  - `git show <hash>`

为什么重要：

- 有时修复已经落地，但 syzbot 还未重新测试。


## 我们使用的脚本/命令（记录）

### A) 抓取 syzbot bug 页面中的状态与线程链接

它会输出：

- Title
- Status 文本 + status 链接
- lore 链接（若存在 patch 线程也会显示）

```bash
python3 - <<'PY'
import urllib.request, re
from html import unescape

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
BUG='https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9'

def get(url):
  req=urllib.request.Request(url, headers=UA)
  with urllib.request.urlopen(req, timeout=30) as r:
    return r.read().decode('utf-8','replace')

html=get(BUG)
print('Bug:', BUG)
# Title
m=re.search(r'<b>(.*?)</b><br>', html, re.I|re.S)
print('Title:', unescape(m.group(1)).strip() if m else '(unknown)')
# Status line
m=re.search(r'Status:\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.I)
if m:
  print('Status:', unescape(m.group(2)).strip())
  print('Status link:', unescape(m.group(1)))

hrefs=[unescape(x) for x in re.findall(r'href="([^"]+)"', html)]
print('\nLore links:')
for h in hrefs:
  if 'lore.kernel.org' in h:
    print(' ', h)
PY
```


### B) 以 raw mbox 方式拉取/解析 lore 补丁邮件

用于确认已发布补丁是否直接关联该 syzbot 报告：

```bash
python3 - <<'PY'
import urllib.request, email
from email import policy

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
url='https://lore.kernel.org/all/20260105093630.1976085-1-edumazet@google.com/raw'
req=urllib.request.Request(url, headers=UA)
mbox=urllib.request.urlopen(req, timeout=30).read().decode('utf-8','replace')
lines=mbox.splitlines()
if lines and lines[0].startswith('From '):
  mbox='\n'.join(lines[1:])
msg=email.message_from_string(mbox, policy=policy.default)

print('Subject:', msg.get('Subject'))
print('From:', msg.get('From'))
print('Message-ID:', msg.get('Message-ID'))

body = msg.get_body(preferencelist=('plain',))
text = body.get_content() if body else ''

for key in ['Fixes:', 'Reported-by:', 'Closes:', 'Link:', 'Signed-off-by:']:
  hits=[l for l in text.splitlines() if l.startswith(key)]
  if hits:
    print(key, hits[0])

print('\n--- first diff header ---')
for i,l in enumerate(text.splitlines()):
  if l.startswith('diff --git'):
    for x in text.splitlines()[i:i+30]:
      print(x)
    break
PY
```


### C) 小型可复用辅助脚本

我们也保存了一个可复用的小脚本：
- [tools/syzbot_check_in_progress.py](../tools/syzbot_check_in_progress.py)

Example:

```bash
./tools/syzbot_check_in_progress.py 3e68572cf2286ce5ebe9
```

输出内容：

- syzbot 的 title/status
- status link
- bug 页面上的 lore 链接（以及被识别为“类似补丁”的线程链接）


## issue #1 的结果示例

Issue:
- https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9

结果：

- syzbot 显示为 “reported”，但 bug 页面链接到了一个包含以下主题的 lore 线程：
  - `[PATCH net] udp: call skb_orphan() before skb_attempt_defer_free()`
- 补丁邮件包含 `Reported-by` 与 `Closes`，明确指向该 syzbot 报告。

结论：

- 该问题已经有人在推进（修复补丁已发布）。
