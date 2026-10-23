#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3 遗留2] **直接驱动**真跑走不到的 stage，录下它们的真实输入。

为什么：`stage=` 接线有 16 处，但一次真跑只能触达其中一部分：
  · `_decompose_normal` / `_decompose_hybrid` / `_decompose_koan` 由**池的
    三态状态**分派（decidable / partial / undecidable），跑一批题只落到一条；
  · `_ask_missing_polarity` / `_check_structure_saturation` 要特定条件。
★「有接线」≠「这跑走得到」—— 要测它们的思考档收益，就得**直接驱动方法**。

做法：把 `LLM.call` 包成**只记录 + 返回固定 JSON** 的桩，然后**调用真方法**
（走的是同一段 prompt 构造 + 同一个 `llm.call(stage=…)`）。
记录到的 (system, user, 温度, max_tokens, json_mode) 就是**真实输入**，
写进 `_v1233_think_capture.json` 的 `stages`（与流程录播**合并**）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.3.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
CAP = HERE / "_v1233_think_capture.json"

Q = ("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？"
     "怎么权衡？")
DEC = ["管网重现期的官方口径", "可改造的投资上限"]
UND = ["本市近十年内涝点的具体成因分布、各成因占比及空间分布无法获得",
       "缺少外部材料：旧城地下管线迁改的成本数据"]

FIX = (
    ("decompose_normal", "_decompose_normal", (Q, DEC, UND)),
    ("decompose_hybrid", "_decompose_hybrid", (Q, DEC, UND)),
    ("decompose_koan", "_decompose_koan", (Q,)),
    ("ask_missing_polarity", "_ask_missing_polarity",
     ([{"id": 1, "left": "重建管网", "right": "局部改造加海绵",
        "question": "排水系统怎么改"},
       {"id": 2, "left": "全量迁云", "right": "维持自建机房",
        "question": "政务系统往哪放"}],)),
    ("check_structure_saturation", "_check_structure_saturation",
     (["印记一：管网能力不足与低洼汇水叠加",
       "印记二：调蓄与扩容必须同步"],
      ["印记三：投资上限未定"])),
)


def main() -> int:
    spec = importlib.util.spec_from_file_location("dgtf_direct1233", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_direct1233"] = m
    spec.loader.exec_module(m)

    rec: list = []
    _orig = m.LLM.call

    def _patched(self, system, user, temperature=0.6, max_tokens=3000,
                 json_mode=False, model=None, thinking=None, stage=None):
        rec.append({"stage": stage, "system": system, "user": user,
                    "temperature": temperature, "max_tokens": max_tokens,
                    "json_mode": json_mode})
        # 固定桩回复：只为让方法**走完那一次调用**，不参与分析。
        if json_mode:
            return '{"sub_questions": [], "judgments": [], "items": [], ' \
                   '"actions": [], "not_do": []}'
        return "{}"

    m.LLM.call = _patched
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(HERE / "outputs" / "_v1233_think_cap_dir")
    cfg["output"]["verbose"] = False
    (HERE / "outputs" / "_v1233_think_cap_dir").mkdir(parents=True,
                                                      exist_ok=True)
    meta = m.MetaDGTF(cfg)
    print("[direct] MetaDGTF 构造完成", flush=True)
    # ★ 三个 `_decompose_*` 与 `_ask_missing_polarity` 挂在 **DGTF**（层对象）
    #   上，不在 MetaDGTF —— 「方法在哪个类」也要先 `grep` 再用。
    try:
        d0 = m.DGTF("0", meta.llm, cfg)
    except Exception as e:  # noqa: BLE001
        print("[direct] DGTF 构造失败：%s: %s" % (type(e).__name__, e),
              flush=True)
        d0 = None

    got: dict = {}
    for stage, meth, args in FIX:
        n0 = len(rec)
        _owner = d0 if (d0 is not None and hasattr(d0, meth)) else meta
        try:
            getattr(_owner, meth)(*args)
        except Exception as e:  # noqa: BLE001
            print("[direct] %-28s 抛错（可接受）：%s: %s"
                  % (stage, type(e).__name__, str(e)[:70]), flush=True)
        sel = [c for c in rec[n0:] if c.get("stage") == stage]
        if sel:
            got[stage] = sel[:2]
            print("[direct] %-28s ✓ 录到 %d 次调用（user %d 字）"
                  % (stage, len(sel), len(sel[0]["user"])), flush=True)
        else:
            print("[direct] %-28s ✗ 没有产生带 stage 的调用"
                  % stage, flush=True)
    m.LLM.call = _orig

    # 与已有存档**合并**（不覆盖）
    cur = {}
    if CAP.is_file():
        cur = json.loads(CAP.read_text(encoding="utf-8"))
    stages = cur.get("stages") or {}
    for k, v in got.items():
        stages[k] = [{"system": c["system"], "user": c["user"],
                      "temperature": c["temperature"],
                      "max_tokens": c["max_tokens"],
                      "json_mode": c["json_mode"]} for c in v]
    cur["src"] = SRC.name
    cur["stages"] = stages
    cur["direct"] = sorted(got)
    CAP.write_bytes(json.dumps(cur, ensure_ascii=False, indent=1)
                    .encode("utf-8"))
    print("[direct] 已合并进 %s：%d 个 stage（本次新增 %d）"
          % (CAP.name, len(stages), len(got)), flush=True)
    print("DIRECT_CAPTURE_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
