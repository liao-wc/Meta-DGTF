# -*- coding: utf-8 -*-
"""P-1 前置测量：mock 真跑四层，量每次 LLM.call 的 prompt 组成。

只读测量（不改任何东西）。输出：逐调用 (stage, sys_chars, user_chars) + 汇总 +
「user 里各区块」的占比（靠打点 `_expand_from_views` 的各段长度）。
"""
import importlib.util
import sys
import threading
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tgt", HERE / "元DGTF-V1.23.41.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["tgt"] = mod
spec.loader.exec_module(mod)
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

LOCK = threading.Lock()
REC = []
SEGS = []

# ── 打点 1：每次 LLM.call 的 prompt 尺寸 ──
_orig_call = st.mod.LLM.call


def _rec_call(self, system, user, temperature=0.6, max_tokens=3000,
              json_mode=False, model=None, thinking=None, stage=None):
    with LOCK:
        REC.append({"stage": str(stage), "sys": len(str(system)),
                    "user": len(str(user))})
    return _orig_call(self, system, user, temperature=temperature,
                      max_tokens=max_tokens, json_mode=json_mode, model=model,
                      thinking=thinking, stage=stage)


st.mod.LLM.call = _rec_call

# ── 打点 2：`_pool_text` / `View.shape_of` 的尺寸（各段谁大） ──
_orig_pool_text = st.mod.DGTF._pool_text


def _rec_pool_text(self, pool):
    r = _orig_pool_text(self, pool)
    with LOCK:
        SEGS.append(("pool_text", len(r)))
    return r


st.mod.DGTF._pool_text = _rec_pool_text

_orig_shape = st.mod.View.shape_of


def _rec_shape(v):
    r = _orig_shape(v)
    with LOCK:
        SEGS.append(("view.shape_of", len(r)))
    return r


st.mod.View.shape_of = staticmethod(_rec_shape)

q = ("什么样的制度设计能让一个群体的长期协作既保持活力又不失去方向？"
     "请从激励、信息、边界三个角度分析。")
meta = st.mod.MetaDGTF(st.build_cfg(False))
res = meta.run(q, route=["0", "1", "both", "all"],
               rounds={"0": 2, "1": 2, "both": 2, "all": 2}, run_id="")

print("=" * 72)
print("P-1 前置测量 · mock 四层 各 2 圈")
print("=" * 72)
tot_sys = sum(r["sys"] for r in REC)
tot_user = sum(r["user"] for r in REC)
print("LLM.call 次数: %d | 累计 sys %d 字符 / user %d 字符（合计 %d）"
      % (len(REC), tot_sys, tot_user, tot_sys + tot_user))
print("\n按 stage 汇总（次数 / user 总字符 / 单次均值）:")
agg = {}
for r in REC:
    a = agg.setdefault(r["stage"], [0, 0])
    a[0] += 1
    a[1] += r["user"]
for s, (n, u) in sorted(agg.items(), key=lambda x: -x[1][1])[:12]:
    print("  %-34s %3d 次 | user 总 %7d | 均 %6d" % (s, n, u, u // n))
print("\n单次 user 最大 top5:")
for r in sorted(REC, key=lambda x: -x["user"])[:5]:
    print("  %-30s user %6d  sys %5d" % (r["stage"], r["user"], r["sys"]))
print("\n各段尺寸（pool_text / view.shape_of）:")
sa = {}
for k, v in SEGS:
    a = sa.setdefault(k, [0, 0, 0])
    a[0] += 1
    a[1] += v
    a[2] = max(a[2], v)
for k, (n, s, mx) in sa.items():
    print("  %-16s 调用 %3d 次 | 总 %7d | 最大 %6d | 均 %6d" % (k, n, s, mx, s // n))
