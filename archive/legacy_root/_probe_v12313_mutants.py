# -*- coding: utf-8 -*-
"""v1.23.13 变异体：证明 check_v12313_auto_dispatch 有判别力。

M1 显式泄漏    ：explicit 分支改成「只要有显式就套到所有项」
M2 总开关失效  ：`_on = _auto_enabled(cfg)` → 恒 True
M3 历史不读    ：`_auto_history` 直接返回空 dict
M4 装配器被绕  ：单调用路径改回手写 dict（schema 分叉）
M5 两段式绕开  ：两段式出口改回手写 dict（schema 分叉）
M6 产物表不渲染：`_auto_dispatch_lines` 恒返回 []
M7 stop 策略空 ：`_auto_pick_stop` 恒返回 {}
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.13.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

MUTS = {
    "M1_显式泄漏": (
        '        if ex.get(name) is not None:\n',
        '        if any(v is not None for v in ex.values()):\n',
    ),
    "M2_总开关失效": (
        "    _on = _auto_enabled(cfg)\n",
        "    _on = True\n",
    ),
    "M3_历史不读": (
        '    h = {\n        "n": 0, "calls_med": 0, "tokens_med": 0,',
        '    return {"n": 0, "calls_med": 0, "tokens_med": 0,\n'
        '            "tri_rate": None, "cut_rate": None, "layer_rounds": {},\n'
        '            "modes": {}, "profiles": {}, "web_hit": 0, "web_fail": 0,\n'
        '            "web_empty": 0, "mismatch": 0}\n'
        '    h = {\n        "n": 0, "calls_med": 0, "tokens_med": 0,',
    ),
    "M4_单调用绕过装配器": (
        '''        return _assemble_plan(mode, rnd, cfg, orientation=_ori,
                              reason=reason, confidence=conf)''',
        '''        return {"mode": mode, "rounds": rnd, "reason": reason,
                "orientation": _ori, "confidence": conf}''',
    ),
    "M5_两段式绕开装配器": (
        '''    return _assemble_plan(
        r.get("mode", "serial"), r.get("rounds", {}), cfg,
        route=r.get("route", list(_ROUTE_PRESETS["full"])),
        orientation=o["orientation"], max_calls=r.get("max_calls", 0),
        reason=_reason, confidence=r.get("confidence", 0.0),
        extra={"_orientation_reason": o.get("reason", ""),
               "cost_profile": prof})''',
        '''    return {
        "mode": r.get("mode", "serial"), "rounds": r.get("rounds", {}),
        "route": r.get("route", list(_ROUTE_PRESETS["full"])),
        "orientation": o["orientation"], "max_calls": r.get("max_calls", 0),
        "reason": _reason, "confidence": r.get("confidence", 0.0)}''',
    ),
    "M6_产物表不渲染": (
        '    plan = res.get("_auto_dispatch")\n    if not isinstance(plan, dict) or not (plan.get("_items") or {}):\n        return []',
        '    return []\n    plan = res.get("_auto_dispatch")\n    if not isinstance(plan, dict) or not (plan.get("_items") or {}):\n        return []',
    ),
    "M8_显式值不落配置": (
        '        return (items.get(name) or {}).get("source") in ("auto", "explicit")\n',
        '        return (items.get(name) or {}).get("source") == "auto"\n',
    ),
    "M7_stop策略空": (
        'def _auto_pick_stop(feat, hist, cfg):\n    """停止阈值：只调**阈值**，不动判据本身。"""\n',
        'def _auto_pick_stop(feat, hist, cfg):\n    """停止阈值：只调**阈值**，不动判据本身。"""\n    return {}, "变异体"\n',
    ),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, "[%s] 变异锚点命中 %d 次（要求 1）" % (tag, n)
    p = HERE / ("_mut_v12313_%s.py" % tag)
    p.write_bytes(txt.replace(old, new, 1).replace("\n", "\r\n").encode("utf-8"))
    return p


def run_harness(target, tag):
    src = SMOKE.read_text(encoding="utf-8")
    assert len(SRC_RE.findall(src)) == 1, "smoke SRC 行不是 1 行"
    src = SRC_RE.sub('SRC = Path(r"%s")' % str(target).replace("\\", "\\\\"),
                     src, count=1)
    hm = types.ModuleType("harness_" + tag)
    hm.__file__ = str(SMOKE)
    sys.modules[hm.__name__] = hm
    exec(compile(src, str(SMOKE), "exec"), hm.__dict__)
    return hm


def main():
    ok = True
    hm = run_harness(SRC, "clean")
    r = hm.check_v12313_auto_dispatch()
    print("[control 未变异] -> %s（要求 True）" % r)
    ok &= (r is True)

    for tag, (old, new) in MUTS.items():
        try:
            p = build_mutant(tag, old, new)
        except AssertionError as e:
            print("[%s] -> 锚点失效（判红）: %s" % (tag, e))
            ok = False
            continue
        hm = run_harness(p, tag)
        try:
            r = hm.check_v12313_auto_dispatch()
        except Exception as e:  # noqa: BLE001
            print("[%s] -> 抛异常（也算判红）: %s: %s"
                  % (tag, type(e).__name__, e))
            r = False
        print("[%s] -> %s（要求 False）" % (tag, r))
        ok &= (r is False)

    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
