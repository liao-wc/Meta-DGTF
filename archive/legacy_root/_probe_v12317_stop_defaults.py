# -*- coding: utf-8 -*-
"""v1.23.17 前置探针：三个停止阈值/门槛改动的 before-after 对表。

用法：python _probe_v12317_stop_defaults.py 元DGTF-V1.23.16.py
     （改前/改后同一支探针各跑一次，两份 txt 对表）

量四类：
  A 源码字面：两处 sat 缺省、四处 soft_max 缺省各是多少
  B 出厂默认：DEFAULT_CONFIG["spiral"] 的 soft_max / structure_saturation_every_n
  C 行为：_stop_reasons 条件 1 是否对 entry="1" 生效（改前被 entry in ("all","both") 挡）
         + soft_max 对条件 1 的 deferral（layer_no < soft_max）
  D 行为：_apply_view_to_pool_locked 在 entry 0/1 下把复述圈数写到哪，
         经 _compute_rephrase_streak 能不能读回来
  E 现网差异：出厂 yaml 的 sat 值与 DEFAULT_CONFIG 是否一致（另一条真 bug 的读数）
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.16.py")
spec = importlib.util.spec_from_file_location("m", str(TARGET))
mod = importlib.util.module_from_spec(spec)
sys.modules["m"] = mod
spec.loader.exec_module(mod)

out = {}
SRC = TARGET.read_text(encoding="utf-8")

# ── A 源码字面 ──────────────────────────────────────────────
out["A_sat_缺省字面"] = sorted(set(re.findall(
    r'structure_saturation_every_n",\s*(\d+)', SRC)))
out["A_soft_缺省字面"] = sorted(set(re.findall(
    r'soft_max",\s*(\d+)', SRC)))
out["A_soft_or字面"] = sorted(set(re.findall(
    r'soft_max",\s*\d+\s*\)\s*or\s*(\d+)', SRC)))

# ── B 出厂默认 ─────────────────────────────────────────────
_sp = mod.DEFAULT_CONFIG.get("spiral") or {}
out["B_def_soft_max"] = _sp.get("soft_max")
out["B_def_sat"] = _sp.get("structure_saturation_every_n")

# ── C 行为：条件 1 对 entry 0/1 ─────────────────────────────
CFG = mod.load_config(str(HERE / "__nope__.yaml"))
_mr = mod.MetaDGTF(CFG)
_body = SRC.replace("\r\n", "\n")
try:
    _i = _body.index("    def _stop_reasons(")
    _j = _body.index("\n    def ", _i + 10)
    _fn = _body[_i:_j]
except ValueError:
    _fn = ""
out["C_门槛仍在_stop_reasons内"] = _fn.count('if entry in ("all", "both"):')


def _reasons(entry, layer_no, soft, carry, reph):
    _r, _ = _mr._stop_reasons(
        entry=entry, layer_no=layer_no, rounds_n=3, total_rounds=3,
        sp=dict(_sp), soft_max=soft, sim_thr=0.8, stable_need=2,
        idle_limit=2, r_idle_limit=2, r_stall_limit=2,
        rephrase_streak=reph, carry_streak=carry,
        idle_new_amp=0, idle_new_thread=0, idle_stall=0,
        stall_why="", sat_override=False,
        prev_product="", view=mod.View(entry=entry), idles=0)
    return " | ".join(str(x) for x in _r)


for _e in ("0", "1"):
    try:
        _t = _reasons(_e, 3, int(_sp.get("soft_max", 3)), 2, 2)
        out["C_entry%s_软阈%s_有理由" % (_e, _sp.get("soft_max"))] = bool(_t)
        out["C_entry%s_理由" % _e] = _t[:70]
        out["C_entry%s_含复述" % _e] = "圈复述" in _t
        out["C_entry%s_含点名" % _e] = "点名同一批问题未消化" in _t
    except Exception as exc:  # noqa: BLE001
        out["C_entry%s_异常" % _e] = "%s: %s" % (type(exc).__name__, exc)

# soft_max 对条件 1 的 deferral：同一输入，只改 soft_max / layer_no
for _s, _ln in ((3, 2), (2, 2), (2, 3), (3, 3)):
    try:
        _t = _reasons("1", _ln, _s, 2, 2)
        out["C_soft%s_ln%s_有理由" % (_s, _ln)] = bool(_t)
    except Exception as exc:  # noqa: BLE001
        out["C_soft%s_ln%s_异常" % (_s, _ln)] = type(exc).__name__

# ── D 行为：entry 0/1 的复述信号能否被读回 ─────────────────
for _e in ("0", "1"):
    try:
        _pool = mod.Pool()
        _v = mod.View(entry=_e)
        _v._ing_rephrase_ratio = 0.6      # 直接判复述
        _st = {"rephrased_streak": 0, "meta_idle_streak": 0}
        for _k in range(2):
            _st["rephrased_streak"], _st["meta_idle_streak"] = (
                _mr._apply_view_to_pool_locked(
                    _v, _pool, _e, _st["rephrased_streak"],
                    _st["meta_idle_streak"], 2))
        out["D_entry%s_rephrased_streak" % _e] = _st["rephrased_streak"]
        out["D_entry%s_view_meta_idle" % _e] = getattr(
            _v, "_meta_idle_streak", None)
        out["D_entry%s_读到" % _e] = mod._compute_rephrase_streak(_v, _st)
    except Exception as exc:  # noqa: BLE001
        out["D_entry%s_异常" % _e] = "%s: %s" % (type(exc).__name__, exc)

# ── E 现网差异：出厂 yaml vs 默认 ─────────────────────────
try:
    _y = mod.load_config(str(HERE / "dgtf_config.yaml"))
    out["E_yaml生效_sat"] = _y["spiral"].get("structure_saturation_every_n")
    out["E_yaml生效_soft"] = _y["spiral"].get("soft_max")
    out["E_yaml与默认一致_sat"] = (
        out["E_yaml生效_sat"] == out["B_def_sat"])
except Exception as exc:  # noqa: BLE001
    out["E_异常"] = type(exc).__name__

for k in sorted(out):
    print("%-30s %s" % (k, out[k]))
