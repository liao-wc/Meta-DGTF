# -*- coding: utf-8 -*-
"""V2.2.10 -> V2.2.11

问题：answer_ready 有 3 个出口（quality / decision_trace / answer_summary），
      但 answer_ready_reason 只写进 decision_trace ⇒ 读 quality 的消费者
      （outputs 一致性护栏 / App 产物索引 / bench）永远看不见原因。
      实测 208 个产物包：answer_ready=False 的 85 个里，73 个 reason 只在
      decision_trace、quality 为空 ⇒ 「说不能答却不给原因」，护栏判红。

改动：
  1. docstring 标题 + __version__ 升到 V2.2.11；新增补丁说明段。
  2. 在「答案门」之后（最后一个能改 answer_ready 的位置）插入统一出口段：
     - 把 dt 的 reason 同步到 quality 与 answer_summary（三出口同源）；
     - 未就绪且 reason 仍空时，给出**可指认**的兜底原因（过程合同 / 原始就绪 /
       答案质量 / 题型），不留空、不写空话。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

SRC = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.10.py")
DST = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.11.py")

data = SRC.read_bytes()
crlf = data.count(b"\r\n")
lf = data.count(b"\n")
assert crlf == lf, "源文件不是纯 CRLF：crlf=%d lf=%d" % (crlf, lf)
src = data.decode("utf-8").replace("\r\n", "\n")
print("read: %s | lines=%d" % (SRC.name, src.count("\n") + 1))

edits = []

# ---- 1. 版本号：docstring 标题 ----
a = "Meta-DGTF-道生三阶模型 · V2.2.10"
b = "Meta-DGTF-道生三阶模型 · V2.2.11"
edits.append((a, b, 1))

# ---- 2. 版本号：__version__ ----
a = '__version__ = "2.2.10"'
b = '__version__ = "2.2.11"'
edits.append((a, b, 1))

# ---- 3. docstring 新增补丁段（插在 V2.2.10 段之前）----
a = "★ V2.2.10 补丁（补上成本归因的第三批盲区）：7 处调用点补 stage。"
b = (
    "★ V2.2.11 补丁（就绪原因的出口补齐 + 兜底）：`answer_ready_reason` 此前只写进\n"
    "     decision_trace，而 answer_ready 有 3 个出口 ⇒ 读 quality 的消费者（一致性\n"
    "     护栏 / App 产物索引 / bench）永远看不到「为什么没就绪」。实测 85 个未就绪\n"
    "     包里 73 个属于这种情况。现在三出口同源；且未就绪而原因仍空时，由过程合同 /\n"
    "     原始就绪 / 答案质量 / 题型 拼出**可指认**的原因，不留空。\n"
    "★ V2.2.10 补丁（补上成本归因的第三批盲区）：7 处调用点补 stage。"
)
edits.append((a, b, 1))

# ---- 4. 代码：答案门之后统一出口（最后一个能改 answer_ready 的位置）----
a = "            # ★ [Round 132] 验证语义拆分 + 告警分级 + 溯源指纹"
b = (
    "            # ★ [就绪原因出口] answer_ready 有 3 个出口（decision_trace / quality /\n"
    "            #   answer_summary），但 answer_ready_reason 此前只写进第一个 ⇒\n"
    "            #   读 quality 的消费者（一致性护栏 / App 产物索引 / bench）永远看不见\n"
    "            #   「为什么没就绪」。这里在**最后一个能改 answer_ready 的位置之后**\n"
    "            #   统一三出口，并对「未就绪且原因仍空」给出可指认的兜底原因。\n"
    "            _rr0 = str(_dt0.get(\"answer_ready_reason\") or \"\").strip()\n"
    "            if not _dt0.get(\"answer_ready\") and not _rr0:\n"
    "                _rr0 = (\"未就绪：过程合同=%s，原始就绪=%s，答案质量=%s，题型=%s\"\n"
    "                        % (\"通过\" if _process_ok else \"未通过\",\n"
    "                           \"是\" if _dt0.get(\"raw_answer_ready\") else \"否\",\n"
    "                           _dt0.get(\"answer_quality\") or \"未判定\",\n"
    "                           _dt0.get(\"question_type\") or \"未识别\"))\n"
    "            if _rr0:\n"
    "                _dt0[\"answer_ready_reason\"] = _rr0\n"
    "                _q0[\"answer_ready_reason\"] = _rr0\n"
    "                _asum0[\"answer_ready_reason\"] = _rr0\n"
    "            # ★ [Round 132] 验证语义拆分 + 告警分级 + 溯源指纹"
)
edits.append((a, b, 1))

for old, new, want in edits:
    got = src.count(old)
    assert got == want, "锚点命中 %d 次（期望 %d）：%r" % (got, want, old[:60])
    src = src.replace(old, new)
    print("  ok: %s" % old[:52].replace("\n", "\\n"))

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 \\r\\r\\n"
DST.write_bytes(out)
print("written: %s | lines=%d | CRLF=%d LF=%d"
      % (DST.name, out.count(b"\n") + 1, out.count(b"\r\n"), out.count(b"\n")))
assert out.count(b"\r\n") == out.count(b"\n"), "输出不是纯 CRLF"
print("PATCH OK")
