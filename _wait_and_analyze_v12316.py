# -*- coding: utf-8 -*-
"""等 v1.23.16 真跑落盘，然后与 v1.23.15 的 auto 组逐项对照。

对照口径（同题 / 同调用方式）：
  v1.23.15 auto 组（基线）：自然停 1/4 层、截断 3/4；实际停圈 4/4/5/7；
  193 calls / 2,420,429 tokens；模式 B；联网收 24 条。
"""
import json
import re
import time
from pathlib import Path

HERE = Path(".").resolve()
OUT = HERE / "outputs" / "_v12316_auto"
SUM = HERE / "_v12316_realrun_summary.json"
DRV = HERE / "_v12316_realrun_driver.log"
LOG = HERE / "_v12316_run_auto.log"

t0 = time.time()
while time.time() - t0 < 3600:
    if SUM.is_file() or OUT.is_dir() and list(OUT.glob("*.md")):
        time.sleep(3)
        break
    time.sleep(20)

print("等待结束（%.0f 秒）" % (time.time() - t0))
print("driver:", DRV.read_text(encoding="utf-8", errors="replace").strip()[-200:])

mds = sorted(OUT.glob("*.md"), key=lambda p: p.stat().st_mtime) if OUT.is_dir() else []
pks = sorted(OUT.glob("*.packed.json"), key=lambda p: p.stat().st_mtime) if OUT.is_dir() else []
print("产物 md:", [p.name for p in mds])
print("产物 packed:", [p.name for p in pks])

res = {"md": [str(p) for p in mds], "packed": [str(p) for p in pks]}
if mds:
    txt = mds[-1].read_text(encoding="utf-8", errors="replace")
    head = txt.split("\n")[:60]
    res["头部关键行"] = [l for l in head if l.startswith("**")
                       and any(k in l for k in ("调度", "停止", "实际停圈",
                                                "并行模式", "自动调度", "资源",
                                                "外部锚点"))]
    print("\n=== 产物头部 ===")
    for l in res["头部关键行"]:
        print("  ", l[:150])
if pks:
    d = json.loads(pks[-1].read_text(encoding="utf-8"))
    res["llm_calls"] = d.get("llm_calls")
    res["llm_tokens"] = d.get("llm_tokens")
    print("\n=== 各层 ===")
    n_nat = 0
    rounds = []
    for e in ("0", "1", "both", "all"):
        v = (d.get("views") or {}).get(e) or {}
        sr = str(v.get("stop_reason") or "")
        if sr:
            n_nat += 1
        rounds.append(v.get("rounds_run"))
        print("  %-5s rounds_run=%-3s cap=%-3s stop=%s"
              % (e, v.get("rounds_run"), v.get("rounds_cap"), sr[:70]))
    res["自然停层数"] = n_nat
    res["各层停圈"] = rounds
    res["calls"] = d.get("llm_calls")
    res["tokens"] = d.get("llm_tokens")
    rl = []
    for e in ("0", "1", "both", "all"):
        v = (d.get("views") or {}).get(e) or {}
        for r in (v.get("round_log") or []):
            rl.append(dict(r, entry=e))
    res["round_log"] = rl
    print("\n=== 逐圈新增/空转（前 12 条）===")
    for r in rl[:12]:
        print("  %-5s 第%s圈 new_amps=%s idle_amp=%s idle_stall=%s"
              % (r.get("entry"), r.get("round"), r.get("new_amps"),
                 r.get("idle_amp"), r.get("idle_stall")))

# sat 判定触发次数（日志）
if LOG.is_file():
    t = LOG.read_bytes().decode("utf-8", errors="replace")
    # 日志是 GBK 中文，按出现次数统计关键块
    res["sat_判定次数"] = t.count("结构饱和度判断")
    res["螺旋停止次数"] = t.count("螺旋停止")
    print("\nsat 判定次数 =", res["sat_判定次数"],
          "| 螺旋停止出现 =", res["螺旋停止次数"])

(HERE / "_v12316_realrun_analysis.json").write_text(
    json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n已写 _v12316_realrun_analysis.json")
