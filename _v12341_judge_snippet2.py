def check_v12341_excavate_dir():
    """[v1.23.41 · P2] `excavate` 方向**口径统一**（文档/声明 + 显示）。

    ★ 矛盾：模块声明说「每条读数越大越接近目标」、docstring 说「读数 = 1 − 边际新增」，
      而实现 + 判据⑫ 都是「小=好（边际新增率）」。
    ★ 判据：三处口径必须一致为「小=好」，且产物显示要**消歧**（防误读成「一分没挖」）。
    """
    import io as _io
    import contextlib as _ctx
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    # ① 声明不再一刀切「每条读数越大越接近目标」
    if "每条读数都是「**越大越接近该层目标**」" in src:
        bad.append("[P2] 模块声明仍一刀切「每条越大越接近」（excavate 方向相反）")
    if "距离型" not in src:
        bad.append("[P2] 声明未把 excavate 标成距离型（越小越接近挖尽）")
    # ② docstring 不再写与实现相反的「读数 = 1 − 边际新增」
    if "故本读数 = **1 − 归一化边际新增**" in src:
        bad.append("[P2] docstring 仍写「读数 = 1 − 边际新增」（与实现相反）")

    # ③ 行为：excavate 取值仍 = 边际新增率（busy > done，与判据⑫同向，防「改文档顺手
    #   把值也翻向」）
    _b = (mod.layer_goal_readings(
        {"0": {"aspect_units": [{"id": str(i)} for i in range(9)],
               "rounds_run": 4, "aspect_hist": [2, 4, 6, 9]}}).get("0") or {}
    ).get("excavate")
    _d = (mod.layer_goal_readings(
        {"0": {"aspect_units": [{"id": str(i)} for i in range(6)],
               "rounds_run": 4, "aspect_hist": [2, 4, 5, 6]}}).get("0") or {}
    ).get("excavate")
    if not (_b is not None and _d is not None and _b > _d):
        bad.append("[P2] excavate 值方向被改了（还在挖应 > 已挖尽）：%r vs %r"
                   % (_b, _d))

    # ④ 显示消歧：真驱动 `_finalize_layer_common` ⇒ 修行层 goal_verdict 带方向提示
    try:
        cfg = build_cfg(False)
        m = mod.MetaDGTF(cfg)
        v = mod.View(entry="0")
        v.aspect_units = [{"id": "A%d" % i} for i in range(9)]
        v.rounds_run = 3
        v.aspect_hist = [2, 4, 6, 9]
        v.stop_reason = "体力耗尽（3 圈走满）"
        stt = {"roles_hist": ["x"], "total_rounds": 3, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 3, "rounds_n": 3, "sp": mod._spiral_for(cfg, "0")}
        with _ctx.redirect_stdout(_io.StringIO()):
            m._finalize_layer_common("0", v, stt)
        gv = str(getattr(v, "goal_verdict", "") or "")
        if "excavate=" not in gv:
            bad.append("[P2] 修行层 goal_verdict 缺 excavate：%r" % gv)
        elif not ("趋零" in gv or "边际新增率" in gv):
            bad.append("[P2] excavate 显示未给方向提示（易误读成「没挖」）：%r" % gv)
    except Exception as e:  # noqa: BLE001
        bad.append("[P2] 驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.41 P2 excavate 口径统一（声明/docstring 标距离型 · 取值仍=边际新增率 · "
          "产物显示带「趋零即挖尽」提示）全过")
    return True
