# -*- coding: utf-8 -*-
"""v1.23.50 真跑对表（A/B 对照，唯一花钱的一步，用户已确认）。

★ 与 `_fullrun_V1249AB.py` 的区别：引擎换 v1.23.50，且 **run_id 固定**
  （`V1250A` / `V1250B`）+ 启动时**自动探测快照续跑** —— 被宿主回收后
  **重发同一条命令即可接着跑**（已完成的层不重跑、不重烧钱）。

★ 与 `_fullrun_V1248AB.py` 的唯一区别：引擎换成 v1.23.49 —— **带跑中快照
  安全网**（12:37 那次 V1248 真跑被宿主回收 ⇒ 24 分钟 / ~¥2 全丢；
  本版起 live_checkpoint 默认 true ⇒ 中断可找回）。A/B 设计一字未动。

**设计（最优 = 单位元信息量最大）**：
  · 同一题、同 route/rounds/serial ⇒ A 与 B 只差「新优化项开不开」；
  · **Run A（BASE）** = 出厂 yaml + 引擎 `_ALL_ON_ITEMS`（11 项，与 V1236FULL 同配置）
    + **新键全关** ⇒ 既是「零回归」对照，也是成本基线；
  · **Run B（ALLNEW）** = A + 五个新键全开（P-1 裁剪 / P-2 早停 / P-3 冷启 / P-3b 语义合并 /
    P-5 口径）。差值 = 本轮全部优化的净效果。
  · **顺序跑**（A→B）：避免两次跑同时写 EML 库互相污染，让 A/B 可比。
  · 全程记账：显式 `run(..., run_id=...)`（EML 只学**有 id** 的跑次；
    `_eml_finish` 由 `run()` 内部调用，此处**不得**重复调用）。
预算：按历史 ~¥4.17/次估算，两次约 ¥8.4。
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.50.py"

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
    run_id = "V1250%s" % tag           # ★ 固定 id ⇒ 重发命令即可续跑
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
    # ★ 续跑探测：同一 run_id 已有快照 ⇒ 能续就续；已完成就直接读产物。
    _ck = Path(eng.run_ckpt_path(run_id))
    _resume, _prev = "", None
    if _ck.is_file():
        try:
            _d = json.loads(_ck.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _d = {}
        _st = str((_d or {}).get("status") or "")
        _done = sorted((_d or {}).get("views") or {})
        print("[%s] 发现快照 %s：status=%s 已完成层=%s"
              % (tag, _ck.name, _st, _done))
        if _st in ("running", "interrupted", "paused"):
            _resume = str(_ck)
            print("[%s] ⇒ 从快照**续跑**（已完成的层不重烧）" % tag)
        elif _st == "done" and len(_done) >= len(ROUTE):
            _p = HERE / ("_fullrun_V1250%s.json" % tag)
            if _p.is_file():
                _prev = json.loads(_p.read_text(encoding="utf-8"))
    if _prev is not None:
        print("[%s] 已有完成产物（%s）⇒ 直接用它出表"
              % (tag, _p.name))
        return _prev
    m = eng.MetaDGTF(cfg)
    t0 = time.time()
    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=run_id,
                resume_ckpt=_resume)
    # ★ [学一次] `run()` 内部**已经**调过 `_eml_finish`（`run_id` 盖进产物之后）。
    #   这里只在「真的没有 playbook 块」或「那块是异常兜底」时补一次 —— 无条件
    #   再调一次会让同一跑次写两条 episode、把 weight 罚两遍（实测脏了 5 个文件，
    #   见 `_commitmsg_dedup_20261016.txt`）。
    _pb = res.get("playbook")
    if not isinstance(_pb, dict) or _pb.get("error"):
        try:
            res["playbook"] = m._eml_finish(res)
        except Exception as e:  # noqa: BLE001
            print("[%s] _eml_finish 抛错（不影响本次对表）：%r" % (tag, e))
    dt = time.time() - t0
    out = HERE / ("_fullrun_V1250%s.json" % tag)
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
        (HERE / "_fullrun_V1250A.sum.json").write_text(
            json.dumps(_summary(A), ensure_ascii=False, indent=1), encoding="utf-8")
    if which in ("b", "both"):
        B = _one("B", True)
        (HERE / "_fullrun_V1250B.sum.json").write_text(
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
