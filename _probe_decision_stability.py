# -*- coding: utf-8 -*-
"""
判定稳定性探针：把「输入随机」和「采样随机」分开。

做法：
  1. 跑一次修行层（拿到一个**固定的** zero_view）
  2. 对**同一个** zero_view 重复调用池评估 N 次

判读：
  · N 次结果不一致 → 输入固定也漂移，是**采样随机**（温度/单次采信）
  · N 次结果一致   → 漂移来自**输入**（修行层形状每次跑都不一样）

用法：python -u _probe_decision_stability.py "<问题>" [圈数] [重复次数]
"""
import sys
import json
import collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import importlib.util
from dotenv import load_dotenv

load_dotenv(HERE / ".env")

spec = importlib.util.spec_from_file_location("dgtf61", HERE / "元DGTF-V1.21.61.py")
mod = importlib.util.module_from_spec(spec)
# 必须先注册再 exec：模块里的 @dataclass 解析要查 sys.modules[cls.__module__]
sys.modules["dgtf61"] = mod
spec.loader.exec_module(mod)

QUESTION = sys.argv[1] if len(sys.argv) > 1 else \
    "怎么衡量一条城市地铁线路的运营效率？用什么指标、数据从哪来？"
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
N = int(sys.argv[3]) if len(sys.argv) > 3 else 5

print(f"=== 判定稳定性探针 ===")
print(f"问题：{QUESTION}")
print(f"修行层 {ROUNDS} 圈，随后对**同一 view** 重复评估 {N} 次\n")

cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
meta = mod.MetaDGTF(cfg)

# ---- 1. 跑修行层，拿到固定的 zero_view ----
res = meta.run(QUESTION, route=["0"], rounds={"0": ROUNDS},
               parallel_mode="serial")
zero_view = meta._results.get("0")
if zero_view is None:
    print("❌ 修行层没产出 view，探针终止")
    sys.exit(1)

print(f"\n--- 修行层产出（评估输入，已固定）---")
print(f"  candidates={len(zero_view.candidates or [])}  "
      f"amps={len(zero_view.amps or [])}  "
      f"threads={len(zero_view.threads or [])}  "
      f"suspensions={len(zero_view.suspensions or [])}  "
      f"collision={len(zero_view.collision or '')}字")

# ---- 2. 同一输入重复评估 ----
votes = collections.Counter()
und_sets = []
print(f"\n--- 对同一 view 重复评估 {N} 次 ---")
for i in range(1, N + 1):
    try:
        r = meta._assess_decidability_from_pool_view(QUESTION, zero_view)
    except Exception as e:
        print(f"  #{i} 调用失败：{type(e).__name__}: {e}")
        continue
    st = r.get("decidability", "?")
    und = tuple(r.get("undecidable_aspects") or [])
    votes[st] += 1
    und_sets.append(und)
    print(f"  #{i} → {st}"
          f"｜不可判定 {len(und)} 条：{list(und)[:2]}")

print(f"\n=== 结论 ===")
print(f"判定分布：{dict(votes)}")
_distinct_und = len(set(und_sets))
print(f"不可判定清单的不同版本数：{_distinct_und} / {len(und_sets)}")
if len(votes) > 1:
    print("★ 输入固定，判定仍然漂移 → 采样随机（温度/单次采信）是根因之一")
elif _distinct_und > 1:
    print("★ 判定值一致，但**不可判定清单**每次不同 → 方面级漂移，"
          "判定值稳定是假象")
else:
    print("★ 输入固定时判定稳定 → 漂移来自输入（修行层形状每次不同）")
