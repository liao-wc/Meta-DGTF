# -*- coding: utf-8 -*-
"""[v1.23.3] 受控投票实验：补「组间 ≥ 组内」的**标准统计实现**（F 检验）
+ `--reuse`（跳过已采集的臂，只重算指标与 md，不重复花钱）。

为什么补 F 检验：
  「组间 ≥ 组内」在实验设计里的标准含义是 **MS_组间 ≥ MS_组内**（ANOVA），
  等价于配对 t 的 **|Δ| ≥ SE = σ/√n**，即 F = t² ≥ 1。
  原实现的 `|Δ| ≥ σ_个体` 是另一个更苛刻的读法 —— 对二值指标
  （d ∈ {−1,0,+1}）几乎不可能成立；它量的是**效应异质性**而非噪声。
  两个读法**都报**，并写明主判据是哪个、为什么。
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


rep1('''            report["pair"][temp_tag] = {
                "mean_w4_minus_off": round(mean, 3), "sd_within": round(sd, 3),
                "ratio": (None if ratio == float("inf") else round(ratio, 2)),
                "verdict_B": vb, "n": n,
                "ci": [round(bm[int(0.025 * len(bm))], 3),
                       round(bm[int(0.975 * len(bm)) - 1], 3)]}''',
     '''            # ★ 标准口径（与 ANOVA 一致）：组间 ≥ 组内 ⇔ MS_b ≥ MS_w
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
                       round(bm[int(0.975 * len(bm)) - 1], 3)]}''',
     "① pair 加 SE/t/F")

rep1('''    w("| 温度 | Δ（W4开−关） | σ_组内 | |Δ|/σ | 95% 区间 | 判定 |")
    w("|---|---|---|---|---|---|")
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag)
        if not d:
            w("| %s | — | — | — | — | — |" % tag)
            continue
        w("| %s | %s | %s | %s | %s | %s |"
          % (tag, d["mean_w4_minus_off"], d["sd_within"],
             d.get("ratio", "∞"), d["ci"], d["verdict_B"]))
    w()''',
     '''    w("同一份配对数据有**两个读法**，两个都报 —— 哪个是主判据写在这里：")
    w()
    w("| 读法 | 口径 | Δ | 结果 | 主判据? |")
    w("|---|---|---|---|---|")
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag) or {}
        if not d:
            w("| — | — | — | — | — |")
            continue
        w("| **F 检验**（标准 / ANOVA 一致） | 组间 ≥ 组内 ⇔ MS_b ≥ MS_w "
          "⇔ F = t² ≥ 1 ⟺ \\\\|Δ\\\\| ≥ SE = σ/√n | %s | F = %s，t = %s ⇒ %s | "
          "✅ 主判据 |"
          % (d["mean_w4_minus_off"], d.get("F"), d.get("t"),
             d.get("verdict_F")))
    for tag in ("t0", "t7"):
        d = rep["pair"].get(tag) or {}
        if not d:
            continue
        w("| 个体级 σ（更苛刻的读法） | \\\\|Δ\\\\| ≥ σ_组内 | %s | \\\\|Δ\\\\|/σ = %s "
          "⇒ %s | ✗ 不作主判据 |"
          % (d["mean_w4_minus_off"], d.get("ratio", "∞"), d["verdict_B"]))
    w()
    w("★ **为什么 F 检验是主判据**：「组间 ≥ 组内」在实验设计里的标准含义就是")
    w("  MS_组间 ≥ MS_组内（ANOVA），等价于配对 t 的 \\\\|Δ\\\\| ≥ SE。")
    w("  而「\\\\|Δ\\\\| ≥ σ_个体」是另一个更苛刻的读法 —— 对**二值**指标")
    w("  （每条子问题的差 d ∈ {−1, 0, +1}）几乎不可能成立；它量的其实是")
    w("  **效应异质性**（效应是否在每条子问题上同号同幅），不是噪声。")
    w("  两个都列出，避免「换个口径把它做绿」的嫌疑。")
    w()''', "② md 三·B 改写")

rep1('''    w("| 臂 | 1、2 票一致的条数 | 第 3 票唱反调 | 唱反调率 |")''',
     '''    w("**唱反调率 = 1、2 票一致时第 3 票唱反调的比例**（0 = 橡皮图章）。")
    w()
    w("| 臂 | 1、2 票一致的条数 | 第 3 票唱反调 | 唱反调率 |")''',
     "③ md 功能读出加说明")

rep1('''    raw: dict = {}
    t0 = time.time()
    for name, w4, temp, ev_kind in ARMS:
        sys_list = _sys_list(m, w4, ev_kind)''',
     '''    raw: dict = {}
    t0 = time.time()
    if "--reuse" in sys.argv and OUTJ.is_file():
        # ★ 只重算指标 / 重写 md，**不重跑 LLM**（默认口径改了之后用这个，
        #   避免把同一批样本再采一遍 —— 那会变成「换个口径+换批样本」，
        #   两处同时变，读数不可比）。
        raw = (json.loads(OUTJ.read_text(encoding="utf-8")).get("arms") or {})
        print("[votes] --reuse：复用已存 %d 臂（跳过采集）" % len(raw),
              flush=True)
    for name, w4, temp, ev_kind in ARMS:
        if name in raw:
            continue
        sys_list = _sys_list(m, w4, ev_kind)''', "④ --reuse")

P.write_text(s, encoding="utf-8")
ast.parse(s)
print("实验脚本已加 F 检验 + --reuse")
