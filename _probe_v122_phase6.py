#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6 探针] 行为对照：`auto_plan` 收口前后的逐字段对比。

用法：
    python _probe_v122_phase6.py baseline --out _v122_phase6_baseline_before.json
    python _probe_v122_phase6.py baseline --out _v122_phase6_baseline_after.json
    diff -u ..._before.json ..._after.json     # 期望无差异

设计要点：
- **打桩**：把模块级 `LLM` 换成一个按 `stage` 返回固定 JSON 的桩，
  于是两版跑出来的 mode/rounds 可直接逐字比 —— 不做桩的话每次调用
  都是新抽样，对照毫无意义。
- 三个入口都测：`MetaDGTF._auto_plan(question)`（run() 用的就是它）、
  模块级 `auto_plan(question, cfg)`（两次调用路径）、以及若存在的
  `auto_plan(question, cfg, llm=...)`（收口后的单调用路径）。
- 另外把 `_rephrase_streak` 的**计算结果**记下来（不是记它怎么写），
  这样「收口」不会因为写法变了而漏过行为变化。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PLAN_JSON = ('{"mode": "serial", "rounds": {"0": 3, "1": 3, "both": 3, '
             '"all": 3}, "reason": "stub", "confidence": 0.8}')
ORI_JSON = '{"orientation": "decision", "reason": "stub", "confidence": 0.8}'
RES_JSON = ('{"route": ["0", "1"], "mode": "serial", "rounds": {"0": 3, "1": 3}, '
            '"max_calls": 0, "reason": "stub", "confidence": 0.8}')


class _StubLLM:
    """按 stage 返回固定 JSON 的桩；同时记下被调了几次。"""

    calls = []

    def __init__(self, cfg=None, *a, **k):
        self.cfg = cfg

    def call(self, system, user, *a, stage=None, **k):
        _StubLLM.calls.append(stage)
        if stage == "plan_orientation":
            return ORI_JSON
        if stage == "plan_resources":
            return RES_JSON
        return PLAN_JSON

    def parse_json(self, raw):
        return json.loads(raw)


class _View:
    def __init__(self, s=None):
        self._meta_idle_streak = s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="baseline")
    ap.add_argument("--src", default="元DGTF-V1.22.0-rc1.py")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    src = HERE / a.src
    spec = importlib.util.spec_from_file_location("dgtf_probe6", src)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_probe6"] = m
    spec.loader.exec_module(m)

    # 打桩：模块级 LLM 换成固定桩（一条都不能漏）
    m.LLM = _StubLLM
    cfg = json.loads(json.dumps(m.DEFAULT_CONFIG))

    Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？"
    out = {"src": a.src, "version": getattr(m, "__version__", "?"),
           "question": Q}

    # ① 方法入口（run() 用的）
    _StubLLM.calls = []
    try:
        inst = m.MetaDGTF(cfg)
        inst.llm = _StubLLM(cfg)
        out["A_method_auto_plan"] = inst._auto_plan(Q)
        out["A_stages"] = list(_StubLLM.calls)
    except Exception as e:  # noqa: BLE001
        out["A_method_auto_plan"] = f"{type(e).__name__}: {e}"

    # ② 模块级入口（两次调用路径，llm 不给）
    _StubLLM.calls = []
    try:
        r = m.auto_plan(Q, cfg)
        out["B_module_auto_plan"] = r
        out["B_stages"] = list(_StubLLM.calls)
    except Exception as e:  # noqa: BLE001
        out["B_module_auto_plan"] = f"{type(e).__name__}: {e}"

    # ③ 模块级入口（单调用路径，llm 给）—— 收口后才有
    _StubLLM.calls = []
    try:
        r2 = m.auto_plan(Q, cfg, llm=_StubLLM(cfg))
        out["C_module_auto_plan_with_llm"] = r2
        out["C_stages"] = list(_StubLLM.calls)
    except Exception as e:  # noqa: BLE001
        out["C_module_auto_plan_with_llm"] = f"{type(e).__name__}: {e}"
    finally:
        sys.modules.pop(getattr(m, "__file__", None) or "x", None)

    # ④ rephrase streak 的**计算结果**（两种写法应给出同一个数）
    f = getattr(m, "_compute_rephrase_streak", None)
    cases = [(_View(None), {"meta_idle_streak": 2}),
             (_View(3), {"meta_idle_streak": 1}),
             (_View(0), {}),
             (_View(None), None)]
    if f is None:
        # 收口前：按两处各自的写法算一遍，记录**结果**
        vals = []
        for v, st in cases:
            _mi = getattr(v, "_meta_idle_streak", 0)
            _mi = 0 if _mi is None else _mi
            vals.append(max(int((st or {}).get("meta_idle_streak", 0) or 0),
                            int(_mi or 0)))
        out["D_rephrase_streak"] = {"impl": "inline(两处各一份)", "values": vals}
    else:
        out["D_rephrase_streak"] = {
            "impl": "module-level _compute_rephrase_streak",
            "values": [f(v, st) for v, st in cases]}

    Path(a.out).write_bytes(json.dumps(out, ensure_ascii=False,
                                       indent=2, sort_keys=True).encode("utf-8"))
    print(f"probe -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
