def check_v12346_duty_span():
    """[v1.23.46 · P-5] 职责 S 口径对称化 —— 修 C(全文)/R(逐句) 的**长度不对称**。

    ★ 实测：真产物 `{S:0.0, C:0.25, R:0.0}` ⇒ S=0 是被 **R=0** 拖的。
      根因：C 用 `_hit(问项, 全文)`、R 用 `_hit(问项, 单句)`，而 `_hit` 的 gram
      覆盖率按**问项长度**归一 ⇒ 问项**跨句**时 C 记、R 不记。
    ★ 判据：① 默认（span_tolerant=False）⇒ **逐字不变**（R=0/S=0）；
      ② 夹具里 C>0（跨句问项在全文被命中）；③ True ⇒ R 上升（跨句窗口补上）；
      ④ 接线（`duty_of_layer` → `duty_components` 真转发）；⑤ 配置键在源码。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("span_tolerant: bool = False",
                '"span_tolerant": False,',
                "span_tolerant=_dspan)",
                "span_tolerant=span_tolerant)"):
        if tok not in src:
            bad.append("[P5] 源码缺：%s" % tok)

    # ★ 夹具必须让问项**真跨句**、且两句都 >=6 字（<6 的段会被过滤掉 —— 首版栽在这）
    _asp = [{"text": "甲乙丙丁戊己庚辛", "kind": "core", "weight": 1.0}]
    _d = "甲乙丙丁在甲地。戊己庚辛在乙地。"
    try:
        off = mod.duty_components(_asp, _d, span_tolerant=False)
        on = mod.duty_components(_asp, _d, span_tolerant=True)
    except TypeError as e:
        bad.append("[P5] duty_components 不吃 span_tolerant（没转发）：%r" % (e,))
        off = on = {}
    # ① 默认 ⇒ 零行为差
    if off and (off.get("R") != 0.0 or off.get("S") != 0.0):
        bad.append("[P5] 默认（False）竟然变了：R=%r S=%r"
                   % (off.get("R"), off.get("S")))
    # ② C 判全文 ⇒ 覆盖 > 0
    if off and float(off.get("C") or 0) <= 0:
        bad.append("[P5] 夹具 C 应为正（跨句问项在全文被命中）：%r" % (off.get("C"),))
    # ③ True ⇒ R 上升
    if off and on and float(on.get("R") or 0) <= float(off.get("R") or 0):
        bad.append("[P5] 跨句窗口没让 R 上升：off=%r on=%r"
                   % (off.get("R"), on.get("R")))
    # ④ 端到端：duty_of_layer 真转发
    try:
        _dl = mod.duty_of_layer("1", "甲乙丙丁戊己庚辛是什么？", _d,
                                span_tolerant=True)
        if float(_dl.get("R") or 0) <= 0:
            bad.append("[P5] duty_of_layer(span_tolerant=True) 的 R 仍 0（转发断了）：%r"
                       % (_dl.get("R"),))
    except Exception as e:  # noqa: BLE001
        bad.append("[P5] duty_of_layer 驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.46 P5 职责 S 口径对称化（默认零行为差 · C>0 而 R=0 复现 · "
          "跨句窗口让 R 上升 · 转发在源码）全过")
    return True
