# -*- coding: utf-8 -*-
"""v1.23.16 前置探针：自然停治本三条 + 成本档维度删除。

用法：python _probe_v12316_stop_therapy.py [目标.py]

量法三项原则：
  ① 尽量走生产入口（`MetaDGTF.run` + 桩 LLM），不手造内部对象；
  ② 每项都有一条**在改前就为「旧值」**的读数（否则没有判别力）；
  ③ 形态量法只用于「没有行为入口」的项（如窗口参照集的构造串）。
"""
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "元DGTF-V1.23.15.py")

src = SMOKE.read_text(encoding="utf-8")
PAT = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(PAT.findall(src)) == 1, "SRC 行不是 1 行"
src = PAT.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), src)

TD = tempfile.mkdtemp(prefix="v12316_")
os.environ["SMOKE_SAVE_DIR"] = TD
hm = types.ModuleType("harness")
hm.__file__ = str(SMOKE)
sys.modules["harness"] = hm
exec(compile(src, str(SMOKE), "exec"), hm.__dict__)
mod = hm.mod
CFG = hm.build_cfg(False)

out = {}
out["ver"] = getattr(mod, "__version__", "?")

# ── A · 成本档维度是否存在 ────────────────────────────────────
out["A__COST_PROFILES_在"] = hasattr(mod, "_COST_PROFILES")
out["A__profile_plan_在"] = hasattr(mod, "_profile_plan")
out["A__auto_pick_cost_profile_在"] = hasattr(mod, "_auto_pick_cost_profile")
out["A__auto_profile_在"] = hasattr(mod, "_auto_profile")
out["A_DEFAULT_CONFIG含cost_profile"] = "cost_profile" in (mod.DEFAULT_CONFIG or {})
out["A_auto项数"] = len(getattr(mod, "_AUTO_ITEM_ORDER", ()))
out["A_auto含cost_profile"] = "cost_profile" in getattr(mod, "_AUTO_ITEM_ORDER", ())
_src_txt = TARGET.read_text(encoding="utf-8")
out["A_源码含--profile"] = "--profile" in _src_txt
out["A_源码含_COST_PROFILES"] = "_COST_PROFILES" in _src_txt

# ── B · 低频项惰性化 ─────────────────────────────────────────
try:
    _m = mod.MetaDGTF(CFG)
    out["B_lazy_every_n_3"] = _m._lazy_every_n(3)
except Exception as e:  # noqa: BLE001
    out["B_lazy_every_n_3"] = "异常:%s" % type(e).__name__
if hasattr(mod, "_profile_plan"):
    out["B_profile_plan默认档"] = mod._profile_plan({}).get("profile")
    out["B_plan_lazy_lowfreq"] = mod._profile_plan({}).get("lazy_lowfreq")

# ── C · 窗口参照集的构造形态（无行为入口，用形态）────────────
out["C_窗口串_serial"] = _src_txt.count("win_amps[-r_window:]")
out["C_窗口串_b通道"] = _src_txt.count('state["win_amps"][-r_window:]')
out["C_sat入口含entry限制"] = (
    'and entry in ("1", "all")' in _src_txt)
out["C_sat_override只对entry1"] = (
    'if entry == "1":\n                        idle_new_amp = max(' in
    _src_txt.replace("\r\n", "\n"))

# ── D · 自然停通路（行为：桩驱动四层 × 4 圈）─────────────────
SAT = {"n": 0}
ROUND = {"n": 0}
ORIG = mod.LLM.call


MOCK = {"n": 0, "hit": 0, "sys": [], "users": []}


def _mock_run(self, system, user, *a, **kw):
    """主 run 调用：返回含 amps / threads 的 JSON（每圈不同，保证 new_amps 非空）。"""
    MOCK["n"] += 1
    if len(MOCK["sys"]) < 6:
        MOCK["sys"].append((system or "")[:36])
    if len(MOCK["users"]) < 4:
        MOCK["users"].append((user or "")[:150])
    if "【& 候选" in (user or ""):
        MOCK["hit"] += 1
        ROUND["n"] += 1
        k = ROUND["n"]
        return json.dumps({
            "amps": [{"desc": "第%d圈第%d条结构：槽位%s的状态列可空但不可由人名填充"
                              % (k, i, "甲乙丙"[i % 3]), "type": "ontological"}
                     for i in range(1, 4)],
            "threads": ["第%d圈线头：%s" % (k, "丁戊己"[k % 3])],
            "meta": [],
        }, ensure_ascii=False)
    if "结构饱和度检查者" in (system or ""):
        SAT["n"] += 1
        return json.dumps({"new_dimension": False,
                           "reason": "smoke-sat：仅换措辞",
                           "shared_axes": []}, ensure_ascii=False)
    return ORIG(self, system, user, *a, **kw)


# ★ 隔离干扰判据：本组只想看「sat 判定 → 计数推动」这一条通路。
#   · 空转 / 无推进阈值拉到 9 ⇒ 前几圈不会因它们停；
#   · soft_max=9 ⇒ 「复述/自省」与「自然安住」两条（都要求
#     layer_no >= soft_max）压根不进；
#   · `structure_saturation_every_n=1`：改前经 `_lazy_every_n(+1)` 变 2
#     （第 2 圈触发）、改后不惰性化 ⇒ 第 1 圈触发；
#   · `round_idle_limit` 保持默认 2 —— 它就是 sat 判 False 时要推到的门槛。
_c = hm.build_cfg(False)
_sp = _c.setdefault("spiral", {})
_sp["structure_saturation_every_n"] = 1
_sp["round_stall_limit"] = 9
_sp["round_idle_limit"] = 2
_sp["idle_limit"] = 9
_sp["soft_max"] = 9
_sp["min_rounds"] = {"0": 0, "1": 0, "both": 0, "all": 0}

mod.LLM.call = _mock_run
SAT["n"] = 0
ROUND["n"] = 0
try:
    _m2 = mod.MetaDGTF(_c)
    res = _m2.run("测试题：这份方案怎么落地，责任怎么分",
                  route=["0", "1", "both", "all"],
                  rounds={"0": 4, "1": 4, "both": 4, "all": 4},
                  parallel_mode="serial")
finally:
    mod.LLM.call = ORIG

out["D_sat触发次数"] = SAT["n"]
out["D_桩被调"] = MOCK["n"]
out["D_桩命中&候选"] = MOCK["hit"]
for _i, _u in enumerate(MOCK["users"]):
    print("  [user%d] %s" % (_i, _u.replace(chr(10), " / ")))
for _i, _v in enumerate(MOCK["sys"]):
    print("  [sys%d] %s" % (_i, _v.replace(chr(10), " / ")))
LAYERS = {}
for e in ("0", "1", "both", "all"):
    v = (res.get("views") or {}).get(e) or {}
    LAYERS[e] = (v.get("rounds_run"), str(v.get("stop_reason") or ""))
    out["D_%s_停圈" % e] = v.get("rounds_run")
    out["D_%s_自然停" % e] = bool(v.get("stop_reason"))
    out["D_%s_元维度停" % e] = "结构饱和度" in str(v.get("stop_reason") or "")
    out["D_%s_停因" % e] = str(v.get("stop_reason") or "")[:56]
out["D_自然停层数"] = sum(1 for e in LAYERS if LAYERS[e][1])
out["D_四层停圈"] = [LAYERS[e][0] for e in ("0", "1", "both", "all")]

# ── E · auto plan 的 schema 键 ───────────────────────────────
try:
    _p = mod.auto_dispatch("这份方案怎么落地", hm.build_cfg(False))
    out["E_auto项"] = len(_p.get("_items") or {})
    out["E_auto含cost_profile"] = "cost_profile" in (_p.get("_items") or {})
except Exception as e:  # noqa: BLE001
    out["E_auto项"] = "异常:%s" % type(e).__name__

for k, v in out.items():
    print("%-34s = %s" % (k, v))
