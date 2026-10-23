def check_v12343_gain_stop():
    """[v1.23.43 · P-2] 早停：单标量 `refinement_gain` + 配置式阈值 `stop.gain_floor`。

    ★ SOTA：最优停止 = **单一阶段无关阈值**（arXiv:2608.10729）。
    ★ 判据：① 增益**方向**统一（修行取「上一圈−本圈」，其余取「本圈−上一圈」）；
      ② 没上一圈 ⇒ None；③ `gain_floor=0`（默认）⇒ 不生效（零行为差）；
      ④ 饱和（连续增益趋零）⇒ 命中；⑤ 有进展 ⇒ **不**误停（负对照）；
      ⑥ 配置键 + 接线在源码里。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("def refinement_gain(entry: str",
                "def layer_gain_stop_signal(entry: str",
                '"gain_floor": 0.0,',
                "layer_gain_stop_signal(str(entry), _now, _tr, _gf)"):
        if tok not in src:
            bad.append("[P2] 源码缺：%s" % tok)

    G = mod.refinement_gain
    # ① 方向统一：都「越大越有进展」
    if G("0", {"excavate": 0.2}, [{"excavate": 0.5}]) != 0.3:
        bad.append("[P2] 修行增益方向错：%r"
                   % (G("0", {"excavate": 0.2}, [{"excavate": 0.5}]),))
    if G("1", {"settle": 0.8}, [{"settle": 0.5}]) != 0.3:
        bad.append("[P2] 研究增益方向错：%r"
                   % (G("1", {"settle": 0.8}, [{"settle": 0.5}]),))
    if G("both", {"fuse": 0.6}, [{"fuse": 0.2}]) != 0.4:
        bad.append("[P2] 对撞增益错：%r"
                   % (G("both", {"fuse": 0.6}, [{"fuse": 0.2}]),))
    # 停滞 ⇒ 0
    if G("1", {"settle": 0.5}, [{"settle": 0.5}]) != 0.0:
        bad.append("[P2] 停滞增益应为 0")
    # ② 没上一圈 ⇒ None
    if G("1", {"settle": 0.5}, []) is not None:
        bad.append("[P2] 无上一圈竟给值（应 None）")
    if G("1", {"settle": None}, [{"settle": 0.5}]) is not None:
        bad.append("[P2] 本圈无读数竟给值（应 None）")

    S = mod.layer_gain_stop_signal
    _flat = [{"settle": 0.5}, {"settle": 0.5}, {"settle": 0.5}]
    _rise = [{"settle": 0.2}, {"settle": 0.5}, {"settle": 0.8}]
    # ③ 默认 0 ⇒ 关（零行为差）
    if S("1", _flat[-1], _flat, 0.0) != (False, ""):
        bad.append("[P2] gain_floor=0 竟生效（零行为差被破）")
    if S("1", _flat[-1], _flat) != (False, ""):
        bad.append("[P2] 缺省参数竟生效")
    # ④ 饱和 ⇒ 命中
    _h, _w = S("1", _flat[-1], _flat, 0.01)
    if not (_h and "refinement_gain" in _w):
        bad.append("[P2] 饱和未命中：%r" % ((_h, _w),))
    # ⑤ 有进展 ⇒ 不误停（负对照）
    if S("1", _rise[-1], _rise, 0.01)[0] is not False:
        bad.append("[P2-负对照] 有进展却被判停")
    # 圈数不足 ⇒ 不表态
    if S("1", {"settle": 0.5}, [{"settle": 0.5}], 0.01)[0] is not False:
        bad.append("[P2] 圈数不足竟判停")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.43 P2 早停（单标量增益方向统一 · 无上一圈=None · 默认关零行为差 · "
          "饱和命中 · 有进展不误停）全过")
    return True
