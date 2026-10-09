# -*- coding: utf-8 -*-
"""v1.23.19 变异体：每条判据都要有能把它判红的畸形实现。"""
import re
import sys
import types
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
BASE = HERE / "元DGTF-V1.23.19.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

MUTS = {
    "M1_早退复活": (
        '        if not cfg.get("enabled") or entry == "all":\n            return',
        '        if not cfg.get("enabled") or entry == "all" or not self._anchors:\n'
        '            return',
        "check_v12319_anchor_retrieval_reachable",
    ),
    "M2_unconfigured对所有模式": (
        '            _mode0 = str(cfg.get("retriever") or "snapshot").strip().lower()\n'
        '            if _mode0 == "snapshot":',
        '            _mode0 = str(cfg.get("retriever") or "snapshot").strip().lower()\n'
        '            if True:',
        "check_v12319_anchor_retrieval_reachable",
    ),
    "M3_渲染只提一条路": (
        '                   "**开（未挂锚点文件）** —— 两条接入路二选一："\n'
        '                   "① `external_anchor.path` 指向锚点快照 JSON；"\n'
        '                   "② `external_anchor.retriever: tavily` 按圈真检索"\n'
        '                   "（读 `TAVILY_API_KEY`）。本次结论只取决于池内材料")',
        '                   "**开（未挂锚点文件）** —— 把 `external_anchor.path` 指向"\n'
        '                   "锚点快照 JSON 即自动接入；本次结论只取决于池内材料")',
        "check_v12319_anchor_retrieval_reachable",
    ),
    "M4_检索结果不并池": (
        '            self._anchors = list(self._anchors or []) + got\n',
        '',
        "check_v12319_anchor_retrieval_reachable",
    ),
}

_src = BASE.read_text(encoding="utf-8")
results = []
for tag, (old, new, judge) in MUTS.items():
    n = _src.count(old)
    if n != 1:
        results.append((tag, "锚点命中 %d 次（变异体失效）" % n))
        continue
    mp = TMP / ("mut19_%s.py" % tag.split("_")[0])
    mp.write_bytes(_src.replace(old, new, 1).encode("utf-8"))
    txt = SMOKE.read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.19\.py"')
    assert len(pat.findall(txt)) == 1
    txt = pat.sub(lambda _m: 'SRC = Path(r"%s")' % str(mp), txt, count=1)
    m = types.ModuleType("mut19_" + tag)
    m.__file__ = str(SMOKE)
    sys.modules[m.__name__] = m
    exec(compile(txt, str(SMOKE), "exec"), m.__dict__)
    try:
        ok = getattr(m, judge)()
    except Exception as exc:  # noqa: BLE001
        ok = "异常 %s: %s" % (type(exc).__name__, exc)
    results.append((tag, "判红" if ok is False else "★ 没判红（%r）" % ok))

_txt = SMOKE.read_text(encoding="utf-8")
_c = types.ModuleType("ctl19")
_c.__file__ = str(SMOKE)
sys.modules["ctl19"] = _c
exec(compile(_txt, str(SMOKE), "exec"), _c.__dict__)
_ctl = all(getattr(_c, _j)() for _j in {v[2] for v in MUTS.values()})

print("=" * 60)
_bad = 0
for tag, r in results:
    print("[%s] %s" % (r, tag))
    if r != "判红":
        _bad += 1
print("control（原版）:", "判绿" if _ctl else "★ 判红（判据本身有问题）")
print("MUTANTS: %d/%d 判红" % (len(results) - _bad, len(results)))
sys.exit(1 if (_bad or not _ctl) else 0)
