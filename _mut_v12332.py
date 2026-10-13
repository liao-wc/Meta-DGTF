#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 变异体：给 `check_v12332_discipline` 背书（M1~M9）。"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.32.py"

MUTS = [
    ("M1 α 不做机会校正（退化成原始一致率）",
     "    return {\"alpha\": 1.0 - (Do / De), \"n_units\": len(_units),",
     "    return {\"alpha\": 1.0 - Do, \"n_units\": len(_units),"),
    ("M2 α 恒 1（全绿假读数）",
     "    if De <= 1e-12:",
     "    if True:"),
    ("M3 少数类一致不筛类（把全部 unit 计入）",
     "        if _rare not in _r:\n            continue",
     "        if False:\n            continue"),
    ("M4 尺度登记失效（三态登记成 ratio）",
     '    "tri_state_agreement": "ordinal",',
     '    "tri_state_agreement": "ratio",'),
    ("M5 定序禁词检查恒空",
     "    _bad = _SCALE_FORBIDDEN.get(str(scale), ())",
     "    _bad = ()"),
    ("M6 级联主因取最后一条（放弃优先级）",
     "    _ordered = sorted(_rs, key=lambda r: (stop_priority(r), _rs.index(r)))",
     "    _ordered = list(_rs)"),
    ("M7 主因硬造成固定串（不在 all 里）",
     "    return {\"primary\": _ordered[0], \"ordered\": _ordered, \"all\": _rs}",
     "    return {\"primary\": \"自然安住\", \"ordered\": _ordered, \"all\": _rs}"),
    ("M8 CSD 恒判「有前兆」",
     "            \"hint\": bool(_rising and _ac1 > 0.3)}",
     "            \"hint\": True}"),
    ("M9 成本两分失效（分类恒 ops）",
     '    return "eval" if str(stage or "") in _LLM_EVAL_STAGES else "ops"',
     '    return "ops"'),
    ("M10 截断两向只报一面（丢的恒 0）",
     '        "lost_core": len(_miss),',
     '        "lost_core": 0,'),
    ("M11 输入自检规则类恒空",
     '    _q = str(q or "")\n    out = []',
     '    return []\n    _q = str(q or "")\n    out = []'),
    ("M12 言语行为判词恒空（公文体不告警）",
     '        _verdict = "公文体风险：全部/多数为「请求」，无「承诺」型动作（没人认领）"',
     '        _verdict = ""'),
    ("M13 FMEA 恒判可检测",
     '    return "⚠️ **不可检测**（没有对应标记 —— 它不会出现在任何读数里）"',
     '    return "可检测"'),
    ("M14 多样性组合数恒满配",
     '    _combos = max(0, len(_layers)) * max(0, len(_ch))',
     '    _combos = 12'),
    ("M15 nogoods 记录内容失效（kind/why 抹空）",
     '            "kind": str(kind or ""), "why": str(why or ""),',
     '            "kind": "", "why": "",')
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
    code += "sys.exit(0 if st.check_v12332_discipline() else 1)\n"
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
        print("X 干净基线不绿：\n", out[-1200:])
        sys.exit(2)
    print("OK 干净基线判绿")
    res = []
    for i, (name, old, new) in enumerate(MUTS, 1):
        if only and i not in only:
            continue
        src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        n = src.count(old)
        if n != 1:
            print("X %s：锚点命中 %d 次（失效）" % (name, n))
            res.append((i, name, "ANCHOR"))
            continue
        tmp = Path(tempfile.gettempdir()) / ("_mut_v12332_%d.py" % i)
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
