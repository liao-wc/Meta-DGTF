# -*- coding: utf-8 -*-
"""[v1.23.2] 同步两处**过时判据**（不是放宽，是改到新语义）。

1. `_probe_v123_w2.py` 的变异体 M2：本版在 W# 进表那块中间插了 tier 门 ⇒
   原来「从 `if getattr(pool, "web_as_evidence"...` 到 `break`」的连续锚不再
   连续，命中 0 次。改成**尾段锚**（`_wi += 1` 到 `break`），变异体改 `pass`。
2. `_probe_v1231_left.py` 的 L4（空票留痕）：本版加了**空票重试**（默认 1 次），
   桩在重试时会成功 ⇒ 不再产生空票。要把「空票必须留痕」这条钉住，
   必须显式把 `tri_vote_retry_empty` 置 0（= 退回 v1.23.1 那条路径），
   并**另加**一条「默认重试会救回来」的正向判据。
"""
import ast
from pathlib import Path

# ---------------- 1 W2 探针的 M2 锚点 ----------------
P = Path("_probe_v123_w2.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")
OLD = """            ("M2 W# 进表",
             '    if getattr(pool, "web_as_evidence", False):\\n'
             '        _wi = 0\\n'
             '        for _w in (getattr(pool, "web_results", None) or []):\\n'
             '            if not str((_w or {}).get("claim", "")).strip():\\n'
             '                continue\\n'
             '            _wi += 1\\n'
             '            out.append((str(_w.get("id") or ("W" + str(_wi))),\\n'
             '                        str(_w.get("claim", ""))[:120]))\\n'
             '            if _wi >= 20:\\n'
             '                break\\n', ""),"""
NEW = """            # ★ [v1.23.2] 锚点改为**尾段**：本版在这块中间插了 W# tier 门
            #   ⇒ 原来从 `if getattr(pool, ...)` 到 `break` 的连续锚已不连续
            #   （命中 0 次）。变异体改 `pass`：删掉 append 后 W# 同样进不了
            #   引用表，M2 的判据意图（「W# 有没有进表」）一字未改。
            ("M2 W# 进表",
             '            _wi += 1\\n'
             '            out.append((str(_w.get("id") or ("W" + str(_wi))),\\n'
             '                        str(_w.get("claim", ""))[:120]))\\n'
             '            if _wi >= 20:\\n'
             '                break\\n',
             '            pass\\n'),"""
n = s.count(OLD)
assert n == 1, "W2 的 M2 锚点命中 %d 次" % n
s = s.replace(OLD, NEW)
ast.parse(s)
P.write_bytes(s.encode("utf-8"))
print("1) W2 探针 M2 锚点已改为尾段")

# ---------------- 2 left 探针的 L4 ----------------
Q = Path("_probe_v1231_left.py")
t = Q.read_bytes().decode("utf-8").replace("\r\n", "\n")

O2 = """def _adj(empty):
    o = object.__new__(mod.MetaDGTF)
    o.llm = _LLM3(empty)
    o.config = _cfg(enabled=False)"""
N2 = """def _adj(empty, retry=0):
    # ★ [v1.23.2] 本版默认**空票重试 1 次**；要复现「空票无声」那条旧路径，
    #   必须显式把 `tri_vote_retry_empty` 置 0（= v1.23.1 行为）。
    o = object.__new__(mod.MetaDGTF)
    o.llm = _LLM3(empty)
    o.config = _cfg(enabled=False)
    o.config["actions"] = {"tri_vote_retry_empty": retry}"""
assert t.count(O2) == 1, "L4 _adj 锚点命中 %d 次" % t.count(O2)
t = t.replace(O2, N2)

O3 = """_o9, _ = _adj(99)                      # 三票都正常"""
N3 = """_o9, _ = _adj(99)                      # 三票都正常
_o10, _s10 = _adj(1, retry=1)          # [v1.23.2] 默认重试 1 次
ck("L4.6 ★ 默认重试：空票重试一次就救回来 → 3 票可用、不报空票",
   len(_s10[0].get("votes") or []) == 3
   and not any("票可用" in str(x) for x in _o10.pools["1"].meta),
   repr([v["label"] for v in _s10[0].get("votes") or []]))"""
assert t.count(O3) == 1
t = t.replace(O3, N3)
ast.parse(t)
Q.write_bytes(t.encode("utf-8"))
print("2) left 探针 L4 已适配空票重试（+L4.6）")
