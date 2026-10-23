#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P8：把 CSD/发散/anytime 的计算挪到 `view.round_log` 赋值之后。

真跑暴露的第二个时序 bug：`_layer_csd_now(entry, view)` 在
`view.round_log = list(state.get("round_log") or [])` **之前**调用 ⇒ 收尾时
`view.round_log` 还是空的 ⇒ 逐圈序列为空 ⇒ **CSD / 发散三态 / anytime 下界
恒为空**（产物里那三行永远不出现，且不报错）。

★ 通则（与本轮「读数要进产物」同族）：
  **凡是「读逐圈序列」的计算，必须排在「序列被赋值」之后** ——
  顺序错了不报错，只是**永远算不出东西**（沉默失效）。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

BLOCK = '''        # ★ [CSD 早期预警] 逐圈序列读数（只算，不改行为）。
        try:
            self._layer_csd_now(entry, view)
        except Exception:
            pass
'''


def main():
    b = SRC.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
    s = b.decode("utf-8").replace("\r\n", "\n")
    assert s.count(BLOCK) == 1, s.count(BLOCK)
    s = s.replace(BLOCK, "", 1)

    anchor = '        view.round_log = list(state.get("round_log") or [])\n'
    assert s.count(anchor) == 1, s.count(anchor)
    s = s.replace(anchor, anchor + BLOCK, 1)

    ast.parse(s)
    SRC.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))

    s2 = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    i_rl = s2.find('view.round_log = list(state.get("round_log")')
    i_csd = s2.find("self._layer_csd_now(entry, view)")
    assert i_rl < i_csd, "挪位失败"
    assert s2.count("\r\r\n") == 0
    print("OK P8：CSD/发散/anytime 已排到 round_log 赋值之后（行 %d < %d）"
          % (s2[:i_rl].count("\n") + 1, s2[:i_csd].count("\n") + 1))


if __name__ == "__main__":
    main()
