def check_v12348_eml_semantic():
    """[v1.23.48 · P-3b] EML **commit 前语义近重合并**（防冗余堆积）。

    ★ 实测：只按精确 `(kind,cond,action)` 去重 ⇒ 值差一点就另开一条 ⇒ 冗余堆积
      （SOTA 点名的 failure mode：noisy accumulation / redundancy）。
    ★ 判据：① 精确键 **仍去重**（零行为差）；② 默认 False ⇒ 值差 ⇒ **仍两条**；
      ③ True ⇒ 粗键命中 ⇒ **并成一条**（证据累加）；④ **负对照**：`action.key`
      不同 ⇒ **不并**（语义不同不能混）；⑤ 配置键 + 接线在源码。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("semantic_merge: bool = False) -> dict:",
                'semantic_merge=_smerge)',
                '"eml_semantic_merge": False,'):
        if tok not in src:
            bad.append("[P3b] 源码缺：%s" % tok)

    M = mod.eml_merge_candidate

    def _cand(delta, key="rounds_delta", issue="cut", ev="r1"):
        return {"kind": "schedule", "cond": {"issue": issue, "layer": "0"},
                "action": {"key": key, "layer": "0", "delta": delta},
                "evidence": [ev], "why": "x"}

    # ③ True ⇒ 值差也并（粗键命中）
    pb = [M([], _cand(1), 1000.0)]           # 第一条（delta=1）
    assert len(pb) == 1
    _e = M(pb, _cand(2, ev="r2"), 1001.0, semantic_merge=True)   # delta=2，粗键同
    if len(pb) != 1:
        bad.append("[P3b] semantic_merge=True 竟新开了一条（冗余没合）：len=%d" % len(pb))
    if int(_e.get("n_evidence") or 0) < 2:
        bad.append("[P3b] 合并后证据没累加：n=%r" % (_e.get("n_evidence"),))
    # ② 默认 False ⇒ 值差 ⇒ 仍两条（零行为差）
    pb2 = [M([], _cand(1), 1000.0)]
    M(pb2, _cand(2, ev="r2"), 1001.0)        # 不传 semantic_merge
    if len(pb2) != 2:
        bad.append("[P3b] 默认（False）竟合了（零行为差被破）：len=%d" % len(pb2))
    # ① 精确键仍去重（两版都必须）
    for _sm in (False, True):
        pb3 = [M([], _cand(1), 1000.0)]
        M(pb3, _cand(1, ev="r2"), 1001.0, semantic_merge=_sm)
        if len(pb3) != 1:
            bad.append("[P3b] 精确同键竟然新开（sm=%s）：len=%d" % (_sm, len(pb3)))
    # ④ 负对照：action.key 不同 ⇒ 不并
    pb4 = [M([], _cand(1), 1000.0)]
    M(pb4, _cand(1, key="duty_floor", ev="r2"), 1001.0, semantic_merge=True)
    if len(pb4) != 2:
        bad.append("[P3b-负对照] action.key 不同竟被并（语义不同不能混）：len=%d" % len(pb4))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.48 P3b EML 语义近重合并（精确仍去重 · 默认值差=两条 · True 并成一条 · "
          "action.key 不同不并）全过")
    return True
