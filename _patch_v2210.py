# -*- coding: utf-8 -*-
"""V2.2.9 → V2.2.10 补丁：补上成本归因的**第三批**盲区（7 处）。

为什么 V2.2.9 之后仍有 `unknown`
--------------------------------
V2.2.9 修的是「传了变量但值是 None」。打点抓栈后又抓到 7 处**根本没传**：

    UNKNOWN-STAGE 调用栈: run:11711 <- _manifest:16610 <- _call_long:11268
    UNKNOWN-STAGE 调用栈: main:33011 <- run:26353 <- propose:71

★ 根因是**判据范围不够**：原来的 AST 审计
  · 只扫**主文件**（`Meta-DGTF-VX.py`），不扫 `dgtf_v2/*.py` 模块 ⇒ 漏 4 处
  · 只扫 `*.call(`，不扫 `*_call_long(`（包装器）⇒ 漏 3 处
  ⇒ 报「0 处缺失」而产物里照样有盲区。**判据测错了东西比没判据更危险**。

本补丁同时修两件事
------------------
1. 补齐 7 处 stage（引擎 3 处 + 模块 4 处）
2. 判据扩到「主文件 + 全部模块」×「call + _call_long」（见 tests_cost_stage.py）

★ 为什么用 `stage=` 而不是 `cost_stage=`：这些模块是**跨版本共用**的，
  旧引擎的 `LLM.call` 没有 `cost_stage` 参数，传进去会 TypeError。
  `stage=` 所有版本都认，且 V2.2.9+ 的 `cost_stage or stage` 会用它兜底。

★ 安全性核对（不是拍脑袋）：`ing` / `manifest` / `playbook_llm_feedback`
  等新名字在**两个配置**（`dgtf_config.yaml`、`configs/道生专属模式.yaml`）
  的 `api.thinking.stages` 里都**未声明** ⇒ `thinking_stages.get(name)` 返回
  None ⇒ 仍掉回 `default`，与现在（stage=None）**逐字等价**。
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V2 = ROOT / "dgtf_engine" / "dgtf_v2"
SRC = V2 / "engine" / "Meta-DGTF-V2.2.9.py"
DST = V2 / "engine" / "Meta-DGTF-V2.2.10.py"


def die(msg: str) -> None:
    print("❌ " + msg)
    sys.exit(1)


# ───────────────────────── 1. 引擎主文件 ─────────────────────────
raw = SRC.read_bytes()
if raw.count(b"\r\n") != raw.count(b"\n"):
    die("引擎源文件不是纯 CRLF")
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
    print(f"  ✓ 引擎 {old[:56]!r} → 已替换")


sub1('__version__ = "2.2.9"', '__version__ = "2.2.10"')
sub1("Meta-DGTF-道生三阶模型 · V2.2.9", "Meta-DGTF-道生三阶模型 · V2.2.10")
sub1("★ V2.2.9 补丁（补上成本归因的第二个盲区）：新增独立 cost_stage 参数。",
     "★ V2.2.10 补丁（补上成本归因的第三批盲区）：7 处调用点补 stage。\n"
     "     V2.2.9 只修了「传了变量但值是 None」；打点抓栈又抓到 7 处**根本没传**\n"
     "     （引擎 3 处 `_call_long` + 模块 4 处 `llm.call`）。根因是**判据范围不够**：\n"
     "     原 AST 审计只扫主文件、只扫 `*.call(` ⇒ 报「0 处缺失」而产物仍有盲区。\n"
     "★ V2.2.9 补丁（补上成本归因的第二个盲区）：新增独立 cost_stage 参数。")

# `_ing`（两处）与 `_manifest`（一处）
sub1('''            text, trunc = self._call_long(
                system, user, 0.7, 4000, model=self.llm.reasoner_model,
                thinking=self.llm.thinking_reasoner)''',
     '''            text, trunc = self._call_long(
                system, user, 0.7, 4000, model=self.llm.reasoner_model,
                thinking=self.llm.thinking_reasoner, stage="ing")''')
sub1('''                text, trunc = self._call_long(system, user, 0.7, 4000)''',
     '''                text, trunc = self._call_long(system, user, 0.7, 4000,
                                              stage="ing")''')
sub1('''            out, trunc = self._call_long(
                system, user, 0.7, 2500, model=self.llm.reasoner_model,
                thinking=self.llm.thinking_reasoner)''',
     '''            out, trunc = self._call_long(
                system, user, 0.7, 2500, model=self.llm.reasoner_model,
                thinking=self.llm.thinking_reasoner, stage="manifest")''')

out = text.replace("\n", "\r\n").encode("utf-8")
if b"\r\r\n" in out:
    die("引擎写出内容含 \\r\\r\\n")
DST.write_bytes(out)
chk = DST.read_bytes()
if chk.count(b"\r\n") != chk.count(b"\n"):
    die("引擎目标不是纯 CRLF")
try:
    ast.parse(chk.decode("utf-8"))
except SyntaxError as e:
    die(f"引擎语法错误：{e}")
print(f"✅ {DST.name} 生成：{chk.count(b'\n') + 1} 行，纯 CRLF，语法 OK")

# ───────────────────────── 2. 共用模块（跨版本） ─────────────────────────
def patch_module(rel: str, pairs) -> None:
    p = V2 / rel
    b = p.read_bytes()
    crlf = b.count(b"\r\n")
    pure_crlf = (crlf == b.count(b"\n"))
    t = b.decode("utf-8")
    t = t.replace("\r\n", "\n")
    for old, new in pairs:
        n = t.count(old)
        if n != 1:
            die(f"{rel} 锚点命中 {n} 次（应为 1）：{old[:60]!r}")
        t = t.replace(old, new)
    nl = "\r\n" if pure_crlf else "\n"
    o = t.replace("\n", nl).encode("utf-8")
    if b"\r\r\n" in o:
        die(f"{rel} 写出内容含 \\r\\r\\n")
    p.write_bytes(o)
    try:
        ast.parse(o.decode("utf-8"))
    except SyntaxError as e:
        die(f"{rel} 语法错误：{e}")
    print(f"  ✓ {rel} 已补 stage（{'CRLF' if pure_crlf else 'LF'} 保持）")


patch_module("llm_feedback.py", [(
    "        raw = llm.call(SYSTEM, user, 0.2, 1200, json_mode=True)",
    '        raw = llm.call(SYSTEM, user, 0.2, 1200, json_mode=True,\n'
    '                       stage="playbook_llm_feedback")')])

#: multi_turn 用 `**kw`：直接加关键字会与调用方传的 stage 撞（TypeError）
#: ⇒ 用 setdefault，调用方显式给了就尊重调用方。
patch_module("multi_turn.py", [
    ("    hist = list(history or [])\n    out = []\n    for user in (turns or []):\n"
     "        text = llm.call(system, str(user), history=hist, **kw)",
     "    hist = list(history or [])\n    out = []\n"
     "    kw.setdefault(\"stage\", \"multi_turn\")\n    for user in (turns or []):\n"
     "        text = llm.call(system, str(user), history=hist, **kw)"),
    ("    hist = list(history or [])\n    trace = []\n"
     "    for _ in range(max(1, int(max_rounds))):\n"
     "        msg = llm.call(system, str(user), history=hist, tools=tools,\n"
     "                       return_message=True, **kw)",
     "    hist = list(history or [])\n    trace = []\n"
     "    kw.setdefault(\"stage\", \"multi_turn_tool\")\n"
     "    for _ in range(max(1, int(max_rounds))):\n"
     "        msg = llm.call(system, str(user), history=hist, tools=tools,\n"
     "                       return_message=True, **kw)"),
])

patch_module("vision_input.py", [(
    "        return str(llm.call(system, user, 0.2, max_tokens,\n"
    "                            model=model, images=bs) or \"\")",
    "        return str(llm.call(system, user, 0.2, max_tokens,\n"
    "                            model=model, images=bs,\n"
    "                            stage=\"vision_input\") or \"\")")])

# ───────────────────────── 3. 收尾自检：全量重扫 ─────────────────────────
eng_dir = V2 / "engine"


def ver(p: Path):
    m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


eng = sorted(eng_dir.glob("Meta-DGTF-V*.py"), key=ver)[-1]
files = [eng] + sorted(V2.glob("*.py"))
miss = []
for f in files:
    if f.name.startswith("tests"):
        continue
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("call", "_call_long"):
            ks = {k.arg for k in node.keywords if k.arg}
            if "stage" not in ks and "cost_stage" not in ks:
                miss.append((f.name, node.lineno, node.func.attr))
print("─" * 60)
if miss:
    die(f"重扫仍有 {len(miss)} 处缺 stage：{miss[:8]}")
print(f"✅ 全量重扫（主文件 {eng.name} + 全部模块 × call/_call_long）：0 处缺 stage")
