# -*- coding: utf-8 -*-
"""mx batch02 分析：判定环节思考开关（ON vs OFF）。

主判据（预注册 mx_design_batch02.md）：
  - 成本 tokens：组间差 > 组内极差 才断言「开思考更贵」
  - 质量 覆盖率段：组间差 > 组内极差 才断言「开思考更好/更差」
  - 结论规则：更贵 + 覆盖率无增益 → 过度配置，回退低频

覆盖率段 = 日志尾部「覆盖率段：0.xx」，是可判定覆盖率（X/Y 口径）。
注意它是判定环节自评产出，只比组间差、不比绝对值。
"""
import re
import glob
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def parse(tag):
    m = re.match(r"mx2_(on|off)_(eu|ip|tls)_(\d)", tag)
    return m.groups() if m else None


def log_fields(tag):
    lg = sorted(HERE.glob(f"v60_{tag}_*.log"))
    if not lg:
        return None
    txt = lg[0].read_text(encoding="utf-8", errors="replace")
    out = {}
    for key, pat in (
            ("calls", r"llm_calls=(\d+)"),
            ("tokens", r"tokens=(\d+)"),
            ("cov", r"覆盖率段：([0-9.]+)"),
            ("decidability", r"decidability=(\w+)"),
            ("分叉", r"分叉=(\w+)\("),
            ("served", r"served_by=(\[[^\]]*\])")):
        m = re.search(pat, txt, re.M)
        if m:
            v = m.group(1).strip()
            out[key] = (float(v) if key == "cov"
                        else int(v) if key in ("calls", "tokens")
                        else v)
    return out or None


def load():
    rows = []
    for lg in sorted(HERE.glob("v60_mx2_*.log")):
        tag = lg.name.split("_r")[0].replace("v60_", "")
        g = parse(tag)
        if not g:
            print(f"  ⚠️ tag 解析不了：{tag}")
            continue
        arm, qk, rep = g
        f = log_fields(tag)
        if not f:
            print(f"  ⚠️ {tag} 日志字段缺失")
            continue
        rows.append({"tag": tag, "arm": arm, "qkey": qk, "rep": rep, **f})
    return rows


def compare(rows, metric, label):
    on = [r[metric] for r in rows if r["arm"] == "on"
          and metric in r and r[metric] is not None]
    off = [r[metric] for r in rows if r["arm"] == "off"
           and metric in r and r[metric] is not None]
    if not on or not off:
        print(f"  {label}: 数据不足 on={len(on)} off={len(off)}")
        return
    mo, mf = statistics.median(on), statistics.median(off)
    pct = (mf - mo) / mo * 100 if mo else float('nan')
    ro, rf = max(on) - min(on), max(off) - min(off)
    print(f"\n-- {label} --")
    print(f"  ON  n={len(on)} 中位={mo:.4g}  组内极差 {ro:.4g}")
    print(f"  OFF n={len(off)} 中位={mf:.4g}  组内极差 {rf:.4g}")
    print(f"  组间差 {pct:+.1f}%（ON→OFF 变化）")
    if metric == "tokens" or metric == "calls":
        if abs(mf - mo) > max(ro, rf):
            print(f"  → 组间差 > 组内极差：{'开思考更贵' if mo > mf else '关思考更贵'}")
        else:
            print(f"  → 组间差 ≤ 组内极差：**不可判定**（成本差异不足以断言）")
    else:
        if abs(mf - mo) > max(ro, rf):
            print(f"  → 组间差 > 组内极差："
                  f"{'开思考覆盖率更高' if mo > mf else '关思考覆盖率更高'}")
        else:
            print(f"  → 组间差 ≤ 组内极差：**不可判定**（覆盖率差异不足以断言）")


def main():
    rows = load()
    print(f"=== mx batch02：判定环节思考开关对照 ===")
    print(f"载入 {len(rows)} 跑：ON {sum(1 for r in rows if r['arm']=='on')} / "
          f"OFF {sum(1 for r in rows if r['arm']=='off')}")
    if len(rows) < 10:
        print("⚠️ 数据不足，先确认跑批是否完成")
        return

    print("\n=== 明细 ===")
    print(f"{'tag':<22}{'calls':>7}{'tokens':>11}{'覆盖率段':>10}")
    for r in sorted(rows, key=lambda x: (x['arm'], x['qkey'], x['rep'])):
        print(f"{r['tag']:<22}{r.get('calls',0):>7}{r.get('tokens',0):>11}"
              f"{r.get('cov', float('nan')):>10.2f}")

    compare(rows, "tokens", "成本 tokens")
    compare(rows, "calls", "成本 llm_calls")
    compare(rows, "cov", "质量 覆盖率段")

    # 结论规则（预注册）：组间差必须 > 组内极差才许断言
    print("\n=== 结论（按预注册规则：组间差必须 > 组内极差）===")
    on_t = [r['tokens'] for r in rows if r['arm'] == 'on']
    off_t = [r['tokens'] for r in rows if r['arm'] == 'off']
    on_c = [r['cov'] for r in rows if r['arm'] == 'on']
    off_c = [r['cov'] for r in rows if r['arm'] == 'off']
    to, tf = statistics.median(on_t), statistics.median(off_t)
    co, cf = statistics.median(on_c), statistics.median(off_c)
    dcost = to - tf
    dqual = co - cf
    range_t = max(max(on_t) - min(on_t), max(off_t) - min(off_t))
    range_q = max(max(on_c) - min(on_c), max(off_c) - min(off_c))
    cost_sig = abs(dcost) > range_t
    qual_sig = abs(dqual) > range_q
    print(f"  tokens：ON 贵 {dcost/1e5:.1f}万，组内极差 {range_t/1e5:.1f}万"
          f" → {'**显著更贵**' if cost_sig else '不可判定'}")
    print(f"  覆盖率：ON 高 {dqual:+.2f}，组内极差 {range_q:.2f}"
          f" → {'**显著不同**' if qual_sig else '不可判定'}")
    if not cost_sig and not qual_sig:
        print("\n→ **功效不足**：三个指标组间差都 ≤ 组内极差，不能下结论。\n"
              "  方向仅是趋势（ON 覆盖率 +0.04、tokens +20%），都不够格。\n"
              "  按预注册，下一步是加大样本，不许反写成『开思考无用』或『有价值』。")
    elif cost_sig and not qual_sig:
        print("\n→ 开思考**更贵但覆盖率无增益** → 过度配置，建议回退低频。")
    elif qual_sig and cost_sig:
        print("\n→ 覆盖率显著不同且成本显著不同 → 看性价比。")
    elif qual_sig and not cost_sig:
        print("\n→ 覆盖率显著提升且不更贵 → 白赚，保留。")


if __name__ == "__main__":
    main()
