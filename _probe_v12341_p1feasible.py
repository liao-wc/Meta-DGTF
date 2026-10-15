# -*- coding: utf-8 -*-
"""P1 可行性：能否用构造的 View 对 entry='all' 调 _finalize_layer_common，
再看 goal_verdict 是否被（将要加的）刷新改到 1.000。

★ 这是**改前**的探针：预期看到 goal_verdict 仍取旧值（crystallize=0.500），
  证明「刷新前 stale」。
"""
import importlib.util
import io
import sys
import contextlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tgt", HERE / "元DGTF-V1.23.41.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["tgt"] = mod
spec.loader.exec_module(mod)
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

m = mod.MetaDGTF(st.build_cfg(False))
v = mod.View(entry="all")
# 预置：四件事齐（meta_closure 有 total + engagements + suspensions）
v.meta_closure = {"clean": True, "total": 3, "unsettled": 0}
v.engagements = [{"tension_id": "t1"}]
v.suspensions = [{"id": "s1", "status": "active"}]
# 模拟「层停止时」的 stale goal_now（只数到 2 件）
v.goal_now = {"crystallize": 0.5, "n_hits": 2}
v.rounds_run = 2
v.stop_reason = "自省空转，螺旋停止"
stt = {"roles_hist": ["结晶"], "total_rounds": 2, "round_log": [],
       "all_rehashed": [], "all_candidates": [], "all_amps": [],
       "all_threads": [], "all_expanded_descs": [],
       "all_dec_products": [], "all_und_products": [],
       "r": 2, "rounds_n": 2, "sp": mod._spiral_for(st.build_cfg(False), "all")}
try:
    with contextlib.redirect_stdout(io.StringIO()):
        m._finalize_layer_common("all", v, stt)
except Exception as e:
    print("[ERR]", type(e).__name__, e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("meta_closure 落地:", bool(getattr(v, "meta_closure", None)))
print("goal_now:", getattr(v, "goal_now", None))
print("goal_verdict:", getattr(v, "goal_verdict", ""))
# 用最终 view 重算读数，看应得值
fresh = mod.layer_goal_readings({"all": v.to_dict()}).get("all") or {}
print("最终读应得 crystallize:", fresh.get("crystallize"), "| n_hits:", fresh.get("n_hits"))
