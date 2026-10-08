#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.21.72 打补丁脚本：文档整理批 + 可观测性/形态断言窄版的**引擎侧改动**

用法：
    python _mk_v72_patch.py 元DGTF-V1.21.71.py 元DGTF-V1.21.72.py

本版引擎侧只动两件：
  · [#13] `_run_parallel_B` 的预算停机分支补一条**注释**（barrier 语义）；
  · [#20] changelog：删掉重复的「v1.21.63 收束摘要」段、把 v1.21.68 与
    v1.21.69 两段互换、前言补 v1.21.71/72 两行；
  · 版本号两处 + 新 changelog 段。
★ 硬断言：**模块 docstring 归一化后 AST 逐节点完全相同** —— 证明本版
  对引擎可执行语义零影响（注释不进 AST）。
"""
import ast
import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1]).resolve()
DST = Path(sys.argv[2]).resolve()

raw = SRC.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "源文件不是纯 CRLF"
assert raw.count("\r") == raw.count("\r\n"), "源文件里有裸 CR"
assert '__version__ = "1.21.71"' in raw, "源文件版本号不是 1.21.71"
s = raw.replace("\r\n", "\n")

BAR = "\u2550" * 60
LINE = "\u2500" * 60


def _exec_src(text):
    """抠掉模块 docstring，并把它换成占位串（供 AST 比对用）。

    ★ 还要把 `__version__` 的字面量归一化：版本号本身**是在可执行代码里**
      （不是 docstring），它会合理地变；AST 比对要证明的是"**除了版本号
      与注释，可执行语义逐节点未变**"。
    """
    i = text.index('"""')
    j = text.index('"""', i + 3)
    body = text[j + 3:]
    body, n = re.subn(r'__version__ = "1\.21\.\d+"', '__version__ = "X"',
                      body)
    assert n == 1, f"__version__ 行数 = {n}（应为 1）"
    return '"""X"""' + body


AST_BEFORE = ast.dump(ast.parse(_exec_src(s)))
N_BEFORE = len(AST_BEFORE)

REPL = []


def add(tag, old, new):
    REPL.append((tag, old, new))


# ======================================================================
# P0 · 版本号两处 + changelog 新段
# ======================================================================
add("P0-标题", "元 DGTF · v1.21.71\n", "元 DGTF · v1.21.72\n")
add("P0-版本号", '__version__ = "1.21.71"', '__version__ = "1.21.72"')

_NEW_SEC = """  @@BAR@@
v1.21.72 相对 v1.21.71 的改动（文档整理批 + 可观测性/形态断言窄版）
@@BAR@@

  来源：v1.21.71 交付报告的「遗留」段 + 外部清单「刻意不做」里**本批可以
  安全收口**的四项。★ 引擎可执行语义**逐节点未变**（AST 等价，见下
  「验证」），所以本版**不产生新的真跑数据**，也不改任何判据 / 阈值。

  @@LINE@@
  [A] #13 · B 模式预算耗尽「停所有层」的语义写进代码
  @@LINE@@

  **为什么本轮必须做**：外部清单 #13 把它列成「疑似 bug」，任务书给的
  处置是「**本轮只写注释说清，不改代码**」—— v1.21.71 只在报告里写了
  理由，**漏了代码侧那条注释**。本版补上。
  **做法**：在 `_run_parallel_B` 的预算停机分支加注释：同时停掉所有层是
  **barrier 制**的必然（每一波所有层一起跑，预算耗尽 = 这一波谁也跑不
  起来），与 serial / C / D-H 的「本层截断」（只置自己的 `stopped`）是
  **两种都合法**的语义，不要互相「对齐」。
  **行为零改动**：注释不进 AST。
  **判据**：`check_v72_bbarrier_semantics` 两个方向都锁 ——
    · `max_calls=30` 的 mock B 跑 → **四层全部**带「预算用尽」；
    · 不限预算 → **0 层**带（守卫不误触发）。
    ★ 同时是回归锁：若有人把「一起停」改成「只停一层」，`1..n-1` 的
      形态会立刻被抓住。

  @@LINE@@
  [B] #20 · changelog 去重 + 版本段序重排（纯文档）
  @@LINE@@

  **改前实测**（`_probe_v72.py` [C]）：`★ v1.21.63 收束摘要` **出现 2 次**
  （doc 行 1454 / 1491，两段**逐字相同** —— 复制粘贴事故；6/8/12 行窗口
  的重复块扫描都只命中这一处，全库无第二处重复）；版本段序**不单调**
  （…70, **68, 69**, 67…）。
  **做法**：删掉第二次出现的整段；v1.21.68 与 v1.21.69 两段**互换**，
  使段序按版本号严格递减；前言补 v1.21.71 / v1.21.72 两行（前言本来按
  版本累积，v1.21.71 那行也漏了）。
  **判据**：`check_v72_changelog_hygiene` —— ① 任一「★ vX 收束摘要」
  标题不得出现 2 次以上；② `^v1.21.NN 相对` 的版本号必须**严格递减**。
  ★ 把「改前实测」的两种瑕疵变成**常驻断言**，以后再犯当场红；
    把 SRC 指回 v1.21.71 时这条必须判红（那是它的判别力来源）。

  @@LINE@@
  [C] #22（窄版）· 「机制 → 唯一实现点」形态断言
  @@LINE@@

  **不做什么**：任务书把全局调用图框架留给架构批，本版**不建框架**。
  **做什么**：只钉本项目反复栽过的那几个机制，在**抠掉 docstring 的源码**
  上断言：
    · `_normalize_decidability` / `_untraced_undecidable` / `_stop_reasons`
      / `_finalize_layer_common` / `_cached_ext_assess` / `_dispatch_for_pack`
      / `_layer_guard` / `_quality_check` / `_merge_decidability` /
      `_assess_decidability_dynamic` 的 `def` **各只有 1 处**；
    · `_assess_decidability(` 的**调用点恰好 1 处**（= F6 的唯一入口：
      任何「再补一个直调」的改动会立刻红）；
    · `_finalize_layer_common` / `_stop_reasons` 各 **2 个调用点、1 份
      实现**（两通道共用同一份 —— 正是 v1.21.71 F1 的教训）；
    · v1.21.71 删掉的两处旧门**不得复活**（`rounds_n > 1` 的收尾门、
      `total_rounds <= 1` 的早返回）。
  ★ 量的时候必须**先抠 docstring**：changelog 里也写着这些函数名与旧写法。
    第一版在全文上数，`old_finalize_gate_serial` 数出 1（代码里其实是 0）。

  @@LINE@@
  [D] #24（窄版）· 长度异常自动冒烟警告
  @@LINE@@

  **不做什么**：不改 `dump_view_fields` 的 `_OVERSIZED` 机制（v1.21.70 [H]
  有意只钉字段名、不维护「该打什么」的清单，理由成立）。
  **做什么**：把「**超长字段如果不在 `_OVERSIZED` 里就会被整段打进日志**」
  这个失效模式变成常驻告警：
    · 统计走**产物格式**（`View.to_dict()` 的字符串字段长度），阈值 2000 字，
      基线异常数上限 0（v1.21.72 实测：mock 跑 8 个字符串字段全 < 2000）；
    · **负对照**：造一个 `collision` = 8000 字的 view 喂生产入口
      `dump_view_fields` → ① 输出里**有正文**（失效模式真实存在）、
      ② 同一个统计函数必须把它**检出为异常**（判据不是死的）；
    · 反向锁：同长度的 `manifest`（在 `_OVERSIZED` 里）只打长度、无正文。
  ★ 这条的判据形态**必须带负对照**：基线是 0，不喂合成 view 的话这条
    断言永远通过、等于没写。

  @@LINE@@
  刻意不做（本版仍在范围外）
  @@LINE@@

  · **#21 拆文件**：与项目**形态**冲突 —— 单文件 `元DGTF-V1.21.xx.py` 是
    所有探针 / `_run_verif.py` / `smoke_test.py` / `_convergence_matrix.py`
    的加载契约。**不拆，理由是形态本身**，不是工作量。
  · **#23 零触发机制阈值复查**：需要**新数据**（同条件 ≥N 题）才有判别力；
    本轮两次真跑是「四层各 1 圈」的短跑，对「零触发」没有证据力。
    在拿到交叉验证之前**不动任何阈值**（纪律第 5 条）。
  · **F8 方案 B（两份调度实现合一）**：任务书写的是「选其一，不要两件都
    做」，v1.21.71 选了方案 A。它不是「未完成」，是**平行方案**；真要换，
    需要贯通 `plan_orientation` / `plan_resources` 的 `llm` 参数并重测
    自动调度的 route 选择语义 —— 属架构批。
  · **F11 的「按内容去重」替代方案**：同样不是缺口，且会重新引入收尾
    站点的写入（与 F1 的耦合要重算），留待可观测性批。

  @@LINE@@
  验证
  @@LINE@@

  **零语义改动的机器证明**（本版最重的一条）：两版源码把**模块 docstring
  归一化**后 `ast.dump(ast.parse(...))` **逐节点完全相同**（节点数
  1735681）⇒ 本版对引擎的全部影响 = docstring 文本 + 一条 `#` 注释。
  **也正因为如此，本版不做真跑验收**：判据是「这条通道会不会经过我改的
  那行代码」，答案是**没有任何一行**；再跑一次只会得到同一份代码的另一
  次采样。这不是省事 —— 替代证据是 AST 等价 + 全套冒烟 + 4 条新判据。
  **冒烟**：exit 0 / **0 个 ✗**；新增 4 条 `check_v72_*`（每条带负对照或
  反方向），11 条 `check_v71_*` 继续全 ✓。

"""

add("P0-changelog",
    "\n  " + BAR + "\nv1.21.71 相对 v1.21.70 的改动（F1~F11 十一项缺陷修复）\n"
    + BAR,
    "\n" + _NEW_SEC.replace("@@BAR@@", BAR).replace("@@LINE@@", LINE)
    + "  " + BAR
    + "\nv1.21.71 相对 v1.21.70 的改动（F1~F11 十一项缺陷修复）\n" + BAR)


# ======================================================================
# #20-c · 前言补 v1.21.71 / v1.21.72 两行
#   ★ 锚点用短串（`  延伸与卫生。\n`）：它与下面的 P0-changelog 锚点
#     **不重叠**，所以两处替换的先后顺序不会互相吃掉。
# ======================================================================
add("20c-前言",
    "  延伸与卫生。\n",
    """  延伸与卫生。
  v1.21.71 是本轮缺陷修复版：外部代码检查报告（24 项）逐条复核后落地
  F1~F11 十一项，**3 条外部结论经实测不成立**（照实写在该段内）。
  v1.21.72 是本轮文档与可观测性版：补 #13 的代码注释、changelog 去重 +
  版本段序重排（#20）、加「机制→唯一实现点」与「长度异常」两条形态冒烟
  （#22 / #24 的**窄版**）；**引擎可执行语义逐节点未变**。
""")


# ======================================================================
# #13 · B 模式 barrier 语义注释
# ======================================================================
add("13-barrier注释",
    """            if k > warm + 1 and self._budget_exhausted():
                self._note_budget_stop(f"B 模式第 {k} 波")
                for e in active:""",
    """            if k > warm + 1 and self._budget_exhausted():
                self._note_budget_stop(f"B 模式第 {k} 波")
                # [v1.21.72 #13] ★ 这里**同时停掉所有层**是**刻意的 barrier
                #   语义**，不是漏改：B 的每一波是所有层一起跑的，预算耗尽
                #   意味着「这一波谁也跑不起来」；只停当前层会让它去等一个
                #   永远不会来的波次。serial / C / D-H 的「本层截断」
                #   （只置自己的 stopped）是**另一种**合法语义，
                #   两者不要互相「对齐」。
                #   （外部清单 #13 曾疑此为 bug；v1.21.71 复核判定：不是。
                #     这条注释是 v1.21.72 补的 —— v71 只在报告里写了理由。）
                for e in active:""")


# ======================================================================
# 执行（注：#20-a / #20-b 需要按 index 定位，见下）
# ======================================================================
print(f"打补丁：{SRC.name} → {DST.name}")
print(f"计划替换 {len(REPL)} 处\n")

fail = []
for tag, old, new in REPL:
    n = s.count(old)
    if n != 1:
        fail.append(f"{tag}: 命中 {n} 次（必须恰好 1 次）")
        continue
    s = s.replace(old, new, 1)
    print(f"   ✓ {tag}")

if fail:
    print("\n✗ 中止，未写文件：")
    for f in fail:
        print("   -", f)
    sys.exit(1)

# ---------------- #20-a：删掉重复的「v1.21.63 收束摘要」段 ----------------
# ★ 分隔线宽度在文件里**不统一**（这一处 56 个 `─`，别处 60）——
#   第一版拿 60 去拼锚点，命中 0 次。改用「任意宽度的分隔线」正则定位。
_pat63 = re.compile(r"(?m)^  \u2500+\n  ★ v1\.21\.63 收束摘要\n  \u2500+\n")
_ms = list(_pat63.finditer(s))
assert len(_ms) == 2, f"v1.21.63 收束摘要块出现 {len(_ms)} 次（应为 2）"
_m2 = _ms[1]
_start = _m2.start()
while s[_start - 1] == "\n":
    _start -= 1
_end = s.index(BAR + "\nv1.21.62 相对", _m2.end())
s = s[: _start] + "\n\n" + s[_end:]
assert len(_pat63.findall(s)) == 1, "去重后仍不是 1 次"
print("   ✓ 20a-删重复段（v1.21.63 收束摘要 ×2 → ×1）")

# ---------------- #20-b：v1.21.68 与 v1.21.69 两段互换 ----------------
def _h(v):
    return BAR + "\nv" + v + " 相对 "


_i68, _i69, _i67 = (s.index(_h("1.21.68")), s.index(_h("1.21.69")),
                    s.index(_h("1.21.67")))
assert _i68 < _i69 < _i67, (_i68, _i69, _i67)
_b68, _b69 = s[_i68:_i69], s[_i69:_i67]
assert s.count(_b68 + _b69) == 1, "68+69 块不唯一"
s = s.replace(_b68 + _b69, _b69 + _b68, 1)
print("   ✓ 20b-段序互换（68/69 → 69/68）")

# ---------------- 版本段序自检 ----------------
_secs = re.findall(r"^v(1\.21\.\d+) 相对", s, re.M)
print("\n版本段起始序（行号 → 版本）：")
for m in re.finditer(r"^v1\.21\.\d+ 相对", s, re.M):
    print(f"   {s[:m.start()].count(chr(10)) + 1:>6}  "
          f"{s[m.start():m.start() + 22]}")
_ver = [tuple(int(x) for x in v.split(".")) for v in _secs]
assert _ver[0] == (1, 21, 72), f"最新段不在最前：{_secs[:3]}"
assert all(_ver[k] > _ver[k + 1] for k in range(len(_ver) - 1)), \
    f"版本段序不是严格递减：{_secs}"
assert len(_secs) == len(set(_secs)), f"版本段有重复：{_secs}"
print("   ✓ 段序严格递减、无重复段")

# ---------------- 版本号两处 ----------------
assert "元 DGTF · v1.21.72" in s, "docstring 标题没改"
assert '__version__ = "1.21.72"' in s, "__version__ 没改"

# ---------------- ★ 零语义改动：AST 逐节点比对 ----------------
AST_AFTER = ast.dump(ast.parse(_exec_src(s)))
if AST_AFTER != AST_BEFORE:
    i = next(i for i, (a, b) in enumerate(zip(AST_BEFORE, AST_AFTER))
             if a != b)
    print(f"\n✗ AST 不等（首处差异在第 {i} 字符）")
    print(f"   改前 …{AST_BEFORE[max(0, i - 60):i + 60]}…")
    print(f"   改后 …{AST_AFTER[max(0, i - 60):i + 60]}…")
    sys.exit(1)
print(f"   ✓ AST 逐节点相同（{N_BEFORE} 字符的指纹一致）—— 引擎语义零改动")

# ---------------- 回写 CRLF ----------------
out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n"), "回写后有裸 LF"
assert out.count("\r") == out.count("\r\n"), "回写后有裸 CR"
DST.write_bytes(out.encode("utf-8"))
print(f"\n✓ 已写出 {DST.name}（{out.count(chr(10))} 行按 LF 计 / "
      f"{len(out.encode('utf-8'))} 字节）")
