#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3 遗留2] 思考分档的**真实收益**：录播式 A/B。

【为什么要这么测】
`dgtf_config.yaml` 里那 15 行 `api.thinking.stages.*` 所在分组的注释写着
「── 关：思考无收益 ──」—— 但那是**注释里的断言**，从来没有测过。
v1.23.2 只是把**值**改到与实际行为一致（当时那些 stage 压根选不中）。
要真正清掉这条遗留，就必须回答：**开了思考，这个环节的输出变好了吗？**

【设计：录播（record–replay），不是「跑两次整流程比一比」】
  ① 录播：包住 `LLM.call`，跑一次真流程，把**每个 stage 的真实输入**
     （system / user / 温度 / max_tokens / json_mode）原样存下来。
     ⇒ 输入是**生产里真实出现过的**，不是我造的。
  ② A/B：对每个 stage 的真实输入，用**同一输入**分别跑
     `thinking=disabled` 与 `thinking=enabled`，各 R 次。
     两臂除 thinking 外**逐字相同** ⇒ 差异只能来自思考档。
  ③ 度量：JSON 合法率 / 输出规模 / 延迟（客观量）+ **评分**（0-2，独立判分调用）。
  ④ 判据：**等效检验**。margin = 0.3（0-2 量表上的「可忽略」门槛）。
     区间落在 ±margin 内 = 「无收益」（等效，可判定）；下界 > margin = 有收益；
     上界 < -margin = 有损；跨界 = 不可判定（并报本 n 的最小可检效应 MDE）。
     ★ 「无收益」是**结论**，不是「没测出来」—— 这是等效检验与
       「p > 0.05」的区别，必须写清。

用法：
  python _ab_thinking_v1233.py [src.py] [--inputs=2] [--reps=3] [--capture-only]
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(_args[0]) if _args else HERE / "元DGTF-V1.23.3.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
N_IN = int(next((a.split("=", 1)[1] for a in sys.argv
                 if a.startswith("--inputs=")), 2))
REPS = int(next((a.split("=", 1)[1] for a in sys.argv
                 if a.startswith("--reps=")), 3))
CAP_ONLY = "--capture-only" in sys.argv
MARGIN = 0.3
OUT = HERE / "_v1233_thinking.json"
MD = HERE / "_v1233_thinking.md"

JUDGE_SYS = (
    "你是输出评分员。给你某个环节的输入片段与它的输出，按【结构完整 + "
    "可直接被下游使用】给 0-2 分：\n"
    "0 = 不可用（残缺 / 结构错 / 与输入不匹配）；\n"
    "1 = 勉强可用（能读，但需人工修补）；\n"
    "2 = 完整可用（结构齐、信息足、下游能直接用）。\n"
    "严格 JSON：{\"score\":0,\"why\":\"20字内\"}"
)


def _load(src: Path):
    spec = importlib.util.spec_from_file_location("dgtf_think1233", src)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_think1233"] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    m = _load(SRC)
    print("[think] src=%s inputs/stage=%d reps=%d" % (SRC.name, N_IN, REPS),
          flush=True)

    # ---------------------------------------------------------- ① 录播
    rec_calls: list = []
    _orig = m.LLM.call

    def _patched(self, system, user, temperature=0.6, max_tokens=3000,
                 json_mode=False, model=None, thinking=None, stage=None):
        rec_calls.append({
            "stage": stage, "system": system, "user": user,
            "temperature": temperature, "max_tokens": max_tokens,
            "json_mode": json_mode, "thinking": thinking,
        })
        return _orig(self, system, user, temperature, max_tokens, json_mode,
                     model, thinking, stage)

    Q1 = ("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？"
          "怎么权衡？")
    Q2 = ("某市要决定是否把全部政务系统迁到自建机房，但机房选址、"
          "预算上限与迁移窗口都还没定。请给出取舍。")
    # 三组配置：模式不同 ⇒ 触达的 stage 不同（「有接线」≠「这跑走得到」）。
    RUNS = (
        (Q1, "auto", "serial", ["0", "1"], {"0": 1, "1": 1}),
        (Q1, "normal", "auto", ["0", "1", "both", "all"],
         {"0": 2, "1": 2, "both": 1, "all": 1}),
        (Q2, "koan", "serial", ["0", "1"], {"0": 1, "1": 1}),
    )
    _t0 = time.time()
    if "--from-capture" in sys.argv:
        print("[think] --from-capture：跳过录播", flush=True)
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["output"] = dict(cfg.get("output") or {})
        _rd = HERE / "outputs" / "_v1233_think_replay"
        _rd.mkdir(parents=True, exist_ok=True)
        cfg["output"]["save_dir"] = str(_rd)
        cfg["output"]["verbose"] = False
    else:
        m.LLM.call = _patched
        _t0 = time.time()
        for _k, (_q, _ori, _pm, _rt, _rd) in enumerate(RUNS):
            cfg = m.DEFAULT_CONFIG.copy()
            cfg["external_anchor"] = dict(cfg["external_anchor"])
            cfg["external_anchor"].update(
                {"enabled": True, "path": "_test_anchors.json",
                 "as_evidence": "evidence", "tier_floor": 2})
            cfg["output"] = dict(cfg.get("output") or {})
            _d = HERE / "outputs" / ("_v1233_think_cap%d" % _k)
            _d.mkdir(parents=True, exist_ok=True)
            cfg["output"]["save_dir"] = str(_d)
            cfg["output"]["verbose"] = False
            _buf = io.StringIO()
            _n0 = len(rec_calls)
            try:
                with contextlib.redirect_stdout(_buf):
                    meta = m.MetaDGTF(cfg)
                    meta.run(_q, route=_rt, rounds=_rd, parallel_mode=_pm,
                             orientation=_ori)
                print("[think] 组%d ori=%s pm=%s 录到 %d 次调用"
                      % (_k, _ori, _pm, len(rec_calls) - _n0), flush=True)
            except Exception as _e:  # noqa: BLE001
                print("[think] 组%d 失败：%s: %s" % (_k, type(_e).__name__, _e),
                      flush=True)
        m.LLM.call = _orig
    print("[think] 录播完成：%d 次调用 / %.0fs" % (len(rec_calls),
                                                   time.time() - _t0), flush=True)

    by_stage: dict = {}
    if "--from-capture" in sys.argv:
        # ★ 用存档的真实输入（含 `_ab_thinking_direct.py` 直接驱动来的），
        #   不再跑流程 —— 回放本身才是花钱的部分，录播不重复。
        _cp = HERE / "_v1233_think_capture.json"
        if _cp.is_file():
            for _st, _lst in (json.loads(_cp.read_text(encoding="utf-8"))
                              .get("stages") or {}).items():
                by_stage[_st] = [dict(x, stage=_st) for x in _lst]
        print("[think] --from-capture：载入 %d 个 stage 的真实输入"
              % len(by_stage), flush=True)
        rec_calls = [c for v in by_stage.values() for c in v]
    for c in rec_calls:
        if not c.get("stage"):
            continue          # 未接线的调用点（stage=None）无法按环节分组
        by_stage.setdefault(c["stage"], []).append(c)
    # 每个 stage 取 N_IN 条**互不相同**的输入（最长优先：信息量大）
    picked: dict = {}
    for st, lst in by_stage.items():
        seen, keep = set(), []
        for c in sorted(lst, key=lambda x: -len(x["user"])):
            key = (c["system"][:200], c["user"][:200])
            if key in seen:
                continue
            seen.add(key)
            keep.append(c)
            if len(keep) >= N_IN:
                break
        picked[st] = keep
    print("[think] 录到 %d 个 stage：%s"
          % (len(picked), {k: len(v) for k, v in sorted(picked.items())}),
          flush=True)
    if "--from-capture" not in sys.argv:
        # ★ **只在不跳过录播时才写存档** —— 否则回放路径会把只有流程录播的
        #   版本写回去，**覆盖掉** `_ab_thinking_direct.py` 直接驱动来的 stage
        #   （本机实踩：skip 判断放晚了，白跑 16 分钟还差点丢数据）。
        (HERE / "_v1233_think_capture.json").write_bytes(
            json.dumps({"src": SRC.name, "n_calls": len(rec_calls),
                        "stages": {k: [{"system": c["system"][:4000],
                                        "user": c["user"][:4000],
                                        "temperature": c["temperature"],
                                        "max_tokens": c["max_tokens"],
                                        "json_mode": c["json_mode"]}
                                       for c in v]
                                   for k, v in picked.items()}},
                       ensure_ascii=False, indent=1).encode("utf-8"))
    if CAP_ONLY:
        print("CAPTURE_ONLY_DONE", flush=True)
        return 0

    # ---------------------------------------------------------- ② 回放
    rl = m.LLM(cfg)

    def _judge(stage, user, out):
        try:
            raw = rl.call(JUDGE_SYS,
                          "【环节】" + stage + "\n【输入片段】" + user[:300]
                          + "\n【待评输出】" + out[:1500],
                          0.0, 60, json_mode=True, thinking="disabled")
            d = rl.parse_json(raw)
            v = int(d.get("score"))
            return v if v in (0, 1, 2) else None
        except Exception:  # noqa: BLE001
            return None

    rows = []
    for st, lst in sorted(picked.items()):
        for ii, c in enumerate(lst, 1):
            for arm in ("off", "on"):
                for r in range(REPS):
                    t1 = time.time()
                    out, ok = "", False
                    try:
                        out = rl.call(c["system"], c["user"],
                                      c["temperature"], c["max_tokens"],
                                      json_mode=c["json_mode"],
                                      thinking=("enabled" if arm == "on"
                                                else "disabled"))
                        if c["json_mode"]:
                            ok = isinstance(rl.parse_json(out), (dict, list))
                        else:
                            ok = bool(str(out).strip())
                    except Exception as e:  # noqa: BLE001
                        out, ok = "ERR:" + str(e)[:120], False
                    sc = _judge(st, c["user"], str(out))
                    rows.append({"stage": st, "input": ii, "arm": arm,
                                 "rep": r, "json_ok": ok,
                                 "chars": len(str(out)), "secs":
                                 round(time.time() - t1, 1),
                                 "score": sc, "out": str(out)[:1200]})
                    print("[think] %-28s in%d %s r%d ok=%s chars=%d "
                          "score=%s %.1fs"
                          % (st, ii, arm, r, ok, len(str(out)), sc,
                             time.time() - t1), flush=True)

    # ---------------------------------------------------------- ③ 汇总
    stages_out = {}
    for st in sorted(picked):
        off = [x for x in rows if x["stage"] == st and x["arm"] == "off"]
        on = [x for x in rows if x["stage"] == st and x["arm"] == "on"]
        # 按 (input, rep) 配对
        diffs = []
        for x in off:
            y = next((z for z in on if z["input"] == x["input"]
                      and z["rep"] == x["rep"] and z["score"] is not None
                      and x["score"] is not None), None)
            if y is not None:
                diffs.append(y["score"] - x["score"])
        mean = round(sum(diffs) / len(diffs), 3) if diffs else None
        lo = hi = None
        # ★ 门槛从 3 降到 2：配对只有 2 条、且两臂差值**完全相同**时
        #   （如 [0,0] / [2,2]），自助分布退化成单点 ⇒ 区间 [d,d]，
        #   这本身就是可判定的读数。差值不同则区间自然变宽、判不可判定。
        if len(diffs) >= 2:
            rnd = random.Random(11)
            bs = []
            for _ in range(2000):
                s = [diffs[rnd.randrange(len(diffs))] for _ in range(len(diffs))]
                bs.append(sum(s) / len(s))
            bs.sort()
            lo = round(bs[int(0.025 * len(bs))], 3)
            hi = round(bs[min(len(bs) - 1, int(0.975 * len(bs)))], 3)
        if lo is None:
            verdict = "不可判定（有效配对 %d < 2）" % len(diffs)
            mde = None
        elif lo > MARGIN:
            verdict = "有收益 ✅（下界 %.3f > margin %.1f）" % (lo, MARGIN)
            mde = None
        elif hi < -MARGIN:
            verdict = "**有损 ✗**（上界 %.3f < -margin %.1f）" % (hi, MARGIN)
            mde = None
        elif lo > -MARGIN and hi < MARGIN:
            verdict = ("无收益（等效）✅ 区间 [%.3f, %.3f] 全在 ±%.1f 内"
                       % (lo, hi, MARGIN))
            mde = round(max(abs(lo), abs(hi)), 3)
        else:
            mde = round(max(abs(lo), abs(hi)), 3)
            verdict = ("**不可判定**（区间 [%.3f, %.3f] 跨界；本 n 的 MDE ≈ %.3f）"
                       % (lo, hi, mde))
        stages_out[st] = {
            "n_pair": len(diffs), "delta": mean, "ci": [lo, hi],
            "verdict": verdict, "mde": mde,
            "off": {"json_ok": round(sum(1 for x in off if x["json_ok"])
                                     / max(1, len(off)), 3),
                    "chars": round(sum(x["chars"] for x in off)
                                   / max(1, len(off)), 1),
                    "secs": round(sum(x["secs"] for x in off)
                                  / max(1, len(off)), 1),
                    "score": round(sum(x["score"] for x in off
                                       if x["score"] is not None)
                                   / max(1, sum(1 for x in off
                                                if x["score"] is not None)), 3)},
            "on": {"json_ok": round(sum(1 for x in on if x["json_ok"])
                                    / max(1, len(on)), 3),
                   "chars": round(sum(x["chars"] for x in on)
                                  / max(1, len(on)), 1),
                   "secs": round(sum(x["secs"] for x in on)
                                 / max(1, len(on)), 1),
                   "score": round(sum(x["score"] for x in on
                                      if x["score"] is not None)
                                  / max(1, sum(1 for x in on
                                               if x["score"] is not None)), 3)},
        }
    OUT.write_bytes(json.dumps({"src": SRC.name, "reps": REPS,
                                "n_inputs": N_IN, "margin": MARGIN,
                                "stages": stages_out, "rows": rows},
                               ensure_ascii=False, indent=1,
                               default=str).encode("utf-8"))
    _write_md(stages_out)
    print("[think] 已写 %s / %s" % (OUT.name, MD.name), flush=True)
    return 0


def _write_md(st: dict) -> None:
    L = ["# v1.23.3 · 遗留2 思考分档的真实收益（录播式 A/B）", "",
         "> 输入来自**一次真流程的录播**（每个 stage 取 2 条真实输入），",
         "> 两臂除 `thinking` 外逐字相同；评分 0-2；margin = 0.3。", "",
         "| 环节 | 配对n | Δ(开−关) | 95%区间 | MDE | 判定 | 关:合法率/长度/延迟/分 | "
         "开:合法率/长度/延迟/分 |",
         "|---|---|---|---|---|---|---|---|"]
    for k, v in sorted(st.items()):
        o, n = v["off"], v["on"]
        L.append("| %s | %d | %s | %s | %s | %s | %.2f/%d/%.1fs/%.2f | "
                 "%.2f/%d/%.1fs/%.2f |"
                 % (k, v["n_pair"], v["delta"], v["ci"], v["mde"], v["verdict"],
                    o["json_ok"], o["chars"], o["secs"], o["score"],
                    n["json_ok"], n["chars"], n["secs"], n["score"]))
    L.append("")
    Path(MD).write_bytes("\n".join(L).replace("\n", "\r\n").encode("utf-8"))


if __name__ == "__main__":
    sys.exit(main())
