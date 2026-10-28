# -*- coding: utf-8 -*-
"""补丁：V2.2.6 → V2.2.7（答案门：答案是否针对本题 + 跨视角一致性警示）。

背景（实测见 docs/产物质量分析_20261028.md）：
  就绪门拦得住「空」，拦不住「偏」。三个反例都 answer_ready=True：
    · 心率题 → 答了定义，coverage 1.00
    · HTTP 503 → 答成 Retry-After 头，coverage 0.90
    · HTTP 301 → 答「指定网址的方式」，coverage 0.50

改动：
  1) 标题/__version__ → 2.2.7；docstring 增段
  2) DEFAULT_CONFIG.output.answer_gates = {enabled: True, block: False}
     ★ 默认 block=False ⇒ **只留痕，不改 answer_ready**（零行为差）
  3) 产物落 quality.answer_gates（纯增量键）
  4) 打开 block 时把 answer_ready 降级并写原因（可审计）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENG = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
SRC = ENG / "Meta-DGTF-V2.2.6.py"
DST = ENG / "Meta-DGTF-V2.2.7.py"

EDITS = [
    ("标题版本",
     "Meta-DGTF-道生三阶模型 · V2.2.6",
     "Meta-DGTF-道生三阶模型 · V2.2.7"),
    ("版本号",
     '__version__ = "2.2.6"',
     '__version__ = "2.2.7"'),
    ("docstring 增段",
     "★ V2.2.6 补丁（opt-in，默认关 ⇒ 不打开时逐字行为不变）：失败熔断。",
     "★ V2.2.7 补丁（新增读数，默认不改判定）：答案门 answer_gates。\n"
     "  就绪门拦得住「空」，拦不住「偏」—— 实测三个反例都 answer_ready=True：\n"
     "  心率题答了定义（coverage 1.00）、HTTP 503 答成 Retry-After 头（0.90）、\n"
     "  HTTP 301 答「指定网址的方式」（0.50）。coverage 是子问题作答率，不是正确性。\n"
     "  新增 `dgtf_v2/answer_gates.py`（纯函数，可离线复算）：按题型分叉校验\n"
     "  「答案是否针对本题」，并把跨视角一致性 α 作为**警示而非阻断**（α 低是三层\n"
     "  真实分歧，不等于答案错；实测拿它阻断会误杀 108 个正确答案）。\n"
     "  `output.answer_gates = {enabled, block}`：enabled 默认 true（只写\n"
     "  quality.answer_gates 留痕），block 默认 false（不动 answer_ready）。\n"
     "  ⇒ 默认跑次逐字行为不变，只多一个读数键。\n\n"
     "★ V2.2.6 补丁（opt-in，默认关 ⇒ 不打开时逐字行为不变）：失败熔断。"),
    ("默认配置增键",
     '        "self_check": True,\n        "show_probe_diag": False,',
     '        "self_check": True,\n'
     '        "show_probe_diag": False,\n'
     '        # ★ [答案门] 答案是否**针对本题**（+ 跨视角一致性警示）。\n'
     '        #   enabled=true 只写读数 `quality.answer_gates`（纯增量，不改判定）；\n'
     '        #   block=false 默认不降级 —— 打开后 relevance 不过才把 answer_ready\n'
     '        #   置 false 并写原因。★ agreement（α 低）**永远只警示不阻断**：\n'
     '        #   α 低是三层真实认知分歧，不是答案错的证据。\n'
     '        "answer_gates": {"enabled": True, "block": False},'),
    ("产物落读数 + 可选降级",
     '            _q0.update({"answer_ready": bool(_dt0.get("answer_ready")),\n'
     '                        "raw_answer_ready": bool(_dt0.get("raw_answer_ready")),\n'
     '                        "process_ready": bool(_dt0.get("process_ready")),\n'
     '                        "answer_quality": _dt0.get("answer_quality"),\n'
     '                        "answer_summary": _asum0,\n'
     '                        "depth": _depth0})',
     '            _q0.update({"answer_ready": bool(_dt0.get("answer_ready")),\n'
     '                        "raw_answer_ready": bool(_dt0.get("raw_answer_ready")),\n'
     '                        "process_ready": bool(_dt0.get("process_ready")),\n'
     '                        "answer_quality": _dt0.get("answer_quality"),\n'
     '                        "answer_summary": _asum0,\n'
     '                        "depth": _depth0})\n'
     '            # ★ [答案门] 答案是否针对本题。纯函数、零 LLM。\n'
     '            #   默认只留痕（block=false）⇒ 不改任何既有判定；\n'
     '            #   打开 block 才把 relevance 不过的跑次降级。\n'
     '            try:\n'
     '                _agc = (self.config.get("output") or {}).get(\n'
     '                    "answer_gates")\n'
     '                if not isinstance(_agc, dict):\n'
     '                    _agc = {}\n'
     '                if bool(_agc.get("enabled", True)):\n'
     '                    from dgtf_v2.answer_gates import (\n'
     '                        evaluate as _ag_eval,\n'
     '                        should_block as _ag_block,\n'
     '                        block_reason as _ag_why)\n'
     '                    _ag = _ag_eval(str(packed.get("question") or ""),\n'
     '                                   str(_asum0.get("answer") or ""),\n'
     '                                   _q0.get("tri_alpha"),\n'
     '                                   str(_dt0.get("question_type") or ""))\n'
     '                    _q0["answer_gates"] = _ag\n'
     '                    if bool(_agc.get("block", False)) and _ag_block(_ag):\n'
     '                        _dt0["answer_ready"] = False\n'
     '                        _dt0["answer_ready_reason"] = _ag_why(_ag)\n'
     '                        _asum0["answer_ready"] = False\n'
     '                        _q0["answer_ready"] = False\n'
     '                        logger.info("[答案门] 降级：%s", _ag_why(_ag))\n'
     '            except Exception as _age:\n'
     '                logger.warning("答案门计算失败（不影响主流程）：%s", _age)'),
]


def main() -> int:
    raw = SRC.read_bytes()
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    assert crlf == lf, f"源不是纯 CRLF: {crlf} vs {lf}"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for i, (name, old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        assert n == 1, f"[{i}] {name}: 命中 {n} 次（要求 1）"
        text = text.replace(old, new, 1)
        print(f"  [{i}] OK {name}")
    DST.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    chk = DST.read_bytes()
    c2, l2 = chk.count(b"\r\n"), chk.count(b"\n")
    assert c2 == l2, f"输出不是纯 CRLF: {c2} vs {l2}"
    assert chk.count(b"\r\r\n") == 0
    assert b'"2.2.7"' in chk
    print(f"\n写出 {DST.name}: {len(chk)} bytes / {c2} 行 / 纯 CRLF OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
