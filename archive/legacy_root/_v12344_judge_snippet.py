def check_v12344_eml_adaptive():
    """[v1.23.44 · P-3] 学习闭环：EML 阈值**冷启自适应**（修「升级/遗忘恒 0」）。

    ★ 实测：playbook 3 条 shadow 卡在 `n_evidence=1 < _EML_PROMOTE_N(3)` ⇒ 永不升级。
    ★ 判据：① 默认（adaptive=False）⇒ **逐字不变**（n=1 仍不升）；
      ② adaptive=True 且库小 ⇒ 冷启门槛降到 1，n=1 **可升**；
      ③ **负对照**：库大（≥ _EML_COLD_LIB）⇒ adaptive 也**不降**门槛；
      ④ **负对照**：质量闸不被绕过（`quality_delta<0` 仍不升）；
      ⑤ 遗忘侧：默认 `_rr == retire_recency`（零行为差）；⑥ 配置键 + 接线在源码。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("_EML_COLD_LIB = 20",
                "adaptive: bool = False) -> list:",
                '"eml_adaptive": False,',
                "adaptive=_ad"):
        if tok not in src:
            bad.append("[P3] 源码缺：%s" % tok)

    def _pb(n_shadow=1, n_ev=1, qd=0.1, contra=0, total=None):
        rows = [{"id": "s%d" % i, "status": "shadow", "n_evidence": n_ev,
                 "quality_delta": qd, "cost_delta": -0.1, "contra": contra,
                 "kind": "schedule"}
                for i in range(n_shadow)]
        rows.append({"id": "a0", "status": "active", "n_evidence": 5,
                     "quality_delta": 0.2, "cost_delta": -0.1, "contra": 0,
                     "kind": "probe"})
        if total and total > len(rows):
            rows += [{"id": "f%d" % i, "status": "active", "n_evidence": 9,
                      "quality_delta": 0.1, "cost_delta": -0.1, "contra": 0,
                      "kind": "probe"} for i in range(total - len(rows))]
        return rows

    P = mod.eml_promote
    # ① 默认 ⇒ 逐字不变（n=1 < 3，不升）
    _c0 = P(_pb(), promote_n=3, adaptive=False)
    if any(c.get("to") == "active" for c in _c0):
        bad.append("[P3] 默认 adaptive=False 竟升级了（零行为差被破）")
    # ② adaptive + 小库 ⇒ 冷启降到 1，n=1 可升
    _c1 = P(_pb(), promote_n=3, adaptive=True)
    if not any(c.get("to") == "active" for c in _c1):
        bad.append("[P3] adaptive+小库 没升级（冷启自适应失效）：%r" % (_c1,))
    # ③ 负对照：库大 ⇒ 不降门槛
    _c2 = P(_pb(total=40), promote_n=3, adaptive=True)
    if any(c.get("to") == "active" for c in _c2):
        bad.append("[P3-负对照] 库大时 adaptive 仍降门槛（不该）：%r" % (_c2,))
    # ④ 负对照：质量闸不被绕过
    _c3 = P(_pb(qd=-0.5), promote_n=3, adaptive=True)
    if any(c.get("to") == "active" for c in _c3):
        bad.append("[P3-负对照] 质量下降竟被升（学坏）")
    # ⑤ 遗忘默认零行为差：新鲜条目不被退休
    _now = 1_700_000_000.0
    _fresh = [{"id": "x", "status": "shadow", "n_evidence": 1,
               "t_last": _now, "t_used": []}]
    if mod.eml_sweep_forget(_fresh, _now, adaptive=False):
        bad.append("[P3] 默认就把新鲜条目退休了（零行为差被破）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.44 P3 EML 阈值冷启自适应（默认零行为差 · 小库降门槛 · 大库不降 · "
          "质量闸不被绕 · 遗忘默认不动）全过")
    return True
