# -*- coding: utf-8 -*-
"""补两处：① 判据要真的驱动 `_auto_history`（M3 原先假绿）；② 修 M5 变异体锚点。"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── ① 判据补「历史加载器」正向 + 空目录负对照 ────────────────
SK = HERE / "smoke_test.py"
raw = SK.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = '''    if m._auto_dispatch_lines({}) != []:
        bad.append("没有 plan 时调度表不是空")
'''
NEW = '''    if m._auto_dispatch_lines({}) != []:
        bad.append("没有 plan 时调度表不是空")

    # ── G 历史**加载器**本身（★ 前面几组都是把 hist 直接喂进去，绕过了它
    #     —— 变异体「`_auto_history` 恒返回空」实测假绿，所以必须单独驱动）──
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        Path(td, "x.packed.json").write_text(_json.dumps({
            "llm_calls": 7, "llm_tokens": 123456, "tri_state": [1, 2],
            "views": {"1": {"stop_reason": "体力耗尽（被截断）", "rounds": 3}},
            "dispatch": {"_parallel_mode": "A"}, "cost_profile": "economy",
            "pools": {"1": {"web_results": [{"id": "W1"}], "web_errors": [],
                            "meta": ["[W-EMPTY] x"]}},
        }, ensure_ascii=False), encoding="utf-8")
        _h = m._auto_history(td)
    if _h.get("n") != 1:
        bad.append("历史加载器没读到样本（n=%r）" % _h.get("n"))
    if _h.get("tokens_med") != 123456:
        bad.append("历史 tokens 中位数读错：%r" % _h.get("tokens_med"))
    if _h.get("web_hit") != 1:
        bad.append("历史联网入池读数读错：%r" % _h.get("web_hit"))
    if _h.get("cut_rate") != 1.0:
        bad.append("历史截断率算错：%r" % _h.get("cut_rate"))
    if (_h.get("layer_rounds") or {}).get("1") != 3:
        bad.append("历史各层停圈读错：%r" % _h.get("layer_rounds"))
    if (_h.get("modes") or {}).get("A") != 1:
        bad.append("历史模式分布读错：%r" % _h.get("modes"))
    with _tf.TemporaryDirectory() as td:
        _h0 = m._auto_history(td)          # 负对照：空目录必须不崩、n=0
    if _h0.get("n") != 0:
        bad.append("空目录不该有样本（n=%r）" % _h0.get("n"))
    if m._auto_history(str(HERE / "__nope__")):
        pass                               # 路径不存在：只要不抛就算过
'''
assert s.count(OLD) == 1, "判据插入锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW, 1)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
ast.parse(out.decode("utf-8"))
SK.write_bytes(out)
print("判据已补：历史加载器正向 + 空目录负对照")

# ── ② 修 M5 变异体：整块替换两段式出口 ──────────────────────
MP = HERE / "_probe_v12313_mutants.py"
ms = MP.read_text(encoding="utf-8")
OLD5 = '''    "M5_两段式绕开装配器": (
        \'\'\'    return _assemble_plan(
        r.get("mode", "serial"), r.get("rounds", {}), cfg,
        route=r.get("route", list(_ROUTE_PRESETS["full"])),\'\'\',
        \'\'\'    return {
        "mode": r.get("mode", "serial"), "rounds": r.get("rounds", {}),
        "route": r.get("route", list(_ROUTE_PRESETS["full"])),\'\'\',
    ),'''
NEW5 = '''    "M5_两段式绕开装配器": (
        \'\'\'    return _assemble_plan(
        r.get("mode", "serial"), r.get("rounds", {}), cfg,
        route=r.get("route", list(_ROUTE_PRESETS["full"])),
        orientation=o["orientation"], max_calls=r.get("max_calls", 0),
        reason=_reason, confidence=r.get("confidence", 0.0),
        extra={"_orientation_reason": o.get("reason", ""),
               "cost_profile": prof})\'\'\',
        \'\'\'    return {
        "mode": r.get("mode", "serial"), "rounds": r.get("rounds", {}),
        "route": r.get("route", list(_ROUTE_PRESETS["full"])),
        "orientation": o["orientation"], "max_calls": r.get("max_calls", 0),
        "reason": _reason, "confidence": r.get("confidence", 0.0)}\'\'\',
    ),'''
assert ms.count(OLD5) == 1, "M5 锚点命中 %d 次" % ms.count(OLD5)
MP.write_text(ms.replace(OLD5, NEW5, 1), encoding="utf-8")
print("M5 变异体已修（整块替换）")
