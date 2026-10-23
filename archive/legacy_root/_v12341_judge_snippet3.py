def check_v12341_attribution():
    """[v1.23.41 · P3+P4] 停因**归因补全**（只加不删，不改停止决策）。

    · P3：无判据截断 ⇒ 附**末圈近阈读数**（否则「未触发任何停止判据」不可判远近）。
    · P4：自省未消化 ⇒ 附**未消化点名**（否则「同一批问题」不知是哪批）。
    """
    import io as _io
    import contextlib as _ctx
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "近阈读数" not in src:
        bad.append("[P3] 缺「近阈读数」归因")
    if "未消化点名" not in src:
        bad.append("[P4] 缺「未消化点名」归因")

    def _fin(entry, view_attrs, state_extra):
        cfg = build_cfg(False)
        m = mod.MetaDGTF(cfg)
        v = mod.View(entry=entry)
        for k, val in (view_attrs or {}).items():
            setattr(v, k, val)
        stt = {"roles_hist": ["x"], "total_rounds": 3, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 3, "rounds_n": 3, "sp": mod._spiral_for(cfg, entry)}
        stt.update(state_extra or {})
        with _ctx.redirect_stdout(_io.StringIO()):
            m._finalize_layer_common(entry, v, stt)
        return v

    # ① P3：无停因（被截断）⇒ 消息含「未触发任何停止判据」+「近阈读数」
    try:
        v3 = _fin("1", {}, {"round_log": [
            {"round": 3, "new_amps": 0, "new_threads": 0,
             "idle_amp": 1, "idle_thread": 0, "idle_stall": 1}]})
        s3 = str(v3.stop_reason or "")
        if "未触发任何停止判据" not in s3:
            bad.append("[P3] 截断消息丢了「未触发任何停止判据」：%r" % s3)
        if "近阈读数" not in s3:
            bad.append("[P3] 截断消息没附近阈读数：%r" % s3)
    except Exception as e:  # noqa: BLE001
        bad.append("[P3] 驱动抛错：%r" % (e,))

    # ② P4：自省未消化停因 ⇒ 消息附「未消化点名」
    try:
        v4 = _fin("1", {
            "stop_reason": "自省连续 2 圈点名同一批问题未消化（层内空转）",
            "carry": [{"target": "未消化的甲"}, {"target": "未消化的乙"}],
            "carry_check": {}}, {})
        s4 = str(v4.stop_reason or "")
        if "未消化点名" not in s4:
            bad.append("[P4] 自省未消化停因没附未消化点名：%r" % s4)
        if "未消化的甲" not in s4:
            bad.append("[P4] 未消化点名没带出具体条目：%r" % s4)
    except Exception as e:  # noqa: BLE001
        bad.append("[P4] 驱动抛错：%r" % (e,))

    # ③ 负对照：普通停因不该被附「未消化点名」
    try:
        v5 = _fin("1", {"stop_reason": "研究层双通道均收敛，螺旋停止",
                        "carry": [{"target": "甲"}]}, {})
        if "未消化点名" in str(v5.stop_reason or ""):
            bad.append("[P4-负对照] 普通停因也被附了未消化点名：%r"
                       % v5.stop_reason)
    except Exception as e:  # noqa: BLE001
        bad.append("[P4] 负对照驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.41 P3+P4 停因归因（截断附近阈读数 · 自省未消化附点名 · "
          "普通停因不误加）全过")
    return True
