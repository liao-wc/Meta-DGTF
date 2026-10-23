#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 变异体：给 `check_v12331_memory_loop` 的判别力背书（M1~M10）。"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.31.py"

MUTS = [
    ("M1 质量闸第 1 问失效（无读数也收）",
     '    if not isinstance(c.get("readings"), dict) or not c["readings"].get("before"):',
     '    if False:'),
    ("M2 质量闸红线检查删掉（放红线入闸）",
     '    if any(k in _blob for k in _bad):',
     '    if False:'),
    ("M3 F2 双边记账失效（只省成本也升级）",
     '        if _qd == 0.0 and _cd < 0.0:',
     '        if False:'),
    ("M4 meso 门槛失效（证据 1 条就升）",
     '        if _n < int(promote_n):\n            continue',
     '        if False:\n            continue'),
    ("M5 遗忘清扫失效（恒不退休）",
     '        if _rec >= float(retire_recency):\n            continue',
     '        if True:\n            continue'),
    ("M6 F1 隔离失效（shadow 也进 recall）",
     '        if e.get("status") != "active":\n            continue',
     '        if False:\n            continue'),
    ("M7 RRIF 频率维失效",
     '        _freq = min(1.5, 1.0 + 0.1 * len(e.get("t_used") or []))',
     '        _freq = 1.0'),
    ("M8 新条目不进 shadow（直接生效）",
     '        "status": "shadow",\n        "weight": 1.0,',
     '        "status": "active",\n        "weight": 1.0,'),
    ("M9 同键候选改为新建行（破坏增量）",
     '        if _ek == _key:',
     '        if False:'),
    ("M10 macro 聚合就地改写原文（违 ACE）",
     '    return parents',
     '    for _x in _act:\n        _x["cond"] = {"aggregated": True}\n    return parents'),
]


def run_check(mut_path=None):
    code = ("import sys; sys.path.insert(0, r'%s');\n"
            "import smoke_test as st;\n") % str(HERE)
    if mut_path is not None:
        code += "from pathlib import Path\n"
        code += "st.SRC = Path(r'%s')\n" % str(mut_path)
        code += (
            "import importlib.util\n"
            "_sp = importlib.util.spec_from_file_location('dgtf_mod', r'%s')\n"
            "_m = importlib.util.module_from_spec(_sp)\n"
            "import sys as _s; _s.modules['dgtf_mod'] = _m\n"
            "_sp.loader.exec_module(_m)\n"
            "st.mod = _m\n"
        ) % str(mut_path)
    code += "sys.exit(0 if st.check_v12331_memory_loop() else 1)\n"
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=str(HERE))
    return r.returncode == 0, r.stdout + r.stderr


def main():
    only = None
    if "--only" in sys.argv:
        only = set(int(x) for x in
                   sys.argv[sys.argv.index("--only") + 1].split(","))
    ok_base, out = run_check(None)
    if not ok_base:
        print("X 干净基线不绿 —— 先修判据：\n", out[-1500:])
        sys.exit(2)
    print("OK 干净基线判绿")
    res = []
    for i, (name, old, new) in enumerate(MUTS, 1):
        if only and i not in only:
            continue
        src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        n = src.count(old)
        if n != 1:
            print("X %s：锚点命中 %d 次，跳过" % (name, n))
            res.append((i, name, "ANCHOR"))
            continue
        tmp = Path(tempfile.gettempdir()) / ("_mut_v12331_%d.py" % i)
        tmp.write_bytes(src.replace(old, new, 1).encode("utf-8"))
        green, out = run_check(tmp)
        print(("OK" if not green else "X"),
              "%s %s" % (name, "红(判别力OK)" if not green else "绿(假绿!)"))
        res.append((i, name, "RED" if not green else "GREEN"))
        tmp.unlink(missing_ok=True)
    bad = [r for r in res if r[2] != "RED"]
    print("\n=== 变异体汇总：%d 判红 / %d 总数 ==="
          % (len(res) - len(bad), len(res)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
