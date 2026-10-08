# -*- coding: utf-8 -*-
"""[v1.23.3] 补丁：把投票实验的指标段重写成「缺票记 None」+ 加 id 基准统计

为什么必须重写指标段：
  · 原式 `int(0 in vs and 2 in vs and vs[0]==vs[2])` 在**缺 2 号票**时给出 0
    ⇒ 把「弃权」读成「分歧」。这是**非读数被当成测量值**（本项目老坑）。
  · 判据只出了一个口径；任务书写的是「组间 ≥ 组内」，字面对应
    「臂间差 Δ ≥ 组内噪声 σ」⇒ 必须显式算出来。
"""
from pathlib import Path
import ast

P = Path("_ab_tri_votes_v1233.py")
s = P.read_text(encoding="utf-8")

I = "    # ---------------------------------------------------------- 指标"
J = "    OUTJ.write_bytes("
assert s.count(I) == 1 and s.count(J) == 1
i, j = s.index(I), s.index(J)

NEW = '''    # ---------------------------------------------------------- 指标
    report = {"src": SRC.name, "reps": REPS, "n_subs": len(SUBS),
              "arms": {}, "metrics": {}, "icc": {}, "pair": {}, "flip": {},
              "id_base": {}}
    for name, _w4, _t in ARMS:
        report["arms"][name] = raw[name]

    # ★ 缺票一律记 None。把「这票没投」当成「不一致」是**非读数被当成测量值**
    #   （本项目反复踩的老坑）：原式在缺 2 号票时给出 0，把弃权读成了分歧
    #   —— 整张一致率表都会偏。
    per = {}
    for name, _w4, _t in ARMS:
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

    for name, _w4, _t in ARMS:
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
    for name, _w4, _t in ARMS:
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
            report["pair"][temp_tag] = {
                "mean_w4_minus_off": round(mean, 3), "sd_within": round(sd, 3),
                "ratio": (None if ratio == float("inf") else round(ratio, 2)),
                "verdict_B": vb, "n": n,
                "ci": [round(bm[int(0.025 * len(bm))], 3),
                       round(bm[int(0.975 * len(bm)) - 1], 3)]}
        # 第三票是否**改变多数结论**（W4 开臂）
        tot = chg = 0
        for rr in raw[b]["reps"]:
            votes = {int(k): {int(x): y for x, y in vv.items()}
                     for k, vv in rr["votes"].items()}
            for i in range(1, len(SUBS) + 1):
                vs = votes.get(i) or {}
                if len(vs) < 3:
                    continue
                tot += 1
                base = {vs[0]: sum(1 for k3 in (0, 1) if vs[k3] == vs[0])}
                if vs[1] != vs[0]:
                    base[vs[1]] = 1
                b_top = max(base.values())
                b_win = [k2 for k2, c in base.items() if c == b_top]
                allv = {lb: base.get(lb, 0) + (1 if vs[2] == lb else 0)
                        for lb in set(base) | {vs[2]}}
                a_top = max(allv.values())
                a_win = [k2 for k2, c in allv.items() if c == a_top]
                if (len(b_win) == 1 and b_top >= 2
                        and (len(a_win) != 1 or a_win[0] != b_win[0])):
                    chg += 1
        report["flip"][temp_tag] = {"changed": chg, "total": tot,
                                    "rate": round(chg / tot, 3) if tot else None}

'''
s = s[:i] + NEW + s[j:]

# 报告段：补 id 基准表 + 判据 B 行
O = '''    w()
    w("## 四、第三票是否**改变结论**（W4 开臂）")'''
N = '''    w()
    w("## 三·B 字面口径「组间 ≥ 组内」")
    w()
    w("组间 = 臂间配对差 Δ（同子问题配对，消掉子问题难度）；"
      "组内 = 配对后残差的 σ。")
    w("判据：**|Δ| ≥ σ** ⇒ 信号盖过噪声。")
    w()
    w("| 温度 | Δ（W4开−关） | σ_组内 | |Δ|/σ | 95% 区间 | 判定 |")
    w("|---|---|---|---|---|---|")
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag)
        if not d:
            w("| %s | — | — | — | — | — |" % tag)
            continue
        w("| %s | %s | %s | %s | %s | %s |"
          % (tag, d["mean_w4_minus_off"], d["sd_within"],
             d.get("ratio", "∞"), d["ci"], d["verdict_B"]))
    w()
    w("## 三·C 票的 id 基准（★ 0 起 = 整票错位一格，且引擎侧**无声**）")
    w()
    w("引擎按 **1 起** 对齐（`enumerate(subs, 1)`）。若某票返回 **0 起**，")
    w("它的票会**整票错位一格**：第 2 条子问题拿到本该给第 1 条的标签 ——")
    w("既不错也不留痕，读者从产物上完全看不出来。")
    w()
    w("| 臂 | 1 起 | **0 起** | 越界/其他 | 空票 | 非对象 |")
    w("|---|---|---|---|---|---|")
    for name, _w4, _t in ARMS:
        d = rep["id_base"][name]
        w("| %s | %d | **%d** | %d | %d | %d |"
          % (name, d["1起"], d["0起"], d["越界/其他"], d["空票"], d["非对象"]))
    w()
    w("## 四、第三票是否**改变结论**（W4 开臂）")'''
assert s.count(O) == 1
s = s.replace(O, N)

P.write_text(s, encoding="utf-8")
ast.parse(s)
print("指标段重写 + 判据B/id基准表已加")
