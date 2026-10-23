def check_v12347_gain_suggest():
    """[v1.23.47 · P-2b] 早停阈值 α 由 AutoTune **跨跑建议**（只建议，不执行）。

    ★ SOTA：`static thresholds` 是学习回路的失败模式 ⇒ α 该跟着历史跑调。
    ★ 判据：① 无截断证据 ⇒ **不建议**（None，不表态）；② 截断多且**质量不差** ⇒ 建议抬高 α；
      ③ 截断多但**质量差** ⇒ α 保持（不乱抬，防学坏）；④ `learn` 段带出该建议；
      ⑤ 红线：**只建议**（不写配置）。
    """
    bad = []
    S = mod.autotune_suggest_gain_floor
    # ① 无证据 ⇒ 不表态
    r0 = S([])
    if r0.get("ok") is not False or r0.get("suggested") is not None:
        bad.append("[P2b] 无证据竟给建议：%r" % (r0,))
    r0b = S([{"cut_layers": ["0"], "duty": {}}])   # 有截断但无质量读数
    if r0b.get("suggested") is not None:
        bad.append("[P2b] 无质量读数竟给建议：%r" % (r0b,))
    # ② 截断多 + 质量好 ⇒ 抬高
    _good = [{"cut_layers": ["0"], "duty": {"S": 0.6}},
             {"cut_layers": ["both"], "duty": {"S": 0.7}},
             {"cut_layers": ["1"], "duty": {"S": 0.5}}]
    r1 = S(_good, base=0.0, step=0.01)
    if r1.get("suggested") != 0.01:
        bad.append("[P2b] 质量不差竟不抬高：%r" % (r1,))
    # ③ 截断多但质量差 ⇒ 保持
    _bad = [{"cut_layers": ["0"], "duty": {"S": 0.05}},
            {"cut_layers": ["both"], "duty": {"S": 0.01}}]
    r2 = S(_bad, base=0.0, step=0.01)
    if r2.get("suggested") != 0.0:
        bad.append("[P2b] 质量差竟仍抬高（会学坏）：%r" % (r2,))
    # ④ learn 段带出建议
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if '"suggested_gain_floor": _sgf.get("suggested"),' not in src:
        bad.append("[P2b] `autotune_phase_learn` 没带出 suggested_gain_floor")
    if "def autotune_suggest_gain_floor(" not in src:
        bad.append("[P2b] 缺 autotune_suggest_gain_floor")
    # ⑤ 只建议（不写配置）—— 函数体里不得出现配置写入
    try:
        _f = src.split("def autotune_suggest_gain_floor(")[1].split("\ndef ")[0]
        for _t in ("config[", "setdefault(", "apply_to_cfg"):
            if _t in _f:
                bad.append("[P2b] 建议函数里出现配置写入 `%s`（红线：建议≠执行）" % _t)
    except Exception:
        pass

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.47 P2b 阈值跨跑建议（无可证据=不表态 · 质量不差⇒抬高 · 质量差⇒保持 · "
          "learn 带出 · 只建议不写配置）全过")
    return True
