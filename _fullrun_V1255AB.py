# -*- coding: utf-8 -*-
"""v1.23.54 真跑对表（A/B 对照）—— **去掉了上一轮的两处混淆**。

上一轮（V1250A/B）的结论是「B 交付面更足，但**没有省钱**（+46% tokens）」，但那份
结论挂了两处混淆，本轮逐条扣掉：

  ① **bandit 跨臂漂移**：`all_on` 会开预算 bandit，A 跑完更新臂状态 ⇒ B 起跑时
     caps 已经不是同一把尺子（实测修行 8/7、研究 7/8，B 多跑 6 圈）。
     ⇒ 本轮**两臂都强制关 bandit**（caps 由 `ROUNDS` 显式给定，两臂完全一致）。
  ② **P-5 改的是度量口径**（`duty.span_tolerant`）⇒ 两臂的职责 S **不是同一把尺子**，
     S 上升不能当"交付更好"。⇒ 本轮 `duty.span_tolerant` **两臂都开**，只隔离其余
     四个键；S 从此同口径可比。
  ③ 【新增】**两臂记忆库隔离**：各用一份从生产库复制的 `playbook.dir`，
     顺序跑也不再让 A 的学习渗进 B（跨臂污染也是噪声）。
     —— 这一条是 v1.23.53 把目录解析收成一处之后才好做的。

于是本轮隔离出来的差异 = **4 个键**：
  · `spiral.shape_limit = 8`         （P-1 上下文裁剪）
  · `stop.gain_floor = 0.01`         （P-2 早停阈值）
  · `memory.eml_adaptive = True`     （P-3 EML 冷启自适应）
  · `memory.eml_semantic_merge = True`（P-3b commit 前语义近重合并）

**硬成本上限**（用户已确认 ¥9.3）：
  · `cfg["max_calls"] = 300`（**每臂**调用次数天花板 ⇒ 到点引擎自己收尾）
  · `run(..., max_minutes=35)`（每臂墙钟天花板；v1.23.54 起并行也吃这个）
  · 按上轮实测 269 calls ≈ ¥4.17 折算，两臂最坏 ~¥9.3。

用法：
    python _fullrun_V1255AB.py --dry        # 只打印配置与上限，不跑（零花费）
    python _fullrun_V1255AB.py both         # 跑两臂（A→B 顺序）
    python _fullrun_V1255AB.py a            # 只跑 A；重发同一条命令会自动续跑
"""
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.54.py"
AB_DIR = HERE / "_ab_v1255"
PROD_MEM = HERE / "dgtf_memory"

QUESTION = "一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住。"
ROUTE = ["0", "1", "both", "all"]
ROUNDS = {"0": 4, "1": 4, "both": 4, "all": 5}     # ★ 两臂**同一份**（bandit 已关）

MAX_CALLS = 300          # 每臂调用次数硬上限（钱封死）
MAX_MINUTES = 35.0       # 每臂墙钟硬上限（时间封死）

#: 本轮隔离出来的差异（B 臂额外打开这四个）
NEW_KEYS = {
    "spiral.shape_limit": 8,            # P-1 上下文裁剪
    "stop.gain_floor": 0.01,            # P-2 早停阈值
    "memory.eml_adaptive": True,        # P-3 EML 冷启自适应
    "memory.eml_semantic_merge": True,  # P-3b commit 前语义近重合并
}

#: 两臂**共同**的强制项（把上一轮的混淆钉死）
SAME_IN_BOTH = {
    "auto.bandit.enabled": False,   # ① 关 bandit ⇒ caps 不受跨臂漂移影响
    "duty.span_tolerant": True,     # ② S 同口径 ⇒ 两臂可比
}


def _set_dotted(cfg: dict, dotted: str, val) -> None:
    ks = dotted.split(".")
    d = cfg
    for k in ks[:-1]:
        d = d.setdefault(k, {})
        if not isinstance(d, dict):
            return
    d[ks[-1]] = val


def _get_dotted(cfg: dict, dotted: str):
    d = cfg
    for k in dotted.split("."):
        if not isinstance(d, dict) or k not in d:
            return "<缺键>"
        d = d[k]
    return d


def _mem_dir(tag: str) -> Path:
    """每臂一份**独立的**记忆库：从生产库复制一份种子（两臂种子完全相同）。"""
    d = AB_DIR / ("V1255%s_mem" % tag)
    if not d.is_dir():
        d.mkdir(parents=True, exist_ok=True)
        if PROD_MEM.is_dir():
            for f in sorted(PROD_MEM.iterdir()):
                if f.is_file():
                    shutil.copy2(f, d / f.name)
    return d


def _build(engine, tag: str, new_on: bool) -> dict:
    cfg = engine.load_config(str(HERE / "dgtf_config.yaml"))
    # 全开清单：**只读引擎**（单一真相源），本脚本不另存第二份
    for k, v, _why in engine._ALL_ON_ITEMS:
        _set_dotted(cfg, k, v)
    # ★ 两臂共同项：把上一轮的两处混淆钉死（顺序在 NEW_KEYS 之前）
    for k, v in SAME_IN_BOTH.items():
        _set_dotted(cfg, k, v)
    if new_on:
        for k, v in NEW_KEYS.items():
            _set_dotted(cfg, k, v)
    # ★ 硬成本上限 + 记忆库/产物隔离
    cfg["max_calls"] = MAX_CALLS
    cfg.setdefault("playbook", {})
    cfg["playbook"]["mode"] = "on"
    cfg["playbook"]["dir"] = str(_mem_dir(tag))
    cfg.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem_dir(tag))
    cfg.setdefault("output", {})["save_dir"] = str(AB_DIR / ("V1255%s_out" % tag))
    return cfg


def _load_engine(tag: str):
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("eng_%s" % tag, str(SRC))
    eng = importlib.util.module_from_spec(spec)
    sys.modules["eng_%s" % tag] = eng
    spec.loader.exec_module(eng)
    return eng


def _print_cfg(tag: str, cfg: dict) -> None:
    print("[%s] 配置回读：" % tag)
    for k in list(SAME_IN_BOTH) + list(NEW_KEYS):
        print("   %-30s = %-8s 回读=%s"
              % (k, _get_dotted(cfg, k) if k in SAME_IN_BOTH
                 else NEW_KEYS[k], _get_dotted(cfg, k)))
    print("   %-30s = %-8s 回读=%s" % ("max_calls", MAX_CALLS, cfg.get("max_calls")))
    print("   %-30s = %-8s" % ("playbook.dir", cfg["playbook"]["dir"]))
    print("   %-30s = %-8s" % ("bandit.dir", cfg["auto"]["bandit"]["dir"]))


def _ledger_path(tag: str) -> Path:
    return AB_DIR / ("V1255%s.spend.json" % tag)


def _ledger_read(tag: str) -> dict:
    """**跨窗口**累计账本。

    ★ 为什么不能用快照里的 `llm_calls`：那个字段是 `self.llm.total_calls`，
      每个窗口新建实例就归零 ⇒ 用它在第三窗口会算出「还剩很多」，把承诺的
      上限翻倍。账本按窗口累加，才是真的天花板。
    """
    p = _ledger_path(tag)
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return {"calls": int(d.get("calls") or 0),
                    "tokens": int(d.get("tokens") or 0),
                    "windows": int(d.get("windows") or 0)}
        except Exception:  # noqa: BLE001
            pass
    return {"calls": 0, "tokens": 0, "windows": 0}


def _ledger_add(tag: str, calls: int, tokens: int) -> dict:
    d = _ledger_read(tag)
    d["calls"] += int(calls or 0)
    d["tokens"] += int(tokens or 0)
    d["windows"] += 1
    _ledger_path(tag).write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    return d


def _one(tag: str, new_on: bool) -> dict:
    eng = _load_engine(tag)
    cfg = _build(eng, tag, new_on)
    run_id = "V1255%s" % tag                  # ★ 固定 id ⇒ 重发命令即可续跑
    print("\n[%s] run_id=%s | 四个新键=%s | 上限 calls=%d / %.0f min"
          % (tag, run_id, "ON" if new_on else "OFF", MAX_CALLS, MAX_MINUTES))
    _print_cfg(tag, cfg)

    # ★ 续跑探测：同一 run_id 已有快照 ⇒ 能续就续；已完成就直接读产物
    ck_path = Path(eng.run_ckpt_path(run_id))
    resume, prev = "", None
    _spent = 0
    if ck_path.is_file():
        try:
            d = json.loads(ck_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            d = {}
        st = str((d or {}).get("status") or "")
        done = sorted((d or {}).get("views") or {})
        _spent = int((d or {}).get("llm_calls") or 0)
        print("[%s] 发现快照 %s：status=%s 已完成层=%s 已花 calls=%d"
              % (tag, ck_path.name, st, done, _spent))
        if st in ("running", "interrupted", "paused"):
            resume = str(ck_path)
            print("[%s] ⇒ 从快照**续跑**（已完成的层不重烧）" % tag)
        elif st == "done" and len(done) >= len(ROUTE):
            p = AB_DIR / ("V1255%s.json" % tag)
            if p.is_file():
                prev = json.loads(p.read_text(encoding="utf-8"))
    # ★★ [成本天花板按 run_id 累计] `max_calls` 是**按实例**算的（`self.llm` 每建一次
    #   就归零）⇒ 续跑几次就能把承诺的上限翻几倍。这里用快照里的 `llm_calls`
    #   （v1.23.50 起的记账）扣掉已花，**剩余额度**才是本次实例的天花板。
    #   额度用完 ⇒ 拒绝续跑，等人决定是否加预算（不偷偷多花）。
    if resume:
        _led = _ledger_read(tag)
        _left = MAX_CALLS - _led["calls"]
        print("[%s] 账本：已跑 %d 窗口 / 累计 %d calls / %d tokens ⇒ 本次剩余额度 %d"
              % (tag, _led["windows"], _led["calls"], _led["tokens"], _left))
        if _left <= 0:
            print("[%s] ✗ 该臂累计已达 %d calls 上限 ⇒ 不再续跑"
                  % (tag, MAX_CALLS))
            if prev is not None:
                return prev
            raise SystemExit("[%s] 额度用完，需人工决定是否加预算" % tag)
        cfg["max_calls"] = _left

    if prev is not None:
        print("[%s] 已有完成产物 ⇒ 直接用它出表" % tag)
        return prev

    m = eng.MetaDGTF(cfg)
    t0 = time.time()
    res = m.run(QUESTION, route=list(ROUTE), rounds=dict(ROUNDS),
                parallel_mode="serial", run_id=run_id,
                resume_ckpt=resume, max_minutes=MAX_MINUTES)
    # ★ `run()` 内部已调 `_eml_finish`；只有真的没有 playbook 块时才补一次
    pb = res.get("playbook")
    if not isinstance(pb, dict) or pb.get("error"):
        try:
            res["playbook"] = m._eml_finish(res)
        except Exception as e:  # noqa: BLE001
            print("[%s] _eml_finish 抛错（不影响对表）：%r" % (tag, e))
    dt = time.time() - t0
    out = AB_DIR / ("V1255%s.json" % tag)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1,
                              default=str), encoding="utf-8")
    print("[%s] 完成 %.1f min | paused=%s | 产物 %s"
          % (tag, dt / 60.0, res.get("paused"), out.name))
    _led = _ledger_add(tag, res.get("llm_calls") or 0, res.get("llm_tokens") or 0)
    print("[%s] 账本：累计 %d calls / %d tokens（%d 窗口，上限 %d）"
          % (tag, _led["calls"], _led["tokens"], _led["windows"], MAX_CALLS))
    return res


def _summary(res: dict) -> dict:
    """抽对表要用的量。★ duty 在 `views[层]["duty"]` 或 `duty_trace` 末条。"""
    duty = {}
    stops = {}
    for e, v in (res.get("views") or {}).items():
        if not isinstance(v, dict):
            continue
        d = v.get("duty")
        if isinstance(d, dict) and d.get("S") is not None:
            duty[e] = round(float(d.get("S") or 0.0), 3)
        else:
            tr = v.get("duty_trace") or []
            if tr and isinstance(tr[-1], dict) and tr[-1].get("S") is not None:
                duty[e] = round(float(tr[-1].get("S") or 0.0), 3)
        stops[e] = {"rounds": int(v.get("rounds_run") or 0),
                    "cand": len(v.get("candidates") or []),
                    "amp": len(v.get("amps") or []),
                    "thread": len(v.get("threads") or []),
                    "sus": len(v.get("suspensions") or []),
                    "stop": str(v.get("stop_reason") or "")[:40]}
    return {"run_id": res.get("id"),
            "calls": res.get("llm_calls") or {},
            "tokens": res.get("llm_tokens") or {},
            "duty_S": duty, "layers": stops,
            "paused": bool(res.get("paused")),
            "pending": res.get("pending_layers")}


def _cost_cny(tokens) -> float:
    """粗算成本：按上轮实测的**混合单价** ¥2.5/M tokens（输入+输出加权）。

    ★ 引擎的 `llm_tokens` 是**标量**（不是按 prompt/completion 分开的字典）——
      干跑逮到的：写成 `tokens.get("prompt")` 会 AttributeError。
      这里两种形态都吃，只为对表排序，不作为账单。
    """
    if isinstance(tokens, dict):
        t = sum(int(v or 0) for v in tokens.values()
                if isinstance(v, (int, float)))
    else:
        t = int(tokens or 0)
    return round(t / 1e6 * 2.5, 2)


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()

    if which in ("--dry", "dry"):
        for _tag, _on in (("A", False), ("B", True)):
            _e = _load_engine(_tag)
            _c = _build(_e, _tag, _on)
            print("\n[%s] 干跑（不调 LLM）| 四个新键=%s" % (_tag, "ON" if _on else "OFF"))
            _print_cfg(_tag, _c)
        print("\n干跑结束：未运行引擎。上限 calls=%d / %.0f min（每臂），"
              "预估两臂最坏 ~¥9.3。" % (MAX_CALLS, MAX_MINUTES))
        raise SystemExit(0)

    AB_DIR.mkdir(parents=True, exist_ok=True)
    A = B = None
    if which in ("a", "both"):
        A = _one("A", False)
        (AB_DIR / "V1255A.sum.json").write_text(
            json.dumps(_summary(A), ensure_ascii=False, indent=1), encoding="utf-8")
    if which in ("b", "both"):
        B = _one("B", True)
        (AB_DIR / "V1255B.sum.json").write_text(
            json.dumps(_summary(B), ensure_ascii=False, indent=1), encoding="utf-8")
    if A and B:
        sa, sb = _summary(A), _summary(B)
        print("\n=== 对表（A 基线 → B +4 键；bandit 两臂关、S 同口径）===")
        print("calls :", json.dumps(sa["calls"], ensure_ascii=False),
              "→", json.dumps(sb["calls"], ensure_ascii=False))
        print("tokens:", json.dumps(sa["tokens"], ensure_ascii=False),
              "→", json.dumps(sb["tokens"], ensure_ascii=False))
        print("duty_S:", json.dumps(sa["duty_S"], ensure_ascii=False),
              "→", json.dumps(sb["duty_S"], ensure_ascii=False))
        print("粗算成本: ¥%.2f → ¥%.2f" % (_cost_cny(sa["tokens"]),
                                           _cost_cny(sb["tokens"])))
