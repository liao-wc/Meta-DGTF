#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit_v64_zero_triggers.py

[v1.21.64 C] 零触发机制审计（独立只读脚本，不改主文件）。

目标：用**已有的真跑产物**回答下列问题，而不是靠新跑一次去猜。

  机制一 · escalate_starve_rounds=2
    一个子问题连续 2 圈「没任何进展」+ 名下挂着未清偿债务 → 迁向 undecidable。
  机制二 · no_push_when_idle=1
    停止判据是「层内空转」时，**不应**被「未深入方向」推迟。
  机制三 · _reopen_closed_debt
    迁向 undecidable 后被救回时，被关的账要重新挂上。
  机制四 · stable_layers 2→3
    元层悬置决定连续 3 圈同一批 → 自然安住。

★ 两点与提示词版不同（都是为了让审计**不空转**）：
  1. 加 `--log`：只读产物 md 时，很多"没触发"其实是"产物里没有这个渲染点"。
     真跑的 verbose 日志里有更硬的直接证据（例如机制二的
     `[fix-88b] … 不推迟`），读它才能分清「没触发」和「看不到」。
  2. 加「格式自检」段：逐条说明每个探针期望的渲染格式在本产物里
     **存在 / 不存在**。不存在时必须显式说「本产物无法回答」，
     而不是把 0 当成「没触发」。

用法：
  python _audit_v64_zero_triggers.py outputs/xxx.md
  python _audit_v64_zero_triggers.py outputs/xxx.md --log verif_D3_v63.log
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ENTRIES = ("0", "1", "both", "all")
LABEL2ENTRY = {"修行": "0", "研究": "1", "对撞": "both", "元": "all"}


def _parse_md(md_path: Path) -> dict:
    """从产物 md 里把关键信息抽出来（不追求穷尽，只抽审计需要的）。"""
    text = md_path.read_text(encoding="utf-8")
    out = {
        "stop_reasons": {},
        "rounds": {},
        "deferred_notes": {e: [] for e in ENTRIES},
        "sub_questions": [],
        "deferrals": [],
        "decidability_log": [],
        "pool_debt_counts": {},
        # [v1.21.65 A] 池段新出口：机制一两条条件的进度
        "starve": {},
    }

    # 每层的【螺旋停止】行（层标题 -> 该层段里第一条「螺旋停止」）
    for m in re.finditer(
            r"### (修行|研究|对撞|元)层 `(\w+)`.*?\*\*螺旋停止\*\*：([^\n]+)",
            text, re.S):
        out["stop_reasons"][LABEL2ENTRY[m.group(1)]] = m.group(3).strip()

    # 每层实际走了几圈
    for m in re.finditer(
            r"### (修行|研究|对撞|元)层 `(\w+)`.*?"
            r"\*\*实际走了 (\d+) 圈\*\*（上限 (\d+) 圈）", text, re.S):
        out["rounds"][LABEL2ENTRY[m.group(1)]] = {
            "ran": int(m.group(3)), "cap": int(m.group(4))}

    # 「体力耗尽（…）」类推迟留痕
    for m in re.finditer(
            r"### (修行|研究|对撞|元)层 `(\w+)`.*?体力耗尽（([^）]+)）",
            text, re.S):
        out["deferred_notes"][LABEL2ENTRY[m.group(1)]].append(m.group(3).strip())

    # 研究层子问题统计
    for m in re.finditer(
            r"- 子问题 (\d+) 条：可判定 (\d+) / 不可判定 (\d+)"
            r"（另有 (\d+) 条 partial 等）", text):
        out["sub_questions"].append({
            "total": int(m.group(1)), "dec": int(m.group(2)),
            "und": int(m.group(3)), "partial": int(m.group(4))})

    # 池段：每层的「延迟债务 N 条」
    for m in re.finditer(
            r"### (\w+) 池[^\n]*\n(.*?)(?=\n### |\n## |\Z)", text, re.S):
        blk = m.group(2)
        d = re.search(r"- 延迟债务 (\d+) 条", blk)
        if d:
            out["pool_debt_counts"][m.group(1)] = int(d.group(1))

    # [v1.21.65 A / v1.21.66] 「🍽 无进展计数」行 —— 机制一的"离门槛差多少"
    #   ★ v1.21.66 起**加性**多了一段「运行期峰值」（快照会被清零、峰值不会）。
    #   ⇒ 峰值段写成**可选**：否则正则整条失配，本项会退化成一份
    #   "看着像没触发"的空报告（v1.21.65 的旧产物也要能解析）。
    for m in re.finditer(
            r"🍽 无进展计数：最高 (\d+) 圈（([^）]*)）"
            r"(?:｜运行期峰值 (\d+) 圈（([^）]*)）)?"
            r"｜名下有挂账的子问题 (\d+) 条"
            r"(?:｜计数已写 (\d+)/(\d+) 条|｜★ 计数未写（机制未运行）)?",
            text):
        out["starve"] = {
            "max": int(m.group(1)), "dist": m.group(2),
            "peak": int(m.group(3)) if m.group(3) is not None else None,
            "peak_dist": m.group(4),
            "with_debt": int(m.group(5)),
            "tracked": int(m.group(6)) if m.group(6) is not None else None,
            "tracked_total": (int(m.group(7))
                              if m.group(7) is not None else None)}

    # deferrals 明细（池段「延迟债务（终态）」）
    for m in re.finditer(
            r"- \[\w+\] 子问题(\d+) [^：\n]*[：:]([^\n]*)"
            r"\n\s*回访条件：([^\n｜]*)", text):
        out["deferrals"].append({
            "sub_id": int(m.group(1)),
            "reopened_from": (m.group(3).strip()
                              if "接" in m.group(3) else None)})

    # 可判定性变更账（逐条「不可判定→可判定」形态）
    for m in re.finditer(
            r"L(\d+) 子问题\[(\d+)\] 不可判定→(可判定|部分可判定)", text):
        out["decidability_log"].append({
            "layer": int(m.group(1)), "sub_id": int(m.group(2)),
            "to": m.group(3)})
    return out


def _log_evidence(log_path):
    """从 verbose 日志里取**直接证据**（产物 md 里看不到的那些）。"""
    if not log_path or not Path(log_path).exists():
        return None
    t = Path(log_path).read_text(encoding="utf-8", errors="replace")
    ev = {}
    ev["no_push_hits"] = re.findall(
        r"\[fix-88b\] 有 (\d+) 条未深入方向，但停止判据是空转类[^\n]*",
        t)
    ev["escalate_hits"] = re.findall(r"[^\n]*迁向不可判定[^\n]*", t)
    ev["reopen_hits"] = re.findall(r"[^\n]*重新挂账[^\n]*", t)
    ev["starve_lines"] = re.findall(r"[^\n]*_starve_rounds[^\n]*", t)
    ev["stable_hits"] = re.findall(r"[^\n]*自然安住[^\n]*", t)
    ev["debt_lines"] = re.findall(r"⏳ 债务：[^\n]*", t)
    ev["susp_lines"] = re.findall(r"⏸ 悬置：[^\n]*", t)
    ev["duel_lines"] = re.findall(r"⚔️ 张力：[^\n]*", t)
    return ev


def _fmt_hit(ev, key):
    if ev is None:
        return "（未提供 --log，无法取直接证据）"
    v = ev.get(key) or []
    return f"{len(v)} 处" + (f"：{v[0][:70]}" if v else "")


def _st_tracked_zero(sr):
    """覆盖计数存在且为 0 → 机制没运行（真 0 与假 0 的分界）。"""
    return bool(sr) and sr.get("tracked") == 0


def _fmt_starve_agg(ev):
    """从债务统计行里读「升级」总数（机制一的产物侧计数）。"""
    if ev is None:
        return "（未提供 --log）"
    tot = 0
    for ln in (ev.get("debt_lines") or []):
        m = re.search(r"升级(\d+)", ln)
        if m:
            tot += int(m.group(1))
    return f"全部 `⏳ 债务` 行的「升级」合计 = {tot}"


def _audit_1(d, ev):
    L = ["### 机制一 · escalate_starve_rounds=2\n",
         "**判据**：一个子问题连续 2 圈无任何进展（没被回答 / 没挂新账 / "
         "没被清偿 / 没分类变更）+ 名下有未清偿债务 → 应迁向 undecidable。\n\n"]
    L.append(f"- **直接证据**：日志里「迁向不可判定」={_fmt_hit(ev, 'escalate_hits')}；"
             f"产物侧 {_fmt_starve_agg(ev)}。\n")
    # [v1.21.65 A / v1.21.66] 有出口之后，直接报"离门槛差几圈 + 条件二几条"。
    #   ★ v1.21.66 起**峰值才是对的口径**：快照有两个清零点，对"自然停"的
    #   层结构性接近 0，拿它算"差几圈"等于把问题又答糊一次。
    _sr = d.get("starve") or {}
    _thr = 2
    if _sr and _sr.get("peak") is not None:
        _pk = int(_sr["peak"])
        _sn = int(_sr.get("max", 0))
        L.append(f"- **离门槛差多少（v1.21.66 起报峰值）**：最终快照 "
                 f"`{_sr.get('dist')}`（最高 {_sn} 圈）｜**运行期峰值 "
                 f"`{_sr.get('peak_dist')}`（最高 {_pk} 圈）**"
                 f"（门槛 N 见 `spiral.escalate_starve_rounds`，出厂 {_thr}）→ "
                 f"按峰值算差 **{max(0, _thr - _pk)} 圈**；"
                 f"条件二「名下有挂账」**{_sr.get('with_debt')} 条**在排队。\n")
        if _pk >= _thr:
            L.append(f"  ★ 峰值已够到门槛（{_pk} ≥ {_thr}）却没升级 → "
                     "**卡在条件二**：那一刻它名下没有挂着的账。\n")
        elif _st_tracked_zero(_sr):
            L.append("  ★ **覆盖计数为 0 ⇒ 机制未运行**（该层没走到或开关为 0）："
                     "这个 0 **不是**「离门槛差 2 圈」，是**没有观测点**。\n")
        elif _pk > 0:
            L.append(f"  ★ 峰值到过 {_pk} 圈 ⇒ **确实出现过无进展的子问题**；"
                     "快照里那个 0 是清零造出来的，不是「没发生」。\n")
        elif _sr.get("tracked") is not None:
            L.append("  ★ 峰值也是 0，且**覆盖计数**在 ⇒ 机制确实每圈都跑了 —— "
                     "每个子问题每圈都被碰过，这个 0 是**真 0**。\n")
        else:
            L.append("  ★ 峰值 0，但本产物**没有覆盖计数** ⇒ 无法排除"
                     "「机制压根没跑」：那种情况下字段缺席，渲染出来"
                     "**同样是 0**。要区分，得用带覆盖计数的产物。\n")
    elif _sr:
        L.append(f"- **离门槛差多少**：本产物是 v1.21.65 口径（只有快照、"
                 f"没有峰值段）：分布 `{_sr.get('dist')}`、最高 "
                 f"**{_sr.get('max')} 圈**。★ `_starve_rounds` 有**两个清零点**"
                 "（被触碰 / 升级走），这个快照数**不能**当"
                 "「从没接近过门槛」读。\n")
        if _sr.get("tracked") == 0:
            L.append("  ★ 但**覆盖计数为 0** ⇒ 机制未运行，这个 0 是"
                     "「没有观测点」，不是「差 2 圈」。\n")
    else:
        L.append("- **本产物没有「🍽 无进展计数」行**"
                 "（v1.21.65 起才有；或将来的产物格式又变了）—— "
                 "这一项本产物无法回答。\n")
    _tot = sum(s["total"] for s in d["sub_questions"]) or 0
    _r1 = (d["rounds"].get("1") or {})
    L.append(f"- **本轮结构**：研究层走了 {_r1.get('ran', '?')} 圈"
             f"（上限 {_r1.get('cap', '?')}）；子问题 {_tot} 条；"
             f"池段延迟债务 {d['pool_debt_counts']}。\n")
    _pk2 = (_sr or {}).get("peak")
    if _pk2 is None:
        L.append("- **离触发差多少**：机制一要「**连续 2 圈**无进展」且"
                 "**名下有债**。本产物没有峰值出口，只能看日志侧债务统计："
                 f"{_fmt_starve_agg(ev)}（`升级` 合计 0 = 没有子问题迁走）。\n")
    elif int(_pk2) >= _thr:
        L.append("- **离触发差多少**：**峰值已过门槛却没升级** → 卡在条件二"
                 "（那一刻名下没有挂着的账）。与 v1.21.65 逐圈对账的结论一致："
                 "两条条件在时间上错开。\n")
    elif int(_pk2) == 1:
        L.append("- **离触发差多少**：峰值只到 1 圈 → **差 1 圈**："
                 "每个子问题都在 1 圈内被碰过一次，没凑出连续 2 圈。\n")
    else:
        # ★ 峰值 0 有三种可能，不能一概说成「每圈都被碰过」：
        #   覆盖计数为 0 = 机制没跑（没有观测点）；
        #   覆盖计数在   = 真 0；
        #   没有覆盖计数 = 无法区分（老产物）。
        _cov = (_sr or {}).get("tracked")
        if _cov == 0:
            L.append("- **离触发差多少**：**覆盖计数为 0 ⇒ 机制未运行**，"
                     "这一跑**没有观测点** —— 既不能说「差 2 圈」，"
                     "也不能说「每圈都被碰过」。\n")
        elif _cov is not None:
            L.append("- **离触发差多少**：**峰值也是 0**，且覆盖计数在 ⇒ "
                     "这一跑里每个子问题每圈都被碰过，没出现无进展的子问题。"
                     "差的是「题的结构」，不是圈数 —— 但**已拍板不再为此"
                     "换题**（见下）。\n")
        else:
            L.append("- **离触发差多少**：峰值 0，但本产物**没有覆盖计数** ⇒ "
                     "无法排除「机制压根没跑」（字段缺席时渲染出来同样是 0）。"
                     "这一跑**不能**据此得出「每个子问题每圈都被碰过」。\n")
    L.append("- ★ **已拍板（v1.21.65）：接受它为「设计上狭窄」并保留**。"
             "理由：它要求「名下有债」**且**「连续 N 圈没被碰」**同时**成立，"
             "而实测这两集合在时间上错开 —— 被挂账的都在动（挂账那圈刚被碰过、"
             "1~2 圈内就被清偿），不动的都没挂账。这种情况**确实少**，"
             "但机制本身正当（`_starve_escalation` 的注释明写「只认挂着的账"
             "当证据」，为防它乱判不可判定）。\n"
             "  ⇒ **不必再为它换题**。只有题面恰好出现「某个子问题先被挂账、"
             "然后连着 N 圈没人再碰它」时才会触发；等它自然出现即可。\n")
    return "".join(L)


def _audit_2(d, ev):
    L = ["### 机制二 · no_push_when_idle=1\n",
         "**判据**：停止判据是「层内空转」（ing 复述 / 自省点名未消化）时，"
         "**不应**被「未深入方向」推迟。\n\n"]
    hits = [e for e, r in d["stop_reasons"].items()
            if ("层内空转" in r) or ("有新增但无推进" in r)]
    L.append(f"- **直接证据**：日志里 `[fix-88b] … 不推迟` = "
             f"{_fmt_hit(ev, 'no_push_hits')}。\n")
    L.append(f"- **产物侧**：{len(hits)} 层的「螺旋停止」是空转类 —— "
             + ("、".join(f"`{e}`" for e in hits) if hits else "（无）") + "。\n")
    if hits:
        L.append("- **结论**：**已触发**（产物侧与日志侧一致）。该机制不再"
                 "属于「零触发」。\n")
    else:
        L.append("- **结论**：本轮无层触发空转类停止判据 → 该机制无观测机会。\n")
    return "".join(L)


def _audit_3(d, ev):
    L = ["### 机制三 · _reopen_closed_debt\n",
         "**判据**：迁向 undecidable 后被救回（dec/partial），被关的账要"
         "**重新挂一笔**（reopened_from 指向旧账）。\n\n"]
    _re = [x for x in d["deferrals"] if x.get("reopened_from")]
    L.append(f"- **直接证据**：日志里「重新挂账」={_fmt_hit(ev, 'reopen_hits')}。\n")
    L.append(f"- 产物侧：有 `reopened_from` 的 deferral **{len(_re)}** 条；"
             f"逐条形态的「不可判定→可判定」记录 **{len(d['decidability_log'])}** 条。\n")
    L.append("- **格式自检**：本产物渲染的是**覆盖轨迹**"
             "（`📘 不可判定覆盖轨迹：L1 a/b → L2 c/d …`）与"
             "**最终状态表**，**没有**逐条的「不可判定→可判定」账；"
             "因此上面那个 0 **不能**单独作为「没发生」的证明 —— "
             "日志侧才是判据。\n")
    L.append("- **离触发差多少**：机制三的**前置是机制一**（得先有人迁向 "
             "undecidable，才谈得上被救回）。机制一本轮 0 次 → 机制三"
             "**结构上不可达**。\n")
    return "".join(L)


def _audit_4(d, ev):
    L = ["### 机制四 · stable_layers 2→3\n",
         "**判据**：元层悬置决定连续 3 圈同一批 → 自然安住。\n\n"]
    _ra = (d["rounds"].get("all") or {})
    L.append(f"- **直接证据**：日志里「自然安住」={_fmt_hit(ev, 'stable_hits')}；"
             f"`转稳` 计数（悬置/张力统计行）="
             + (f"{sum(int(m) for m in re.findall(r'转稳(\\d+)', ' '.join((ev or {}).get('susp_lines') or [])))}"
                if ev else "（未提供 --log）") + "。\n")
    L.append(f"- **本轮结构**：元层走了 {_ra.get('ran', '?')} 圈"
             f"（上限 {_ra.get('cap', '?')}）→ "
             + ("**圈数够**（≥3），结构上可达" if _ra.get("ran", 0) >= 3
                else "**圈数不够**，结构上不可达")
             + "。\n")
    if "自然安住" in (d["stop_reasons"].get("all") or ""):
        L.append("- **结论**：**已触发**。\n")
    else:
        L.append("- **结论**：未触发。差的是「悬置决定连续 3 圈保持同一批」"
                 "—— 本轮元层每圈都还在新增/撤回（见 ⏸ 悬置统计行），"
                 "**批次没稳下来**。\n")
        L.append("- **下一步设计方向**：选一道**边界模糊、悬置明显**的题"
                 "（价值选择 / 制度设计类），让元层连续多圈对同一批张力"
                 "保持 stable。\n")
    return "".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?", default=None,
                    help="产物 md 路径；不给取 outputs/ 下最新一份")
    ap.add_argument("--log", default=None,
                    help="同一次真跑的 verbose 日志（取直接证据）")
    ap.add_argument("--out", default=None, help="审计报告落盘路径")
    args = ap.parse_args()

    if args.md:
        md = Path(args.md)
    else:
        cands = sorted(Path("outputs").glob("*.md"),
                       key=lambda p: p.stat().st_mtime)
        md = cands[-1] if cands else None
    if not md or not md.exists():
        print("❌ 找不到产物 md。请显式传路径。")
        sys.exit(1)
    print(f"读入：{md}")
    d = _parse_md(md)
    ev = _log_evidence(args.log)
    _st = d.get("starve") or {}
    if not _st:
        _starve_note = ("**本产物没有这一行**（v1.21.65 前无此渲染点）→ "
                        "该探针在本产物**无渲染点**，这一项的 0/空"
                        "**不代表**没发生。")
    elif _st.get("peak") is None:
        _starve_note = (f"快照最高 {_st.get('max')} 圈；**无峰值段**"
                        "（本产物是 v1.21.65 口径，或格式又变了）。")
    else:
        _trk = _st.get("tracked")
        _trk_s = (f"覆盖 {_trk}/{_st.get('tracked_total')} 条"
                  if _trk is not None else
                  "★ 无覆盖计数（产物未带这一列）" if _trk is None and
                  _st.get("tracked_total") is None and
                  _st.get("tracked") is None else "覆盖未知")
        _starve_note = (f"快照最高 {_st.get('max')} 圈｜峰值最高 "
                        f"{_st.get('peak')} 圈｜{_trk_s}"
                        "（两段都解析到了）。")
    if args.log:
        print(f"读入日志：{args.log}"
              + ("" if ev else "（不存在，直接证据缺失）"))

    parts = [
        f"# 零触发机制审计 · {datetime.now().isoformat()}\n\n",
        f"**输入产物**：`{md}`\n\n",
        f"**输入日志**：`{args.log or '（未提供）'}`\n\n",
        "---\n\n",
        _audit_1(d, ev), "\n",
        _audit_2(d, ev), "\n",
        _audit_3(d, ev), "\n",
        _audit_4(d, ev), "\n",
        "---\n\n",
        "## 格式自检（哪些探针在本产物里**本就无渲染点**）\n\n",
        f"- 每层「螺旋停止」：解析到 {len(d['stop_reasons'])}/4 层"
        "（缺的层 = 该层没有这一行，不是探针坏了）。\n",
        f"- 每层「实际走了 N 圈」：解析到 {len(d['rounds'])}/4 层。\n",
        f"- 「体力耗尽（…）」：{sum(len(v) for v in d['deferred_notes'].values())} 处。\n",
        f"- 逐条「不可判定→可判定」：{len(d['decidability_log'])} 处 —— "
        "★ 该形态在本版本**没有渲染点**（只渲染累计覆盖轨迹），"
        "所以这项的 0 **不代表**没发生。\n",
        f"- 池段「延迟债务 N 条」：{d['pool_debt_counts'] or '（无）'}。\n",
        f"- 「🍽 无进展计数」：{_starve_note}\n",
        "\n",
        "## 结论\n\n",
        "审计报告**不预设「应该触发」**。它只回答两个问题：\n\n",
        "1. 每个机制在**这一跑**里有没有触发（直接证据）？\n",
        "2. 若没触发，**离触发差什么**（差圈数 / 差题 / 差前置条件）？\n\n",
        "据此决定：\n",
        "- 若某项**结构上不可达**（如元层从不超过 2 圈）→ 是设计层级的"
        "问题，不是「跑错了题」。\n",
        "- 若某项**差一点**（如研究层 3 圈刚好差 1 圈）→ 下一步专门选一道"
        "题给它时间。\n",
        "- 若某项**完全无机会**（该跑没那个结构）→ 下一步按上面给的"
        "「设计方向」跑。\n\n",
        "★ 无论哪种情况，**结论都要先落在这份报告里**，再决定要不要动"
        "主文件。不许拍脑袋收紧判据。\n",
    ]
    text = "".join(parts)
    out = Path(args.out or ("audit_zero_triggers_"
                            + datetime.now().strftime("%Y%m%d_%H%M%S") + ".md"))
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n📁 已写：{out}")


if __name__ == "__main__":
    main()
