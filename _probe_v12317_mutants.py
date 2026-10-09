# -*- coding: utf-8 -*-
"""v1.23.17 变异体：每条判据都要有能把它判红的畸形实现。

做法（项目通用）：把畸形引擎写到临时 .py，再把 smoke 的 SRC 指过去 exec，
然后用**原样的判据函数**去跑 —— 必须判红。锚点命中 0 次 = 变异体失效，单独报失败。
"""
import importlib
import re
import sys
import types
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
BASE = HERE / "元DGTF-V1.23.17.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

MUTS = {
    "M1_条件1重关门": (
        "        if _src:\n            if layer_no < soft_max:",
        "        if _src and entry in (\"all\", \"both\"):\n"
        "            if layer_no < soft_max:",
        "check_v12317_stop_all_layers",
    ),
    "M2_soft_max回3": (
        '        "soft_max": 2,',
        '        "soft_max": 3,',
        "check_v12317_stop_all_layers",
    ),
    "M3_sat回3": (
        '        "structure_saturation_every_n": 2,',
        '        "structure_saturation_every_n": 3,',
        "check_v12317_stop_all_layers",
    ),
    "M4_复述载体不写": (
        "            try:\n"
        "                view._meta_idle_streak = rephrased_streak\n"
        "            except Exception:\n"
        "                pass",
        "            pass",
        "check_v12317_stop_all_layers",
    ),
    "M5_去推迟": (
        "        if _src:\n            if layer_no < soft_max:",
        "        if _src:\n            if False:",
        "check_v12317_stop_all_layers",
    ),
}

_src_base = BASE.read_text(encoding="utf-8")
results = []
for tag, (old, new, judge) in MUTS.items():
    n = _src_base.count(old)
    if n != 1:
        results.append((tag, "锚点命中 %d 次（变异体失效）" % n, None))
        continue
    mp = TMP / ("mut_%s.py" % tag.split("_")[0])
    mp.write_bytes(_src_base.replace(old, new, 1).encode("utf-8"))
    txt = SMOKE.read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.17\.py"')
    assert len(pat.findall(txt)) == 1, "SRC 行不是 1 行"
    txt = pat.sub(lambda _m: 'SRC = Path(r"%s")' % str(mp), txt, count=1)
    m = types.ModuleType("mut_" + tag)
    m.__file__ = str(SMOKE)
    sys.modules[m.__name__] = m
    exec(compile(txt, str(SMOKE), "exec"), m.__dict__)
    try:
        ok = getattr(m, judge)()
    except Exception as exc:  # noqa: BLE001
        ok = "异常 %s: %s" % (type(exc).__name__, exc)
    results.append((tag, "判红" if ok is False else "★ 没判红（%r）" % ok, judge))

# control：原版必须判绿
_txt = SMOKE.read_text(encoding="utf-8")
_c = types.ModuleType("ctl")
_c.__file__ = str(SMOKE)
sys.modules["ctl"] = _c
exec(compile(_txt, str(SMOKE), "exec"), _c.__dict__)
_ctl = all(getattr(_c, _j)() for _j in {v[2] for v in MUTS.values()})

print("=" * 60)
_bad = 0
for tag, r, _ in results:
    print("[%s] %s" % (r, tag))
    if r != "判红":
        _bad += 1
print("control（原版）:", "判绿" if _ctl else "★ 判红（判据本身有问题）")
print("MUTANTS: %d/%d 判红" % (len(results) - _bad, len(results)))
sys.exit(1 if (_bad or not _ctl) else 0)
