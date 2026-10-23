#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段2c] 修 `DecidabilityFreeze` 的一个真漏洞：翻 `_frozen_answerable` 不判红。

怎么发现的：**探针**（不是读代码）。`_probe_v122_phase2.py` 的 C_freeze
做了三类篡改，第三类「signature 手改」（只翻布尔、不动标签）返回
`未判红（漏洞）`。任务书 Step 3.3 的冒烟标的正是这一刀。

根因：`_canon` 里 `is_answerable` 是**由当前标签现推**的
（`bool(_lab in _DEC_ANSWERABLE)`），所以标签不动时签名恒定 ——
被冻结那个布尔本身根本没进签名，它只是个没人读的副本。

改法（加性）：
1. `_canon` 记录**五元组**：id / 当前标签 / 当前可答性 / 冻结布尔 / 冻结标签。
2. `freeze` 先写 `_frozen_decidability` + `_frozen_answerable` + `_decided_answerable`，
   **再**算 `self.items` —— 顺序反了会导致「刚冻结就验不过」。
   （原来的 freeze 压根没写 `_frozen_decidability`，一并补上。）
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

OLD_CANON = """    def _canon(self, pool) -> List[List[object]]:
        out: List[List[object]] = []
        for s in (getattr(pool, "sub_questions", None) or []):
            _lab = str(s.get("decidability", "") or "")
            out.append([str(s.get("id", "")), _lab,
                        bool(_lab in _DEC_ANSWERABLE)])
        return out
"""

NEW_CANON = """    def _canon(self, pool) -> List[List[object]]:
        \"\"\"签名条目 = 五元组：id / 当前标签 / 当前可答性 / 冻结布尔 / 冻结标签。

        ★ 走过的弯路：早先这里只记 `[id, 当前标签, 由标签现推的可答性]`。
          于是「只把 `_frozen_answerable` 翻过来、标签不动」改不动签名 ——
          被冻结的那个布尔**根本没进签名**，它只是个没人读的副本。
          任务书 Step 3.3 的冒烟标的正是这一刀；探针实测返回「未判红」。
          教训：签名要覆盖**被冻结的每一格**，不能覆盖「能从别的格推出来的
          那一格」—— 后者等于没签。
        \"\"\"
        out: List[List[object]] = []
        for s in (getattr(pool, "sub_questions", None) or []):
            _lab = str(s.get("decidability", "") or "")
            _fz_b = s.get("_frozen_answerable", None)
            _fz_l = s.get("_frozen_decidability", None)
            out.append([str(s.get("id", "")), _lab,
                        bool(_lab in _DEC_ANSWERABLE),
                        None if _fz_b is None else bool(_fz_b),
                        None if _fz_l is None else str(_fz_l)])
        return out
"""

OLD_FREEZE = """    def freeze(self, pool, layer: int = 1) -> str:
        self.layer = int(layer)
        self.items = self._canon(pool)
        self.n = len(self.items)
        for s in (getattr(pool, "sub_questions", None) or []):
            _ans = bool(s.get("decidability") in _DEC_ANSWERABLE)
            s["_frozen_answerable"] = _ans
"""

NEW_FREEZE = """    def freeze(self, pool, layer: int = 1) -> str:
        self.layer = int(layer)
        # ★ 顺序：**先写冻结键、再算 items**。反过来（先算后写）会让
        #   `_canon` 在冻结那一刻记下 None，之后 verify 立刻不匹配 ——
        #   「刚冻结就验不过」这种症状极难往顺序上想。
        for s in (getattr(pool, "sub_questions", None) or []):
            _ans = bool(s.get("decidability") in _DEC_ANSWERABLE)
            s["_frozen_decidability"] = str(s.get("decidability", "") or "")
            s["_frozen_answerable"] = _ans
"""

OLD_FREEZE_TAIL = """        self.frozen_at = datetime.now().isoformat()
        self.signature = self._digest(self.layer, self.items)
        return self.signature
"""

NEW_FREEZE_TAIL = """        self.items = self._canon(pool)
        self.n = len(self.items)
        self.frozen_at = datetime.now().isoformat()
        self.signature = self._digest(self.layer, self.items)
        return self.signature
"""

REPS = [
    ("canon", OLD_CANON, NEW_CANON, 1),
    ("freeze_head", OLD_FREEZE, NEW_FREEZE, 1),
    ("freeze_tail", OLD_FREEZE_TAIL, NEW_FREEZE_TAIL, 1),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段2c 补丁完成；行数 {len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
