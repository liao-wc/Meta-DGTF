# -*- coding: utf-8 -*-
"""[v1.23.3] 实验脚本第二轮修正（遗留1 的关键改动）。

三件事：
  ① **换掉结构性恒 0 的指标**：原 `flip`（第三票改变多数结论）在 3 票制下
     **恒为 0** —— 两人一致时第三人永远改不了多数。留着它就是自欺
     （本项目老规矩：「只升不降 / 恒不触发」的指标要能识别出来）。
     换成两个**真正有语义**的功能读出：
       · `dissent_rate`：1、2 票一致时，第 3 票**唱反调**的比例
         （= 它是不是橡皮图章）；
       · `final_change`：同一条子问题在 W4 开/关两臂下的**最终判决**变化率。
  ② **加证据反事实臂** `on_swap_t0`：同样 W4 开，但外部材料**换成相反的**
     ⇒ 如果第三票随证据变，说明「外部材料**真的**在驱动第三票」——
     这比一致率更能证明 W4 的设计目的。
  ③ `gap` 的定义写清楚（max(a13,a23) − a12），并明确它**不是**「独立度」。
"""
from pathlib import Path
import ast

P = Path("_ab_tri_votes_v1233.py")
s = P.read_text(encoding="utf-8")


def rep1(old, new, tag):
    global s
    assert s.count(old) == 1, "%s：命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new)
    print("  · %s" % tag)


# ---------------- ① 反事实证据 + 五臂
rep1('''ARMS = (
    ("w4_off_t0", False, 0.0),
    ("w4_on_t0", True, 0.0),
    ("w4_off_t7", False, 0.7),
    ("w4_on_t7", True, 0.7),
)''',
     '''# ★ 证据**反事实**：与 EVIDENCE 相反的外部材料。若第三票随它变，
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
     "claim": "没有可用于参照的改造案例综述。",
]

ARMS = (
    ("w4_off_t0", False, 0.0, "none"),
    ("w4_on_t0", True, 0.0, "std"),
    ("w4_off_t7", False, 0.7, "none"),
    ("w4_on_t7", True, 0.7, "std"),
    ("on_swap_t0", True, 0.0, "swap"),
)''', "① 反事实证据 + 五臂")

rep1('''def _sys_list(m, w4: bool):
    """三票的 system 列表：W4 开时把第 3 票换成「外部证据裁判」。"""
    out = list(m._TRI_VOTE_PROMPTS)
    if w4:
        out[2] = m._TRI_VOTE_PROMPTS[2] + m._web_digest_block(EVIDENCE)''',
     '''def _sys_list(m, w4: bool, ev_kind: str = "std"):
    """三票的 system 列表：W4 开时把第 3 票换成「外部证据裁判」。"""
    out = list(m._TRI_VOTE_PROMPTS)
    if w4:
        _ev = EVIDENCE_SWAP if ev_kind == "swap" else EVIDENCE
        out[2] = m._TRI_VOTE_PROMPTS[2] + m._web_digest_block(_ev)''',
     "② _sys_list 收 ev_kind")

rep1('''    for name, w4, temp in ARMS:
        sys_list = _sys_list(m, w4)''',
     '''    for name, w4, temp, ev_kind in ARMS:
        sys_list = _sys_list(m, w4, ev_kind)''', "③ 主循环解包")

rep1('''        raw[name] = {"w4": w4, "temp": temp, "reps": reps_out}''',
     '''        raw[name] = {"w4": w4, "temp": temp, "evidence": ev_kind,
                     "reps": reps_out}''', "④ raw 记 evidence")

# ---------------- metric 循环的元组解包
s = s.replace("""    for name, _w4, _t in ARMS:
        report["arms"][name] = raw[name]""",
              """    for name, _w4, _t, _e in ARMS:
        report["arms"][name] = raw[name]""")
s = s.replace("""    for name, _w4, _t in ARMS:
        seq = {}""", """    for name, _w4, _t, _e in ARMS:
        seq = {}""")
s = s.replace("""    for name, _w4, _t in ARMS:
        cell = per[name]""", """    for name, _w4, _t, _e in ARMS:
        cell = per[name]""")
s = s.replace("""    for name, _w4, _t in ARMS:
        cnt = {"1起": 0""", """    for name, _w4, _t, _e in ARMS:
        cnt = {"1起": 0""")

# ---------------- ⑤ 替换 flip 段：dissent / final_change / swap
_i = s.index("        # 第三票是否**改变多数结论**（W4 开臂）")
_j = s.index("        report[\"flip\"][temp_tag] = {\"changed\": chg, \"total\": tot,")
_j = s.index("\n", _j) + 1
NEWBLOCK = '''    # ------------------------------------------------------------ 功能读出
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

    # ★ 证据反事实：第三票随证据变的比例（同 (sub, rep)）
    rep["_"] = None
'''
s = s[: _i] + NEWBLOCK + s[_j:]

# 反事实臂的比较（放在 main 结尾、写盘之前）
rep1('''    OUTJ.write_bytes(json.dumps(report, ensure_ascii=False, indent=2,
                                default=str).encode("utf-8"))''',
     '''    # ---- 证据反事实：on_swap_t0 vs w4_on_t0（第 3 票逐条比）----
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
                                default=str).encode("utf-8"))''',
     "⑤ 反事实臂比较")

# ---------------- md 写入器：替换"四"节
rep1('''    w()
    w("## 四、第三票是否**改变结论**（W4 开臂）")
    w()
    w("| 温度 | 改变多数结论的条数 / 可算条数 | 比例 |")
    w("|---|---|---|")
    for tag in ("t0", "t7"):
        d = rep["flip"].get(tag) or {}
        w("| %s | %s / %s | %s |" % (tag, d.get("changed"), d.get("total"),
                                     d.get("rate")))
    w()''',
     '''    w()
    w("## 四、第三票的**功能读出**（这才是「正交」该量的东西）")
    w()
    w("★ 原指标「第三票改变多数结论」在 3 票制下**恒为 0**（1、2 票一致时")
    w("  第三人永远改不了多数）—— 已换成下面两个真正有语义的量。")
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
    w()''', "⑥ md 第四节改写")

# 报告字典里删掉 flip 键（避免 KeyError 误用）
s = s.replace('"icc": {}, "pair": {}, "flip": {},\n              "id_base": {}}',
              '"icc": {}, "pair": {}, "func": {}, "final_change": {},\n'
              '              "swap": {}, "id_base": {}}')

P.write_text(s, encoding="utf-8")
ast.parse(s)
print("实验脚本第二轮修正完成")
