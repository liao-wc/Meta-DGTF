#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段2b] 按**完整版**任务书回正阶段 2 的两处口径差。

任务书 Step 2.2 / 2.5 要求逐条写 `votes` / `agreement` / `stability`，
头部按 `stability` 统计 high/medium/low；我上一版写成 `_tri_*` 私有名 +
按 `tri_consensus` 渲染。名字不改，任务书自带的 `bench_calibrate.py`
（读 `it["votes"][i]["label"]`）就会在另一边静默拿到空表。

做法：**加别名不删旧名** —— `_tri_*` 继续供旧探针读，新名供任务书脚本读。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

# ------------------------------------------------ R1 逐条置信（任务书口径键名）
OLD_SUB = """            s["_tri_final"] = s["decidability"]
            s["_tri_level"] = level
            items.append({"sub_id": s.get("id", i),
                          "question": str(s.get("question", ""))[:160],
                          "votes": list(vs),
                          "final": s["decidability"],
                          "first_label": old, "level": level})
"""

NEW_SUB = """            s["_tri_final"] = s["decidability"]
            s["_tri_level"] = level
            # [v122 阶段2b] 任务书 Step 2.2 口径的逐条置信，与 `_tri_*`
            #   **并存**（别名不是冗余：旧探针 grep 前者，任务书自带的
            #   bench_calibrate.py 读后者；删任何一套都会让一边静默读空）。
            s["votes"] = [{"voter": vi, "label": v}
                          for vi, v in enumerate(vs)]
            s["agreement"] = round(top / len(vs), 2)
            s["stability"] = level
            if level == "low":
                # 无多数票 → 落 partial 并标 unstable（不落 undecidable：
                #   _DEC_ANSWERABLE 含 partial，落 und 会把分母砍一截）。
                s["unstable"] = True
            items.append({"sub_id": s.get("id", i),
                          "question": str(s.get("question", ""))[:160],
                          "votes": s["votes"],
                          "final": s["decidability"],
                          "first_label": old, "level": level})
"""

OLD_TAIL = """        self._tri_consensus = (high, med, low)
        self._tri_multi_items = items
"""

NEW_TAIL = """        self._tri_consensus = (high, med, low)
        self._tri_multi_items = items
        # [v122 阶段2b] 校准队列：只有 low 的那些条需要人工核。
        self._calibration_queue = [it for it in items
                                   if it.get("level") == "low"]
"""

# ------------------------------------------------------------ R2 头部按 stability
OLD_HDR = """            _fz = result.get("freeze") or {}
            _cons = result.get("tri_consensus") or []
            _sig = str(_fz.get("signature") or "")
            _cqn = len(result.get("calibration_queue") or [])
            if _cons or _sig:
                if len(_cons) == 3:
                    _cs = f"一致 {_cons[0]} / 多数 {_cons[1]} / 分裂 {_cons[2]}"
                else:
                    _cs = "（无多票记录）"
                f.write(f"**三态多票**（3 票）：{_cs}　"
                        f"**冻结**：sha256={_sig[:16]}…"
                        f"（{len(_sig)} 位）　校准队列 {_cqn} 条\\n\\n")
"""

NEW_HDR = """            _fz = result.get("freeze") or {}
            _cons = result.get("tri_consensus") or []
            _sig = str(_fz.get("signature") or "")
            _cqn = len(result.get("calibration_queue") or [])
            # [v122 阶段2b] 任务书 Step 2.5 口径：按逐条 `stability` 统计。
            _sq1 = ((result.get("pools") or {}).get("1") or {}).get(
                "sub_questions") or []
            _hi = sum(1 for s in _sq1 if s.get("stability") == "high")
            _me = sum(1 for s in _sq1 if s.get("stability") == "medium")
            _lo = sum(1 for s in _sq1 if s.get("stability") == "low")
            if _sq1:
                _rate = (_hi + _me) / max(1, len(_sq1))
                _flag = "" if _rate >= 0.5 else "　⚠️ unstable（＜50%）"
                f.write(f"**三态多票**：high {_hi} / medium {_me} / low {_lo}"
                        f"（共 {len(_sq1)} 条）　一致率 {_rate:.0%}{_flag}\\n")
            if _cons or _sig:
                if len(_cons) == 3:
                    _cs = (f"一致 {_cons[0]} / 多数 {_cons[1]} / "
                           f"分裂 {_cons[2]}")
                else:
                    _cs = "（无多票记录）"
                f.write(f"**三态多票**（3 票）：{_cs}　"
                        f"**冻结**：sha256={_sig[:16]}…"
                        f"（{len(_sig)} 位）　校准队列 {_cqn} 条\\n\\n")
"""

REPS = [
    ("sub_keys", OLD_SUB, NEW_SUB, 1),
    ("tail", OLD_TAIL, NEW_TAIL, 1),
    ("header", OLD_HDR, NEW_HDR, 1),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "主文件不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want} 次"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    import ast
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段2b 补丁完成；行数 {len(b.decode('utf-8').splitlines())} → "
          f"{len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
