# -*- coding: utf-8 -*-
"""F3 真跑诊断探针：在真实引擎里打印回填时刻的读数。

做法：**不改主文件**。用 `importlib` 载入主文件后，**猴补丁**包一层
`_apply_view_to_pool_locked`，把进出时的 `pool.belief_items` /
`view.amps` / `view.belief_items` 打出来，然后跑一次真实 `MetaDGTF.run`
（route 0,1，rounds 1，便宜）。
"""
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.28.py"

spec = importlib.util.spec_from_file_location("modd", str(SRC))
mod = importlib.util.module_from_spec(spec)
sys.modules["modd"] = mod
spec.loader.exec_module(mod)

_LOG = []
_orig = mod.MetaDGTF._apply_view_to_pool_locked


def _wrapped(self, view, pool, entry, *a, **kw):
    n_pool_before = len(pool.belief_items or [])
    n_amp = len(view.amps or [])
    has_und = bool(getattr(view, "undecidable_product", None))
    r = _orig(self, view, pool, entry, *a, **kw)
    n_pool_after = len(pool.belief_items or [])
    n_view = len(view.belief_items or [])
    _LOG.append({
        "entry": entry, "n_amp": n_amp, "has_und": has_und,
        "pool_before": n_pool_before, "pool_after": n_pool_after,
        "view_after": n_view,
    })
    return r


mod.MetaDGTF._apply_view_to_pool_locked = _wrapped

print(">>> 启动真实跑（route 0,1 / rounds 1）...")
try:
    meta = mod.MetaDGTF(config=None)
    res = meta.run(
        "验证信念四态与语义熵是否真的落盘",
        route="0,1", rounds=1, web=False)
except TypeError:
    # 签名不同则退回 CLI 入口
    sys.argv = [str(SRC), "--rounds", "1", "--web", "off",
                "--route", "0,1", "验证信念四态与语义熵是否真的落盘"]
    res = mod.main()

print("\n=== 回填时刻读数（每次 _apply_view_to_pool_locked 一条）===")
for i, r in enumerate(_LOG, 1):
    print("  #%d entry=%s amps=%d has_und=%s pool_before=%d "
          "pool_after=%d view_after=%d"
          % (i, r["entry"], r["n_amp"], r["has_und"],
             r["pool_before"], r["pool_after"], r["view_after"]))

# 产物里 view 的最终读数
try:
    vs = (res or {}).get("views") or {}
except Exception:
    vs = {}
print("\n=== 产物 views.*.belief_items ===")
for k, v in vs.items():
    if isinstance(v, dict):
        print("  view %s -> %d" % (k, len(v.get("belief_items") or [])))
