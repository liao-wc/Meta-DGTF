# -*- coding: utf-8 -*-
"""[v1.21.60] 停止判据收口的**等价性基线**。

用法：
    python _stop_baseline.py save   → 写 _stop_baseline.json
    python _stop_baseline.py diff   → 与当前代码对跑，逐模式比对

比对内容（都取"可观测行为"，不看内部实现）：
  · 每层的 stop_reason / 走了几圈 / idle 计数 / round_log 的 why 列
  · 池计数（& / 线头 / 探针 / 悬置 / 子问题 / 债务）
  · llm_calls（判据少走一圈就会变）
判据重构只要动了行为，这里就会红。
"""
import contextlib
import hashlib
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import smoke_test as st          # 复用它的 mock LLM 与 cfg
mod = st.mod

MODES = ("serial", "A", "B", "C", "D", "E", "F", "G", "H")
OUT = HERE / "_stop_baseline.json"


def snapshot():
    rows = {}
    for mode in MODES:
        st.CALLS["n"] = 0
        cfg = st.build_cfg(False)
        mt = mod.MetaDGTF(cfg)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = mt.run("基线题：AI 在数字 IC 设计里能做什么",
                         route=["0", "1", "both", "all"],
                         rounds={"0": 3, "1": 3, "both": 3, "all": 3},
                         parallel_mode=mode)
        views = {}
        for k, v in sorted(res["views"].items()):
            views[k] = {
                "stop": (v.get("stop_reason") or "")[:120],
                "round_log": [[x.get("round"), x.get("idle_amp"),
                               x.get("idle_thread"), x.get("idle_stall"),
                               x.get("why") or ""]
                              for x in (v.get("round_log") or [])],
                "closure": (v.get("closure_reason") or "")[:60],
                "errors": len(v.get("errors") or []),
            }
        pools = {}
        for k, p in sorted(res["pools"].items()):
            pools[k] = {kk: len(p.get(kk) or []) if isinstance(p.get(kk), list)
                        else p.get(kk) for kk in
                        ("amps", "threads", "probes", "suspensions",
                         "sub_questions", "deferrals", "escalations",
                         "duel_suspensions")}
        logs = (buf.getvalue().replace("\r\n", "\n").split("\n"))
        stop_lines = sorted(l.strip() for l in logs if "螺旋停止" in l)
        rows[mode] = {
            "llm_calls": res["llm_calls"],
            "dispatch": {k: res["dispatch"].get(k) for k in
                         ("order", "ran", "missing", "skipped", "failed")},
            "views": views,
            "pools": pools,
            "stop_lines": stop_lines,
        }
        print(f"  {mode:6s} 调用 {res['llm_calls']:3d} | "
              f"停止行 {len(stop_lines)} | 层 {list(views)}")
    return rows


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "diff"
    print(f"== 快照 9 模式（{action}）==")
    cur = snapshot()
    if action == "save":
        OUT.write_text(json.dumps(cur, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        h = hashlib.sha256(
            json.dumps(cur, ensure_ascii=False, sort_keys=True)
            .encode("utf-8")).hexdigest()[:12]
        print(f"\n已写 {OUT.name}  sha256={h}")
        return 0
    if not OUT.exists():
        print("没有基线文件，先跑 save")
        return 2
    base = json.loads(OUT.read_text(encoding="utf-8"))
    bad = 0
    for mode in MODES:
        a, b = base.get(mode), cur.get(mode)
        if a == b:
            print(f"  ✓ {mode:6s} 行为一致（调用 {b['llm_calls']}）")
            continue
        bad += 1
        print(f"  ✗ {mode:6s} 行为变了！")
        for key in ("llm_calls", "dispatch", "stop_lines", "pools", "views"):
            if a.get(key) != b.get(key):
                print(f"      · {key}:")
                print(f"          基线 {json.dumps(a.get(key), ensure_ascii=False)[:300]}")
                print(f"          现在 {json.dumps(b.get(key), ensure_ascii=False)[:300]}")
    print(f"\n{'全部一致 ✓' if not bad else f'{bad} 个模式行为变了 ✗'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
