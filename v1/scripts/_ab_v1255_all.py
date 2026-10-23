# -*- coding: utf-8 -*-
"""元层单层对照（A/B 各一跑）—— 回答「省的钱是不是靠砍元层换的」。

为什么单跑元层：V1255 全跑里唯一实质分歧就是元层（A 4 圈/47 候选 vs B 2 圈/27 候选）。
其它三层内容持平或更好，成本差异的证据已经够。单层跑 25 分钟就能把这个分歧定性。

设计（照抄 V1255 的去混淆方案，只改 route）：
  · `route=["all"]`、`rounds={"all": 5}`、`parallel_mode="serial"`
  · 两臂都关 bandit · 两臂都开 `duty.span_tolerant` · 每臂隔离记忆库
  · 差异仍然只有 4 个键（shape_limit / gain_floor / eml_adaptive / eml_semantic_merge）
  · 硬上限 **120 calls / 20 min**（比全跑更紧；单层不需要 300）

用法：
    python _ab_v1255_all.py --dry
    python _ab_v1255_all.py both
"""
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.54.py"
AB_DIR = HERE / "_ab_v1255_all"
PROD_MEM = HERE / "dgtf_memory"

QUESTION = "一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住。"
ROUTE = ["all"]
ROUNDS = {"all": 5}          # 与全跑同口径（全跑里 all 的 caps 也是 5）
MAX_CALLS = 120
MAX_MINUTES = 20.0

NEW_KEYS = {
    "spiral.shape_limit": 8,
    "stop.gain_floor": 0.01,
    "memory.eml_adaptive": True,
    "memory.eml_semantic_merge": True,
}
SAME_IN_BOTH = {
    "auto.bandit.enabled": False,
    "duty.span_tolerant": True,
}


def _set_dotted(cfg, dotted, val):
    ks = dotted.split(".")
    d = cfg
    for k in ks[:-1]:
        d = d.setdefault(k, {})
        if not isinstance(d, dict):
            return
    d[ks[-1]] = val


def _get_dotted(cfg, dotted):
    d = cfg
    for k in dotted.split("."):
        if not isinstance(d, dict) or k not in d:
            return "<缺键>"
        d = d[k]
    return d


def _mem_dir(tag):
    d = AB_DIR / ("ALL%s_mem" % tag)
    if not d.is_dir():
        d.mkdir(parents=True, exist_ok=True)
        if PROD_MEM.is_dir():
            for f in sorted(PROD_MEM.iterdir()):
                if f.is_file():
                    shutil.copy2(f, d / f.name)
    return d


def _build(engine, tag, new_on):
    cfg = engine.load_config(str(HERE / "dgtf_config.yaml"))
    for k, v, _why in engine._ALL_ON_ITEMS:
        _set_dotted(cfg, k, v)
    for k, v in SAME_IN_BOTH.items():
        _set_dotted(cfg, k, v)
    if new_on:
        for k, v in NEW_KEYS.items():
            _set_dotted(cfg, k, v)
    cfg["max_calls"] = MAX_CALLS
    cfg.setdefault("playbook", {})
    cfg["playbook"]["mode"] = "on"
    cfg["playbook"]["dir"] = str(_mem_dir(tag))
    cfg.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem_dir(tag))
    cfg.setdefault("output", {})["save_dir"] = str(AB_DIR / ("ALL%s_out" % tag))
    return cfg


def _load_engine(tag):
    import importlib.util
    spec = importlib.util.spec_from_file_location("engall_%s" % tag, str(SRC))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _one(tag, new_on):
    eng = _load_engine(tag)
    cfg = _build(eng, tag, new_on)
    run_id = "V1255ALL%s" % tag
    print("\n[%s] run_id=%s | 4 键=%s | route=%s rounds=%s | 上限 %d calls / %.0f min"
          % (tag, run_id, "ON" if new_on else "OFF", ROUTE, ROUNDS,
             MAX_CALLS, MAX_MINUTES))
    for k in ("auto.bandit.enabled", "duty.span_tolerant", "spiral.shape_limit",
              "stop.gain_floor", "memory.eml_adaptive",
              "memory.eml_semantic_merge"):
        print("   %-30s 回读=%s" % (k, _get_dotted(cfg, k)))

    m = eng.MetaDGTF(cfg)
    t0 = time.time()
    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=run_id,
                max_minutes=MAX_MINUTES)
    pb = res.get("playbook")
    if not isinstance(pb, dict) or pb.get("error"):
        try:
            res["playbook"] = m._eml_finish(res)
        except Exception as e:  # noqa: BLE001
            print("[%s] _eml_finish 抛错：%r" % (tag, e))
    dt = time.time() - t0
    out = AB_DIR / ("ALL%s.json" % tag)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    v = (res.get("views") or {}).get("all") or {}
    d = v.get("duty") or {}
    print("[%s] 完成 %.1f min | calls=%s tokens=%s | 圈=%s 候选=%s & %s 线头=%s "
          "S=%s | paused=%s"
          % (tag, dt / 60.0, res.get("llm_calls"), res.get("llm_tokens"),
             v.get("rounds_run"), len(v.get("candidates") or []),
             len(v.get("amps") or []), len(v.get("threads") or []),
             (round(float(d.get("S")), 3) if d.get("S") is not None else "-"),
             res.get("paused")))
    print("[%s] 停因：%s" % (tag, str(v.get("stop_reason") or "")[:110]))
    return res


def _row(res):
    v = (res.get("views") or {}).get("all") or {}
    d = v.get("duty") or {}
    return {"run_id": res.get("id"),
            "calls": res.get("llm_calls") or 0,
            "tokens": res.get("llm_tokens") or 0,
            "rounds": v.get("rounds_run"),
            "cand": len(v.get("candidates") or []),
            "amp": len(v.get("amps") or []),
            "thread": len(v.get("threads") or []),
            "sus": len(v.get("suspensions") or []),
            "S": (round(float(d.get("S")), 3) if d.get("S") is not None else None),
            "stop": str(v.get("stop_reason") or "")[:70],
            "paused": bool(res.get("paused"))}


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
    if which in ("--dry", "dry"):
        for _t, _on in (("A", False), ("B", True)):
            _e = _load_engine(_t)
            _c = _build(_e, _t, _on)
            print("\n[%s] 干跑 | 4 键=%s | route=%s rounds=%s"
                  % (_t, "ON" if _on else "OFF", ROUTE, ROUNDS))
            for k in list(SAME_IN_BOTH) + list(NEW_KEYS):
                print("   %-30s 回读=%s" % (k, _get_dotted(_c, k)))
            print("   %-30s 回读=%s" % ("max_calls", _c.get("max_calls")))
        print("\n干跑结束：未运行引擎。两臂最坏 ~¥1.4（240 calls）。")
        raise SystemExit(0)

    AB_DIR.mkdir(parents=True, exist_ok=True)
    A = B = None
    if which in ("a", "both"):
        A = _one("A", False)
    if which in ("b", "both"):
        B = _one("B", True)
    if A and B:
        ra, rb = _row(A), _row(B)
        print("\n=== 元层单层对照 ===")
        print("%-8s %8s %8s" % ("项", "A", "B"))
        for k, n in (("rounds", "圈"), ("cand", "候选"), ("amp", "&"),
                     ("thread", "线头"), ("sus", "悬置"), ("calls", "调用"),
                     ("tokens", "tokens"), ("S", "S")):
            print("%-8s %8s %8s" % (n, ra.get(k), rb.get(k)))
        print("A 停因：", ra["stop"])
        print("B 停因：", rb["stop"])
        (AB_DIR / "ALL.sum.json").write_text(
            json.dumps({"A": ra, "B": rb}, ensure_ascii=False, indent=1),
            encoding="utf-8")
