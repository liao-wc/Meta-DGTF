# -*- coding: utf-8 -*-
"""P-1 验证：① limit=0 逐字零行为差（与 v1.23.41 对比）；② limit>0 变短 + 计数表头；
③ mock 真跑的 prompt 尺寸 0 vs 8。"""
import importlib.util
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, HERE / fname)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


m41 = _load("v41", "元DGTF-V1.23.41.py")
m42 = _load("v42", "元DGTF-V1.23.42.py")

# 造一个大 view（每类都超 8 条）
v = m42.View(entry="0")
v.anchor = "一个领域里的常识是如何形成的，它可靠吗？"
v.manifest = "显形说明" * 5
v.candidates = [{"desc": "候选%d：这是一条比较长的候选描述用来撑长度" % i}
                for i in range(48)]
v.amps = [{"type": "ontological", "desc": "& 印记 %d 一条较长的说明文字" % i}
          for i in range(15)]
v.threads = [{"desc": "线头 %d" % i} for i in range(12)]
v.probes = [{"question": "自问 %d？" % i, "link": "回来 %d" % i}
            for i in range(10)]
v.suspensions = [{"target": "悬置 %d" % i, "reason": "理由 %d" % i,
                  "status": "active"} for i in range(9)]

a = m42.View.shape_of(v)            # limit=0
b = m42.View.shape_of(v, limit=8)
a41 = m41.View.shape_of(v)          # 旧版
print("=" * 70)
print("① limit=0 逐字零行为差（v1.23.42 vs v1.23.41）：", "✅ 相同" if a == a41 else "✗ 不同")
print("   len(limit=0) = %d" % len(a))
print("② limit=8: len = %d（↓ %.0f%%）" % (len(b), 100 * (1 - len(b) / len(a))))
print("   含计数表头「共 48，只列最近 8」：", "✅" if "共 48，只列最近 8" in b else "✗")
print("   含「共 15，只列最近 8」(& 印记)：", "✅" if "共 15，只列最近 8" in b else "✗")

# ③ mock 真跑：prompt 尺寸 0 vs 8
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

LC = threading.Lock()
SIZES = {}


def _run(limit):
    REC = []
    orig = st.mod.LLM.call

    def _rc(self, system, user, temperature=0.6, max_tokens=3000,
            json_mode=False, model=None, thinking=None, stage=None):
        with LC:
            REC.append(len(str(system)) + len(str(user)))
        return orig(self, system, user, temperature=temperature,
                    max_tokens=max_tokens, json_mode=json_mode, model=model,
                    thinking=thinking, stage=stage)
    st.mod.LLM.call = _rc
    cfg = st.build_cfg(False)
    cfg.setdefault("spiral", {})["shape_limit"] = limit
    mt = st.mod.MetaDGTF(cfg)
    q = "什么样的制度设计能让一个群体的长期协作既保持活力又不失去方向？请从激励、信息、边界三个角度分析。"
    mt.run(q, route=["0", "1", "both", "all"],
           rounds={"0": 2, "1": 2, "both": 2, "all": 2}, run_id="")
    st.mod.LLM.call = orig
    return len(REC), sum(REC)


for lim in (0, 8):
    n, tot = _run(lim)
    SIZES[lim] = (n, tot)
    print("③ limit=%d: %d 次调用 | 累计 prompt %d 字符" % (lim, n, tot))
n0, t0 = SIZES[0]
n8, t8 = SIZES[8]
print("   prompt 累计 ↓ %.1f%%（%d → %d）" % (100 * (1 - t8 / t0), t0, t8))
