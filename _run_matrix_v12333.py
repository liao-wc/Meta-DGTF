#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题型矩阵真跑（v1.23.33）：**一题一类**，用来
  ①一次性覆盖不同机制面 ②积累数据调优默认配置 ③让 EML 跨跑学习。

题型设计（每类都对应一组**会被激活的机制**）：
  T1 事实型 + 锚点核查 —— 「中微子什么时候发现/别名」
     ⇒ 规则分派命中 serial；web/锚点 → tier / 离线解析验证 / 内部批判 / 分级证明标准
  T2 开放二元对撞 —— 「AI 会先取代设计师还是程序员？」
     ⇒ 含「还是」⇒ 规则命中 **B**；对撞层张力 → 裁决维度拆分 / 悬置
  T3 多目标并列 —— 「如何利用AI帮助人类实现财富自由甚至文明升级？」
     ⇒ 并列目标 → **followup 权重** / 职责守卫点名缺的 core / 与上一版同题可**跨跑对比**
  T4 元问题闭环 —— 「元DGTF 这套方法本身能不能给出可判定的结论？」
     ⇒ route 含 all ⇒ 元层清算 / 三态多票 → **机会校正一致 α/κ** / 多样性预算

★ 全开：每题都走 `all_on: true`（一键全开），并**串行**跑（同一记忆库 ⇒ 后续题
  的 `used_ids` 应非空，演示 EML 跨跑学习）。
★ 停滞看门狗：每题独立进程，**600 秒日志无增长** ⇒ 判停滞、退出码 9，
  跑批脚本**跳过该题继续下一题**（本轮 API 侧不稳，不能一题卡死整批）。
"""

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable

MATRIX = [
    ("T1_fact_anchor",
     "科学家是什么时候发现中微子的？它的别名叫什么？",
     ["0", "1"], {"0": 3, "1": 3}, "事实型 + 锚点核查（serial / tier / 离线验证 / 内部批判）"),
    ("T2_open_duel",
     "AI 会先取代设计师还是程序员？",
     ["0", "1", "both"], {"0": 3, "1": 3, "both": 3}, "开放二元对撞（规则 B / 张力 / 裁决维度）"),
    ("T3_multi_goal",
     "如何利用AI来帮助人类实现财富自由甚至文明升级？",
     ["0", "1", "both"], {"0": 4, "1": 4, "both": 4}, "多目标并列（followup / 职责守卫 / 跨跑对比）"),
    ("T4_meta_closure",
     "元DGTF 这套方法本身能不能给出可判定的结论？",
     ["0", "1", "both", "all"], {"0": 3, "1": 3, "both": 3, "all": 5},
     "元问题闭环（元层清算 / 三态 α·κ / 多样性预算）"),
]


def run_one(tag, q, route, rounds, why):
    print("\n" + "=" * 78)
    print("[%s] %s\n   %s" % (tag, q, why))
    print("   route=%s rounds=%s" % (route, rounds))
    t0 = time.time()
    cmd = [PY, str(HERE / "_run_full_v12333.py"),
           "--src", "元DGTF-V1.23.33.py", "--tag", tag,
           "--question", q, "--stall-sec", "600"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HERE))
    dt = time.time() - t0
    tail = (r.stdout or "")[-400:]
    print("   退出码 %s｜耗时 %.1f min" % (r.returncode, dt / 60))
    if r.returncode == 9:
        print("   ⏸ 判停滞（日志 600s 无增长）⇒ 跳过该题")
    else:
        for ln in tail.splitlines()[-6:]:
            print("   | " + ln)
    return r.returncode, dt


def main():
    res = []
    for tag, q, route, rounds, why in MATRIX:
        # route/rounds 通过环境变量传给 _run_full（它已固定四层全开；这里收窄到矩阵）
        import os
        os.environ["FULLRUN_ROUTE"] = ",".join(route)
        os.environ["FULLRUN_ROUNDS"] = json.dumps({k: int(v) for k, v in rounds.items()})
        rc, dt = run_one(tag, q, route, rounds, why)
        res.append((tag, rc, dt))
    print("\n" + "=" * 78)
    print("矩阵跑批汇总：")
    for tag, rc, dt in res:
        print("  %-16s 退出码 %-3s %.1f min" % (tag, rc, dt / 60))
    ok = sum(1 for _, rc, _ in res if rc == 0)
    print("完成 %d / %d 题" % (ok, len(res)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
