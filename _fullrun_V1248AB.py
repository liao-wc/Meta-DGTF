# -*- coding: utf-8 -*-
"""v1.23.48 真跑对表（A/B 对照，唯一花钱的一步，用户已确认）。

**设计（最优 = 单位元信息量最大）**：
  · 同一题、同 route/rounds/serial ⇒ A 与 B 只差「新优化项开不开」；
  · **Run A（BASE）** = 出厂 yaml + 引擎 `_ALL_ON_ITEMS`（11 项，与 V1236FULL 同配置）
    + **新键全关** ⇒ 既是「零回归」对照，也是成本基线；
  · **Run B（ALLNEW）** = A + 五个新键全开（P-1 裁剪 / P-2 早停 / P-3 冷启 / P-3b 语义合并 /
    P-5 口径）。差值 = 本轮全部优化的净效果。
  · **顺序跑**（A→B）：避免两次跑同时写 EML 库互相污染，让 A/B 可比。
  · 全程记账：显式 `run(..., run_id=...)` + `_eml_finish`（EML 才会学这次跑）。
预算：按历史 ~¥4.17/次估算，两次约 ¥8.4。
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.48.py"

QUESTION = "一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住。"
ROUTE = ["0", "1", "both", "all"]
ROUNDS = {"0": 4, "1": 4, "both": 4, "all": 5}

#: 本轮新增的优化键（默认全关 ⇒ 出厂逐字不变）
NEW_KEYS = {
    "spiral.shape_limit": 8,          # P-1 上下文裁剪
    "stop.gain_floor": 0.01,          # P-2 早停阈值 α
    "memory.eml_adaptive": True,      # P-3 EML 冷启自适应
    "memory.eml_semantic_merge": True,  # P-3b commit 前语义近重合并
    "duty.span_tolerant": True,       # P-5 职责 S 口径对称化
}


def _set_dotted(cfg: dict, dotted: str, val) -> None:
    ks = dotted.split(".")
    d = cfg
    for k in ks[:-1]:
        d = d.setdefault(k, {})
        if not isinstance(d, dict):
            return
    d[ks[-1]] = val


def _build(engine, new_on: bool) -> dict:
    cfg = engine.load_config(str(HERE / "dgtf_config.yaml"))
    # 全开清单：**只读引擎**（单一真相源），本脚本不另存第二份
    for k, v, _why in engine._ALL_ON_ITEMS:
        _set_dotted(cfg, k, v)
    if new_on:
        for k, v in NEW_KEYS.items():
            _set_dotted(cfg, k, v)
    return cfg


def _one(tag: str, new_on: bool) -> dict:
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("eng_%s" % tag, str(SRC))
    eng = importlib.util.module_from_spec(spec)
    sys.modules["eng_%s" % tag] = eng
    spec.loader.exec_module(eng)

    cfg = _build(eng, new_on)
    run_id = "V1248%s_%s" % (tag, time.strftime("%Y%m%d_%H%M%S"))
    print("[%s] run_id=%s | 新键=%s" % (tag, run_id, "ON" if new_on else "OFF"))
    if new_on:
        for k, v in NEW_KEYS.items():
            _c = cfg
            ok = True
            for kk in k.split("."):
                if isinstance(_c, dict) and kk in _c:
                    _c = _c[kk]
                else:
                    ok = False
                    break
            print("   %-28s = %-8s 回读=%s" % (k, v, _c if ok else "缺键"))
    m = eng.MetaDGTF(cfg)
    t0 = time.time()
    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=run_id)
    try:
        res["playbook"] = m._eml_finish(res)
    except Exception as e:  # noqa: BLE001
        print("[%s] _eml_finish 抛错（不影响本次对表）：%r" % (tag, e))
    dt = time.time() - t0
    out = HERE / ("_fullrun_V1248%s.json" % tag)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1,
                              default=str), encoding="utf-8")
    print("[%s] 完成 %.1f min | 产物 %s" % (tag, dt / 60.0, out.name))
    return res


def _summary(res: dict) -> dict:
    """抽对表要用的量（calls / tokens / 分钟 / 质量读数）。

    ★ 干跑逮到的口径：产物里 run_id 的键名是 `id`（不是 `run_id`）；
      duty 不在顶层，在 `views[层]["duty_trace"]` 的最后一条。
    """
    calls = res.get("llm_calls") or {}
    toks = res.get("llm_tokens") or {}
    duty = {}
    for e, v in (res.get("views") or {}).items():
        if not isinstance(v, dict):
            continue
        _d = v.get("duty")
        if isinstance(_d, dict) and _d.get("S") is not None:
            duty[e] = round(float(_d.get("S") or 0.0), 3)
            continue
        _tr = v.get("duty_trace") or []
        if _tr and isinstance(_tr[-1], dict) and _tr[-1].get("S") is not None:
            duty[e] = round(float(_tr[-1].get("S") or 0.0), 3)
    stops = {}
    for e, v in (res.get("views") or {}).items():
        if isinstance(v, dict):
            _tr = v.get("goal_trace") or []
            stops[e] = len(_tr)
    return {"calls": calls, "tokens": toks, "duty_S": duty,
            "run_id": res.get("id"), "rounds_per_layer": stops}


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
    A = B = None
    if which in ("a", "both"):
        A = _one("A", False)
        (HERE / "_fullrun_V1248A.sum.json").write_text(
            json.dumps(_summary(A), ensure_ascii=False, indent=1), encoding="utf-8")
    if which in ("b", "both"):
        B = _one("B", True)
        (HERE / "_fullrun_V1248B.sum.json").write_text(
            json.dumps(_summary(B), ensure_ascii=False, indent=1), encoding="utf-8")
    if A and B:
        sa, sb = _summary(A), _summary(B)
        print("\n=== 对表（A 基线 → B 全开新项）===")
        print("calls:", json.dumps(sa["calls"], ensure_ascii=False),
              "→", json.dumps(sb["calls"], ensure_ascii=False))
        print("tokens:", json.dumps(sa["tokens"], ensure_ascii=False),
              "→", json.dumps(sb["tokens"], ensure_ascii=False))
        print("duty_S:", json.dumps(sa["duty_S"], ensure_ascii=False),
              "→", json.dumps(sb["duty_S"], ensure_ascii=False))
