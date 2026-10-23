#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.24 判据侧补丁：smoke_test.py + _v122_verify.py。

★ 单一行表操作；CRLF 往返；替换前断言命中次数。
★ 新判据 `check_v12324_indep_therapy` 的**判别力由变异体证明**
  （见 `_mut_v12324.py`，7 个变异体必须全部判红）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
VERIFY = HERE / "_v122_verify.py"


def _read_lines(p):
    raw = p.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "%s 不是纯 CRLF" % p.name
    assert raw.count(b"\r\r\n") == 0, "%s 含 CRCRLF" % p.name
    return raw.decode("utf-8").replace("\r\n", "\n").split("\n")


def _write_lines(p, lines):
    out = "\n".join(lines).replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0, "%s 产出含 CRCRLF" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 产出不是纯 CRLF" % p.name
    assert out.count(b"\r") == out.count(b"\r\n"), "%s 产出有游离 CR" % p.name
    p.write_bytes(out)
    assert p.read_bytes() == out, "%s 回读不一致" % p.name


# ====================================================================
# 新判据本体
# ====================================================================
NEW_CHECK = '''def check_v12324_indep_therapy():
    """[v1.23.24] ① 不可判定「独立度」口径（取代误名的结构覆盖率）
       ② 修行层停止判据与文案（去 ing / 补空括号 / 一律附体检）。

    ★ 每条判据都带负对照；判别力另由 `_mut_v12324.py` 的 7 个变异体证明
      （没有变异体的「全绿」只说明判据没跑）。
    ★ 独立度夹具的判别力：旧口径 = 1/3 = 0.333，新口径 = 2/4 = 0.500
      —— 两者不同值，否则这条样例在两种实现下同结论、等于没测。
    """
    import contextlib as _cl
    import inspect as _ins
    import io as _io
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    cfg = build_cfg(False)

    # ================= A. 独立度口径 =================
    _asp = ["本体论地位需要先确定登记位置", "自指结构导致时刻错开",
            "判决实验缺少可操作标准"]
    _amps = ["本体论地位需要先确定登记位置",
             "任何判定都要求对象在登记前已有边界，本体论地位因此没有登记位置",
             "与上述各项均无关的一条独立结构观察结论",
             "关于尺度效应的一条独立观察，与判定标准无关"]
    _p = mod.Pool()
    _p.add_undecidable({"structural_amps": list(_amps), "aligned_amps": [],
                        "clarity": 0.6}, list(_asp), layer=1)
    _ch = _p.undecidable_channel

    if _ch.get("last_indep_pool") != 4 or _ch.get("last_indep_free") != 2:
        bad.append(f"[A] 独立度计数错：pool={_ch.get('last_indep_pool')} "
                   f"free={_ch.get('last_indep_free')}（应 4 / 2）")
    if abs(float(_ch.get("last_indep_ratio") or -1) - 0.5) > 1e-9:
        bad.append(f"[A] 独立度不是 2/4=0.5：{_ch.get('last_indep_ratio')}")
    if list(_ch.get("indep_history") or []) != [0.5]:
        bad.append(f"[A] indep_history 不对：{_ch.get('indep_history')}")
    # ★ 不变式：旧键一个数不许动（历史语料的口径 + 命中轨迹的输入）
    if _ch.get("last_struct_coverage") != 0.3333333333333333:
        bad.append(f"[A] 旧键 last_struct_coverage 被动了："
                   f"{_ch.get('last_struct_coverage')}（应 1/3）")
    # 空池：必须 None（不可计算），不许 0.0（假读数）
    _pe = mod.Pool()
    _pe.add_undecidable({"structural_amps": [], "aligned_amps": [],
                         "clarity": 0.5}, list(_asp), layer=1)
    if _pe.undecidable_channel.get("last_indep_ratio") is not None:
        bad.append(f"[A] 空池的独立度不是 None："
                   f"{_pe.undecidable_channel.get('last_indep_ratio')}")

    # 产物渲染：新口径 + 口径标注；新口径 dict 里不许再出现「结构覆盖率」
    _mg = mod.MetaDGTF(cfg)
    _mg.pools["1"].undecidable_channel = _ch
    _line = _mg._und_channel_line()
    if "独立度 0.50" not in _line:
        bad.append(f"[A] 产物没渲染独立度：{_line!r}")
    if "2/4" not in _line:
        bad.append(f"[A] 独立度的分子分母没渲染：{_line!r}")
    if "不是覆盖率" not in _line:
        bad.append(f"[A] 口径标注（不是覆盖率）缺了：{_line!r}")
    if "结构覆盖率" in _line:
        bad.append(f"[A] 新口径 dict 还在印「结构覆盖率」：{_line!r}")
    # 负对照：历史 packed（只有旧键）必须仍渲染得出来，且显式标「旧口径」
    _m3 = mod.MetaDGTF(cfg)
    # ★ 这是**真实历史 packed** 的形态：v1.23.23 的 add_undecidable 会写
    #   last_struct_coverage。smoke 里 v69 那份手工 dict 裁掉了这个键，
    #   照抄它去测 `_pool_shape`（那里的门正是这个键）会得到「空」——
    #   那是夹具不像历史，不是实现丢了东西。
    _m3.pools["1"].undecidable_channel = {
        "clarity_history": [0.5], "struct_coverage_history": [0.6],
        "und_aspects": [f"面{i}" for i in range(10)],
        "last_struct_hit": 6, "last_struct_coverage": 0.6,
        "structural_amps": ["a"], "aligned_amps": [],
    }
    _l3 = _m3._und_channel_line()
    if "结构覆盖率 0.60" not in _l3 or "旧口径" not in _l3:
        bad.append(f"[A-负对照] 历史 packed 的旧口径读数丢了：{_l3!r}")

    # 喂模型的 shape（★ 运行期可见变化：新口径进、旧口径作回退）
    def _shape(_pl):
        _dg = mod.DGTF("1", mod.LLM(cfg), cfg)
        _dg.verbose = False
        with _cl.redirect_stdout(_io.StringIO()):
            return _dg._pool_shape(_pl, "P")

    _s_new = _shape(_p)
    if "不可判定独立度 0.50" not in _s_new:
        bad.append(f"[A] shape 没喂独立度：{_s_new!r}")
    _s_leg = _shape(_m3.pools["1"])
    if "不可判定结构覆盖 0.60" not in _s_leg:
        bad.append(f"[A-负对照] legacy 池的 shape 旧口径丢了：{_s_leg!r}")

    # 源码接线：两处调用点 + 两处 sat 块
    if src.count("stall_is_sat=_stall_is_sat") != 2:
        bad.append("stall_is_sat 没接到两条通道上（%d 处）"
                   % src.count("stall_is_sat=_stall_is_sat"))
    if src.count(
            "_stall_is_sat = bool(sat_verdict is False and not stalled)") != 2:
        bad.append("两处 sat 块没都算 _stall_is_sat")
    if "stall_is_sat" not in _ins.signature(
            mod.MetaDGTF._stop_reasons).parameters:
        bad.append("_stop_reasons 没有 stall_is_sat 形参")

    # ================= B. 修行层停止判据/文案 =================
    _mr = mod.MetaDGTF(cfg)
    _sp = dict(mod.DEFAULT_CONFIG["spiral"])

    def _rs(**kw):
        base = dict(entry="0", layer_no=3, rounds_n=3, total_rounds=3,
                    sp=_sp, soft_max=3, sim_thr=0.8, stable_need=2,
                    idle_limit=2, r_idle_limit=2, r_stall_limit=2,
                    rephrase_streak=0, carry_streak=0, idle_new_amp=0,
                    idle_new_thread=0, idle_stall=0, stall_why="",
                    sat_override=False, prev_product="",
                    view=mod.View(entry="0"), idles=0)
        base.update(kw)
        with _cl.redirect_stdout(_io.StringIO()):
            _r, _ = _mr._stop_reasons(**base)
        return " | ".join(str(x) for x in _r)

    # B1 空括号：sat 顶计数那一支
    _sat = _rs(idle_stall=2, stall_is_sat=True)
    if "（）" in _sat:
        bad.append(f"[B] sat 支路仍印空括号：{_sat!r}")
    if "结构饱和度判定" not in _sat:
        bad.append(f"[B] sat 支路没有自己的说法：{_sat!r}")
    # 负对照：真 stall 那一支必须照旧带 stall_why
    _real = _rs(idle_stall=2, stall_why="修行层无新增或无推进")
    if "修行层无新增或无推进" not in _real or "（）" in _real:
        bad.append(f"[B-负对照] 真 stall 支路的措辞被改坏了：{_real!r}")
    # 反向：元层 sat_override 那条（条件 2）仍要能印「结构饱和度判定」
    _ov = _rs(entry="all", idle_new_amp=2, sat_override=True,
              view=mod.View(entry="all"))
    if "结构饱和度判定" not in _ov:
        bad.append(f"[B] 元层 sat_override 的说法没了：{_ov!r}")

    # B2 条件 1 文案按层取词：不借「ing」
    for _e, _lab in (("0", "修行层"), ("1", "研究层"),
                     ("both", "对撞层"), ("all", "元层")):
        _t = _rs(entry=_e, rephrase_streak=2, view=mod.View(entry=_e))
        if f"{_lab}连续 2 圈复述" not in _t:
            bad.append(f"[B] {_e} 层条件 1 文案不是「{_lab}…」：{_t!r}")
        if "ing" in _t:
            bad.append(f"[B] {_e} 层停因里还有「ing」：{_t!r}")
    if "圈复述" in _rs(rephrase_streak=0):
        bad.append("[B-负对照] 没复述却给了复述理由")

    # B3 修行层任何停止都附体检；非修行层不附（负对照）
    def _fin(entry, why):
        _v = mod.View(entry=entry)
        _v.stop_reason = why
        _st = {"roles_hist": ["摊开"], "total_rounds": 4, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 4, "rounds_n": 4, "sp": mod._spiral_for(cfg, entry)}
        with _cl.redirect_stdout(_io.StringIO()):
            mod.MetaDGTF(cfg)._finalize_layer_common(entry, _v, _st)
        return _v.stop_reason or ""

    for _why in ("连续 2 轮有新增但无推进（修行层无新增或无推进），螺旋停止",
                 "体力耗尽（4 圈走满，未触发任何停止判据，是被截断不是自然停止）"):
        _o = _fin("0", _why)
        if "未生质量" not in _o or "本轮显形" not in _o:
            bad.append(f"[B] 修行层停因没附体检（{_why[:12]}…）：{_o!r}")
    if "未生质量" in _fin("1", "研究层双通道均收敛，螺旋停止"):
        bad.append("[B-负对照] 非修行层也被附了体检")

    # B4 源码层面：旧红线句已不在、新句在、显式清单在
    if "修行层不追求收敛" in src:
        bad.append("[B] 源码里还有「修行层不追求收敛」这句旧红线")
    if "修行层本来就能停" not in src:
        bad.append("[B] 源码里缺新红线注释")
    if "适用停止条件清单" not in src:
        bad.append("[B] _stop_reasons 的显式适用条件清单缺了")

    if bad:
        for _x in bad:
            print("  \\u2717 [v12324] %s" % _x)
        return False
    print("  \\u2713 [v12324] 独立度口径（旧键不动 / 空池 None / legacy 回退 / "
          "shape 已换）；修行层停因去 ing、无空括号、一律附体检；两通道接线齐")
    return True
'''


def patch_smoke():
    lines = _read_lines(SMOKE)

    def repl_block(old, new, what, expect=1):
        o, n = old.split("\n"), new.split("\n")
        hits = [i for i in range(len(lines) - len(o) + 1)
                if lines[i:i + len(o)] == o]
        assert len(hits) == expect, "%s：命中 %d（要求 %d）" % (
            what, len(hits), expect)
        for i in reversed(hits):
            lines[i:i + len(o)] = n

    def repl_line(old, new, what, expect=1):
        hits = [i for i, ln in enumerate(lines) if old in ln]
        assert len(hits) == expect, "%s：行命中 %d（要求 %d）" % (
            what, len(hits), expect)
        for i in hits:
            lines[i] = lines[i].replace(old, new)

    repl_line('SRC = HERE / "元DGTF-V1.23.23.py"',
              'SRC = HERE / "元DGTF-V1.23.24.py"', "SRC 指向本版")

    # ---- v69 的 B 段（覆盖率 → 独立度）----
    repl_block(
        '      B 走**生产入口** `Pool.add_undecidable` —— 两个覆盖率必须同时落下来，\n'
        '        且旧键 `last_struct_coverage` 的值一个数不许变（它喂模型）。',
        '      B 走**生产入口** `Pool.add_undecidable` —— 独立度与对齐覆盖率必须\n'
        '        同时落下来；旧键 `last_struct_coverage`（旧口径命中比例）\n'
        '        一个数不许变（它喂模型，也是历史语料的口径）。',
        "v69 B 段 docstring")

    repl_block(
        '    if _ch.get("last_aligned_hit") != 1:\n'
        '        bad.append(f"[B] last_aligned_hit 应为 1，实得 "\n'
        '                   f"{_ch.get(\'last_aligned_hit\')}")',
        '    if _ch.get("last_aligned_hit") != 1:\n'
        '        bad.append(f"[B] last_aligned_hit 应为 1，实得 "\n'
        '                   f"{_ch.get(\'last_aligned_hit\')}")\n'
        '    if _ch.get("last_indep_ratio") != 1.0 \\\n'
        '            or _ch.get("last_indep_pool") != 1:\n'
        '        bad.append(f"[B] 独立度没落下来：ratio="\n'
        '                   f"{_ch.get(\'last_indep_ratio\')} "\n'
        '                   f"pool={_ch.get(\'last_indep_pool\')}（应 1.0 / 1）")',
        "v69 B 段独立度落点")

    repl_block(
        '    if "结构覆盖率 0.00" not in _line:\n'
        '        bad.append(f"[B] 结构覆盖率（旧口径）没渲染：{_line!r}")',
        '    if "独立度 1.00" not in _line or "不是覆盖率" not in _line:\n'
        '        bad.append(f"[B] 独立度（新口径）没渲染或没标口径：{_line!r}")',
        "v69 B 段渲染断言")

    # ---- v1.23.17 覆盖率判据：说清它现在走的是 legacy 分支 ----
    repl_line('    # ---- [v1.21.57] 不可判定通道也要双口径（清晰度 + 结构覆盖率）----',
              '    # ---- [v1.21.57 / v1.23.24] 不可判定通道的读数（清晰度 + 结构读数）----\n'
              '    #   ★ 这里喂的是**只有旧键**的 dict ⇒ 走 v1.23.24 的 legacy 分支，\n'
              '    #     渲染成「结构覆盖率 …（旧口径…）」，证明历史 packed 重渲染不丢信息。',
              "v12317 覆盖率注释")
    repl_line("[覆盖率] 不可判定通道的结构覆盖率（代码实算）没显示：",
              "[覆盖率] 不可判定通道的旧口径结构读数（legacy dict）没显示：",
              "v12317 失败信息 1")
    repl_line("    # 只有不可判定时（fallback）也要给结构覆盖率，不能只剩清晰度",
              "    # 只有不可判定时（fallback）也要给结构读数，不能只剩清晰度",
              "v12317 fallback 注释")
    repl_line("[覆盖率] 只有不可判定通道时（fallback）没给结构覆盖率：",
              "[覆盖率] 只有不可判定通道时（fallback）没给结构读数：",
              "v12317 失败信息 2")

    # ---- v1.22 阶段1：红线断言换新句 ----
    repl_line('        assert "修行层不追求收敛" in src, "缺红线注释"',
              '        assert "修行层本来就能停" in src, "缺红线注释"',
              "v122 阶段1 红线断言")

    # ---- 插入新判据（放在 main() 之前）+ 注册 ----
    anchor = "def main():"
    hits = [i for i, ln in enumerate(lines) if ln == anchor]
    assert len(hits) == 1, "def main(): 命中 %d" % len(hits)
    lines[hits[0]:hits[0]] = NEW_CHECK.split("\n")

    repl_block(
        '    if not check_v12323_view_echo_full():\n'
        '        return 1',
        '    if not check_v12323_view_echo_full():\n'
        '        return 1\n'
        '    if not check_v12324_indep_therapy():\n'
        '        return 1',
        "main() 注册新判据")

    _write_lines(SMOKE, lines)
    print("OK smoke_test.py：SRC / v69 B 段 / v12317 legacy 说明 / 红线断言 / "
          "新判据 check_v12324_indep_therapy + 注册")


def patch_verify():
    lines = _read_lines(VERIFY)
    hits = [i for i, ln in enumerate(lines)
            if '"未生质量" in _s and "修行层不追求收敛" in _s' in ln]
    assert len(hits) == 1, "_v122_verify 红线断言命中 %d" % len(hits)
    lines[hits[0]] = lines[hits[0]].replace(
        '"未生质量" in _s and "修行层不追求收敛" in _s',
        '"未生质量" in _s and "修行层本来就能停" in _s')
    nxt = hits[0] + 1
    assert '"源码含 未生质量 / 修行层不追求收敛"' in lines[nxt], lines[nxt]
    lines[nxt] = lines[nxt].replace("修行层不追求收敛", "修行层本来就能停")
    _write_lines(VERIFY, lines)
    print("OK _v122_verify.py：1.5.6 红线锚点换新句")


def main():
    patch_smoke()
    patch_verify()


if __name__ == "__main__":
    main()
