def check_v12341_goal_fresh():
    """[v1.23.41 · P1] 目标读数**收尾刷新** —— 修 crystallize 时序颠倒（恒 0.500）。

    ★ 根因：`goal_verdict` 曾在 `_finalize_layer_common` **前段**从 `goal_now`
      渲染，而 `goal_now` 由**圈循环内**算（那时元层 `meta_closure` 还没落）
      ⇒ 元层恒少数「结晶 + 回看」两件 ⇒ `crystallize` 恒 2/4 = 0.500。
    ★ 判据（时序不变式）：真驱动 `_finalize_layer_common` ⇒ 产物里的
      `goal_verdict` 必须**等于最终 view 的读数**，而不是层停止那刻的旧值。
    """
    import io as _io
    import contextlib as _ctx
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    # ① 静态：标签唯一真相源 + 唯一写入点在收尾
    if "_LG_LABELS = {" not in src:
        bad.append("[P1] 缺 `_LG_LABELS`（goal_verdict 标签唯一真相源）")
    if src.count('{"0": "修行·挖尽", "1": "研究·收敛",') != 1:
        bad.append("[P1] 标签映射不是唯一一份（内联渲染没消掉）")
    if "目标读数收尾刷新] 本层的" not in src:
        bad.append("[P1] 缺收尾刷新（goal_verdict 唯一写入点应在收尾）")

    def _fin(entry, preset):
        cfg = build_cfg(False)
        m = mod.MetaDGTF(cfg)
        v = mod.View(entry=entry)
        for k, val in (preset or {}).items():
            setattr(v, k, val)
        stt = {"roles_hist": ["x"], "total_rounds": 2, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 2, "rounds_n": 2, "sp": mod._spiral_for(cfg, entry)}
        with _ctx.redirect_stdout(_io.StringIO()):
            m._finalize_layer_common(entry, v, stt)
        return v

    # ② 元层：四件事齐 ⇒ 最终读数应 > 旧的 0.5；产物必须等于最终读数
    try:
        v = _fin("all", {"meta_closure": {"clean": True, "total": 3,
                                          "unsettled": 0},
                         "engagements": [{"tension_id": "t1"}],
                         "suspensions": [{"id": "s1", "status": "active"}],
                         "rounds_run": 2, "stop_reason": "自省空转，螺旋停止",
                         "goal_now": {"crystallize": 0.5, "n_hits": 2}})
        _fresh = (mod.layer_goal_readings(
            {"all": v.to_dict()}).get("all") or {}).get("crystallize")
        _gv = str(getattr(v, "goal_verdict", "") or "")
        if _fresh is None:
            bad.append("[P1] 元层最终 crystallize 竟为 None")
        else:
            if ("crystallize=%.3f" % float(_fresh)) not in _gv:
                bad.append("[P1] 元层 goal_verdict 未随最终读数刷新："
                           "fresh=%r verdict=%r" % (_fresh, _gv))
            # 负对照：最终读数与旧值不同 ⇒ 产物里不许再是旧值 0.500
            if abs(float(_fresh) - 0.5) > 1e-9 and "crystallize=0.500" in _gv:
                bad.append("[P1] goal_verdict 仍是层停止那刻的旧值 0.500")
    except Exception as e:  # noqa: BLE001
        bad.append("[P1] 元层驱动抛错：%r" % (e,))

    # ③ 修行层：excavate 的 goal_verdict 也必须等于最终读数
    try:
        v0 = _fin("0", {"aspect_units": [{"id": "A%d" % i} for i in range(9)],
                        "rounds_run": 3, "aspect_hist": [2, 4, 6, 9],
                        "stop_reason": "体力耗尽（3 圈走满）",
                        "goal_now": {"excavate": None}})
        _e0 = (mod.layer_goal_readings(
            {"0": v0.to_dict()}).get("0") or {}).get("excavate")
        _gv0 = str(getattr(v0, "goal_verdict", "") or "")
        if _e0 is not None and ("excavate=%.3f" % float(_e0)) not in _gv0:
            bad.append("[P1] 修行层 goal_verdict 未刷新：e=%r v=%r"
                       % (_e0, _gv0))
    except Exception as e:  # noqa: BLE001
        bad.append("[P1] 修行层驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.41 P1 目标读数收尾刷新（产物 goal_verdict == 最终 view 读数，"
          "元层不再恒 0.500、修行层同步）全过")
    return True
