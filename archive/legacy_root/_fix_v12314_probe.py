# -*- coding: utf-8 -*-
"""修 v1.23.14 探针的两处负对照（用 chr 拼转义，避开 heredoc 吃转义）。"""
import ast
from pathlib import Path

BS_N = chr(92) + "n"
NL = chr(10)
p = Path("_probe_v12314_hist.py")
s = p.read_text(encoding="utf-8")

OLD1 = ('    h0 = mod._auto_history(str(HERE / "__nope__"), 5, cfg=cfg0)' + NL +
        '    out["A_空目录n"] = h0["n"]' + NL +
        '    out["A_空目录不崩"] = h0["n"] == 0 and h0["cap_rounds"] == {}')
NEW1 = ('    h0 = mod._auto_history(str(HERE / "__nope__"), 5, cfg=cfg0)' + NL +
        '    out["A_空目录_无产物样本"] = not (h0["sources"].get("md")' + NL +
        '                                or h0["sources"].get("packed"))' + NL +
        '    # ★ 负对照：**关掉 md / 跑批两个源** ⇒ 只剩落 packed 的那 1 份' + NL +
        '    #   （说明样本量确实是靠扩源拿到的，不是别处兜来的）' + NL +
        '    _p = mod._auto_history("outputs", 200, cfg=cfg0,' + NL +
        '                           want_md=False, want_batch=False)' + NL +
        '    out["A_关掉两源后n"] = _p["n"]' + NL +
        '    out["A_关掉两源后来源"] = _p["sources"]')
assert s.count(OLD1) == 1, "负对照锚点 %d" % s.count(OLD1)
s = s.replace(OLD1, NEW1, 1)

OLD2 = '"**调度**：修行(4圈) → 研究(5圈) → 对元(6圈)' + BS_N + BS_N + '"'
NEW2 = '"**调度**：修行(4圈) → 研究(5圈) → 对撞(6圈)' + BS_N + BS_N + '"'
assert s.count(OLD2) == 1, "调度行锚点 %d" % s.count(OLD2)
s = s.replace(OLD2, NEW2, 1)

p.write_text(s, encoding="utf-8")
ast.parse(s)
print("探针两处已修")
