# -*- coding: utf-8 -*-
"""v1.23.16 变异体：7 个畸形引擎，判据必须全部判红。

用法：python _probe_v12316_mutants.py

每个变异体：拿 v1.23.16 复制一份 → 改一处 → 用 smoke_test.py 的 harness
（只换 SRC 行）加载那份**畸形引擎** → 跑 `check_v12316_stop_therapy`
（以及档位相关断言）→ 必须判红。

★ 变异必须打在**判据读的那个东西**上：
  · M1/M4/M7 打在 `_sat_override` 的三个出口（值、层门、stall 分支）；
  · M2 打在 `_lazy_every_n` 的返回值（判据直接调它）；
  · M3 打在参照集本体（判据数 `list(snap_amps)` 的次数）；
  · M5/M6 打在「维度存在性」上（判据用 hasattr / 长度）。
"""
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(".").resolve()
ENGINE = HERE / "元DGTF-V1.23.16.py"
SMOKE = HERE / "smoke_test.py"
TD = Path(tempfile.mkdtemp(prefix="v12316mut_"))

MUTS = {
    "M1_sat不推计数": (
        "    return (max(idle_new_amp, r_idle_limit),",
        "    return (idle_new_amp,",
    ),
    "M2_惰性化复活": (
        "        return n\n\n    def _coverage_segment(self) -> str:",
        "        return n + 1\n\n    def _coverage_segment(self) -> str:",
    ),
    "M3_参照集换成空表": (
        "            recent_amps = list(snap_amps)",
        "            recent_amps = []",
    ),
    "M4_sat只对研究层": (
        '            entry != "0")',
        '            entry == "1")',
    ),
    "M5_档位常量复活": (
        "_DUP_SIM = 0.85",
        '_DUP_SIM = 0.85\n_COST_PROFILES = ("quality",)',
    ),
    "M6_auto项退回12": (
        '_AUTO_ITEM_ORDER = ("route", "mode", "rounds", "orientation",',
        '_AUTO_ITEM_ORDER = ("route", "cost_profile", "mode", "rounds", "orientation",',
    ),
    "M7_stall分支不推": (
        "            max(idle_stall, r_stall_limit),",
        "            idle_stall,",
    ),
}

_results = {}
for name, (old, new) in MUTS.items():
    src = ENGINE.read_text(encoding="utf-8")
    n = src.count(old)
    if n != 1:
        print("[%s] 锚点命中 %d 次（要求 1）—— 变异体失效" % (name, n))
        _results[name] = None
        continue
    mp = TD / ("mut_%s.py" % name)
    mp.write_text(src.replace(old, new, 1), encoding="utf-8")

    txt = SMOKE.read_text(encoding="utf-8")
    PAT = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
    assert len(PAT.findall(txt)) == 1
    txt = PAT.sub('SRC = Path(r"%s")' % str(mp).replace("\\", "\\\\"), txt)
    hm = types.ModuleType("mut_%s" % name)
    hm.__file__ = str(SMOKE)
    sys.modules[hm.__name__] = hm
    try:
        exec(compile(txt, str(SMOKE), "exec"), hm.__dict__)
        ok = hm.check_v12316_stop_therapy()
    except Exception as e:  # noqa: BLE001
        print("[%s] 判据抛异常（也算判红）：%s: %s" % (name, type(e).__name__, e))
        ok = False
    _results[name] = ok
    print("[%s] 判据 %s" % (name, "绿 ← ★ 假绿！" if ok else "红（正确）"))

_ok = [k for k, v in _results.items() if v is False]
print("\nMUTANTS: %d/%d 判红 %s" % (len(_ok), len(MUTS),
                                   "ALL-OK" if len(_ok) == len(MUTS) else
                                   "失败：%s" % [k for k, v in _results.items()
                                                 if v is not False]))
