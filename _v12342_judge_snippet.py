def check_v12342_ctx_shape():
    """[v1.23.42 · P-1] `View.shape_of` 窗口化（上下文裁剪，默认不限）。

    ★ 根因：`shape_of` 无窗口渲染整个 view，而它每圈当 `views_text` 重灌 ⇒
      后段圈单次 prompt 随圈数上涨（真跑最贵 25–32k tok/次）。
    ★ 判据：① `limit=0` 逐字**零行为差**（渲染全部）；② `limit>0` 变短 + 表头标总数；
      ③ 接线（配置 → `_expand_from_views` → `shape_of(limit=)`）在源码里。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    # ③ 接线
    if "View.shape_of(v, limit=_shape_lim)" not in src:
        bad.append("[P1] 缺接线：`_expand_from_views` 未把 limit 传进 shape_of")
    if '"shape_limit": 0,' not in src:
        bad.append("[P1] 缺配置键 `spiral.shape_limit`（默认 0）")
    if "def shape_of(v: \"View\", limit: int = 0) -> str:" not in src:
        bad.append("[P1] `shape_of` 签名没带 `limit` 形参")

    # 造一个「每类都超 8 条」的 view
    v = mod.View(entry="0")
    v.anchor = "锚点问题"
    v.candidates = [{"desc": "候选%d：一条较长的候选描述" % i} for i in range(48)]
    v.amps = [{"type": "ontological", "desc": "& %d 说明" % i} for i in range(15)]
    v.threads = [{"desc": "线头 %d" % i} for i in range(12)]
    v.suspensions = [{"target": "悬置 %d" % i, "reason": "理由",
                      "status": "active"} for i in range(9)]

    full = mod.View.shape_of(v)             # limit=0
    win = mod.View.shape_of(v, limit=8)     # 窗口

    # ① limit=0 渲染全部（零行为差：48 条候选全在）
    if not all(("候选%d：" % i) in full for i in range(48)):
        bad.append("[P1] limit=0 竟没渲染全部候选（零行为差被破）")
    if "只列最近" in full:
        bad.append("[P1] limit=0 竟出现窗口表头（零行为差被破）")
    # ② limit>0：变短 + 计数表头 + 只留最近 8
    if not (len(win) < len(full)):
        bad.append("[P1] limit=8 没变短：%d vs %d" % (len(win), len(full)))
    if "共 48，只列最近 8" not in win:
        bad.append("[P1] limit=8 缺计数表头「共 48，只列最近 8」")
    if "候选47：" not in win:                # 最后一条在
        bad.append("[P1] limit=8 丢了最后一条候选")
    if "候选0：" in win:                     # 最早的在窗口外
        bad.append("[P1] limit=8 仍渲染了最早的候选（窗口没生效）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.42 P1 shape_of 窗口化（limit=0 逐字零行为差 · limit>0 变短+计数表头 · "
          "接线在源码里）全过")
    return True
