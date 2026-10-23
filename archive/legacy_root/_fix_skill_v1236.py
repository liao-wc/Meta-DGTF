#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① SKILL.md 补「v1.23.6 落地实测」；② MEMORY.md 压掉与 SKILL 重复的两条。都幂等。"""
from pathlib import Path

SK = Path(r"C:\Users\18432\.workbuddy\skills\dgtf-version-bump\SKILL.md")
MEM = Path(__file__).resolve().parent / ".workbuddy" / "memory" / "MEMORY.md"

ANC = "无论选哪条，报告里都要写清「删了多少块 / 多少行」+「判据为 0」的实测数字。"
ADD = """

### v1.23.6 落地实测（口径与规模都改了，别再用窄口径）

**版次标记的真实口径**（判据与清理工具必须同一把尺子）：

```
TAG = \\[v\\d[^\\]]*\\]     |  (?<![A-Za-z0-9_-])v\\d+(?:\\.\\d+)*(?![A-Za-z0-9_-])
```

- 上一版写的窄口径 `v1\\.2\\d` **只报 395 行**；实测是 **441 行注释 / 378 块 / 1479 行**
  —— 漏了短标签 `[v122 P6 G6.2]` 与裸 `v59` / `v1.19`，而且按行数会**低估到 1/4**
  （块内只有首行带标记，其余是续行；最大一块 18 行）。★ **一律按「块」量。**

**★★ 最重要的教训：测试套件把「注释」当锚点 —— 注释不是随手可删的东西。**
实测三类耦合，清理时全部会翻红：

1. `assert "修行层不追求收敛" in src, "缺红线注释"` —— 该短语**只**出现在一行带版次
   标签的**宪法红线注释**里。盲目按标记删 = 打掉红线。
2. `check_v72_bbarrier_semantics` 要求 `"[v1.21.72 #13]" in getsource(_run_parallel_B)`
   —— 把**版次标签本身**当「注释在位」的锚点。
3. 变异体的 `old` 锚点**含注释行**（如 M3）⇒ 注释被删后 `src.count(old) == 0`，断言炸。

**做法（`_mk_v1236_strip.py` 可复用）**：

- **P1**：含 `[AUDIT-<数字>]` 的注释行**不删**（冒烟按它数 pending_fix 条数），
  行内版次标记另行抹掉。
- **P2 判据驱动的「最小代价保护」**：从 `smoke_test.py` + `_v122_verify.py` 收集全部
  `"X" in src` / `"X" not in src` / `src.count("X")` 的 X（本轮 156 个）；某片段若
  **全部出现处**都在待删行里，只保住其中**最短的那一行**。
  ★ **保护粒度就是清理的成败**：第一版按「块」保护，被 `'文件'`、`'断言'` 这种 2 字
  泛词一下保住 **57 个块**（等于没清）；改「每片段最多保一行」后只多保 3 行。
  ★ 收集时**连 `not in` 一起匹配** —— 漏了它，`[v1.21.72 #13]` 那条被判据点名要求的
  注释就被删了。
- 对**锚点本身就是版本标签/注释**的判据，按「判据随实现更新」改到新语义（不是放宽）：
  换内容短语、或只锚代码行，**判据意图一字未改**，并在报告里写明理由。

**零行为变化的机器证明（四条，`_mk_v1236_strip.py`）**：
① 删注释后 AST（抠模块 docstring + 归一化 `__version__`）**严格等价** —— 因为
   **注释不进 AST**，「只删注释」可以被机器证明为零代码改动；
② 剥 docstring 前导标记后逐字符串常量比对（按 `ast.walk` 顺序 1:1）：差异数 == C 类数，
   且每处都满足 `old == tag + new`；
③ 把所有字符串常量值抹空再比 AST —— 严格等价；
④ 判据需要的片段**一个都没少**（全局断言）。
★ 别用位置键（lineno/col_offset）配对常量 —— 删了行之后会错位；用 `ast.walk` 顺序。

**新判据与验证**：`check_v1236_no_version_tags`（抠 docstring 后无版次标记、无以标记
开头的 docstring）；**负对照内置**（对上一版文件跑同一函数必须判红，本轮扫到 441 行）；
**5 个变异体**（M1 全行 / M2 docstring 前导 / M3 行尾 必须判红；**M4 只在模块 docstring
里塞标记必须仍绿** —— 这条才是「判据真抠掉了 docstring」的证明）。

**工程细节**：`smoke_test.py` **没有模块级 `import ast`** ⇒ 注入判据用局部
`import ast as _ast`；`re.sub` 的替换串含 Windows 路径会报 `bad escape \\U` ⇒ 用
`re.sub(pat, lambda m: ...)`；本机 bash **偶发执行两次** ⇒ 一次性补丁脚本必须幂等，
且写盘后**换一条命令回读**（沙箱 overlay 会吞写入，本轮主文件头部被吞过一次）。"""

SK_RAW = SK.read_bytes()
sk = SK_RAW.decode("utf-8").replace("\r\n", "\n")
if "v1.23.6 落地实测" in sk:
    print("[skip] SKILL 已含落地实测")
else:
    n = sk.count(ANC)
    assert n == 1, "SKILL 锚点命中 %d 次" % n
    sk = sk.replace(ANC, ANC + ADD, 1)
    SK.write_bytes(sk.replace("\n", "\r\n").encode("utf-8"))
    print("已插入 SKILL「v1.23.6 落地实测」")

TRIM = [("- **口径**（判据与清理工具必须同一把尺子）：`\\[v\\d[^\\]]*\\]` 方括号短标签 ｜\n"
        "  `(?<![A-Za-z0-9_-])v\\d+(?:\\.\\d+)*(?![A-Za-z0-9_-])` 裸 v+数字；两侧 lookaround\n"
        "  挡掉 `deepseek-v4-pro` 这类假阳性。\n", ""),
        ("- 残留口径：docstring **正文中段**的版本提及（40 个常量 / 76 行）不动 —— 那是文档\n"
         "  行文，不是「代码前面的修改描述」；清它属编辑决策，另开一批。\n",
         "- 残留：docstring **正文中段**的版本提及（40 个常量 / 76 行）不动（是文档行文，\n"
         "  不是「代码前面的修改描述」）。\n")]
mem = MEM.read_bytes().decode("utf-8").replace("\r\n", "\n")
if "两侧 lookaround" in mem:
    for old, new in TRIM:
        assert mem.count(old) == 1, "MEM 锚点命中 %d 次" % mem.count(old)
        mem = mem.replace(old, new, 1)
    MEM.write_bytes(mem.replace("\n", "\r\n").encode("utf-8"))
    print("已压 MEMORY.md 两条")
else:
    print("[skip] MEM 已压过")

for p in (SK, MEM):
    b = p.read_bytes()
    print("%-14s %d 字节 字符=%d 行=%d CRLF=%d 裸LF=%d CRCRLF=%d"
          % (p.name, len(b), len(b.decode("utf-8")), b.count(b"\n"), b.count(b"\r\n"),
             b.count(b"\n") - b.count(b"\r\n"), b.count(b"\r\r\n")))
