# -*- coding: utf-8 -*-
"""把 v1.23.13 的六条教训追加进 dgtf-version-bump 技能。"""
import re
from pathlib import Path

p = Path.home() / ".workbuddy" / "skills" / "dgtf-version-bump" / "SKILL.md"
raw = p.read_bytes()
crlf = raw.count(b"\r\n") > (raw.count(b"\n") - raw.count(b"\r\n"))
s = raw.decode("utf-8").replace("\r\n", "\n")

SENT = "### 20. \u2605\u2605 \u8865\u4e01\u811a\u672c\u53ea\u7559**\u4e00\u5904\u771f\u76f8\u6e90**"

ADD = """
### 20. ★★ 补丁脚本只留**一处真相源**：文本级与行级混用会静默丢替换

v1.23.13 首版补丁脚本里，前半段用 `s = s.replace(...)` 改文本、后半段用
`lines[i:i+n] = [...]` 改行，中间一次 `s = "\\n".join(lines)` 把**前面所有文本级
替换丢掉**。症状：版本号没升、`_assemble_plan` 的 4 处调用全丢、
`_normalize_orientation` 只剩定义 —— 而 `ast.parse` **照样通过**、脚本**报 EXIT=0**。
是探针（`HAS_调度器 = False`）与补丁末尾的结构性自检抓出来的。

**固定做法**：一个补丁脚本只操作一个行表 —— 全部编辑（含整块替换）都在 `lines`
上做，**最后 join 一次、转一次 CRLF、写一次盘**。整块替换也按行比对：

```python
def repl(old, new, what, expect=1):
    o, n = old.split("\\n"), new.split("\\n")
    hits = [i for i in range(len(lines) - len(o) + 1)
            if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：块命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
```

★ 这是「状态漂移」这一类错的**第二次**（v1.23.12 是「先算索引、后替换」，见第 15 条）。
两次都满足「AST 通过 + 脚本 EXIT=0」，两次都靠**探针**抓出来。

### 21. ★★ 判据可能**绕过被测函数** —— 「自带输入」的组要再补真实介质断言

v1.23.13 的 `check_v12313_auto_dispatch` 把合成 `hist` **直接喂给**
`auto_dispatch(..., history=H)`，于是**绕过了** `_auto_history` 本身；
变异体「`_auto_history` 恒返回空 dict」**假绿**。
补一组「把一份 packed 写进临时目录、真的调 `_auto_history(td)`」并断言
`n / tokens_med / web_hit / cut_rate / layer_rounds / modes` 读数 + 空目录负对照，
才判红。

**通则**：凡是判据**自带输入**的组，都要再问一句「我给的这份输入，是**从哪来的**？」——
如果被测的那一层（加载器 / 解析器 / 读盘函数）被跳过了，这一组等于没测。

### 22. ★ 策略函数判据必须断言它**输出的值**，不是「有理由」

`stop` 那一组首版只断言「留痕里有 reason」，于是
`_auto_pick_stop` 恒返回 `{}`（什么都不调）**也判过**。
补「事实短题阈值 = 1 / 含元层阈值 = 3」两向断言后才判红。

### 23. ★ 判据耦合**源码字面**，重构时必然误报 —— 改成行为断言

`P5.2.b` 原来数 `"orientation": _ori` 在源码里出现 ≥2 次。它的**意图**是
「早退分支也带出取向」，写法却是对**实现字面**的计数。v1.23.13 把三条出口收进
唯一装配器 `_assemble_plan(orientation=_ori)` ⇒ 字面消失、**行为没变**，判据误报。
改成行为断言（低置信打桩 ⇒ 断言 `mode == "serial"` 且 `orientation == "boundary"`）
—— **不是放宽，是换成更强的断言**。

★ 顺带：同一个判据可能在**多个文件里有副本**（本次 `P5.2.b` 同时存在于
`smoke_test.py` 与 `_v122_verify.py`）。改判据前先 `grep -rn "判据名"` 全仓库。

### 24. ★★ 「来源 / 标签」不是「写不写」的依据 —— 显式值必须真的落进配置

v1.23.13 首版 `_apply_auto_dispatch` 只写**来源是 `auto`** 的项，理由是
「explicit/config 的值本就来自命令行或配置，再写一遍会把用户给的盖章成系统算的」。
**这个推理是错的**：explicit 的值只存在于 plan 里、没人搬进 `cfg`，
于是 `--web off` / `--profile quality` / `--thinking on` / `--effort max`
**全部失效**（`_apply_runtime` 读到的还是配置里的 `auto`）。

**正确规则**：写 **来源 ∈ {auto, 显式}** 的项；`source` 字段是给**留痕**用的
（产物里显示「谁定的」），不是给「写不写」用的。
★ 这条是**功能级** bug，冒烟与验收档都抓到了（`v1.23.4 运行期总控` 与 `V7.a`），
因为它们量的正是「开关有没有真的落下去」——**接线判据有它不可替代的价值**。

### 25. ★ 改文件的脚本自身也要**幂等**

`_mk_v12313_config_sync.py` 第二次跑就断言失败（「头部版本已是 v1.23.13」）。
凡是「改文件」的脚本，都要能被重复执行：先判「是否已改」再改
（如 `if HEAD in s: 先抠旧段`，见 `_mk_v12313_changelog.py`）。

### 26. ★ 新增配置键的版本，`load_config 差异 0` 的含义**变了**

`load_config` 把 yaml 叠到 `DEFAULT_CONFIG` 上 ⇒ 新增键由出厂值补齐，
两版 load 结果**本来就相等**。此时「差异 0」不再能证明「yaml 没被改坏」。
**新口径三条**：① 逐字差异为 ∅（yaml 没有引入任何**非默认**覆盖）；
② yaml 文本层面真的写出了新键（人能看见、能改）；
③ yaml 覆盖 `DEFAULT_CONFIG` 的**全部**键（漏一个就是「写了但没生效」）。
"""

if SENT in s:
    print("[skip] 已追加过")
else:
    if not s.endswith("\n"):
        s += "\n"
    s += ADD
    out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
    p.write_bytes(out)
    print("已追加第 20-26 条")

chk = p.read_bytes()
fixed = re.sub(rb"\r+\n", b"\r\n", chk)
if fixed != chk:
    p.write_bytes(fixed)
    chk = fixed
    print("★ 修复了 CRCRLF")
print("技能 CRLF %d | CRCRLF %d | 字节 %d"
      % (chk.count(b"\r\n"), chk.count(b"\r\r\n"), len(chk)))
