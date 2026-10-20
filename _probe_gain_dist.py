# -*- coding: utf-8 -*-
"""增益分布探针：跑**修行层**（`route=["0"]`，合法、不需要上游），把每圈
`excavate` 读数与 `refinement_gain` 全部打出来 —— 用来**定阈值**，而不是盲扫。

为什么只跑修行层：
  · 元层要 ≥2 个上游（`route=["all"]` 会被调度守卫拒），单跑它不合法；
  · 修行层单层合法，而且它在 A/B 里跑 4~6 圈 —— 正好够 `gain_floor` 需要的 ≥3 条历史
    （v1.23.57 修好跨圈携带之后才够）；
  · 一轮 ~50 calls ≈ ¥0.5，比"扫 6/8/12 三跑 ¥12"便宜一个量级。

产出：`_ab_v1255/gain_probe.json`（每圈读数 + 相邻增益 + 几个候选阈值下的命中数）。

★ 上限：`max_calls=80` / `max_minutes=15`（硬封顶，到点引擎自己收尾）。
"""

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.57.py"
OUT = HERE / "_ab_v1255"
PROD_MEM = HERE / "dgtf_memory"

QUESTION = "一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住。"
ROUTE = ["0"]
ROUNDS = {"0": 6}
MAX_CALLS = 80
MAX_MINUTES = 15.0
RUN_ID = "V1257G0"


def _set(cfg, dotted, val):
    ks = dotted.split(".")
    d = cfg
    for k in ks[:-1]:
        d = d.setdefault(k, {})
        if not isinstance(d, dict):
            return
    d[ks[-1]] = val


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location("eng_g0", str(SRC))
    eng = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = eng
    spec.loader.exec_module(eng)

    cfg = eng.load_config(str(HERE / "dgtf_config.yaml"))
    for k, v, _why in eng._ALL_ON_ITEMS:
        _set(cfg, k, v)
    _set(cfg, "auto.bandit.enabled", False)     # 与 A/B 同口径：caps 显式给定
    _set(cfg, "duty.span_tolerant", True)
    _set(cfg, "spiral.shape_limit", 8)          # 已知唯一有正收益的键
    _set(cfg, "stop.gain_floor", 0.0)           # ★ 关掉：只为读分布，不改行为
    _set(cfg, "memory.eml_adaptive", True)
    _set(cfg, "memory.eml_semantic_merge", True)
    cfg["max_calls"] = MAX_CALLS
    OUT.mkdir(parents=True, exist_ok=True)
    mem = OUT / "gain_probe_mem"
    if not mem.is_dir():
        mem.mkdir(parents=True, exist_ok=True)
        if PROD_MEM.is_dir():
            import shutil
            for f in sorted(PROD_MEM.iterdir()):
                if f.is_file():
                    shutil.copy2(f, mem / f.name)
    cfg.setdefault("playbook", {})
    cfg["playbook"]["mode"] = "on"
    cfg["playbook"]["dir"] = str(mem)
    cfg.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mem)
    cfg.setdefault("output", {})["save_dir"] = str(OUT / "gain_probe_out")

    print("上限 calls=%d / %.0f min | gain_floor=0（只读分布）| route=%s rounds=%s"
          % (MAX_CALLS, MAX_MINUTES, ROUTE, ROUNDS))
    m = eng.MetaDGTF(cfg)
    t0 = time.time()
    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=RUN_ID, max_minutes=MAX_MINUTES)
    dt = time.time() - t0
    v = (res.get("views") or {}).get("0") or {}
    gt = list(v.get("goal_trace") or [])
    print("\n完成 %.1f min | calls=%s tokens=%s | 圈=%s | goal_trace 条数=%d"
          % (dt / 60.0, res.get("llm_calls"), res.get("llm_tokens"),
             v.get("rounds_run"), len(gt)))

    # 逐圈读数与相邻增益（★ 修行层：增益 = 上圈 − 本圈）
    rows, gains = [], []
    for i, rec in enumerate(gt):
        cur = rec.get("excavate")
        prev = gt[i - 1].get("excavate") if i else None
        g = None
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            g = round(max(0.0, min(1.0, prev - cur)), 4)
            gains.append(g)
        rows.append({"round": rec.get("round"), "excavate": cur,
                     "n_aspects": rec.get("n_aspects"), "gain": g})

    print("\n%-6s %-10s %-10s %-8s" % ("圈", "excavate", "n_aspects", "增益"))
    for r in rows:
        print("%-6s %-10s %-10s %-8s"
              % (r["round"], r["excavate"], r["n_aspects"], r["gain"]))

    print("\n%s" % ("=" * 56))
    print("增益序列：%s" % (gains or "（不足两圈，算不出）"))
    if gains:
        print("可判定的连续对数：%d（早停判据要连看 2 对）" % len(gains))
        for a in (0.01, 0.02, 0.05, 0.1, 0.2):
            hit = sum(1 for g in gains if g < a)
            print("  α=%-5s ⇒ %d/%d 个增益低于它" % (a, hit, len(gains)))
        print("\n结论提示：α 要落在「有 2 个以上增益比它小」的区间才可能触发；"
              "\n          如果最小的两个增益都比 0.01 大，那 0.01 就是**永远不触发**。")

    (OUT / "gain_probe.json").write_text(
        json.dumps({"run_id": res.get("id"), "calls": res.get("llm_calls"),
                    "tokens": res.get("llm_tokens"), "rounds": v.get("rounds_run"),
                    "stop_reason": v.get("stop_reason"),
                    "rows": rows, "gains": gains},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n产物：%s" % (OUT / "gain_probe.json"))


if __name__ == "__main__":
    main()
