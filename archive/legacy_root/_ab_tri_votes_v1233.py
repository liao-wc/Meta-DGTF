#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3 遗留1] 三票正交度：**受控实验**（固定子问题，只让三票重投）。

【为什么必须重做口径 —— 这不是「多跑几次」能解决的】
`v1232_报告.md` §十 第 1 条写的是「正交度仍不可判定：噪声大于信号」。
根因不是 n 小，是**口径本身结构化地不可判定**：
  判据是「组间 ≥ 组内」（组 = 题，组内 = 同题重复跑）。但**子问题集合
  每跑都重新拆解**，于是「组内变异」里混进了**上游拆解的变异**，
  不只有被测量的那个机制（三票）的变异。
  实测（同题两跑）：`agree13` = **0.0 vs 1.0** —— 组内极差 1.0，而组间差
  只有 0.083。**再跑一百次也一样**：测得的是「拆解每次都不一样」，
  不是「三票稳不稳」。

【本实验的设计】
把被测量的机制**单独拿出来**：固定一组子问题（K 条，覆盖不同清晰度）
＋固定一份外部材料，只让三票重投 R 次。于是：
  · 组 = 子问题；组内 = 同一子问题的 R 次重投。
  · 「组内变异」**只含三票自己的变异** ⇒ 判据「组间 ≥ 组内」才是可判定的。
这是测量学里的 test–retest 设计（固定刺激，重复测量），
和 `P2.4.a` 那次「采样 → 构造性证明」是同一族的修法。

【四臂（内含负对照）】
  W4 关 / W4 开  ×  温度 0.0（生产实参） / 温度 0.7（**故意注入随机性**）
★ 温度 0.7 那一对是**变异体**：如果 ICC 在注入噪声后**不下降**，
  说明我算的这个 ICC **没有判别力**，「组间 ≥ 组内」全绿也只是没测到东西。

用法：
  python _ab_tri_votes_v1233.py [src.py] [--reps=6] [--mock]
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(_args[0]) if _args else HERE / "元DGTF-V1.23.2.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
REPS = int(next((a.split("=", 1)[1] for a in sys.argv
                 if a.startswith("--reps=")), 6))
MOCK = "--mock" in sys.argv
OUTJ = HERE / "_v1233_votes.json"
OUTM = HERE / "_v1233_votes.md"

# ------------------------------------------------------------------ 固定刺激
QUESTION = ("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？"
            "怎么权衡？")

# K 条子问题：**故意覆盖不同清晰度**（清楚的 / 半清的 / 明显判不出的），
#   否则「组间变异」会被压成 0，ICC 同样不可判定。
SUBS = [
    "老城区雨水管渠的设计重现期应当取几年一遇",
    "重建方案与局部改造方案的初投资差额是多少",
    "海绵城市措施在本地土壤渗透条件下的年径流总量控制率能达到多少",
    "排水系统的运行维护责任主体是市政还是属地街道",
    "该市近五年内涝点位的空间分布是否与管网老旧程度重合",
    "上游是否有官方标准规定此类改造的验收指标",
    "本方案的最终取舍本身就是自指的，需要一个没有共同参照系的判断",
    "施工期间对沿街商户营业损失如何补偿",
    "调蓄池与管网扩容的投资优先次序",
    "居民对改造期间出行的容忍阈值是多少",
    "黑臭水体治理任务与内涝治理任务的考核权重如何分配",
    "改造后内涝风险降低的社会效益如何货币化",
]

# 固定外部材料（不让实验依赖网络；W4 第三票只读这个）
EVIDENCE = [
    {"id": "W1", "stage": "research_evidence", "tier": 1,
     "source": "GB50014-2021",
     "claim": ("《室外排水设计标准》GB50014-2021 第 3.2.4 条：雨水管渠"
               "设计重现期，特大城市中心城区应取 3~5 年，重要地区可取"
               "10~50 年。")},
    {"id": "W2", "stage": "research_evidence", "tier": 1,
     "source": "《海绵城市建设技术指南（试行）》",
     "claim": ("年径流总量控制率应按当地降雨与土壤渗透条件分区确定，"
               "指南给出分区表；老城区改造应以源头减排 + 过程控制为主，"
               "管网扩容需与调蓄同步，否则单独扩容收效有限。")},
    {"id": "W3", "stage": "research_evidence", "tier": 3,
     "source": "行业媒体综述",
     "claim": ("某行业媒体综述称：多数老城区改造案例最终选择了局部改造"
               "加海绵措施，理由是拆迁与地下管线迁改成本过高。")},
]

# ★ 证据**反事实**：与 EVIDENCE 相反的外部材料。若第三票随它变，
#   就证明「外部材料**真的**在驱动第三票」—— 这比一致率更直接。
EVIDENCE_SWAP = [
    {"id": "W1", "stage": "research_evidence", "tier": 1,
     "source": "（反事实材料）",
     "claim": ("该标准已废止，雨水管渠设计重现期不再有国家层面的统一规定，"
               "各地自行确定；因此本条没有可引用的官方指标。")},
    {"id": "W2", "stage": "research_evidence", "tier": 1,
     "source": "（反事实材料）",
     "claim": ("该市从未做过内涝成因统计，历史内涝点位与成因分布均无数据；"
               "土壤渗透条件亦无实测资料。")},
    {"id": "W3", "stage": "research_evidence", "tier": 3,
     "source": "（反事实材料）",
     "claim": "没有可用于参照的改造案例综述。"},
]

ARMS = (
    ("w4_off_t0", False, 0.0, "none"),
    ("w4_on_t0", True, 0.0, "std"),
    ("w4_off_t7", False, 0.7, "none"),
    ("w4_on_t7", True, 0.7, "std"),
    ("on_swap_t0", True, 0.0, "swap"),
)


def _load(src: Path):
    spec = importlib.util.spec_from_file_location("dgtf_votes1233", src)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_votes1233"] = m
    spec.loader.exec_module(m)
    return m


def _sys_list(m, w4: bool, ev_kind: str = "std"):
    """三票的 system 列表：W4 开时把第 3 票换成「外部证据裁判」。"""
    out = list(m._TRI_VOTE_PROMPTS)
    if w4:
        _ev = EVIDENCE_SWAP if ev_kind == "swap" else EVIDENCE
        out[2] = m._TRI_VOTE_PROMPTS[2] + m._web_digest_block(_ev)
        out[2] += ("\n【裁判口径】你的这一票**只看**上面这些外部材料与锚点；"
                   "池内产物一律不计入。\n")
    return out


def _user_text():
    lines = ["  %d. %s" % (i, s[:200]) for i, s in enumerate(SUBS, 1)]
    return ("【原始问题】\n" + QUESTION + "\n\n【待判的子问题】\n"
            + "\n".join(lines))


def _one_rep(m, llm, sys_list, temp, reps_retry=1):
    """投一轮：返回 ({sid: {voter_index: label}}, 空票数, 逐票 id 基准)。"""
    user = _user_text()
    votes: dict = {}
    empty = 0
    ids_meta: list = []
    for vi, sysp in enumerate(sys_list):
        data = None
        for _try in range(1 + max(0, reps_retry)):
            try:
                raw = llm.call(sysp, user, temp, 1200, json_mode=True,
                               stage="adjudicate_sub_tristate_multi")
                data = llm.parse_json(raw)
            except Exception as exc:  # noqa: BLE001
                print("   ! 第 %d 票失败：%s" % (vi + 1, exc), flush=True)
                data = None
                break
            if isinstance(data, dict) and (data.get("judgments") or []):
                break
        if not isinstance(data, dict):
            ids_meta.append({"voter": vi, "status": "非对象"})
            continue
        if not (data.get("judgments") or []):
            empty += 1
            ids_meta.append({"voter": vi, "status": "空票"})
            continue
        _raw_ids = []
        for it in (data.get("judgments") or []):
            if isinstance(it, dict):
                try:
                    _raw_ids.append(int(it.get("id", 0)))
                except (TypeError, ValueError):
                    pass
        # ★ id 基准检测：引擎按 **1 起** 对齐（`enumerate(subs, 1)`）。
        #   实测有票返回 **0 起** ⇒ 整票错位一格且**完全无声**。
        _n = len(SUBS)
        if _raw_ids and set(_raw_ids) <= set(range(1, _n + 1)):
            _base = 1
        elif _raw_ids and set(_raw_ids) <= set(range(0, _n)) and 0 in _raw_ids:
            _base = 0
        else:
            _base = -1
        ids_meta.append({"voter": vi, "status": "ok", "base": _base,
                         "ids": sorted(_raw_ids)[:4] + ["…"] +
                         sorted(_raw_ids)[-2:]
                         if len(_raw_ids) > 6 else sorted(_raw_ids)})
        _tmp: dict = {}
        for it in (data.get("judgments") or []):
            if not isinstance(it, dict):
                continue
            try:
                sid = int(it.get("id", 0))
            except (TypeError, ValueError):
                continue
            st = str(it.get("decidability", "")).lower().strip()
            if st not in ("decidable", "partial", "undecidable"):
                continue
            _tmp[sid] = st
        # ★ 必须按**引擎的口径**归一化后再算指标：否则 0 起那一票会被记成
        #   「错位」，一致率反映的是**我的桩没对齐**而不是被测量的机制。
        #   （`base` 的**原始**统计仍照记 —— 那才是这条 bug 的频度证据。）
        if _base == 1:
            _shift = 0
        elif _base == 0:
            _shift = 1
        else:
            continue
        for _k, _v in _tmp.items():
            votes.setdefault(_k + _shift, {})[vi] = _v
    return votes, empty, ids_meta


def _icc_oneway(y, groups):
    """单因素随机效应 ICC(1,1)：y 与 group 标签（沿用 ANOVA 方差分量）。

    返回 (icc, ms_between, ms_within)。组数 <2 或组内 R<2 → (None, ...)。
    """
    from collections import defaultdict
    buckets = defaultdict(list)
    for v, g in zip(y, groups):
        buckets[g].append(v)
    k = len(buckets)
    if k < 2:
        return None, None, None
    ns = [len(v) for v in buckets.values()]
    r_bar = sum(ns) / k
    grand = sum(y) / len(y)
    ss_b = sum(len(v) * ((sum(v) / len(v)) - grand) ** 2
               for v in buckets.values())
    ss_w = sum(sum((x - sum(v) / len(v)) ** 2 for x in v)
               for v in buckets.values())
    df_b, df_w = k - 1, len(y) - k
    if df_b <= 0 or df_w <= 0:
        return None, None, None
    ms_b, ms_w = ss_b / df_b, ss_w / df_w
    den = ms_b + (r_bar - 1) * ms_w
    icc = ((ms_b - ms_w) / den) if den > 0 else None
    return icc, ms_b, ms_w


def _boot_icc(pairs, n_boot=2000, seed=20261006):
    """按**组（子问题）**重采样求 ICC 的 95% 区间。

    ★ 重采样单位必须是组，不是单条观测 —— 单条重采样会把组内相关
      打散，区间假窄（本项目「判据的锚要对准实现本体」的同族坑）。
    """
    from collections import defaultdict
    byg = defaultdict(list)
    for g, v in pairs:
        byg[g].append(v)
    keys = list(byg)
    rnd = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        pick = [keys[rnd.randrange(len(keys))] for _ in range(len(keys))]
        y, gs = [], []
        for i, g in enumerate(pick):
            for v in byg[g]:
                y.append(v)
                gs.append((i, g))     # 重采样的组要当成**新组**
        icc, _, _ = _icc_oneway(y, gs)
        if icc is not None:
            vals.append(icc)
    if not vals:
        return None, None
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    return round(lo, 3), round(hi, 3)


def _verdict(lo, hi):
    """CI 与 0.5 的关系 → 可判定 / 不可判定。"""
    if lo is None:
        return "不可判定（样本不足）"
    if lo > 0.5:
        return "可判定 ✅ 组间 ≥ 组内（ICC 区间 [%s, %s] 全在 0.5 之上）" % (lo, hi)
    if hi < 0.5:
        return "可判定 ✗ 组内 > 组间（ICC 区间 [%s, %s] 全在 0.5 之下）" % (lo, hi)
    return "**不可判定**（ICC 区间 [%s, %s] 跨过 0.5）" % (lo, hi)


def main() -> int:
    global REPS
    m = _load(SRC)
    print("[votes] src=%s reps=%d subs=%d" % (SRC.name, REPS, len(SUBS)),
          flush=True)
    llm = m.LLM(m.DEFAULT_CONFIG.copy())

    raw: dict = {}
    t0 = time.time()
    if "--reuse" in sys.argv and OUTJ.is_file():
        # ★ 只重算指标 / 重写 md，**不重跑 LLM**（默认口径改了之后用这个，
        #   避免把同一批样本再采一遍 —— 那会变成「换个口径+换批样本」，
        #   两处同时变，读数不可比）。
        raw = (json.loads(OUTJ.read_text(encoding="utf-8")).get("arms") or {})
        # ★ 重复次数必须按**存下来的那份**取：用 CLI 默认值会把 8 次
        #   当成 6 次读（读数会变，且头部写错）—— 本项目「判据的锚不能
        #   依赖隐含前提」的同族坑。
        _r0 = next(iter(raw.values())) if raw else {}
        if _r0.get("reps"):
            REPS = len(_r0["reps"])
        print("[votes] --reuse：复用已存 %d 臂 × %d 次重复（跳过采集）"
              % (len(raw), REPS), flush=True)
    for name, w4, temp, ev_kind in ARMS:
        if name in raw:
            continue
        sys_list = _sys_list(m, w4, ev_kind)
        reps_out = []
        for r in range(REPS):
            v, empty, ids_meta = _one_rep(m, llm, sys_list, temp)
            reps_out.append({"votes": {str(k): v[k] for k in v},
                             "empty": empty, "ids_meta": ids_meta})
            print("[votes] %-11s rep %d/%d  票数=%s 空票=%d"
                  % (name, r + 1, REPS,
                     [len(v.get(i) or {}) for i in range(1, len(SUBS) + 1)],
                     empty), flush=True)
        raw[name] = {"w4": w4, "temp": temp, "evidence": ev_kind,
                     "reps": reps_out}
        print("[votes] %-11s 用时 %.0fs（累计 %.0fs）"
              % (name, 0, time.time() - t0), flush=True)

    # ---------------------------------------------------------- 指标
    report = {"src": SRC.name, "reps": REPS, "n_subs": len(SUBS),
              "arms": {}, "metrics": {}, "icc": {}, "pair": {}, "func": {}, "final_change": {},
              "swap": {}, "id_base": {}}
    for name, _w4, _t, _e in ARMS:
        report["arms"][name] = raw[name]

    # ★ 缺票一律记 None。把「这票没投」当成「不一致」是**非读数被当成测量值**
    #   （本项目反复踩的老坑）：原式在缺 2 号票时给出 0，把弃权读成了分歧
    #   —— 整张一致率表都会偏。
    per = {}
    for name, _w4, _t, _e in ARMS:
        seq = {}
        for r in range(REPS):
            votes = {int(k): {int(v): lb for v, lb in vv.items()}
                     for k, vv in raw[name]["reps"][r]["votes"].items()}
            for i in range(1, len(SUBS) + 1):
                vs = votes.get(i) or {}
                cell = seq.setdefault(i, {"a12": [], "a13": [], "a23": [],
                                          "labels": []})
                cell["labels"].append([vs.get(0), vs.get(1), vs.get(2)])
                for key, (a, b) in (("a12", (0, 1)), ("a13", (0, 2)),
                                    ("a23", (1, 2))):
                    cell[key].append(int(vs[a] == vs[b])
                                     if (a in vs and b in vs) else None)
        per[name] = seq

    def _flat(cell, key):
        return [x for i in cell for x in cell[i][key] if x is not None]

    for name, _w4, _t, _e in ARMS:
        cell = per[name]
        a12, a13, a23 = (_flat(cell, k) for k in ("a12", "a13", "a23"))
        gaps = [max(cell[i]["a13"][r], cell[i]["a23"][r])
                - cell[i]["a12"][r]
                for i in cell for r in range(REPS)
                if None not in (cell[i]["a12"][r], cell[i]["a13"][r],
                                cell[i]["a23"][r])]
        report["metrics"][name] = {
            "agree12": round(sum(a12) / len(a12), 3) if a12 else None,
            "agree13": round(sum(a13) / len(a13), 3) if a13 else None,
            "agree23": round(sum(a23) / len(a23), 3) if a23 else None,
            "n12": len(a12), "n13": len(a13), "n23": len(a23),
            "gap": round(sum(gaps) / len(gaps), 3) if gaps else None,
            "gap_n": len(gaps),
        }
        iccs = {}
        for mk in ("a12", "a13", "a23"):
            y, gs = [], []
            for i in cell:
                for v in cell[i][mk]:
                    if v is not None:
                        y.append(v)
                        gs.append(i)
            icc, _msb, _msw = _icc_oneway(y, gs) if y else (None, None, None)
            lo, hi = _boot_icc(list(zip(gs, y))) if y else (None, None)
            wr = None
            if y:
                _rs = [max(x for x in cell[i][mk] if x is not None)
                       - min(x for x in cell[i][mk] if x is not None)
                       for i in cell
                       if any(x is not None for x in cell[i][mk])]
                wr = round(max(_rs), 3) if _rs else None
            iccs[mk] = {"icc": (round(icc, 3) if icc is not None else None),
                        "ci": [lo, hi], "verdict": _verdict(lo, hi),
                        "within_max_range": wr, "n": len(y)}
        report["icc"][name] = iccs

    # id 基准统计（★ 0 起 = 整票错位一格，且引擎侧**无声**）
    for name, _w4, _t, _e in ARMS:
        cnt = {"1起": 0, "0起": 0, "越界/其他": 0, "空票": 0, "非对象": 0}
        for rr in raw[name]["reps"]:
            for md in (rr.get("ids_meta") or []):
                st = md.get("status")
                if st == "空票":
                    cnt["空票"] += 1
                elif st == "非对象":
                    cnt["非对象"] += 1
                elif md.get("base") == 1:
                    cnt["1起"] += 1
                elif md.get("base") == 0:
                    cnt["0起"] += 1
                else:
                    cnt["越界/其他"] += 1
        report["id_base"][name] = cnt

    # 臂间配对差（同子问题，W4 开 − 关，同温度）
    for temp_tag in ("t0", "t7"):
        a, b = "w4_off_" + temp_tag, "w4_on_" + temp_tag
        bys, diffs = {}, []
        for i in range(1, len(SUBS) + 1):
            for r in range(REPS):
                ca, cb = per[a][i], per[b][i]
                if None in (ca["a12"][r], ca["a13"][r], ca["a23"][r],
                            cb["a12"][r], cb["a13"][r], cb["a23"][r]):
                    continue
                ga = max(ca["a13"][r], ca["a23"][r]) - ca["a12"][r]
                gb = max(cb["a13"][r], cb["a23"][r]) - cb["a12"][r]
                bys.setdefault(i, []).append(gb - ga)
                diffs.append(gb - ga)
        if diffs:
            n = len(diffs)
            mean = sum(diffs) / n
            sd = ((sum((x - mean) ** 2 for x in diffs) / (n - 1)) ** 0.5
                  if n > 1 else 0.0)
            # 判据 B（「组间 ≥ 组内」的字面口径）：
            #   组间 = 臂间配对差 Δ；组内 = 配对后残差的 σ。
            #   配对已消掉「子问题难度」这个共同分量，剩下的才是组内噪声。
            if sd == 0:
                ratio = float("inf") if mean != 0 else 0.0
            else:
                ratio = abs(mean) / sd
            if ratio >= 1:
                vb = ("可判定 ✅ 组间 ≥ 组内（|Δ|/σ = %s）"
                      % ("∞" if ratio == float("inf") else round(ratio, 2)))
            else:
                vb = "可判定 ✗ 组内 > 组间（|Δ|/σ = %s）" % round(ratio, 2)
            rnd = random.Random(7)
            keys = list(bys)
            bm = []
            for _ in range(2000):
                pick = [keys[rnd.randrange(len(keys))]
                        for _ in range(len(keys))]
                vals = [v for gg in pick for v in bys[gg]]
                bm.append(sum(vals) / len(vals))
            bm.sort()
            # ★ 标准口径（与 ANOVA 一致）：组间 ≥ 组内 ⇔ MS_b ≥ MS_w
            #   ⇔ F = t^2 ≥ 1 ⇔ |Δ| ≥ SE = σ_d / sqrt(n)。
            _se = (sd / (n ** 0.5)) if n > 1 else 0.0
            _t = (abs(mean) / _se) if _se > 0 else (
                float("inf") if mean != 0 else 0.0)
            _F = _t * _t
            if _t >= 1:
                _vf = ("可判定 ✅ 组间 ≥ 组内（F = %s ≥ 1；|Δ|/SE = %s）"
                       % (round(_F, 2) if _F != float("inf") else "∞",
                          round(_t, 2) if _t != float("inf") else "∞"))
            else:
                _vf = "可判定 ✗ 组内 > 组间（F = %s < 1）" % round(_F, 3)
            report["pair"][temp_tag] = {
                "mean_w4_minus_off": round(mean, 3), "sd_within": round(sd, 3),
                "ratio": (None if ratio == float("inf") else round(ratio, 2)),
                "verdict_B": vb, "n": n, "se": round(_se, 4),
                "t": (None if _t == float("inf") else round(_t, 2)),
                "F": (None if _F == float("inf") else round(_F, 2)),
                "verdict_F": _vf,
                "ci": [round(bm[int(0.025 * len(bm))], 3),
                       round(bm[int(0.975 * len(bm)) - 1], 3)]}
    # ------------------------------------------------------------ 功能读出
    # ★ 原 `flip`（第三票改变多数结论）在 3 票制下**恒为 0**（两人一致时
    #   第三人永远改不了多数）—— 恒不触发的指标是自欺，换掉。
    # 真正的功能读出有两个：
    #   · dissent_when_unanimous：1、2 票一致时第 3 票唱反调的比例
    #     （0 = 橡皮图章；> 0 = 独立检查真的在做）
    #   · final_change：同一条 (sub, rep) 下，W4 开/关的**最终判决**变化率
    def _func_reads(name):
        n_una = n_dis = 0
        for rr in raw[name]["reps"]:
            votes = {int(k): {int(x): y for x, y in vv.items()}
                     for k, vv in rr["votes"].items()}
            for i in range(1, len(SUBS) + 1):
                vs = votes.get(i) or {}
                if 0 in vs and 1 in vs and 2 in vs:
                    if vs[0] == vs[1]:
                        n_una += 1
                        n_dis += 1 if vs[2] != vs[0] else 0
        return n_dis, n_una

    report["func"] = {}
    for name, _w4, _t, _e in ARMS:
        _d, _u = _func_reads(name)
        report["func"][name] = {
            "dissent": _d, "unanimous": _u,
            "dissent_rate": (round(_d / _u, 3) if _u else None)}

    # 最终判决变化（W4 开 vs 关，同温同 (sub, rep)）
    def _final(vs):
        _all = list(vs)
        _c = {}
        for lb in _all:
            _c[lb] = _c.get(lb, 0) + 1
        _top = max(_c.values())
        _win = [k for k, c in _c.items() if c == _top]
        return _win[0] if (len(_win) == 1 and _top >= 2) else "partial"

    report["final_change"] = {}
    for temp_tag in ("t0", "t7"):
        a, b = "w4_off_" + temp_tag, "w4_on_" + temp_tag
        ch = tot = 0
        for rr_i in range(REPS):
            va = {int(k): {int(x): y for x, y in vv.items()}
                  for k, vv in raw[a]["reps"][rr_i]["votes"].items()}
            vb = {int(k): {int(x): y for x, y in vv.items()}
                  for k, vv in raw[b]["reps"][rr_i]["votes"].items()}
            for i in range(1, len(SUBS) + 1):
                sa, sb = va.get(i) or {}, vb.get(i) or {}
                if len(sa) < 3 or len(sb) < 3:
                    continue
                tot += 1
                ch += 0 if _final(sa.values()) == _final(sb.values()) else 1
        report["final_change"][temp_tag] = {
            "changed": ch, "total": tot,
            "rate": (round(ch / tot, 3) if tot else None)}


    # ---- 证据反事实：on_swap_t0 vs w4_on_t0（第 3 票逐条比）----
    _ch = _tt = 0
    for rr_i in range(REPS):
        va = {int(k): {int(x): y for x, y in vv.items()}
              for k, vv in raw["w4_on_t0"]["reps"][rr_i]["votes"].items()}
        vb = {int(k): {int(x): y for x, y in vv.items()}
              for k, vv in raw["on_swap_t0"]["reps"][rr_i]["votes"].items()}
        for i in range(1, len(SUBS) + 1):
            if 2 in (va.get(i) or {}) and 2 in (vb.get(i) or {}):
                _tt += 1
                _ch += 0 if va[i][2] == vb[i][2] else 1
    report["swap"] = {"third_vote_changed": _ch, "total": _tt,
                      "rate": (round(_ch / _tt, 3) if _tt else None)}

    OUTJ.write_bytes(json.dumps(report, ensure_ascii=False, indent=2,
                                default=str).encode("utf-8"))
    print("[votes] 已写 %s" % OUTJ.name, flush=True)
    _write_md(report)
    print("[votes] 已写 %s" % OUTM.name, flush=True)
    return 0


def _write_md(rep: dict) -> None:
    L: list = []

    def w(s=""):
        L.append(s)

    w("# v1.23.3 · 遗留1 受控投票实验（固定子问题，只让三票重投）")
    w()
    w("> 数据源：`%s`（src `%s`）；每臂 **%d 次重复** × **%d 条子问题**。"
      % (OUTJ.name, rep["src"], rep["reps"], rep["n_subs"]))
    w("> 四臂 = W4 关/开 × 温度 0.0/0.7。★ **温度 0.7 是变异体**：")
    w("> 注入随机性后 ICC 若**不下降**，说明这个 ICC 没有判别力。")
    w()
    w("## 一、一致率（跨 rep 汇总）")
    w()
    w("| 臂 | W4 | 温度 | agree12 | agree13 | agree23 | 第三票落差 | 样本 |")
    w("|---|---|---|---|---|---|---|---|")
    for name, _w4, _t, _e in ARMS:
        d = rep["metrics"][name]
        w("| %s | %s | %s | %s | %s | %s | %s | %d |"
          % (name, "开" if _w4 else "关", _t, d["agree12"], d["agree13"],
             d["agree23"], d["gap"], d["n12"]))
    w()
    w("## 二、判据「组间 ≥ 组内」的 **ICC(1,1) + 自助 95% 区间**")
    w()
    w("组 = 子问题（%d 组），组内 = 同一子问题的 %d 次重投。"
      % (rep["n_subs"], rep["reps"]))
    w("判定线是 **ICC = 0.5**（σ²_组间 = σ²_组内）。")
    w()
    w("| 臂 | 指标 | ICC | 95% 区间 | 组内极差(最大) | 判定 |")
    w("|---|---|---|---|---|---|")
    for name, _w4, _t, _e in ARMS:
        for mk in ("a12", "a13", "a23"):
            d = rep["icc"][name][mk]
            w("| %s | %s | %s | %s | %s | %s |"
              % (name, mk, d["icc"], d["ci"], d["within_max_range"],
                 d["verdict"]))
    w()
    w("## 三、W4 的**效果**（同子问题配对，W4 开 − W4 关）")
    w()
    w("差 = 「第三票与前两票的最大一致」在同一条子问题上的变化 ⇒ > 0 表示")
    w("W4 让第三票**更独立**（与前两票更不一致）。")
    w()
    w("| 温度 | 平均差 | 95% 区间（按子问题重采样） | n |")
    w("|---|---|---|---|")
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag)
        if not d:
            w("| %s | — | — | — |" % tag)
            continue
        w("| %s | %s | %s | %d |" % (tag, d["mean_w4_minus_off"], d["ci"],
                                     d["n"]))
    w()
    w("## 三·B 字面口径「组间 ≥ 组内」")
    w()
    w("组间 = 臂间配对差 Δ（同子问题配对，消掉子问题难度）；"
      "组内 = 配对后残差的 σ。")
    w("判据：**|Δ| ≥ σ** ⇒ 信号盖过噪声。")
    w()
    w("同一份配对数据有**两个读法**，两个都报 —— 哪个是主判据写在这里：")
    w()
    w("| 读法 | 口径 | Δ | 结果 | 主判据? |")
    w("|---|---|---|---|---|")
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag) or {}
        if not d:
            w("| — | — | — | — | — |")
            continue
        w("| **F 检验**（标准 / ANOVA 一致） | 组间 ≥ 组内 ⇔ MS_b ≥ MS_w "
          "⇔ F = t² ≥ 1 ⟺ \\|Δ\\| ≥ SE = σ/√n | %s | F = %s，t = %s ⇒ %s | "
          "✅ 主判据 |"
          % (d["mean_w4_minus_off"], d.get("F"), d.get("t"),
             d.get("verdict_F")))
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag) or {}
        if not d:
            continue
        w("| 个体级 σ（更苛刻的读法） | \\|Δ\\| ≥ σ_组内 | %s | \\|Δ\\|/σ = %s "
          "⇒ %s | ✗ 不作主判据 |"
          % (d["mean_w4_minus_off"], d.get("ratio", "∞"), d["verdict_B"]))
    w()
    w("★ **为什么 F 检验是主判据**：「组间 ≥ 组内」在实验设计里的标准含义就是")
    w("  MS_组间 ≥ MS_组内（ANOVA），等价于配对 t 的 \\|Δ\\| ≥ SE。")
    w("  而「\\|Δ\\| ≥ σ_个体」是另一个更苛刻的读法 —— 对**二值**指标")
    w("  （每条子问题的差 d ∈ {−1, 0, +1}）几乎不可能成立；它量的其实是")
    w("  **效应异质性**（效应是否在每条子问题上同号同幅），不是噪声。")
    w("  两个都列出，避免「换个口径把它做绿」的嫌疑。")
    w()
    w("## 三·C 票的 id 基准（★ 0 起 = 整票错位一格，且引擎侧**无声**）")
    w()
    w("引擎按 **1 起** 对齐（`enumerate(subs, 1)`）。若某票返回 **0 起**，")
    w("它的票会**整票错位一格**：第 2 条子问题拿到本该给第 1 条的标签 ——")
    w("既不错也不留痕，读者从产物上完全看不出来。")
    w()
    w("| 臂 | 1 起 | **0 起** | 越界/其他 | 空票 | 非对象 |")
    w("|---|---|---|---|---|---|")
    for name, _w4, _t, _e in ARMS:
        d = rep["id_base"][name]
        w("| %s | %d | **%d** | %d | %d | %d |"
          % (name, d["1起"], d["0起"], d["越界/其他"], d["空票"], d["非对象"]))
    w()
    w("## 四、第三票的**功能读出**（这才是「正交」该量的东西）")
    w()
    w("★ 原指标「第三票改变多数结论」在 3 票制下**恒为 0**（1、2 票一致时")
    w("  第三人永远改不了多数）—— 已换成下面两个真正有语义的量。")
    w()
    w("**唱反调率 = 1、2 票一致时第 3 票唱反调的比例**（0 = 橡皮图章）。")
    w()
    w("| 臂 | 1、2 票一致的条数 | 第 3 票唱反调 | 唱反调率 |")
    w("|---|---|---|---|")
    for name, _w4, _t, _e in ARMS:
        d = (rep.get("func") or {}).get(name) or {}
        w("| %s | %s | %s | %s |"
          % (name, d.get("unanimous"), d.get("dissent"), d.get("dissent_rate")))
    w()
    w("**最终判决变化率**（同一 (子问题, 重复) 下 W4 开 vs 关）：")
    w()
    w("| 温度 | 变化条数 / 可比条数 | 比例 |")
    w("|---|---|---|")
    for tag in ("t0", "t7"):
        d = (rep.get("final_change") or {}).get(tag) or {}
        w("| %s | %s / %s | %s |" % (tag, d.get("changed"), d.get("total"),
                                     d.get("rate")))
    w()
    w("## 五、证据**反事实**：第三票是不是真的在被外部材料驱动")
    w()
    w("同一批子问题、同样 W4 开，只把外部材料换成**相反**的说法 ⇒ 统计")
    w("第 3 票的标签变化率。**变** = 外部材料真的进了它的判断；")
    w("**不变** = 那一票根本没读材料（W4 就是接线没通电）。")
    w()
    d = rep.get("swap") or {}
    w("- 第 3 票标签变化：**%s / %s = %s**" % (d.get("third_vote_changed"),
                                          d.get("total"), d.get("rate")))
    w()
    OUTM.write_bytes("\n".join(L).replace("\n", "\r\n").encode("utf-8"))


if __name__ == "__main__":
    sys.exit(main())
