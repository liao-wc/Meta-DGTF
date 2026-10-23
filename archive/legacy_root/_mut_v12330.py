#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 变异体：给 `check_v12330_duty_guard` 的判别力背书（M1~M9）。

★ 干净基线先行（否则 N 个变异体全红只是判别力失效的假绿）。
★ 变异点打在**判据读的那个东西**上。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.30.py"

MUTS = [
    ("M1 问项抽取只归 core（followup 分类失效）",
     '        if any(x.startswith(w) or (w + x) in q for w in _DUTY_FOLLOWUP_LEAD):',
     '        if False:'),
    ("M2 followup 权重抬到与 core 同档（并列洗成高覆盖）",
     '_DUTY_KIND_W = {"core": 0.70, "background": 0.30, "followup": 0.10}',
     '_DUTY_KIND_W = {"core": 0.70, "background": 0.30, "followup": 0.70}'),
    ("M3 S 改成算术平均（调和平均失效）",
     '    S = (2.0 * C * R / (C + R)) if (C + R) > 0 else 0.0',
     '    S = (C + R) / 2.0'),
    ("M4 命中判据恒真（覆盖永远满分）",
     '        if str(asp_text) in seg:\n            return True',
     '        if True:\n            return True'),
    ("M5 R 的 Useless 不计入分母（相关恒 1）",
     '    R = (direct / (direct + useless)) if (direct + useless) else 0.0',
     '    R = 1.0 if direct else 0.0'),
    ("M6 floor 比较失效（恒不 short）",
     '    d["short"] = bool(float(d.get("S", 0.0)) < _fl)',
     '    d["short"] = False'),
    ("M7 署名纪律失效（职责未尽不改署名）",
     '        if _duty_fin and _duty_fin.get("short"):',
     '        if False:'),
    ("M8 duty_short 补回删掉（被收尾清洗吞掉）",
     '        if (view.duty or {}).get("short") \\\n'
     '                and "duty_short" not in view.quality_flags:',
     '        if False:'),
    ("M9 distance 缺省退回 1.0（缺省冒充读数）",
     '                view.distance_to_question = (\n'
     '                    None if _d2q_raw is None else float(_d2q_raw))',
     '                view.distance_to_question = 1.0'),
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
    code += "sys.exit(0 if st.check_v12330_duty_guard() else 1)\n"
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
        print("✗ 干净基线不绿——先修判据再谈变异体：\n", out[-1500:])
        sys.exit(2)
    print("✓ 干净基线判绿")
    res = []
    for i, (name, old, new) in enumerate(MUTS, 1):
        if only and i not in only:
            continue
        src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        n = src.count(old)
        if n != 1:
            print("✗ %s：锚点命中 %d 次，跳过" % (name, n))
            res.append((i, name, "ANCHOR"))
            continue
        tmp = Path(tempfile.gettempdir()) / ("_mut_v12330_%d.py" % i)
        tmp.write_bytes(src.replace(old, new, 1).encode("utf-8"))
        green, out = run_check(tmp)
        print(("✓" if not green else "✗"),
              "%s %s" % (name, "红(判别力OK)" if not green else "绿(假绿!)"))
        res.append((i, name, "RED" if not green else "GREEN"))
        tmp.unlink(missing_ok=True)
    bad = [r for r in res if r[2] != "RED"]
    print("\n=== 变异体汇总：%d 判红 / %d 总数 ==="
          % (len(res) - len(bad), len(res)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
