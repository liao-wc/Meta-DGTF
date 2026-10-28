# -*- coding: utf-8 -*-
"""V2.2.8 → V2.2.9 补丁：补上成本归因的**第二个**盲区（`unknown` 桶）。

背景（实测）
------------
V2.2.5 用 AST 扫出 4 处「没传 stage=」并补上具名 stage，判据全绿。
但 V2.2.8 第一次真跑完的本地跑次里，`llm_by_stage` 仍然有：

    {"stage": "unknown", "calls": 2, "tokens": 4224, "ms": 31}

—— 占该跑 13 次调用里的 2 次、21323 tokens 里的 4224。**AST 说 0 处缺失，
产物里却有盲区**，说明这是**另一种**机制。

根因：一个参数两种语义
----------------------
`LLM.call(stage=...)` 的 `stage` 同时承担两件事：
  1. thinking 档位选择（`thinking_stages.get(stage)`）
  2. 联网授权环节名（`_web_augment`）
  3. **成本归因标签**（`_sn = str(stage or "unknown")`）

而 18 个调用点写的是 `stage=_thinking_stage(self.config, 'X')`，
`_thinking_stage()` **只在「该环节在 thinking 表里声明过」时才返回名字，
否则返回 None** ⇒ thinking 关 ⇒ stage=None ⇒ 成本标签掉进 `unknown`。

★ 「AST 判据说 0 处缺失」属于**判据测错了东西**：它只查「有没有 `stage=`
  这个 kwarg」，查不出「传了变量但值是 None」。

修法（零行为变化的保守方案）
----------------------------
给 `LLM.call()` 新增**独立**的 `cost_stage` 参数，只服务成本归因：
  · `stage` 一字不动 ⇒ thinking 档位、联网授权完全照旧
  · 18 个调用点加 `cost_stage='X'`（与 thinking 用的名字同一个字面量）
  · 归因与归桶都用 `cost_stage or stage` ⇒ 标签恒有、eval/ops 按真实环节分

★ 为什么不直接改 `_thinking_stage()` 恒返回名字：那会让 3 个调用点
  （`self_check`）在联网增强里从栈推断名 `self_check_llm/…decide_narrow`
  变成 `self_check`，属于**非默认配置下的行为变化**。本补丁不冒这个险。

副作用（必须在变更记录里写明）
------------------------------
被记成 ops 的这些调用现在按真实环节归桶：`self_check` 等在设计上属 eval
（`_LLM_EVAL_STAGES`），⇒ eval 读数会上升。这是**修正**不是新行为。
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.8.py"
DST = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.9.py"


def die(msg: str) -> None:
    print("❌ " + msg)
    sys.exit(1)


raw = SRC.read_bytes()
if raw.count(b"\r\n") != raw.count(b"\n"):
    die(f"源文件不是纯 CRLF（CRLF={raw.count(b'/r/n')} LF={raw.count(b'/n')}）")
if DST.exists():
    die(f"目标已存在：{DST}")
shutil.copyfile(SRC, DST)
text = raw.decode("utf-8").replace("\r\n", "\n")


def sub1(old: str, new: str) -> None:
    global text
    n = text.count(old)
    if n != 1:
        die(f"锚点命中 {n} 次（应为 1）：{old[:80]!r}")
    text = text.replace(old, new)
    print(f"  ✓ {old[:60]!r} → 已替换")


# ───────────── 1. 版本号（两处 + docstring 补丁说明） ─────────────
sub1('__version__ = "2.2.8"', '__version__ = "2.2.9"')
sub1("Meta-DGTF-道生三阶模型 · V2.2.8", "Meta-DGTF-道生三阶模型 · V2.2.9")
sub1("★ V2.2.8 补丁（产物落盘不再被单层渲染拖死）：逐层明细渲染失败只降级该层",
     "★ V2.2.9 补丁（补上成本归因的第二个盲区）：新增独立 cost_stage 参数。\n"
     "   `stage` 一个参数承担三种语义（thinking 档位 / 联网授权 / 成本标签），\n"
     "   而它未声明时为 None ⇒ 实测一跑里 2/13 次调用、4224/21323 tokens\n"
     "   落进 `unknown` 桶（AST 判据查不出：它只看有没有这个 kwarg）。\n"
     "★ V2.2.8 补丁（产物落盘不再被单层渲染拖死）：逐层明细渲染失败只降级该层")

# ───────────── 2. call() 增加 cost_stage 参数 ─────────────
sub1("             json_mode=False, model=None, thinking=None, stage=None,",
     "             json_mode=False, model=None, thinking=None, stage=None,\n"
     "             cost_stage=None,")

# ───────────── 3. 归因与归桶改用真实环节名 ─────────────
sub1('''                    if cost_bucket(stage) == "eval":
                        self.eval_calls += 1
                        self.eval_tokens += _tk
                    else:
                        self.ops_calls += 1
                        self.ops_tokens += _tk
                    _sn = str(stage or "unknown")''',
     '''                    # ★ 成本归因的环节名必须**恒有**。`stage` 一个参数承担
                    #   两件事（thinking 档位 / 联网授权）且未声明时为 None，
                    #   拿它当成本标签 ⇒ 盲区（实测 2/13 次调用落进 unknown）。
                    #   `cost_stage` 只服务归因，恒由调用点给出。
                    _sn = str(cost_stage or stage or "unknown")
                    if cost_bucket(_sn) == "eval":
                        self.eval_calls += 1
                        self.eval_tokens += _tk
                    else:
                        self.ops_calls += 1
                        self.ops_tokens += _tk''')

# ───────────── 4. 18 个调用点补 cost_stage ─────────────
#: ★ DOTALL + 允许逗号后有换行：实测有一处调用把 `'self_check'` 折到了下一行
#:   （`stage=_thinking_stage(self.config,\n   'self_check')`），按「整行字面」
#:   找锚点会静默漏掉它 —— 正是本项目反复栽的「锚点命中 0 次」。
PAT = re.compile(r"stage=_thinking_stage\((.{0,140}?),\s*'(\w+)'\s*\)", re.DOTALL)
names = PAT.findall(text)
if len(names) != 18:
    die(f"`_thinking_stage` 调用点 {len(names)} 个（应为 18）")
text = PAT.sub(lambda m: "stage=_thinking_stage(%s, '%s'), cost_stage='%s'"
               % (m.group(1), m.group(2), m.group(2)), text)
print(f"  ✓ 18 个调用点已补 cost_stage："
      f"{sorted({n for _, n in names})[:6]} …")

# ───────────── 自检 + 写回（纯 CRLF） ─────────────
try:
    tree = ast.parse(text)
except SyntaxError as e:
    die(f"语法错误：{e}")

# 自检：所有 cost_stage 都跟它的 thinking 名字一致
bad = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "call":
        kv = {k.arg: k.value for k in node.keywords}
        if "cost_stage" not in kv:
            continue
        cs = kv["cost_stage"].value
        st = kv.get("stage")
        lit = None
        if isinstance(st, ast.Call) and getattr(st.func, "id", "") == "_thinking_stage":
            for a in st.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    lit = a.value
        if lit is not None and lit != cs:
            bad.append((node.lineno, lit, cs))
if bad:
    die(f"cost_stage 与 thinking 名字不一致：{bad}")

out = text.replace("\n", "\r\n").encode("utf-8")
if b"\r\r\n" in out:
    die("写出内容含 \\r\\r\\n")
DST.write_bytes(out)
chk = DST.read_bytes()
if chk.count(b"\r\n") != chk.count(b"\n"):
    die("目标不是纯 CRLF")

print("─" * 60)
print(f"✅ {DST.name} 生成：{chk.count(b'\n') + 1} 行，纯 CRLF，语法 OK")
