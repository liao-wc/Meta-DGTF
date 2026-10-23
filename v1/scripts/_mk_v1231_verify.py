# -*- coding: utf-8 -*-
"""[v1.23.1] 给 `_v122_verify.py` 加验收档 `v123_w6`（幂等）。

哨兵用**最后一项**注册串（上一版踩过：用第一项当哨兵会在「已注册 w1、
要补 w2~w5」时静默跳过注册 ⇒ 新档以 `PASS 5/FAIL 0` 假绿）。
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_v122_verify.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

SENTINEL = '"v123_w6": phase_v123_w6'
if SENTINEL in s:
    print("已注册 v123_w6，跳过")
    sys.exit(0)

NEW = '''def phase_v123_w6(src, mod):
    """[v1.23.1 遗留收尾] 真圈号 + tier 提案 + 三场景/正交度 + P2.4 复真。

    判据在 `_probe_v1231_left.py`（24 条，含 3 变异体）；这里只补
    「产物级」的三条：P2.4 的三题产物必须由**本版**产出、分析文件在。
    """
    import json as _json
    _run_probe("_probe_v1231_left.py", src)
    check("L1.rep", (HERE / "v1231_报告.md").is_file(), "v1231_报告.md 存在")
    _jf = HERE / "_v1230_w6_runs.json"
    check("L1.json", _jf.is_file(), "_v1230_w6_runs.json 存在")
    if _jf.is_file():
        _d = _json.loads(_jf.read_text(encoding="utf-8"))
        _want = Path(src).name
        check("L1.src ★ 跑批产物出自本版（不是旧版的陈旧读数）",
              _d.get("src") == _want,
              "跑批 src=%r，本版=%r" % (_d.get("src"), _want))
        _runs = [r for r in (_d.get("runs") or []) if r.get("ok")]
        check("L1.n 跑数 ≥ 9（3 题 × (1 OFF + 2 ON)）", len(_runs) >= 9,
              "成功跑 %d 条" % len(_runs))
        _on = [r for r in _runs if r.get("arm") == "ON"]
        _off = [r for r in _runs if r.get("arm") == "OFF"]
        check("L1.arm 两臂都在", bool(_on) and bool(_off),
              "ON %d / OFF %d" % (len(_on), len(_off)))
        # 负对照：OFF 臂零检索（默认关 = 零调用）
        check("L1.off0 ★ 负对照：OFF 臂 web_n 全 0 且 gate 零调用",
              all((r.get("web_n") or 0) == 0
                  and ((r.get("gate") or {}).get("run_total") or 0) == 0
                  for r in _off),
              repr([(r.get("tag"), r.get("web_n")) for r in _off]))
        # ON 臂真的走了真圈号（round_kind 只能是 in；前置的 pre 也应有）
        _kinds = sorted({k for r in _on for k in (r.get("web_round_kinds") or [])})
        check("L1.kind ON 臂留痕 round_kind 合法",
              all(k in ("pre", "in") for k in _kinds), repr(_kinds))
        _it = [x for r in _on for x in (r.get("web_items") or [])]
        check("L1.pair ★ round_kind 与 round 自洽（pre ⟺ 0；in ⟹ ≥1）",
              bool(_it) and all(
                  (int(x.get("round", -1)) == 0)
                  if str(x.get("round_kind")) == "pre"
                  else int(x.get("round", -1)) >= 1
                  for x in _it),
              repr([(x.get("round"), x.get("round_kind")) for x in _it][:6]))
    _ana = HERE / "_v1230_w6_analysis.md"
    check("L1.ana", _ana.is_file(), "_v1230_w6_analysis.md 存在")
    if _ana.is_file():
        _t = _ana.read_text(encoding="utf-8")
        check("L1.ana2 分析含「命中率」与「组间/组内」两段",
              "命中率" in _t and "组内" in _t, "")
    # P2.4 的判据锚：三题产物必须存在（由本版跑批产出）
    for _i in (1, 2, 3):
        _dd = HERE / "outputs" / ("p2_run%d" % _i)
        _mds = sorted(_dd.glob("*.md")) if _dd.is_dir() else []
        check("L1.p24.%d" % _i, bool(_mds), "p2_run%d 有产物" % _i)


'''

A = "PHASES = {"
assert s.count(A) == 1, "PHASES 锚点 %d 次" % s.count(A)
s = s.replace(A, NEW + A)

O = '          "v123_w5": phase_v123_w5}'
assert s.count(O) == 1, "注册锚点 %d 次" % s.count(O)
s = s.replace(O, '          "v123_w5": phase_v123_w5,\n'
                 '          "v123_w6": phase_v123_w6}')

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
ast.parse(s)
print("已加并注册 phase_v123_w6")
