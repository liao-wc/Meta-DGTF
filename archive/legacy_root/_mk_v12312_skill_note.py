# -*- coding: utf-8 -*-
"""把 v1.23.12 的四条教训追加进 dgtf-version-bump 技能。"""
import re
from pathlib import Path

p = Path.home() / ".workbuddy" / "skills" / "dgtf-version-bump" / "SKILL.md"
raw = p.read_bytes()
crlf = raw.count(b"\r\n") > (raw.count(b"\n") - raw.count(b"\r\n"))
s = raw.decode("utf-8").replace("\r\n", "\n")

SENT = "### 15. \u2605\u2605 \u300c\u5148\u5b9a\u4f4d\u3001\u540e\u63d2\u5165\u300d"

ADD = """
### 15. ★★ 「先定位、后插入」的补丁：**插入前必须重扫锚点**，并加结构性自检

v1.23.12 的补丁脚本里，我先算出 `_render_landing_decision` 的行号，接着 §2 的
替换让全文少了 9 行，最后才按**旧行号**插入两个新函数 ⇒ 新函数被塞进了
`_render_landing_decision` 的 docstring 之后、函数体之前；函数体被**悄悄并进
上一个函数**，`_render_landing_decision` 只剩 docstring（返回 `None`）。
★ 而 `ast.parse` **照样通过**（缩进合法），`grep` 数函数名也照样 1 处。
只有探针真的驱动 `render_landing` 时才崩在 `body.find` 上。

**固定做法**：① 替换与插入分开写；② **插入前重新 `find_row` 一次**（别复用
开头算好的索引）；③ 补丁脚本末尾加一条**结构性自检** —— 本次是
「三档 `render_landing` 都必须返回 `str` 且带第七节」。

### 16. ★★ 判据的**取材范围**要卡到那一个渲染点：「整篇里有」≠「这个点渲染了」

首版 `check_v12312_anchor_lanes` 断言「整篇产物里有两条通道」⇒ 变异体
「删掉 `save_result` 头部那处调用」**假绿**：产物正文后面还有
`render_manifestation` 的「显化说明」，两条通道又从那里出现一次。
收紧为「**首个二级标题之前**的头部区间」后立即判红。

**通则**：一个渲染点一条判据；取材范围 = **那一段**（表头 / 那一节 / 那一行）。
凡「某处被删了还判过」的假绿，先怀疑取材范围太宽。

### 17. ★★ 「旧渲染形态」和「信息」要分开判断 —— 撤形态前先分类

v1.23.12 首版把头部那几行 `锚点对照 / 锚点分级 / triage 降级 / 冲突 / 锚点入池`
当成「旧单通道块」整段撤掉 ⇒ `_v122_verify.py` 的
`[4.7] 头部含『锚点分级』+『triage 降级』` 当场判红；`_p2_triage_from_md`
（正则 `\\*\\*triage 降级\\*\\*：(\\d+) 条`）也会**静默取不到值**。

两条通道只是**多一条出口**，那些读数是**信息**。
⇒ 改渲染结构前逐行问一句：**这是「形态」还是「读数」？** 读数一律保留；
并给「保留」这件事补一条自己的判据（本次补了判据 G 段 + M6 变异体）。
★ 判据侧同理：`[4.7]` 没被改动，改的是实现 —— **让实现回到判据的语义**，
比「判据随实现更新」更优先，只要判据守的是信息而不是形态。

### 18. ★ 报告里引用**验收档条目前缀**（`X.xxx.py`）也会被 H1 判红

第 6 条的续：H1 会解析报告里出现的文件名并逐个查存在性。
本次我在对照表里写了「`X._probe_v1232_audit.py` 的 C2/C3」—— 那是**验收档
条目前缀**，不是文件路径 ⇒ 判红 `缺：['X._probe_v1232_audit.py']`。
**写真实文件名**（`_probe_v1232_audit.py`）；要表达「某条判据」时把 `X.` 前缀
去掉，或不要把它包成文件名的形态。

### 19. ★ bash heredoc 里的转义会被再吃一层 —— 长文本补丁写成 `.py` 文件

`<<'PYEOF'` 里写 `"\\\\n"`，Python 收到的是**字面** `\\n`（反斜杠+n）而不是换行；
写 `\\\\u2192` 则得到字面 `\\u2192` 而不是箭头（锚点命中 0 次）。
更隐蔽的是 MSYS/Git Bash 会把 `\\n` 吃掉一层变成 `/n`，
于是变异体产出 `elif False://n` —— 语法错误，但报错位置在**生成物**而不是补丁脚本。
⇒ 只要补丁里含中文、箭头、`\\n`/`\\u` 转义，**用 Write 工具写成 `.py` 文件再跑**。
"""

if SENT in s:
    print("[skip] 已追加过")
else:
    if not s.endswith("\n"):
        s += "\n"
    s += ADD
    out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
    p.write_bytes(out)
    print("已追加第 15-19 条")

chk = p.read_bytes()
fixed = re.sub(rb"\r+\n", b"\r\n", chk)
if fixed != chk:
    p.write_bytes(fixed)
    chk = fixed
    print("★ 修复了 CRCRLF")
print("技能 CRLF %d | CRCRLF %d | 字节 %d"
      % (chk.count(b"\r\n"), chk.count(b"\r\r\n"), len(chk)))
