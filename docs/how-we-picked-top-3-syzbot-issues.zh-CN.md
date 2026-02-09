# 我们如何挑选 “top 3” 入门级内核问题（syzbot）

[English](how-we-picked-top-3-syzbot-issues.md)

本文记录我们如何为“第一次真实修复补丁”练习，挑选 3 个真实的内核问题。

**目标约束**（我们优化的方向）：

- **真实 upstream 问题**（面向主线，不是私有问题）。
- **可复现**：最好有 **C reproducer**，否则是 syz repro。
- **不需要特殊硬件**（应可在 QEMU/VM 中跑）。
- **不太复杂**（定位清晰、warning/OOB 等局部问题、影响面小）。

我们以 **syzbot/syzkaller upstream bug 列表** 为主要数据源，因为它提供：

- 每个问题的公开追踪页面
- repro 附件（`ReproC`、`ReproSyz`）
- syzbot 测试过的内核配置（`KernelConfig`）


## 使用的数据来源

### 1) syzbot upstream 列表（JSON）
- URL: https://syzkaller.appspot.com/upstream?json=1
- Schema 说明：该接口刻意精简；每条记录基本只有：
  - `title`
  - `link`（通常是相对路径，如 `/bug?extid=...`）

因此仅靠 JSON **无法** 判断是否有 reproducer。

### 2) Bug 详情页（HTML）
- 例子：https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9
- HTML 页面包含附件链接，如：
  - `/text?tag=ReproC&x=...`
  - `/text?tag=ReproSyz&x=...`
  - `/text?tag=KernelConfig&x=...`
  - `/text?tag=CrashReport&x=...`

我们抓取这些链接来判断一个问题是否可复现、是否“适合入门”。

### 3) lore.kernel.org `syzbot` 列表（早期探索）
我们也尝试过 lore 的 feed，看是否能直接从近期 syzbot 邮件中挖掘问题：
- Atom: https://lore.kernel.org/syzbot/new.atom

但在我们查看的样本里，很多条目是 **CI/审核** 类邮件；部分 “Email from syzbot” 线程在 mbox 中几乎是空内容。因此我们转而抓取 syzkaller bug 页面作为权威来源。


## 选择方法（高层）

1. 从 syzkaller 拉取 upstream bug 列表 JSON。
2. 逐个打开 bug 页面。
3. 仅 **保留** 含有 **ReproC** 或 **ReproSyz** 附件链接的问题。
4. 用简单的“无需特殊硬件”规则过滤：排除标题中提到常见硬件驱动的条目。
5. 收集到 3 个候选后停止。

这样可以得到一个适合后续阶段的 shortlist：复现 → 最小化 → 修补 → 发送上游。


## 使用的脚本（含说明）

### A) 快速查看 lore 的 `syzbot` Atom feed
目的：验证 lore `syzbot` feed 是否包含可用的 bug 线程。

```bash
python3 - <<'PY'
import urllib.request, xml.etree.ElementTree as ET, re
UA={'User-Agent':'kernel_radar/0.1 (+local)'}

def fetch(url):
  req=urllib.request.Request(url, headers=UA)
  with urllib.request.urlopen(req, timeout=30) as r:
    return r.read().decode('utf-8','replace')

def entries(atom_xml):
  root=ET.fromstring(atom_xml)
  ns={'a':root.tag.split('}',1)[0][1:]} if root.tag.startswith('{') else {}
  es=root.findall('a:entry', ns) if ns else root.findall('entry')
  for e in es:
    t=(e.findtext('a:title',default='',namespaces=ns) if ns else e.findtext('title',''))
    l=''
    for ln in (e.findall('a:link',ns) if ns else e.findall('link')):
      if ln.attrib.get('rel','') in ('alternate',''):
        l=ln.attrib.get('href','')
        if l: break
    yield (t or '').strip(), l

a=fetch('https://lore.kernel.org/syzbot/new.atom')
count=0
for title, link in entries(a):
  if re.search(r'syzbot|syzkaller|KASAN|BUG:|WARNING:', title, re.I):
    print('-', title)
    print(' ', link)
    count += 1
    if count>=30:
      break
print('printed', count)
PY
```

结论：样本中多数是 CI/审核类线程，不适合作为直接 shortlist 来源。


### B) Lore 原始消息探测
目的：确认哪些 “raw” URL 返回 RFC822/mbox，哪些返回 HTML。

关键发现：

- `.../raw` 返回 mbox 类内容
- `...?raw=1` 返回 HTML（不是原始消息）

示例探测：

```bash
python3 - <<'PY'
import urllib.request
base='https://lore.kernel.org/syzbot/20251229085057.5B6A8C4CEF7@smtp.kernel.org/'
for suffix in ['raw','?raw=1','?x=raw','?format=raw','?x=mbox']:
  url=base+suffix
  try:
    req=urllib.request.Request(url, headers={'User-Agent':'kernel_radar/0.1 (+local)'})
    data=urllib.request.urlopen(req, timeout=30).read(200)
    print(suffix, '->', data[:60].replace(b'\n',b'\\n'))
  except Exception as e:
    print(suffix, '-> ERR', e)
PY
```

这项调查让我们更倾向于把 **syzkaller bug 页面** 作为 repro/config 的权威来源。


### C) 实际的 “pick top 3” 脚本（可重复运行）
我们把最终筛选逻辑整理成一个小脚本，便于以后复用：

- Script: [tools/syzbot_pick_top3.py](../tools/syzbot_pick_top3.py)

它的行为：

- 拉取 https://syzkaller.appspot.com/upstream?json=1
- 遍历 bug，直到找到 `ReproC`/`ReproSyz` 链接
- 过滤明显偏硬件的标题（USB/WiFi/BT/DRM 等）
- 输出包含 bug URL、status/subsystems 和附件链接的 shortlist

在仓库根目录运行：

```bash
./tools/syzbot_pick_top3.py
# or:
./tools/syzbot_pick_top3.py --scan-limit 800 --count 3
```

定向筛选特定领域（cgroup/namespaces/scheduler/GPU）：

```bash
# 按 syzbot subsystem 标签过滤（当标签与目标匹配时效果最好）：
./tools/syzbot_pick_top3.py --count 3 --include-subsystem cgroup
./tools/syzbot_pick_top3.py --count 3 --include-subsystem namespaces
./tools/syzbot_pick_top3.py --count 3 --include-subsystem scheduler

# 或按标题关键词正则过滤：
./tools/syzbot_pick_top3.py --count 3 --include-title-re 'cgroup|memcg'
./tools/syzbot_pick_top3.py --count 3 --include-title-re 'namespace|setns|unshare|nsfs'
./tools/syzbot_pick_top3.py --count 3 --include-title-re 'sched|scheduler|cfs|rtmutex'

# GPU/DRM 说明：默认标题排除包含 drm/amdgpu/nouveau。
# 如果明确要 GPU 问题，请关闭默认排除：
./tools/syzbot_pick_top3.py --count 3 --no-exclude-title --include-title-re 'drm|amdgpu|nouveau'
```


### D) 快速预览 C reproducer
目的：确认 repro 不需要特殊硬件，且是“正常的系统调用”。

```bash
python3 - <<'PY'
import urllib.request
UA={'User-Agent':'kernel_radar/0.1 (+local)'}
url='https://syzkaller.appspot.com/text?tag=ReproC&x=16e6089a580000'
req=urllib.request.Request(url, headers=UA)
text=urllib.request.urlopen(req, timeout=30).read().decode('utf-8','replace')
print('\n'.join(text.splitlines()[:80]))
PY
```


## 选出的 3 个问题（快照）

这是当时（2026-01-06）的 shortlist：

1) WARNING in `skb_attempt_defer_free` (net)
- Bug: https://syzkaller.appspot.com/bug?extid=3e68572cf2286ce5ebe9
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a11e0f726bfb6765
- ReproC: https://syzkaller.appspot.com/text?tag=ReproC&x=16e6089a580000
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=1545c89a580000

2) KASAN: slab-out-of-bounds Read in `strnchr` (bpf)
- Bug: https://syzkaller.appspot.com/bug?extid=2c29addf92581b410079
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a94030c847137a18
- ReproC: https://syzkaller.appspot.com/text?tag=ReproC&x=16de569a580000
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=10c82e22580000

3) INFO: task hung in `vhost_worker_killed` (workqueue/vhost-ish)
- Bug: https://syzkaller.appspot.com/bug?extid=a9528028ab4ca83e8bac
- KernelConfig: https://syzkaller.appspot.com/text?tag=KernelConfig&x=a94030c847137a18
- ReproSyz: https://syzkaller.appspot.com/text?tag=ReproSyz&x=13a67222580000


## 备注 / 局限

- “不需要特殊硬件”的过滤是基于 **标题** 的启发式规则，仍可改进。
- 有些问题可能仍需要特定内核配置/调试选项；脚本输出了 syzbot `KernelConfig` 链接以供参考。
- 若需要更深入的优先级排序，可额外抓取：
  - 是否已经修复
  - 是否有 cause/fix bisection
  - 复现频率

但对于第一次实修补丁来说，**reproducer 可用性 + 清晰的 crash 位置** 通常是最高 ROI。
