# 如何提取并审阅 lore 线程的跟进回复

[English](how-to-review-lore-thread-followups.md)

本文记录我们如何确认你的补丁是否在 lore.kernel.org 收到跟进回复，以及如何提取回复内容。

为什么重要：

- 回复里常包含 review 反馈、“applied/queued” 状态或需要 v2 的请求。
- lore 的 HTML 搜索有时会出现 bot-check 页面，但 thread feed/mbox 下载往往仍可用。


## 最可靠的 lore 端点

给定一个 **Message-ID**（不含外层 `<>`）和一个 lore **list 名称**：

- Thread Atom feed（显示线程中的每条消息）：
  - `https://lore.kernel.org/<list>/<message-id>/t.atom`

- Thread mbox（可下载、可导入邮件客户端）：
  - `https://lore.kernel.org/<list>/<message-id>/t.mbox.gz`

- 单条 raw 消息（RFC822/mbox）：
  - `https://lore.kernel.org/<list>/<message-id>/raw`

以你的补丁为例：

- List: `lkml`
- Message-ID: `20260106040158.31461-1-oldrunner999@gmail.com`

因此：
- `t.atom`: `https://lore.kernel.org/lkml/20260106040158.31461-1-oldrunner999@gmail.com/t.atom`
- `t.mbox.gz`: `https://lore.kernel.org/lkml/20260106040158.31461-1-oldrunner999@gmail.com/t.mbox.gz`


## 我们使用的流程

### 步骤 1 — 使用 thread Atom feed 统计回复数

我们拉取 `t.atom` 并统计 `<entry>` 数量。

- 如果只有 1 个 entry，那就是你的原始消息（没有回复）。
- 如果 >1，则说明有回复/跟进。

示例脚本：

```bash
python3 - <<'PY'
import urllib.request, xml.etree.ElementTree as ET
from html import unescape

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
mid='20260106040158.31461-1-oldrunner999@gmail.com'
atom=f'https://lore.kernel.org/lkml/{mid}/t.atom'
req=urllib.request.Request(atom, headers=UA)
with urllib.request.urlopen(req, timeout=30) as r:
  data=r.read().decode('utf-8','replace')

root=ET.fromstring(data)
ns={'a':root.tag.split('}',1)[0][1:]} if root.tag.startswith('{') else {}
entries=root.findall('a:entry', ns) if ns else root.findall('entry')
print('entries', len(entries))

for e in entries:
  title=(e.findtext('a:title',default='',namespaces=ns) if ns else e.findtext('title','')).strip()
  link=''
  for ln in (e.findall('a:link',ns) if ns else e.findall('link')):
    href=ln.attrib.get('href','')
    if href:
      link=href
      break
  updated=(e.findtext('a:updated',default='',namespaces=ns) if ns else e.findtext('updated','')).strip()
  print('-', unescape(title))
  print(' ', updated)
  print(' ', link)
PY
```


### 步骤 2 — 下载 `t.mbox.gz` 并列出线程消息

我们下载并解压 mbox，然后解析每条消息：

- `From`, `Date`, `Subject`, `Message-ID`, `In-Reply-To`

这是最稳妥的方式，可确认：

- 谁回复了
- 有多少回复
- 回复的 Message-ID

示例脚本：

```bash
python3 - <<'PY'
import urllib.request, email, gzip
from email import policy

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
mid='20260106040158.31461-1-oldrunner999@gmail.com'
url=f'https://lore.kernel.org/lkml/{mid}/t.mbox.gz'
req=urllib.request.Request(url, headers=UA)
with urllib.request.urlopen(req, timeout=30) as r:
  gz=r.read()

mbox=gzip.decompress(gz).decode('utf-8','replace')

msgs=[]
cur=[]
for line in mbox.splitlines(True):
  if line.startswith('From mboxrd@z '):
    if cur:
      msgs.append(''.join(cur))
      cur=[]
    continue
  cur.append(line)
if cur:
  msgs.append(''.join(cur))

print('messages in thread', len(msgs))
for i,m in enumerate(msgs,1):
  msg=email.message_from_string(m, policy=policy.default)
  print('\n#', i)
  print('From:', msg.get('From'))
  print('Date:', msg.get('Date'))
  print('Subject:', msg.get('Subject'))
  print('Message-ID:', msg.get('Message-ID'))
  print('In-Reply-To:', msg.get('In-Reply-To'))
PY
```


### 步骤 3 — 拉取具体回复并阅读（`/raw`）

拿到回复 Message-ID 之后，我们逐一拉取 raw RFC822 内容：

- `https://lore.kernel.org/lkml/<reply-message-id>/raw`

示例脚本（打印每条回复正文的前一部分）：

```bash
python3 - <<'PY'
import urllib.request, email
from email import policy

UA={'User-Agent':'kernel_radar/0.1 (+local)'}
msgs=[
 'https://lore.kernel.org/lkml/20260106094433.GW3707891@noisy.programming.kicks-ass.net/raw',
 'https://lore.kernel.org/lkml/20260106095018.GH3708021@noisy.programming.kicks-ass.net/raw',
]
for url in msgs:
  req=urllib.request.Request(url, headers=UA)
  mbox=urllib.request.urlopen(req, timeout=30).read().decode('utf-8','replace')
  lines=mbox.splitlines()
  if lines and lines[0].startswith('From '):
    mbox='\n'.join(lines[1:])
  msg=email.message_from_string(mbox, policy=policy.default)
  body=msg.get_body(preferencelist=('plain',))
  text=body.get_content() if body else msg.get_content()

  print('\n====', msg.get('Message-ID'), '====')
  print('From:', msg.get('From'))
  print('Date:', msg.get('Date'))
  print('Subject:', msg.get('Subject'))

  out=[]
  for l in text.splitlines():
    if l.strip()=='' and not out:
      continue
    out.append(l.rstrip())
    if len(out)>=60:
      break
  print('\n'.join(out))
PY
```


## 已保存的可复用脚本

我们把上述流程保存成可复用工具：
- [tools/lore_thread_followups.py](../tools/lore_thread_followups.py)

Example:

```bash
./tools/lore_thread_followups.py --list lkml --mid 20260106040158.31461-1-oldrunner999@gmail.com
./tools/lore_thread_followups.py --list lkml --mid 20260106040158.31461-1-oldrunner999@gmail.com --show-bodies 2
```


## 我们的结果（你的补丁线程）

按照上述流程，我们发现 Peter Zijlstra 有 2 条回复。
其中一条表示他已采纳补丁并补上了生成文件的更新；另一条说明修正了一个小的多余改动。
