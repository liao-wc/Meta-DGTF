# -*- coding: utf-8 -*-
"""侦察：mock 桩能不能驱动到「结构饱和度判定」这条通路。

决定新判据怎么写 —— 如果 mock 下各层产不出 &，sat 判定根本不会跑
（它要求 `new_amps` 非空），那行为判据就得另想。

用法：python _probe_v12316_mockcheck.py [目标.py]
"""
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "元DGTF-V1.23.15.py")

src = SMOKE.read_text(encoding="utf-8")
PAT = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(PAT.findall(src)) == 1, "SRC 行不是 1 行"
src = PAT.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), src)

TD = tempfile.mkdtemp(prefix="v12316mock_")
os.environ["SMOKE_SAVE_DIR"] = TD
hm = types.ModuleType("harness")
hm.__file__ = str(SMOKE)
sys.modules["harness"] = hm
exec(compile(src, str(SMOKE), "exec"), hm.__dict__)
mod = hm.mod

# 包一层，数「结构饱和度检查者」被调了几次，并让它返回 new_dimension=False
SAT = {"n": 0, "seen": []}
ORIG = mod.LLM.call


def patched(self, system, user, *a, **kw):
    s = system or ""
    if "结构饱和度检查者" in s:
        SAT["n"] += 1
        SAT["seen"].append((user or "")[:60])
        return json.dumps({"new_dimension": False,
                           "reason": "smoke-sat: 仅换措辞",
                           "shared_axes": []}, ensure_ascii=False)
    return ORIG(self, system, user, *a, **kw)


print("目标:", TARGET.name)
print("mod.__version__ =", getattr(mod, "__version__", "?"))

cfg = hm.build_cfg(False)
m = mod.MetaDGTF(cfg)
mod.LLM.call = patched
try:
    res = m.run("测试题：这份方案怎么落地，责任怎么分",
                route=["0", "1", "both", "all"],
                rounds={"0": 3, "1": 3, "both": 3, "all": 3},
                parallel_mode="serial")
finally:
    mod.LLM.call = ORIG

print("\n=== 各层 ===")
for e in ("0", "1", "both", "all"):
    v = (res.get("views") or {}).get(e)
    if not v:
        print("  %-5s 缺层" % e)
        continue
    print("  %-5s amps=%-3d threads=%-3d rounds_run=%s  stop=%s"
          % (e, len(v.get("amps") or []), len(v.get("threads") or []),
             v.get("rounds_run"), str(v.get("stop_reason"))[:52]))
print("\nsat 判定触发次数 =", SAT["n"])
for x in SAT["seen"][:3]:
    print("   prompt 片段:", x.replace("\n", " | "))
print("\n落盘目录:", TD)
