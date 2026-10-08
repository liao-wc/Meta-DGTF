# -*- coding: utf-8 -*-
"""[v1.23.2] 修 P2.4.a 的变异体样例（两个真因）+ 去掉 DEBUG。

真因 1：`_MUT` 里把**视角**写成了裸字符串（`"[外] …"`）。
  `_triage_suggestions(und_aspects, …)` 内部是 `for _a in (und_aspects or [])`
  —— 传字符串会**逐字符迭代**，于是每条都是单字、全被判为非候选 ⇒ 恒 []。
  ⇒ 变异体永远「不判红」，判据假绿。（第一版即此。）
真因 2：「真·自指」样例 `"此时此处的最优方案本身（自指…）"` **不是 triage 候选**
  （没有 `[外]` 前缀、也没有语义关键词）⇒ 拦它的是 `_is_triage_candidate` 那条，
  而不是 `_is_never_downgrade` ⇒ **抠掉 never-downgrade 判据它照样不触发**，
  变异体测不到东西。
  ⇒ 正确样例必须**同时**是候选又是自指：`"[外] 该方案是否自指（无共同参照系）"`。
"""
import ast
from pathlib import Path

P = Path("_v122_verify.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

# ---- 0 去 DEBUG ----
s = s.replace('''            import os as _os
            print("DEBUG mut", _k, "count=", txt.count(_o),
                  "file=", str(_mp), "exists=", _mp.is_file(),
                  "cwd=", _os.getcwd(), "asp=", repr(_asp)[:40],
                  "anc=", repr(_anc)[:70])
''', "")
s = s.replace('''                import inspect as _ins
                _srcf = _ins.getsource(_mm._triage_suggestions)
                print("DEBUG mut src has if True:",
                      "                     if True" in _srcf,
                      "| tiers of anc:", [x.get("tier") for x in _anc])
                print("DEBUG hit_answers:", _mm._hit_by_answers(_asp, ["上游是否有官方标准"]),
                      "| cand:", _mm._is_triage_candidate(_asp),
                      "| never:", _mm._is_never_downgrade(_asp))
''', "")

# ---- 1 自指样例改成「既是候选又是自指」----
O1 = '''        _n1 = _tq(["此时此处的最优方案本身（自指，无共同参照系）"],
                  [{"id": "X1", "tier": 1, "claim": "最优方案本身"}])'''
N1 = '''        # ★ 样例必须**同时**是「triage 候选」和「真·自指」：
        #   否则拦它的是 `_is_triage_candidate` 那条，`_is_never_downgrade`
        #   那条判据的变异体就测不到东西（第一版用「最优方案本身…」就是这样）。
        _n1 = _tq(["[外] 该方案是否自指（无共同参照系）"],
                  [{"id": "X1", "tier": 1,
                    "answers": ["该方案是否自指（无共同参照系）"]}])'''
assert s.count(O1) == 1, "n1 锚点命中 %d 次" % s.count(O1)
s = s.replace(O1, N1)

# ---- 2 _MUT 的两个样例都改成**列表**（并同步自指样例）----
O2 = '''        _MUT = (
            ("tier 门",
             '                     if int(x.get("tier", 3) or 3) <= _floor',
             "                     if True",
             ("[外] 上游是否有官方标准",
              [{"id": "X1", "tier": 4, "answers": ["上游是否有官方标准"]}])),
            ("自指剔除",
             "        if _is_never_downgrade(_a):" + chr(10) + "            continue",
             "        if False:" + chr(10) + "            continue",
             ("此时此处的最优方案本身（自指，无共同参照系）",
              [{"id": "X1", "tier": 1, "claim": "最优方案本身"}])),
        )'''
N2 = '''        # ★ 变异体样例里的「视角」必须是**列表**：`_triage_suggestions` 内部是
        #   `for _a in (und_aspects or [])`，传裸字符串会**逐字符迭代** ⇒
        #   全被判非候选 ⇒ 恒 [] ⇒ 变异体永不判红（第一版即此，属假绿）。
        _MUT = (
            ("tier 门",
             '                     if int(x.get("tier", 3) or 3) <= _floor',
             "                     if True",
             (["[外] 上游是否有官方标准"],
              [{"id": "X1", "tier": 4, "answers": ["上游是否有官方标准"]}])),
            ("自指剔除",
             "        if _is_never_downgrade(_a):" + chr(10) + "            continue",
             "        if False:" + chr(10) + "            continue",
             (["[外] 该方案是否自指（无共同参照系）"],
              [{"id": "X1", "tier": 1,
                "answers": ["该方案是否自指（无共同参照系）"]}])),
        )'''
assert s.count(O2) == 1, "_MUT 锚点命中 %d 次" % s.count(O2)
s = s.replace(O2, N2)

ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("已修两个真因并去 DEBUG")
