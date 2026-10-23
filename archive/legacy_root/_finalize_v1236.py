#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6 收尾：当日记忆追加 + MEMORY.md 该节重写 + SKILL.md 补实测教训。三处幂等。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAILY = HERE / ".workbuddy" / "memory" / "2026-10-09.md"
MEM = HERE / ".workbuddy" / "memory" / "MEMORY.md"
SK = Path(r"C:\Users\18432\.workbuddy\skills\dgtf-version-bump\SKILL.md")

DAILY_ADD = """
---

## v1.23.6：清掉代码正文里的版次批注（零功能改动）

### 结果
- 23237 → **21761 行**（-1476 行 / -123 KB）。A 全行批注块 **378 块 / 1476 行**
  （连块删）、B 行尾批注 9 处（只删注释）、C docstring 前导标记 66 处（只剥标记）。
- 冒烟 **exit 0 / 0 ✗ / 201 ✓**（上一版 200 ✓ + 新增 1 条判据）；配置
  `load_config` 差异 **0 项**；纯 CRLF；收束摘要已写进 docstring（21841 行）。
- 被删内容全文存档 `docs/版次批注存档-v1.23.5.md`（3092 行，带行号 + def/class 归属）。

### 零行为变化的机器证明（`_mk_v1236_strip.py` 四条断言）
① A+B+保护行剥标记后 **AST 严格等价**（注释不进 AST ⇒ 删注释可被机器证明为零代码改动）；
② 剥 docstring 前导标记后逐字符串常量比对：**差异 66 处，每处都 `old == tag + new`**；
③ 抹空全部字符串常量后 AST 仍严格等价；
④ 判据需要的 156 个片段**一个都没少**。

### ★★ 本轮最大的发现：测试套件把「注释」当锚点
三类耦合（所以注释不是「随手可删的东西」）：
1. `assert "修行层不追求收敛" in src, "缺红线注释"` —— 该短语**只**在一行宪法红线注释里；
2. `check_v72_bbarrier_semantics` 直接要求 `"[v1.21.72 #13]" in getsource(_run_parallel_B)`
   —— 把**版次标签**当「注释在位」的锚点；
3. 变异体 M3 的 `old` 锚点**含两行注释** ⇒ 注释被删后 `src.count(old) == 0`，断言炸。
→ 解法：P1 含 `[AUDIT-n]` 的行不删；P2 从 smoke + 验收档收集 156 个「判据需要的
片段」，做**最小代价保护**（只保最短那一行）。删除量 1479 → 1476（多保 3 行）。
→ 另有两处锚点**本身就是版本标签或注释** ⇒ 按项目规矩「判据随实现更新」改到新语义：
前者换成注释里的两条内容短语（`刻意的 barrier` + `同时停掉所有层`），后者只锚代码行；
**判据意图一字未改**。改动记录在 `_fix_v1236_anchor.py` / `_fix_v1236_m3.py`。

### 口径修正（重要）
上一版定的窄口径 `v1\\.2\\d` 只报 **395 行**；实测放宽后 **441 行注释 / 378 块 / 1479 行**。
窄口径漏掉两类：短标签 `[v122 P6 G6.2]`、裸 `v59` / `v1.19`；且**按行数**会低估到 1/4
（块内只有首行带标记，其余是续行）。**通则：注释类清理一律按「块」量。**

### 本机环境坑（第 N 次）
- ★ bash 命令**偶发被执行两次**（本轮 3 次）：一次性补丁脚本**必须幂等**
  （`_fix_v1236_sec.py` 非幂等，第二次直接断言失败）。
- ★ 沙箱 overlay **吞写入**：`_mk_v1236_head.py` 的写入被吞过一次（回读发现标题还是
  1.23.5）。**写完立刻换一条命令回读**，别只看脚本自己的打印。
- ★ `re.sub` 的替换串含 Windows 路径反斜杠会报 `bad escape \\U` ⇒ 用函数形式
  `re.sub(pat, lambda m: ...)`（变异体探针里踩到）。
- ★ smoke_test.py **没有模块级 `import ast`** ⇒ 注入的判据要用 `import ast as _ast`
  （局部导入），否则 `NameError`（第一次注入就踩到）。
"""

MEM_OLD = """## ★ v1.23.6 起：代码正文不留「版次批注」
- 模块 docstring **之外**不留带版本号的注释（`# [vX.Y.Z …]` 形态）；变更记录统一
  由 docstring changelog 承担。
- **量法按「块」不按「行」**：清前实测 注释行 **395** / 批注块 **346** / 块覆盖
  **1394 行**（最长一块 18 行，只有首行带版本号）。
- 判据：抠掉 docstring 后 `^\\s*#.*v1\\.2\\d` 为空 + 变异体（插一行版本批注必须判红）；
  **抠前先归一化换行**（否则静默失配、退化成全文件扫描）。取舍三选一见 SKILL。"""

MEM_NEW = """## ★ v1.23.6 起：代码正文不留「版次批注」（已落地）
- 模块 docstring **之外**不留版次标记；变更记录统一由 docstring changelog 承担。
- **口径**（判据与清理工具同一把尺子）：`\\[v\\d[^\\]]*\\]` 方括号短标签 ｜
  `(?<![A-Za-z0-9_-])v\\d+(?:\\.\\d+)*(?![A-Za-z0-9_-])` 裸 v+数字；两侧 lookaround
  挡掉 `deepseek-v4-pro` 这类假阳性。
- **量法按「块」不按「行」**：实测 注释行 441 / **批注块 378 个 / 覆盖 1479 行**
  （窄口径 `v1\\.2\\d` 只报 395 行 ⇒ 低估到 1/4；块内只有首行带标记）。
- ★★ **测试套件会把注释当锚点** —— 三类耦合：`assert "<注释片段>" in src`、
  `getsource(方法)` 里查注释、**变异体锚点含注释**（本轮 156 个片段）。
  ⇒ **清理必须配「判据驱动的保护名单」**：P1 含 `[AUDIT-n]` 的行不删；
  P2 判据片段做**最小代价保护**（只在会全部消失时保最短那一行）。保护粒度 = 成败。
- ★ **只删注释可被机器证明为零代码改动**（注释不进 AST）：AST 严格等价 + 字符串
  常量差异逐点 == 「剥前导标记」。见 `_mk_v1236_strip.py` 四条断言。
- 判据：抠 docstring 后无版次标记 + 变异体（插一行必须判红）；抠前**先归一化换行**。
- 残留口径：docstring **正文中段**的版本提及（40 个常量 / 76 行）不动 —— 那是文档
  行文，不是「代码前面的修改描述」；清它属编辑决策，另开一批。"""

SK_ANC = "无论选哪条，报告里都要写清「删了多少块 / 多少行」+「判据为 0」的实测数字。"
SK_ADD = """

### v1.23.6 落地实测（口径与规模都改了，别再用窄口径）

**版次标记的真实口径**（判据与清理工具必须同一把尺子）：

```
TAG = \\[v\\d[^\\]]*\\]     |  (?<![A-Za-z0-9_-])v\\d+(?:\\.\\d+)*(?![A-Za-z0-9_-])
```

- 上一版写的窄口径 `v1\\.2\\d` **只报 395 行**，实测是 **441 行注释 / 378 块 / 1479 行**
  —— 漏了短标签 `[v122 P6 G6.2]` 与裸 `v59` / `v1.19`，而且按行数会**低估到 1/4**
  （块内只有首行带标记，其余是续行；最大一块 18 行）。
- ★ **一律按「块」量。**

**★★ 最重要的教训：测试套件把「注释」当锚点 —— 注释不是随手可删的东西。**
实测三类耦合，清理时全部会翻红：

1. `assert "修行层不追求收敛" in src, "缺红线注释"` —— 该短语**只**出现在一行
   带版次标签的**宪法红线注释**里。盲目按标记删 = 打掉红线。
2. `check_v72_bbarrier_semantics` 要求 `"[v1.21.72 #13]" in getsource(_run_parallel_B)`
   —— 把**版次标签本身**当「注释在位」的锚点。
3. 变异体的 `old` 锚点**含注释行**（如 M3）⇒ 注释被删后 `src.count(old) == 0`，断言炸。

**做法（`_mk_v1236_strip.py` 可复用）**：

- **P1**：含 `[AUDIT-<数字>]` 的注释行**不删**（冒烟按它数 pending_fix 条数），
  行内版次标记另行抹掉。
- **P2 判据驱动的「最小代价保护」**：从 `smoke_test.py` + `_v122_verify.py` 收集
  全部 `"X" in src` / `"X" not in src` / `src.count("X")` 的 X（本轮 156 个）；
  某片段若**全部出现处**都在待删行里，只保住其中**最短的那一行**。
  ★ **保护的粒度就是清理的成败**：第一版按「块」保护，被 `'文件'`、`'断言'`
  这种 2 字泛词一下保住 **57 个块**（等于没清）；改「每片段最多保一行」后只多保 3 行。
  ★ 收集时要**连 `not in` 一起匹配** —— 漏了它，`[v1.21.72 #13]` 那条被判据点名
  要求的注释就被删了。
- 对**锚点本身就是版本标签/注释**的判据，按「判据随实现更新」改到新语义
  （不是放宽）：换内容短语、或只锚代码行，**判据意图一字未改**，并在报告里写明。

**零行为变化的机器证明（四条，`_mk_v1236_strip.py`）**：
① 删注释后 AST（抠模块 docstring + 归一化 `__version__`）**严格等价** ——
   因为**注释不进 AST**，「只删注释」可以被机器证明为零代码改动；
② 剥 docstring 前导标记后逐字符串常量比对（按 `ast.walk` 顺序 1:1）：差异数 == C 类数，
   且每处都满足 `old == tag + new`；
③ 把所有字符串常量值抹空再比 AST —— 严格等价；
④ 判据需要的片段**一个都没少**（全局断言）。
★ 位置键（lineno/col）不要用来配对常量 —— 删了行之后会错位；用 `ast.walk` 顺序。

**新判据与验证**：`check_v1236_no_version_tags`（抠 docstring 后无版次标记 + 无前导
标记 docstring）；**负对照内置**（对上一版文件跑同一函数必须判红，本轮扫到 441 行）；
**5 个变异体**（M1 全行 / M2 docstring 前导 / M3 行尾 必须判红；M4 只在模块 docstring
里塞标记必须**仍绿** —— 这条才是「判据真抠掉了 docstring」的证明）。

**工程细节**：smoke_test.py **没有模块级 `import ast`** ⇒ 注入判据用局部
`import ast as _ast`；`re.sub` 替换串含 Windows 路径会报 `bad escape \\U` ⇒ 用
`re.sub(pat, lambda m: ...)`；本机 bash **偶发执行两次** ⇒ 一次性补丁脚本必须幂等，
且写盘后**换一条命令回读**（沙箱 overlay 会吞写入）。"""


def patch(path: Path, old: str, new: str, label: str, skip_if: str = None):
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n") > 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    if skip_if and skip_if in t:
        print("[skip] %s" % label)
        return
    n = t.count(old)
    assert n == 1, "%s 锚点命中 %d 次" % (label, n)
    t = t.replace(old, new, 1)
    out = t.replace("\n", "\r\n").encode("utf-8") if crlf else t.encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    path.write_bytes(out)
    print("已改：%s（CRLF=%s）" % (label, crlf))


# ① 当日记忆（append-only）
raw = DAILY.read_bytes()
t = raw.decode("utf-8").replace("\r\n", "\n")
if "v1.23.6：清掉代码正文里的版次批注" in t:
    print("[skip] 当日记忆已追加")
else:
    DAILY.write_bytes((t.rstrip("\n") + "\n" + DAILY_ADD).encode("utf-8"))
    print("已追加当日记忆")
# ② MEMORY.md
patch(MEM, MEM_OLD, MEM_NEW, "MEMORY.md v1.23.6 节", skip_if="已落地）\n- 模块 docstring")
# ③ SKILL.md
patch(SK, SK_ANC, SK_ANC + SK_ADD, "SKILL.md v1.23.6 落地实测", skip_if="v1.23.6 落地实测")

for p in (DAILY, MEM, SK):
    b = p.read_bytes()
    print("%-46s %d 字节 CRLF=%d 裸LF=%d CRCRLF=%d"
          % (p.name, len(b), b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"), b.count(b"\r\r\n")))
