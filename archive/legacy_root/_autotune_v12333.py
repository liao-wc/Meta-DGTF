#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoTune 驱动：把「自学习 → 定最优模式/层集/圈数」串成一条可跑命令。

子命令：
  report   —— 只读历史 `episodes.jsonl` 出建议（**零 API 调用**，随时可跑）
  sweep    —— 按 **Successive-Halving** 跑设计空间（真跑），累积 episode 后出建议

设计空间（可 `--space` 覆盖）：
  · 层集 route   ：["0","1"] / ["0","1","both"] / ["0","1","both","all"]
  · 并行模式 mode ：serial / B / D（规则分派对开放题有区分度）
  · 圈数 rounds   ：{layer: n}（由 SH 档位给出，逐档翻倍）

★ 预算纪律：SH 档位表保证「候选数 ↓ / 逐候选预算 ↑」，总预算线性可控。
  所有真跑一律走出厂 `all_on: true`（全开），跑批串行（共享记忆库 ⇒ 跨跑学习）。
★ 停滞看门狗：单题日志 N 秒无增长 ⇒ 判停滞、跳过该题（本轮 API 侧不稳）。
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = "元DGTF-V1.23.33.py"
PY = sys.executable

#: 设计空间：`(tag, mode, route, rounds, why)`
#   ★ 预算纪律（用户：除非预算不足否则继续）：SH 第一档 = 最小圈数 ⇒ 先跑**最小
#     可比集**（层集是首要问题：both/all 两层到底加不加质量），够用再扩。
SPACE = [
    ("P1_2L_serial", "serial", ["0", "1"],
     {"0": 2, "1": 2}, "两层·串行：最省，验「砍层是否掉质量」"),
    ("P2_4L_serial", "serial", ["0", "1", "both", "all"],
     {"0": 2, "1": 2, "both": 2, "all": 2}, "四层·串行：加对撞层+元层"),
    ("P3_3L_serial", "serial", ["0", "1", "both"],
     {"0": 2, "1": 2, "both": 2}, "三层·串行：只加对撞层（分离 both/all 贡献）"),
]

#: 题型（跨配置用**同一批题**，否则跨配置不可比）。
QUESTIONS = [
    "AI 会先取代设计师还是程序员？",
    "如何利用AI来帮助人类实现财富自由甚至文明升级？",
]


def _load_mod():
    spec = importlib.util.spec_from_file_location("dgtf_at", HERE / SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_at"] = mod
    spec.loader.exec_module(mod)
    return mod


def cmd_report(a):
    mod = _load_mod()
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    rec = mod.autotune_run(cfg, write=(not a.dry))
    print("=" * 74)
    print("[AutoTune report] 读 episode %d 条" % rec.get("n_read", 0))
    if not rec.get("ok"):
        print("  ✗ 暂不可建议：%s" % rec.get("why"))
        print("  → 先跑 `sweep` 把带 duty 读数的 episode 攒够。")
        return 0
    print("  ✓ 建议：模式=%s  层集=%s  圈数上限=%s"
          % (rec["mode"], rec["route"], rec["rounds_cap"]))
    print("  质量中位=%.3f  成本中位=%.0f tok  分组=%d"
          % (rec["quality_med"], rec.get("cost_med") or 0.0, rec.get("n_groups", 0)))
    print("  理由：%s" % rec["why"])
    print("  帕累托前沿（质量↓ / 成本↑ 前 6）：")
    for f in rec.get("frontier", []):
        print("    %-8s %-26s 质量=%.3f 成本=%.0f"
              % (f["mode"], f["route"], f["quality_med"], f["cost_med"]))
    if rec.get("written"):
        print("  建议已落盘：%s" % rec["written"])
    return 0


def _run_one(mod_tag, q, mode, route, rounds, qidx):
    tag = "%s_Q%d" % (mod_tag, qidx)
    env = dict(os.environ)
    env["FULLRUN_ROUTE"] = ",".join(route)
    env["FULLRUN_MODE"] = mode
    env["FULLRUN_ROUNDS"] = json.dumps({k: int(v) for k, v in rounds.items()})
    cmd = [PY, str(HERE / "_run_full_v12333.py"), "--src", SRC,
           "--tag", tag, "--question", q, "--stall-sec", "600"]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HERE),
                       env=env)
    return r.returncode, time.time() - t0, (r.stdout or "")[-500:]


def _done_prefixes(mod):
    """已完成的 `TAG_Qn` 前缀集合（幂等跑批：跳过已完成项，不重复烧预算）。

    ★ run_id 形如 `P1_2L_serial_Q1_20261014_084928` ⇒ 用正则取到 `_Q<n>` 为止，
      **不能**按 `_2` 切（`P1_2L` 里也有 `_2`，会切错）。
    """
    import re as _re
    done = set()
    for ep in mod.autotune_load_episodes():
        rid = str(ep.get("run_id") or "")
        mt = _re.match(r"^(.*_Q\d+)_", rid)
        if mt:
            done.add(mt.group(1))
    return done


def cmd_sweep(a):
    mod = _load_mod()
    conc = max(1, int(a.conc))
    done = _done_prefixes(mod) if not a.no_skip else set()
    work = []
    for tag, mode, route, rounds, why in SPACE:
        if a.only and tag not in a.only:
            continue
        for qi, q in enumerate(QUESTIONS, 1):
            key = "%s_Q%d" % (tag, qi)
            if key in done:
                print("  ⏭ %s 已完成，跳过（幂等）" % key)
                continue
            work.append((tag, mode, route, rounds, why, qi, q))
    print("=" * 74)
    print("[AutoTune sweep] 设计空间 %d 点 × %d 题 ⇒ 待跑 %d 次（并发 %d，串行内建锁保护记忆库）"
          % (len(SPACE), len(QUESTIONS), len(work), conc))
    print("  SH 档位（候选数缩 / 逐档加圈）：%s" % (mod.autotune_sh_rounds(5, 2, 3),))
    rows = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        futs = {ex.submit(_run_one, t[0], t[6], t[1], t[2], t[3], t[5]): t
                for t in work}
        for fu in as_completed(futs):
            t = futs[fu]
            try:
                rc, dt, tail = fu.result()
            except Exception as e:
                rc, dt, tail = -1, 0.0, repr(e)
            print("  %-18s Q%d 退出码=%-3s %.1f min  %s"
                  % (t[0], t[5], rc, dt / 60,
                     "⏸停滞" if rc == 9 else ("✗" if rc else "✓")))
            rows.append({"tag": t[0], "q": t[5], "rc": rc, "min": round(dt / 60, 1)})
    print("-" * 74)
    print("跑批汇总：%d 次，成功 %d，总耗时 %.1f min"
          % (len(rows), sum(1 for r in rows if r["rc"] == 0),
             (time.time() - t0) / 60))
    # ── 跑完立刻出建议（自学习闭环）──
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    rec = mod.autotune_run(cfg, write=(not a.dry))
    print("=" * 74)
    if not rec.get("ok"):
        print("[AutoTune] 仍不可建议：%s" % rec.get("why"))
    else:
        print("[AutoTune] 建议：模式=%s 层集=%s 圈数=%s"
              % (rec["mode"], rec["route"], rec["rounds_cap"]))
        print("  理由：%s" % rec["why"])
        for f in rec.get("frontier", []):
            print("    %-8s %-26s 质量=%.3f 成本=%.0f"
                  % (f["mode"], f["route"], f["quality_med"], f["cost_med"]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("report")
    p1.add_argument("--dry", action="store_true", help="不落盘建议")
    p2 = sub.add_parser("sweep")
    p2.add_argument("--only", nargs="*", default=None, help="只跑指定 tag")
    p2.add_argument("--conc", type=int, default=3, help="并发度（默认 3）")
    p2.add_argument("--no-skip", action="store_true", help="不跳过已完成项")
    p2.add_argument("--dry", action="store_true", help="不落盘建议")
    a = ap.parse_args()
    return cmd_report(a) if a.cmd == "report" else cmd_sweep(a)


if __name__ == "__main__":
    sys.exit(main())
