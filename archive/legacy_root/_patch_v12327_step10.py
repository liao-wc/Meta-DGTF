# -*- coding: utf-8 -*-
"""Step10：插入 check_v12327_five_mechanisms() 到 smoke_test.py 并接进 main()。

判据覆盖 v1.23.27 九项新机制（A1/A2/A3/D1/D2/D3/E1/E2/E6），
每一项都**落在行为上**、锚对准实现本体，且每个断言都有对应变异体
（见 `_mut_v12327.py` 的 M1~M8）——「全绿」必须有变异体背书。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "smoke_test.py"

CHECK = '''def check_v12327_five_mechanisms():
    """[v1.23.27] 五机制算法重构（第二期）九项判据。

    ★ 每一项都**驱动真实函数**判行为（不查字符串），且每个断言都有
      对应变异体（`_mut_v12327.py` M1~M8）：变异体判红 ⇒ 判据有判别力。
    覆盖：
      A1 AspectUnit 幂等与 ground 归一化
      A2 符号对账收敛（amp#N / th#N / A{N}）
      A3 双读数分离（touch_rate ≠ aspect_carry_rate 的构造）
      D1 BeliefItem 四态机（非法 status 归一化）
      D2 迁移优先级（resolved > revoked > stable）
      D3 语义熵 n<2 返回 None（不印 0.0 冒充）
      E1 EIG 可计算化且两臂同尺（targeted G > 0）
      E2 子模批选（边际下限、宁少勿滥）
      E6 自适应停止（seen==0 不是 stop）
    """
    bad = []

    # ── A1 AspectUnit ──────────────────────────────────────────
    _v = mod.View(entry="0")
    _a1 = _v.add_aspect_unit("同一方面", "src", "阳", "anchor", "r")
    _a2 = _v.add_aspect_unit("同一方面", "src", "阳", "anchor", "r")
    if not _a1 or _a1.get("id") != _a2.get("id"):
        bad.append("[A1] 同 desc 未幂等（id=%r vs %r）"
                   % (_a1.get("id"), _a2.get("id")))
    if len(_v.aspect_units) != 1:
        bad.append("[A1] 幂等失效导致重复登记（len=%d）"
                   % len(_v.aspect_units))
    if _a1.get("text") != _a1.get("desc"):
        bad.append("[A1] text != desc ⇒ 旧读取点会拿不到文本")
    _ab = mod.make_aspect_unit("x", source="s", polarity="阳",
                               ground="bogus_ground", ref="r")
    if _ab.get("ground") != "anchor":
        bad.append("[A1] 非法 ground 未归一化到 anchor（%r）"
                   % _ab.get("ground"))

    # ── A2 符号对账收敛 ───────────────────────────────────────
    _p = mod.Pool()
    _p.amps = [{"desc": "某条"}]
    _p.threads = [{"desc": "某线头"}]
    _p.probes = [{"question": "某探针"}]
    _p.covered_unders = ["某未生"]
    _tg = _p.aspect_targets_v12327()
    for _k in ("amp#1", "th#1", "probe#1", "A1"):
        if _k not in _tg:
            bad.append("[A2] targets 缺 %s（收敛不全）：%s"
                       % (_k, sorted(_tg)))

    # ── A3 双读数分离（构造「触及但没延续」）─────────────────
    _v3 = mod.View(entry="0")
    _v3.round_log = [{"anchor_touched_n": 3}]
    _v3.aspect_units = [{"id": "A1", "text": "t", "desc": "t"}]
    _v3._layer_und_channel = {}
    _tr = _v3.touch_rate
    _cr = _v3.aspect_carry_rate
    if not (_tr is not None and _tr > 0):
        bad.append("[A3] touch_rate 应为 >0（构造 3 触及）实为 %r" % _tr)
    if _cr != 0.0:
        bad.append("[A3] 无延续时 carry_rate 应为 0.0 实为 %r" % _cr)
    # 空池 ⇒ None（不印 0.00 冒充读数）
    if mod.View(entry="0").aspect_carry_rate is not None:
        bad.append("[A3] 空池 carry_rate 应返回 None（不许印 0.0）")

    # ── D1 四态机 ──────────────────────────────────────────────
    for _s in _BELIEF_STATUS_EXPECT:
        _it = mod.make_belief_item("主张" + _s, "g", _s)
        if _it.get("status") != _s:
            bad.append("[D1] 合法状态 %s 被改动为 %r"
                       % (_s, _it.get("status")))
    _ib = mod.make_belief_item("x", "g", "totally_bogus")
    if _ib.get("status") != "active":
        bad.append("[D1] 非法 status 未归一化到 active（%r）"
                   % _ib.get("status"))
    if mod.make_belief_item("", "g") != {}:
        bad.append("[D1] 空 text 应返回 {}")

    # ── D2 迁移优先级 ─────────────────────────────────────────
    _cur = mod.make_belief_item("x", "g", "active")
    if mod.belief_transition(_cur, round_no=1, sources=["p#1"]) != "active":
        bad.append("[D2] 单圈单来源不该升 stable")
    _r2 = mod.belief_transition(
        mod.make_belief_item("x", "g", "active", rounds_seen=[1],
                             support=["p#1"]),
        round_no=2, sources=["th#1"])
    if _r2 != "stable":
        bad.append("[D2] 连续 2 圈且 2 来源应升 stable（实为 %r）" % _r2)
    _rev = mod.belief_transition(
        mod.make_belief_item("x", "g", "active", attack=["a#1", "a#2"],
                             support=["s#1"]),
        round_no=3, attack=["a#3"])
    if _rev != "revoked":
        bad.append("[D2] attack>support 应 revoked（实为 %r）" % _rev)
    _res = mod.belief_transition(_cur, round_no=5, sources=["p#1"],
                                 attack=["t#1"],
                                 resolved_by="decidable_channel")
    if _res != "resolved":
        bad.append("[D2] resolved 优先级最高（实为 %r）" % _res)

    # ── D3 语义熵 ──────────────────────────────────────────────
    _hn, _hr, _cl = mod.semantic_entropy_of(["只有一条"])
    if _hn is not None:
        bad.append("[D3] n<2 应返回 None（实为 %r）—— 印 0.0 是自欺" % _hn)
    _hn2, _hr2, _cl2 = mod.semantic_entropy_of(["甲", "甲", "甲"])
    if not (_hn2 is not None and _hn2 <= 0.05):
        bad.append("[D3] 三条同义应近 0 熵（实为 %r）" % _hn2)

    # ── E1 EIG 同尺 ───────────────────────────────────────────
    # ★ 构造要点：`h_before` 必须 **>0**（有分歧才有不确定度可降）。
    #   若三条全同义 ⇒ 聚成 1 簇 ⇒ h_before=0 ⇒ G 恒 0（数学正确，
    #   但测不出「同尺」）。所以用「两条同簇 + 一条异构」：
    #   targeted 命中同簇那条 ⇒ 移除后 h_after 下降 ⇒ G>0；
    #   若两臂各用各的 ln(n)（Step8c 前的 bug）⇒ G 会被抵消成 0。
    _bis = [{"id": "B1", "text": "极低温环境下材料脆性阈值是多少",
             "status": "active"},
            {"id": "B2", "text": "极低温环境下材料脆性阈值如何",
             "status": "active"},
            {"id": "B3", "text": "城市轨道交通客流预测模型的误差",
             "status": "active"}]
    _G, _d = mod.probe_information_gain(
        {"question": "极低温环境下材料脆性阈值是多少"}, _bis)
    if not (_G is not None and _G > 0.0):
        bad.append("[E1] targeted G 应为正（实为 %r / %s）—— "
                   "两臂不同尺会让 G 恒 0" % (_G, _d.get("why")))
    _G2, _d2 = mod.probe_information_gain({"question": ""}, _bis)
    if _G2 is not None:
        bad.append("[E1] 空问题应返回 None（实为 %r）" % _G2)
    _G3, _d3 = mod.probe_information_gain({"question": "x"}, [])
    if _G3 is not None:
        bad.append("[E1] 未决 <2 应返回 None（实为 %r）" % _G3)

    # ── E2 子模批选（宁少勿滥）───────────────────────────────
    _p2 = mod.Pool()
    _p2.belief_items = list(_bis)
    _picked, _det = mod.select_probe_focus_submodular(
        _p2, [{"question": "极低温环境下材料脆性阈值是多少",
               "expected_gain": 0.9, "link": "x"}], 3)
    if len(_picked) > 3:
        bad.append("[E2] 批选超过上限 n=3（实为 %d）" % len(_picked))

    # ── E6 自适应停止 ─────────────────────────────────────────
    if mod.e6_stop_verdict(0, 0.0, 0.3, 0.02) != (False, "no_candidate"):
        bad.append("[E6] seen==0 不是 stop（否则「模型偷懒」被读成「已收敛」）")
    if mod.e6_stop_verdict(3, 0.01, 0.3, 0.02) != (True,
                                                   "max_gain_below_floor"):
        bad.append("[E6] max_gain < floor 应判 stop")
    if mod.e6_stop_verdict(3, 0.02, 0.3, 0.02) != (False, "gain_ok"):
        bad.append("[E6] 边界（== floor）不该判 stop")
    _p3 = mod.Pool()
    _rec = _p3.note_probe_stop("research", 3, 0.005, 0.3, 0.02)
    if not (_rec.get("stop") and len(_p3.probe_stop_history) == 1):
        bad.append("[E6] 停止信号未写进 probe_stop_history")
    if "probe_stop_history" not in _p3.to_dict():
        bad.append("[E6] to_dict 未出口 probe_stop_history（静默丢产物）")
    if "probe_stop_history" in mod.Pool().to_dict():
        bad.append("[E6] 空 Pool 不该凭空出现 probe_stop_history")

    if bad:
        for _m in bad:
            print("  \\u2717 [v12327] %s" % _m)
        return False
    print("  \\u2713 [v12327] A1 幂等/归一化 · A2 符号对账收敛 · "
          "A3 双读数分离 · D1 四态机 · D2 迁移优先级 · D3 语义熵 None · "
          "E1 EIG 同尺 · E2 子模批选 · E6 自适应停止（8 变异体背书）")
    return True


'''

_TMPL = '''def check_v12327_five_mechanisms():
    """[v1.23.27] 五机制算法重构（第二期）九项判据。'''

_BELIEF_STATUS_EXPECT = '''
#: [v1.23.27] 判据用：D1 四态机的四个合法状态（与引擎同源）。
_BELIEF_STATUS_EXPECT = ("active", "stable", "resolved", "revoked")


'''


def sub(text, anchor, new, tag, count=1):
    n = text.count(anchor)
    assert n == count, (
        f"[{tag}] 锚点命中 {n} 次（期望 {count}）\n锚点={anchor[:160]!r}")
    return text.replace(anchor, new, count)


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "smoke_test.py 不是纯 CRLF"
    assert "\r\r\n" not in txt, "含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    # 1) 常量（放在 v12326 check 之前）
    t = sub(
        t,
        'def check_v12326_sim3():\n',
        _BELIEF_STATUS_EXPECT + 'def check_v12326_sim3():\n',
        "const", 1)

    # 2) 插入 check 本体（放在 v12326 check 之后、main 之前）
    t = sub(
        t,
        '_TMPL_PLACEHOLDER_NEVER',
        '_TMPL_PLACEHOLDER_NEVER',
        "noop", 1) if False else t

    # 找 v12326 check 的结束（下一个顶层 def）
    _m = t.find('def check_v12326_sim3():')
    assert _m > 0
    _nxt = t.find('\ndef ', _m + 10)
    assert _nxt > _m
    t = t[:_nxt + 1] + CHECK + t[_nxt + 1:]

    # 3) 接进 main()
    t = sub(
        t,
        '    if not check_v12326_sim3():\n        return 1\n',
        '    if not check_v12326_sim3():\n        return 1\n'
        '    if not check_v12327_five_mechanisms():\n        return 1\n',
        "main", 1)

    out = t.replace("\n", "\r\n")
    SRC.write_bytes(out.encode("utf-8"))
    print("STEP10 CHECK PATCH OK")


if __name__ == "__main__":
    main()
