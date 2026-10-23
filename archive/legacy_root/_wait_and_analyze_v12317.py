# -*- coding: utf-8 -*-
"""等 v1.23.17 真跑落盘，然后与 v1.23.16 auto 组逐层对表。

★ 对照口径：同题、同调用方式（`-c` 极简 cfg ⇒ 走引擎默认值）。
  所以这一跑量的正是「sat 间隔 3→2、soft_max 3→2、条件 1 四层通用」的净效果。
"""
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}


def wait_packed(d, timeout=4200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        fs = sorted(d.glob("*.packed.json"), key=lambda p: p.stat().st_mtime)
        done = ("完成" in (HERE / "_v12317_realrun_driver.log").read_text(
            encoding="utf-8", errors="replace"))
        if fs and done:
            return fs[-1]
        time.sleep(20)
    return None


def layers(pk):
    d = json.loads(pk.read_text(encoding="utf-8"))
    out = {}
    for e in ("0", "1", "both", "all"):
        v = (d.get("views") or {}).get(e) or {}
        out[e] = {"run": v.get("rounds_run"), "cap": v.get("rounds_cap"),
                  "stop": str(v.get("stop_reason") or "")}
    out["_calls"] = d.get("llm_calls")
    out["_tokens"] = d.get("llm_tokens")
    return out


def satcount(log):
    p = Path(log)
    if not p.is_file():
        return None
    t = p.read_bytes().decode("utf-8", errors="replace")
    return t.count("结构饱和度判断")


pk16 = sorted((HERE / "outputs" / "_v12316_auto").glob("*.packed.json"))[-1]
a = layers(pk16)
pk17 = wait_packed(HERE / "outputs" / "_v12317_auto")
if pk17 is None:
    print("超时：真跑没落盘")
    raise SystemExit(1)
b = layers(pk17)

print("=" * 78)
print("%-4s %-26s | %-26s" % ("层", "v1.23.16(auto)", "v1.23.17(auto)"))
for e in ("0", "1", "both", "all"):
    def fmt(x):
        st = x["stop"]
        kind = ("自然" if "体力耗尽" not in st else "截断")
        return "%s%s圈/%s (%s)" % (NAME[e], x["run"], x["cap"], kind)
    print("%-4s %-26s | %-26s" % (e, fmt(a[e]), fmt(b[e])))
nat = {k: 0 for k in ()}
for k in ("a", "b"):
    pass
va = [a[e]["stop"] for e in ("0", "1", "both", "all")]
vb = [b[e]["stop"] for e in ("0", "1", "both", "all")]
print()
print("自然停层数: %d/4 → %d/4"
      % (sum(1 for s in va if "体力耗尽" not in s),
         sum(1 for s in vb if "体力耗尽" not in s)))
print("calls: %s → %s | tokens: %s → %s"
      % (a["_calls"], b["_calls"], a["_tokens"], b["_tokens"]))
print("sat 判定次数: %s → %s"
      % (satcount(HERE / "_v12316_run_auto.log"),
         satcount(HERE / "_v12317_run_auto.log")))
print()
print("=== v1.23.17 逐层停因 ===")
for e in ("0", "1", "both", "all"):
    print("  %-4s run=%s cap=%s | %s" % (e, b[e]["run"], b[e]["cap"],
                                         b[e]["stop"][:96]))
print()
print("=== ★ v1.21.48 老风险检查：研究层停在第几圈 ===")
print("  研究层 run=%s（间隔 2 下若第 2 圈就停，则该风险复现）" % b["1"]["run"])
print("  研究层停因:", b["1"]["stop"][:110])
json.dump({"v12316": a, "v12317": b}, open(HERE / "_v12317_cmp.json", "w",
          encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已写 _v12317_cmp.json")
