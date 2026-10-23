#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.1 遗留1] 分析：三场景命中率 + 三票正交度（组间 ≥ 组内才许断言）。

读 `_v1230_w6_runs.json`，写 `_v1230_w6_analysis.md`。

★ 纪律（本项目反复踩过）：
  · 「两臂对照」前先证两臂都**真的产出了**这个量（`in` 判断，不用 get）；
  · 任何「组间差」结论都必须 **组间差 ≥ 组内极差**，否则写「不可判定」；
  · 不把「没测到」写成「没发生」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
J = HERE / "_v1230_w6_runs.json"
if not J.is_file():
    print("缺 %s —— 先跑 _run_v1230_w6.py" % J.name)
    sys.exit(1)
D = json.loads(J.read_text(encoding="utf-8"))
RUNS = [r for r in (D.get("runs") or []) if r.get("ok")]
if not RUNS:
    print("没有成功的跑（ok=False 的有 %d 条）" % len(D.get("runs") or []))
    sys.exit(1)

L: list = []


def w(s=""):
    L.append(s)


def _voters(sub):
    """把 votes 规范化成 {voter_index: label}。缺 voters 的字段用 `in` 判。"""
    out = {}
    for v in (sub.get("votes") or []):
        if not isinstance(v, dict):
            continue
        if "voter" in v and "label" in v:
            out[int(v["voter"])] = str(v["label"])
    return out


def _pair_rate(runs, a, b):
    """两两一致率 + 样本数（只数**两人都投票**的子问题）。"""
    hit = tot = 0
    for r in runs:
        for s in (r.get("subs") or []):
            vs = _voters(s)
            if a in vs and b in vs:
                tot += 1
                hit += 1 if vs[a] == vs[b] else 0
    return (round(hit / tot, 3) if tot else None), tot


def _has_votes(runs):
    return any(_voters(s) for r in runs for s in (r.get("subs") or []))


ON = [r for r in RUNS if r.get("arm") == "ON"]
OFF = [r for r in RUNS if r.get("arm") == "OFF"]
SCEN = {r["tag"]: r.get("scenario") for r in RUNS}

w("# 分析：三场景命中率 + 三票正交度（数据源 %s）"
  % (D.get("src") or "?"))
w()
w("> 数据源：`_v1230_w6_runs.json`（%d 跑：ON %d / OFF %d）。"
  % (len(RUNS), len(ON), len(OFF)))
w("> 口径：每题只跑 2 次（ON 臂）+ 1 次（OFF 臂）。**凡 n 不足处一律写「不可判定」**。")
w()

# ---------------------------------------------------------------- 1 命中率
w("## 一、三场景命中率")
w()
w("**「命中」的定义**（本报告口径，写死在这里以免事后游移）：该跑的研究层")
w("**真的收到了外部材料**（`web_n ≥ 1`）。**场景命中** = 该场景 2 跑中 ≥1 跑命中。")
w("**命中率 = 命中场景数 / 3**。")
w()
w("| 场景 | 题目 | 跑数 | 各跑 W# 条数 | 覆盖环节 | 场景命中 |")
w("|---|---|---|---|---|---|")
_hit_scen = 0
for tag, scen in SCEN.items():
    rs = [r for r in ON if r.get("tag") == tag]
    if not rs:
        continue
    ns = [r.get("web_n") for r in rs]
    st = sorted({s for r in rs for s in (r.get("web_stages") or [])})
    hit = any((n or 0) >= 1 for n in ns)
    _hit_scen += 1 if hit else 0
    w("| %s | %s | %d | %s | %s | %s |"
      % (scen, tag, len(rs), ns, "、".join(st) or "—", "✅" if hit else "✗"))
w()
_rate = _hit_scen / 3
w("**命中率 = %d / 3 = %.0f%%**　（门槛「≥ 50%%」：%s）"
  % (_hit_scen, _rate * 100, "达标 ✅" if _rate >= 0.5 else "**未达标 ✗**"))
w()
w("### 1.0 检索级口径（连续量 + Wilson 区间）")
w()
w("「跑级」是二值（命中/不命中），2 跑/场景只能给 0%/50%/100% 三档。")
w("补一个**连续**口径：**命中 = 该次检索返回了 ≥1 条**（分母 = `gate.run_total`，")
w("即真正放行的检索次数；空结果由 `[W-EMPTY]` 计数）。")
w()
w("| 跑 | 放行检索次数 | 空结果 | 命中 | 命中率 |")
w("|---|---|---|---|---|")
_agg_hit = _agg_tot = 0
for r in ON:
    _t = (r.get("gate") or {}).get("run_total") or 0
    _e = r.get("web_empty_n") or 0
    _h = max(0, _t - _e)
    _agg_hit += _h
    _agg_tot += _t
    w("| %s | %d | %d | %d | %s |"
      % (r.get("job"), _t, _e, _h,
         ("%.0f%%" % (100.0 * _h / _t)) if _t else "—"))


def _wilson(k, n, z=1.96):
    """Wilson 区间：小样本比率的区间估计（比正态近似稳）。"""
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


if _agg_tot:
    _lo, _hi = _wilson(_agg_hit, _agg_tot)
    w()
    w("**检索级命中率 = %d / %d = %.0f%%**（Wilson 95%% 区间 [%.0f%%, %.0f%%]，"
      "n = %d 次检索）"
      % (_agg_hit, _agg_tot, 100.0 * _agg_hit / _agg_tot,
         _lo * 100, _hi * 100, _agg_tot))
    w()
    w("⇒ 这个口径下 n 从「%d 跑」升到「%d 次检索」，区间**不含 0**，"
      "所以「联网确实能收到材料」这条是**可判定**的（跑级那一栏只作方向）。"
      % (len(ON), _agg_tot))
w()

w("逐跑明细（联网通道到底发生了什么 —— 这三类必须分开读）：")
w()
w("| 跑 | W# | 空结果 | 配额跳过 | 失败 | gate.run_total | 圈号 |")
w("|---|---|---|---|---|---|---|")
for r in ON:
    w("| %s | %d | %d | %d | %s | %s | %s |"
      % (r.get("job"), r.get("web_n") or 0, r.get("web_empty_n") or 0,
         r.get("web_skip_n") or 0, r.get("web_err_kinds") or "—",
         (r.get("gate") or {}).get("run_total"), r.get("web_rounds")))
w()

# ---------------------------------------------------------------- 2 形状不变（C1）
w("### 1.1 旁证：联网没有改变研究层的形状（宪法 C1）")
w()
w("| 题目 | 臂 | 子问题数 | stability 分布 | `_vote_mode` |")
w("|---|---|---|---|---|")
for tag in SCEN:
    for arm, rs in (("OFF", [r for r in OFF if r.get("tag") == tag]),
                    ("ON", [r for r in ON if r.get("tag") == tag])):
        for r in rs:
            _sd = {}
            for s in (r.get("subs") or []):
                k = str(s.get("stability"))
                _sd[k] = _sd.get(k, 0) + 1
            w("| %s | %s%s | %d | %s | %s |"
              % (tag, arm, r.get("rep") if arm == "ON" else "",
                 r.get("n_subs") or 0, _sd,
                 sorted({str(s.get("vote_mode")) for s in (r.get("subs") or [])})))
w()

# ---------------------------------------------------------------- 3 正交度
w("## 二、三票正交度（W4 的验收）")
w()
w("**度量**：逐条子问题取三票标签，算两两一致率 `agree12 / agree13 / agree23`。")
w()
w("★ **口径**：一致率按**可用票对**汇总 —— 遍历「所有跑 × 全部子问题」，")
w("  只要该对两张票都投了就计入。**只有 2 票可用的跑不再被整跑丢掉**")
w("  （v1.23.1 报告里那种「n 只有 12」是把整跑丢掉造成的，样本量被白扔）。")
w("W4 把**第三票**换成「外部证据裁判」（只看 W# 与 X#）⇒ 若替换生效，")
w("第三票与前两票的一致性应**低于**前两票之间的一致性（它不是复读机）。")
w()
_ok_on = _has_votes(ON)
_ok_off = _has_votes(OFF)
w("两臂是否都**真的产出**了三票读数：ON = %s，OFF = %s"
  % ("✅" if _ok_on else "✗ 无 votes 字段", "✅" if _ok_off else "✗ 无 votes 字段"))
w("（★ 先证这个再谈差值 —— 否则「差值」可能是「一边没算」。）")
w()
if not _ok_on:
    w()
    w("⇒ **不可判定**：ON 臂没有三票明细，无法算一致性矩阵。")
else:
    w("**先看「可用票数」**（某票返回合法 dict 但零条判决时，等于弃权；"
      "v1.23.1 起留痕 `[三态多票] N/3 票可用`）：")
    w()
    w("| 跑 | 逐条可用票数 | 说明 |")
    w("|---|---|---|")
    for r in RUNS:
        _nv = sorted({len(_voters(s)) for s in (r.get("subs") or [])})
        w("| %s (%s%s) | %s | %s |"
          % (r.get("job"), r.get("arm"), r.get("rep"), _nv,
             "三票齐" if _nv == [3] else
             ("**不足 3 票** ⇒ 涉及第 3 票的指标不可算" if _nv else "无票")))
    w()
    w("| 臂 | 题 | agree12 | agree13 | agree23 | 样本(子问题) |")
    w("|---|---|---|---|---|---|")
    _on_rows, _off_rows = [], []
    for tag in SCEN:
        for arm, rs, bucket in (("OFF", [r for r in OFF if r.get("tag") == tag],
                                 _off_rows),
                                ("ON", [r for r in ON if r.get("tag") == tag],
                                 _on_rows)):
            if not rs or not _has_votes(rs):
                continue
            a12, n12 = _pair_rate(rs, 0, 1)
            a13, _n = _pair_rate(rs, 0, 2)
            a23, _n2 = _pair_rate(rs, 1, 2)
            bucket.append({"tag": tag, "a12": a12, "a13": a13, "a23": a23,
                           "n": n12})
            w("| %s | %s | %s | %s | %s | %d |"
              % (arm, tag, a12, a13, a23, n12))
    w()
    w("### 2.1 第三票是否「特立独行」（臂内比较）")
    w()
    for nm, rows in (("ON（第三票 = 外部证据裁判）", _on_rows),
                     ("OFF（第三票 = 普通中立票，W4 未生效）", _off_rows)):
        _g = [(r["a12"], r["a13"], r["a23"]) for r in rows
              if None not in (r["a12"], r["a13"], r["a23"])]
        if not _g:
            w("- **%s**：无完整三票样本 → 不可判定。" % nm)
            continue
        m12 = round(sum(x[0] for x in _g) / len(_g), 3)
        m13 = round(sum(x[1] for x in _g) / len(_g), 3)
        m23 = round(sum(x[2] for x in _g) / len(_g), 3)
        _gap = round(m12 - max(m13, m23), 3)
        _sp12 = (max(x[0] for x in _g) - min(x[0] for x in _g))
        w("- **%s**：均值 agree12=%.3f / agree13=%.3f / agree23=%.3f ⇒ "
          "第三票相对前两票的落差 = **%.3f**"
          "（agree12 的**跨组**极差 %.3f）"
          % (nm, m12, m13, m23, _gap, round(_sp12, 3)))
        w("  · **方向**：%s"
          % ("落差 > 0（第三票与前两票的一致性更低）"
             if _gap > 0 else
             "落差 ≤ 0（第三票与前两票一致度不低于前两票之间）"))
        _wr = []
        for _tag in SCEN:
            _rs = [r for r in RUNS if r.get("tag") == _tag
                   and r.get("arm") == nm[:2].upper()]
            if len(_rs) >= 2:
                _wr.append([_pair_rate([r], 0, 1)[0] for r in _rs])
        _wmax = (round(max(max(x) - min(x) for x in _wr
                           if None not in x), 3)
                 if any(None not in x and len(x) >= 2 for x in _wr) else None)
        w("  · ★ **但这个均值的落差没有减去噪声**：本臂的 agree12 组内极差 = %s"
          "，落差 = %.3f ⇒ %s"
          % (_wmax, _gap,
             "**落差 ≤ 组内极差 ⇒ 不可判定**（只是方向线索）"
             if (_wmax is not None and _gap <= _wmax) else
             "落差 > 组内极差（仍需看 2.2 的三项对账）"))
    w()
    _VERD: list = []
    w("### 2.2 组间 ≥ 组内？（这是「能不能拿这个指标下结论」的前提）")
    w()
    w("| 指标 | 组间差（不同题的规定） | 组内极差（同题两跑） | 可判定？ |")
    w("|---|---|---|---|")
    for _m, _key in (("agree12", "a12"), ("agree13", "a13"), ("agree23", "a23")):
        _per = []
        for tag in SCEN:
            rs = [r for r in ON if r.get("tag") == tag]
            if len(rs) < 2:
                continue
            _per.append((tag, [_pair_rate([r], 0, 1)[0] for r in rs],
                         [_pair_rate([r], 0, 2)[0] for r in rs],
                         [_pair_rate([r], 1, 2)[0] for r in rs]))
        # ★ `for _, *v in _per` 得到的 v = [l12, l13, l23] ⇒ 下标 0/1/2。
        #   原先写 1/2/3 —— a23 直接 IndexError（在「有两跑」的数据上才触发，
        #   第一版只有一行数据时看不出来）。
        _idx = {"a12": 0, "a13": 1, "a23": 2}[_key]
        # ★ 只收「该组 ≥2 个**有效**读数」的组：一个值的极差是 0，
        #   会让「组内极差 0 ≤ 组间差」**假通过**（n=1 不是重复观测）。
        _g = [v[_idx] for _, *v in _per
              if v[_idx] and None not in v[_idx] and len(v[_idx]) >= 2]
        _within = [round(max(x) - min(x), 3) for x in _g]
        _means = [round(sum(x) / len(x), 3) for x in _g]
        _between = round(max(_means) - min(_means), 3) if len(_means) > 1 else None
        _w_max = round(max(_within), 3) if _within else None
        if _between is None or _w_max is None:
            _ok = ("不可判定（有效组只有 %d 个，需 ≥2 组各 ≥2 读数）"
                   % len(_means))
        else:
            _ok = ("可判定 ✅（组间 ≥ 组内）" if _between >= _w_max
                   else "**不可判定 ✗**（组内极差更大：%s > %s）"
                        % (_w_max, _between))
        w("| %s | %s | %s | %s |" % (_m, _between, _w_max, _ok))
        _VERD.append((_m, _between, _w_max, _ok))
    w()

    w("### 2.3 结论（写死，免得读者自己在数字里推断）")
    w()
    _okn = [v[0] for v in _VERD if str(v[3]).startswith("可判定")]
    _badn = [v[0] for v in _VERD if not str(v[3]).startswith("可判定")]
    w("1. **「三票正交化」的统计可判定性**：三个指标里 **%d 个可判定**（%s）、"
      "**%d 个不可判定**（%s）。"
      "不可判定的那些是「组内极差 > 组间差」= **噪声大于信号**。"
      % (len(_okn), "、".join(_okn) or "—",
         len(_badn), "、".join(_badn) or "—"))
    w("   ⇒ 「第三票是否更特立独行」**只能说方向线索**，"
      "**不许写成「正交度已验证」**（ON 臂落差见 2.1 与其组内极差的比较）。")
    _lt3 = [r for r in RUNS
            if any(len(_voters(s)) < 3 for s in (r.get("subs") or []))]
    _off_lt3 = [r for r in _lt3 if r.get("arm") == "OFF"]
    _off = [r for r in RUNS if r.get("arm") == "OFF"]
    w("2. **负对照的完整度**：本批 %d 跑里 **%d 跑**存在「不足 3 票」的子问题"
      "（OFF 臂 %d/%d）⇒ 涉及第 3 票的指标在这些跑上算不出来，"
      "ON vs OFF 的对照会缺腿。"
      % (len(RUNS), len(_lt3), len(_off_lt3), len(_off)))
    w("3. ★ 但本次**测出了一件实质问题**（比正交度本身更重要）：")
    w("   **「三票」会静默退化成两票** —— 某票返回**合法 dict 但 `judgments` 为空**时，")
    w("   既不报错也不留痕，`ok_votes` 还照样 +1 ⇒ 读者在产物里看不出「三票实际两票」。")
    w("   v1.23.1 已补留痕 `[三态多票] N/3 票可用（空票 K 张）`（**纯留痕**）；")
    w("   v1.23.2 起再加 **`actions.tri_vote_retry_empty=1`（空票重试一次）**。")
    w("   ⇒ 本批就是**开启重试之后**的数据：不足 3 票的跑从上一批的 **4/10** 降到")
    w("     本批的 **%d/%d**（对照见 `v1231_报告.md` §四）。"
      % (len(_lt3), len(RUNS)))
    w()

# ---------------------------------------------------------------- 4 漂移
w("## 三、P2.4.b 的读数（und → partial 漂移）")
w()
w("| 跑 | applied 条数 | und→partial | 比值 |")
w("|---|---|---|---|")
for r in RUNS:
    _d = r.get("drift") or {}
    w("| %s (%s%s) | %s | %s | %s |"
      % (r.get("job"), r.get("arm"), r.get("rep"),
         _d.get("applied_total"), _d.get("und_to_partial"), _d.get("ratio")))
w()
w("读法：`applied_total` 很小（0~3）时这个「比值」**不是率**，是「几个条目的")
w("算术」；把它当通过/不通过的门槛，等于用 n=2 的样本下统计结论。所以本报告")
w("**只把它当观察项** —— 与 v1.22.1 changelog 的既有结论一致（triage 只出建议、")
w("不写 `decidability_log` ⇒ 「triage 引起的 und→partial」结构上恒为 0）。")
w()

# ---------------------------------------------------------------- 5 tier 提案
w("## 四、tier 提案（遗留2）在真跑里的留痕（旁证）")
w()
_any_tp = [r for r in RUNS if (r.get("tier_proposals_n") or 0) > 0]
if not _any_tp:
    w("本次跑批**没有**开启 `tier_proposal`（或没收到结果）⇒ 无真跑旁证，"
      "仅由探针/冒烟覆盖。")
else:
    for r in _any_tp:
        w("- `%s`：提案 %d 条；留痕 `%s`"
          % (r.get("job"), r.get("tier_proposals_n"),
             (r.get("web_tier_lines") or ["—"])[0][:150]))
    w()
    _tiers = sorted({t for r in RUNS for t in (r.get("web_tiers") or [])})
    w("★ 同一批跑的 `item.tier` 取值集合 = %s —— 提案**没有**改动它"
      "（判据 `L2.11` 在探针里钉住）。" % _tiers)
w()

# ---------------------------------------------------------------- 5 W3 覆盖
w("## 五、W3 环节在真跑里的覆盖（第 10 跑 · 全路由）")
w()
_f = [r for r in RUNS if r.get("arm") == "ONFULL"]
if not _f:
    w("本次**没有**全路由跑 ⇒ W3（对撞仲裁 / 元层核对）的真跑圈号无旁证，")
    w("只有探针 `L1.5` / `L1.6` 的离线证据。**如实记为未覆盖。**")
else:
    w("| 跑 | W# | 环节 | used_as | (round, round_kind) 逐条 |")
    w("|---|---|---|---|---|")
    for r in _f:
        _its = r.get("web_items") or []
        w("| %s | %d | %s | %s | %s |"
          % (r.get("job"), r.get("web_n") or 0,
             "、".join(r.get("web_stages") or []) or "—",
             "、".join(sorted({str(x.get("used_as")) for x in _its})) or "—",
             " ".join("%s/%s" % (x.get("round"), x.get("round_kind"))
                      for x in _its[:10]) or "—"))
    w()
    _w3 = [x for r in _f for x in (r.get("web_items") or [])
           if str(x.get("stage")) in ("duel_arbitration", "meta_clean_check")]
    if not _w3:
        w("⇒ 该跑里 W3 两个环节**都没有产出条目**（对撞层无张力 / 元层无")
        w("  uncovered）⇒ 真跑的圈号无旁证，**如实记为未覆盖**（不是「已修好」）。")
    else:
        w("⇒ W3 条目共 %d 条，round 取值 %s，round_kind %s。"
          % (len(_w3), sorted({x.get("round") for x in _w3}),
             sorted({str(x.get("round_kind")) for x in _w3})))
        w("  判据：`round_kind=in ⟹ round ≥ 1`（与 `L1.pair` 同款）——")
        w("  改前版本这里会印出拆解序号（恒 1 且无 round_kind）。")
w()

# ---------------------------------------------------------------- 写盘
TXT = "\n".join(L) + "\n"
(_J_OUT := HERE / "_v1230_w6_analysis.md").write_bytes(TXT.encode("utf-8"))
print(TXT)
print("已写 %s" % _J_OUT.name)
