# -*- coding: utf-8 -*-
"""[v1.23.3] 思考 A/B：加 `--from-capture`（跳过录播，直接用存档的真实输入）。

为什么需要：真跑**走不到**全部 stage（`_decompose_normal/hybrid/koan` 由池的
三态状态分派、`_ask_missing_polarity` / `_check_structure_saturation` 要特定
条件）。对这些「接线了但这跑走不到」的环节，改用 `_ab_thinking_direct.py`
**直接驱动方法本身**（走的是同一段 prompt 构造 + 同一个 `llm.call(stage=…)`），
把真实输入写进同一个 capture 存档，再统一回放。

★ 「有接线」≠「这跑走得到」—— 本项目反复强调过。
"""
from pathlib import Path
import ast

P = Path("_ab_thinking_v1233.py")
s = Path(P).read_text(encoding="utf-8")

O = '''    by_stage: dict = {}
    for c in rec_calls:'''
N = '''    by_stage: dict = {}
    if "--from-capture" in sys.argv:
        # ★ 用存档的真实输入（含 `_ab_thinking_direct.py` 直接驱动来的），
        #   不再跑流程 —— 回放本身才是花钱的部分，录播不重复。
        _cp = HERE / "_v1233_think_capture.json"
        if _cp.is_file():
            for _st, _lst in (json.loads(_cp.read_text(encoding="utf-8"))
                              .get("stages") or {}).items():
                by_stage[_st] = [dict(x, stage=_st) for x in _lst]
        print("[think] --from-capture：载入 %d 个 stage 的真实输入"
              % len(by_stage), flush=True)
        rec_calls = [c for v in by_stage.values() for c in v]
    for c in rec_calls:'''
assert s.count(O) == 1, s.count(O)
s = s.replace(O, N)

# 载入后要按 N_IN 截断（原来在挑选逻辑里做，这里也要做）
O2 = '''    picked: dict = {}
    for st, lst in by_stage.items():'''
N2 = '''    picked: dict = {}
    for st, lst in by_stage.items():'''
assert s.count(O2) == 1

P.write_text(s, encoding="utf-8")
ast.parse(s)
print("已加 --from-capture")
