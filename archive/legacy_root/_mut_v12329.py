#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 变异体：给 `check_v12329_convergence` 的判别力背书。

★ 干净基线先行：先对**未变异**源跑一遍判据（必须绿），否则 N 个变异体
  全红只是「判别力失效的假绿」。
★ 每个变异体：复制主文件 → 单点变异 → importlib 重载 → 只跑
  `check_v12329_convergence`（含函数级两臂）→ 必须**判红**。
★ 变异点打在「判据读的那个东西」上（不是改前缀名）。
★ 支持 `--only 1,3,5` 分片（防 sandbox 干扰）。
"""
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"
SMOKE = HERE / "smoke_test.py"

# (名字, 旧串, 新串) —— 旧串在源中必须恰命中 1 次
MUTS = [
    ("M1 A1 索引标题没了",
     "## 这一次我是谁（索引）", "## 这一次我是谁（X引）"),
    ("M2 B1 可达模式集放水（收回 D~H）",
     '_AUTO_REACHABLE_MODES = ("serial", "B", "C")',
     '_AUTO_REACHABLE_MODES = ("serial", "B", "C", "D")'),
    ("M3 C1 逐圈前提守卫失效（恒真）",
     '_has_per_round = any(',
     '_has_per_round = True or any('),
    ("M4 D1 rel 触发分支关死",
     'thr.strip().lower() == "rel"',
     'thr.strip().lower() == "rel_disabled"'),
    ("M5 D2 阈值放水（0.85→0.30，会把不同主张错并）",
     "_BELIEF_MERGE_SIM = 0.85",
     "_BELIEF_MERGE_SIM = 0.30"),
    ("M6 D2 认领段开关旁路（关着也归并）",
     'if _tgt is None and getattr(self, "merge_semantic", False):',
     'if _tgt is None and True:'),
    ("M7 D2 merge_log 出口删掉",
     'd["merge_log"] = list(getattr(self, "merge_log", []) or [])',
     'pass  # mutated'),
    ("M8 D2 配置下发断线",
     "_p.merge_semantic = _mg",
     "pass  # mutated"),
]


def load_mutated(mut_path):
    """把变异副本挂进 smoke_test 的 SRC/mod，返回其模块。"""
    spec = importlib.util.spec_from_file_location("dgtf_mut", str(mut_path))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_mut"] = m
    spec.loader.exec_module(m)
    return m


def run_check(mut_path=None):
    """在子进程里跑 check_v12329_convergence，返回是否判绿。

    ★ 用子进程：smoke_test 的模块级 fake LLM 桩与全局状态不能被
      反复 exec 污染（干净基线的教训）。
    """
    import subprocess
    code = (
        "import sys; sys.path.insert(0, r'%s');\n"
        "import smoke_test as st\n"
    ) % str(HERE)
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
    code += "sys.exit(0 if st.check_v12329_convergence() else 1)\n"
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=str(HERE))
    return r.returncode == 0, r.stdout + r.stderr


def main():
    only = None
    if "--only" in sys.argv:
        only = set(int(x) for x in
                   sys.argv[sys.argv.index("--only") + 1].split(","))
    # 干净基线
    ok_base, out = run_check(None)
    if not ok_base:
        print("✗ 干净基线不绿——先修判据再谈变异体：\n", out[-2000:])
        sys.exit(2)
    print("✓ 干净基线判绿")
    results = []
    for i, (name, old, new) in enumerate(MUTS, 1):
        if only and i not in only:
            continue
        src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        n = src.count(old)
        if n != 1:
            print("✗ %s：锚点命中 %d 次（要求 1），跳过" % (name, n))
            results.append((i, name, "ANCHOR"))
            continue
        tmp = Path(tempfile.gettempdir()) / ("_mut_v12329_%d.py" % i)
        tmp.write_bytes(src.replace(old, new, 1).encode("utf-8"))
        is_green, out = run_check(tmp)
        verdict = "红(判别力OK)" if not is_green else "绿(假绿!)"
        print(("✓" if not is_green else "✗"),
              "%s %s" % (name, verdict))
        results.append((i, name, "RED" if not is_green else "GREEN"))
        tmp.unlink(missing_ok=True)
    bad = [r for r in results if r[2] != "RED"]
    print("\n=== 变异体汇总：%d 判红 / %d 总数 ==="
          % (len(results) - len(bad), len(results)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
