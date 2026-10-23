#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.24 主文件补丁：① P1「独立度」口径切换 ② 修行层停止判据与文案重设计。

★ 一个补丁脚本只操作**一个行表**（`lines`）：全部编辑都在它上面做，
  最后 join 一次、转一次 CRLF、写一次盘。（v1.23.13 吃过「文本级与行级混用」
  导致前面所有替换被静默丢掉的亏。）
★ 替换前断言块命中次数 == 1。
★ 末尾自带**结构性自检**：真加载模块 + 真调 `_stop_reasons`，不是只 parse。
"""
import ast
import importlib.util
import inspect
import io
import contextlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.24.py"


def main():
    raw = TGT.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "不是纯 CRLF"
    assert raw.count(b"\r\r\n") == 0, "已含 CRCRLF"
    lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")

    edits = []

    def repl_block(old, new, what, expect=1):
        o = old.split("\n")
        n = new.split("\n")
        hits = [i for i in range(len(lines) - len(o) + 1)
                if lines[i:i + len(o)] == o]
        assert len(hits) == expect, "%s：块命中 %d 次（要求 %d）" % (
            what, len(hits), expect)
        for i in reversed(hits):
            lines[i:i + len(o)] = n
        edits.append(what)

    def repl_line(old_sub, new_sub, what, expect=1):
        hits = [i for i, ln in enumerate(lines) if old_sub in ln]
        assert len(hits) == expect, "%s：行命中 %d 次（要求 %d）" % (
            what, len(hits), expect)
        for i in hits:
            lines[i] = lines[i].replace(old_sub, new_sub)
        edits.append(what)

    # ================================================================
    # P1-1 · 口径来源：update_undecidable 的 channel 初始化加新键
    # ================================================================
    repl_block(
        '                "last_struct_coverage": 0.0,',
        '                "last_struct_coverage": 0.0,\n'
        '                "last_indep_ratio": None, "last_indep_pool": 0,\n'
        '                "last_indep_free": 0, "indep_history": [],',
        "P1-1 channel 初始化加独立度新键")

    # ================================================================
    # P1-2 · 独立度计算（加性：旧键一字不动）
    # ================================================================
    repl_block(
        '        def _append_trace(_pool, _hits, _trace_key, _first_key):',
        '        #  ★ 独立度（取代「结构覆盖率」这个名字）：提示词要求\n'
        '        #    structural_amps「独立提炼、不得直接复述 und_aspects 的原话」，\n'
        '        #    所以对它的读数该问「有多独立」，而不是「覆盖了几个方面」——\n'
        '        #    后者与提示词的方向**正好相反**（复述得越像，旧读数越高），\n'
        '        #    这就是它长期恒 0 而没人当回事的原因。\n'
        '        #    分母是 structural_amps 条数 ⇒ 越高越合规。\n'
        '        #  ★ 旧键（last_struct_coverage / struct_coverage_history /\n'
        '        #    last_struct_hit / struct_trace）**一字不动**：\n'
        '        #    它们是历史 packed 的口径，也是命中轨迹的输入。\n'
        '        _amps_pool = list(self.undecidable_channel["structural_amps"])\n'
        '        _free_amps = [sa for sa in _amps_pool\n'
        '                      if not any(_overlap_coef(asp, sa) >= 0.3\n'
        '                                 for asp in aspects)]\n'
        '        indep_ratio = (len(_free_amps) / len(_amps_pool)\n'
        '                       if _amps_pool else None)\n'
        '        self.undecidable_channel["last_indep_ratio"] = indep_ratio\n'
        '        self.undecidable_channel["last_indep_pool"] = len(_amps_pool)\n'
        '        self.undecidable_channel["last_indep_free"] = len(_free_amps)\n'
        '        self.undecidable_channel.setdefault("indep_history", []).append(\n'
        '            indep_ratio)\n'
        '\n'
        '        def _append_trace(_pool, _hits, _trace_key, _first_key):',
        "P1-2 独立度计算")

    # ================================================================
    # P1-3 · 产物渲染 _und_channel_line（新口径 + 历史 packed 旧口径回退）
    # ================================================================
    _old_und = '''    def _und_channel_line(self) -> str:
        """不可判定通道的一行（双口径）；无数据返回空串。

        两个口径：
          · 清晰度（模型自评）= undecidable_product.clarity，取最近一次。
          · 结构覆盖率（代码实算）= 评估阶段圈出的 und_aspects 里，
            有多少个被 structural_amps 命中（_overlap_coef >= 0.3）。
            [v1.21.57] 以前只在 _pool_shape 里喂给模型，产物里看不到。
        """
        ch = getattr(self.pools["1"], "undecidable_channel", None) or {}
        cl_hist = list(ch.get("clarity_history") or [])
        sc_hist = list(ch.get("struct_coverage_history") or [])
        ac_hist = list(ch.get("aligned_coverage_history") or [])
        if not cl_hist and not sc_hist and not ac_hist:
            return ""
        parts = []
        if cl_hist:
            parts.append(f"清晰度 {cl_hist[-1]:.2f}"
                         f"（模型自评，累计 {len(cl_hist)} 次记录）")
        if sc_hist:
            aspects = list(ch.get("und_aspects") or [])
            hit = int(ch.get("last_struct_hit", 0) or 0)
            _hard = (f"，已对上 {hit}/{len(aspects)} 个不可判定方面"
                     if aspects else "")
            parts.append(f"结构覆盖率 {sc_hist[-1]:.2f}"
                         f"（代码实算{_hard}）")
        if ac_hist:
            aspects = list(ch.get("und_aspects") or [])
            ahit = int(ch.get("last_aligned_hit", 0) or 0)
            _hard2 = (f"，已对上 {ahit}/{len(aspects)} 个不可判定方面"
                      if aspects else "")
            parts.append(f"对齐覆盖率 {ac_hist[-1]:.2f}"
                         f"（代码实算{_hard2}）")
        return "研究层不可判定通道：" + "｜".join(parts) + "\\n"'''

    _new_und = '''    def _und_channel_line(self) -> str:
        """不可判定通道的一行；无数据返回空串。

        口径：
          · 清晰度（模型自评）= undecidable_product.clarity，取最近一次。
          · 独立度（代码实算）= structural_amps 里**不与任何 und_aspects
            重合**（_overlap_coef < 0.3）的条数 / structural_amps 总条数。
            ★ 它量的是「独立提炼出来的结构有多独立」，**不是覆盖率** ——
              提示词要求 structural_amps「不得直接复述 und_aspects 的原话」，
              所以越高越合规。旧名「结构覆盖率」与这条要求方向相反（复述得
              越像读数越高），已废弃。空池记 `None`（不可计算），
              不印 0.00 冒充读数。
          · 对齐覆盖率（代码实算）**保留原名**：aligned_amps 的定义就是
            「正好对应 und_aspects 中的某一项」，用覆盖率是自洽的。
        ★ 历史 packed 只有旧键（struct_coverage_history）时按旧口径渲染，
          并显式标注「旧口径」，保证老产物重渲染不丢信息、也不误导。
        """
        ch = getattr(self.pools["1"], "undecidable_channel", None) or {}
        cl_hist = list(ch.get("clarity_history") or [])
        ih_hist = list(ch.get("indep_history") or [])
        sc_hist = list(ch.get("struct_coverage_history") or [])
        ac_hist = list(ch.get("aligned_coverage_history") or [])
        if not cl_hist and not ih_hist and not sc_hist and not ac_hist:
            return ""
        parts = []
        if cl_hist:
            parts.append(f"清晰度 {cl_hist[-1]:.2f}"
                         f"（模型自评，累计 {len(cl_hist)} 次记录）")
        if ih_hist:
            _iv = ih_hist[-1]
            _nfree = int(ch.get("last_indep_free", 0) or 0)
            _npool = int(ch.get("last_indep_pool", 0) or 0)
            if _iv is None:
                parts.append("独立度 —（无独立结构，不可计算）")
            else:
                parts.append(f"独立度 {_iv:.2f}"
                             f"（代码实算：独立结构 {_nfree}/{_npool} 条"
                             f"不与评估阶段方面重合；这是「独立比例」，"
                             f"不是覆盖率）")
        elif sc_hist:
            aspects = list(ch.get("und_aspects") or [])
            hit = int(ch.get("last_struct_hit", 0) or 0)
            _hard = (f"，已对上 {hit}/{len(aspects)} 个不可判定方面"
                     if aspects else "")
            parts.append(f"结构覆盖率 {sc_hist[-1]:.2f}"
                         f"（旧口径{_hard}）")
        if ac_hist:
            aspects = list(ch.get("und_aspects") or [])
            ahit = int(ch.get("last_aligned_hit", 0) or 0)
            _hard2 = (f"，已对上 {ahit}/{len(aspects)} 个不可判定方面"
                      if aspects else "")
            parts.append(f"对齐覆盖率 {ac_hist[-1]:.2f}"
                         f"（代码实算{_hard2}）")
        return "研究层不可判定通道：" + "｜".join(parts) + "\\n"'''
    repl_block(_old_und, _new_und, "P1-3 _und_channel_line 渲染")

    # ================================================================
    # P1-4 · _coverage_segment docstring
    # ================================================================
    repl_line("        结构覆盖率（代码实算）。以前这两个量只进了喂模型的 shape，",
              "        独立度（代码实算）。以前这两个量只进了喂模型的 shape，",
              "P1-4 _coverage_segment docstring")

    # ================================================================
    # P1-5 · 终端渲染 _update_trackers 的 📘 行
    # ================================================================
    _old_tr = '''        if struct_cov is not None:
            ch = self.pools["1"].undecidable_channel
            n_hit = ch.get("last_struct_hit", 0)
            n_aspects = len(ch.get("und_aspects", []))
            n_indep = len(ch.get("structural_amps", []))
            n_aligned = len(ch.get("aligned_amps", []))
            self.vp(f"   📘 不可判定结构覆盖率 "
                    f"{struct_cov:.0%}"
                    f"（{n_hit}/{n_aspects} und_aspects 命中）")
            _acov = ch.get("last_aligned_coverage")
            if _acov is not None:
                self.vp(f"   📘 不可判定对齐覆盖率 {_acov:.0%}"
                        f"（{int(ch.get('last_aligned_hit', 0) or 0)}"
                        f"/{n_aspects} und_aspects 命中）")
            self.vp(f"      ↳ 独立结构 {n_indep} 条（计入结构覆盖率），"
                    f"对齐结构 {n_aligned} 条（计入对齐覆盖率）")'''
    _new_tr = '''        if struct_cov is not None:
            ch = self.pools["1"].undecidable_channel
            n_hit = ch.get("last_struct_hit", 0)
            n_aspects = len(ch.get("und_aspects", []))
            n_indep = len(ch.get("structural_amps", []))
            n_aligned = len(ch.get("aligned_amps", []))
            _iratio = ch.get("last_indep_ratio")
            if "indep_history" not in ch:
                # 历史 packed 重渲染：只认旧口径，别硬套新名。
                self.vp(f"   📘 不可判定结构覆盖率 {struct_cov:.0%}"
                        f"（旧口径 {n_hit}/{n_aspects} und_aspects 命中）")
            elif _iratio is None:
                self.vp("   📘 不可判定独立度 —（无独立结构，不可计算）")
            else:
                self.vp(f"   📘 不可判定独立度 {_iratio:.0%}"
                        f"（{int(ch.get('last_indep_free', 0) or 0)}"
                        f"/{n_indep} 条独立结构不与 und_aspects 重合；"
                        f"不是覆盖率）")
            _acov = ch.get("last_aligned_coverage")
            if _acov is not None:
                self.vp(f"   📘 不可判定对齐覆盖率 {_acov:.0%}"
                        f"（{int(ch.get('last_aligned_hit', 0) or 0)}"
                        f"/{n_aspects} und_aspects 命中）")
            self.vp(f"      ↳ 独立结构 {n_indep} 条（独立度分母），"
                    f"对齐结构 {n_aligned} 条（计入对齐覆盖率）")'''
    repl_block(_old_tr, _new_tr, "P1-5 _update_trackers 📘 行")

    # ================================================================
    # P1-6 · 喂模型的 shape（★ 运行期可见变化，报告里要写清）
    # ================================================================
    _old_sh = '''        if pool.undecidable_channel.get("last_struct_coverage"):
            bits.append(f"  📘 不可判定结构覆盖 "
                        f"{pool.undecidable_channel['last_struct_coverage']:.2f}")'''
    _new_sh = '''        _uc = pool.undecidable_channel
        if "indep_history" in _uc:
            _ir = _uc.get("last_indep_ratio")
            if _ir is not None:
                bits.append(f"  📘 不可判定独立度 {_ir:.2f}"
                            f"（独立结构不与评估阶段方面重合的比例）")
        elif _uc.get("last_struct_coverage"):
            bits.append(f"  📘 不可判定结构覆盖 "
                        f"{_uc['last_struct_coverage']:.2f}")'''
    repl_block(_old_sh, _new_sh, "P1-6 _pool_shape 喂模型")

    # ================================================================
    # P1-7 · 视图 dump / md 附录里的两处「计入覆盖率」
    # ================================================================
    repl_line('                      "  独立结构（计入覆盖率）："]',
              '                      "  独立结构（独立度分母）："]',
              "P1-7a 视图 dump 独立结构行")
    repl_line('                lines.append("  对齐 und_aspects（另计，不参与覆盖率）：")',
              '                lines.append("  对齐 und_aspects（另计，不参与独立度）：")',
              "P1-7b 视图 dump 对齐行")
    repl_line('                f.write("- 独立结构（计入覆盖率）：\\n")',
              '                f.write("- 独立结构（独立度分母）：\\n")',
              "P1-7c md 附录 独立结构行")
    repl_line('                    f.write("- 对齐 und_aspects（另计，不参与覆盖率）：\\n")',
              '                    f.write("- 对齐 und_aspects（另计，不参与独立度）：\\n")',
              "P1-7d md 附录 对齐行")

    # ================================================================
    # P1-8 · 复述指标的 docstring 去「ing」（它是层内指标，不是对撞层专属）
    # ================================================================
    repl_line("「ing 连续几圈在复述」的唯一实现。",
              "「本层连续几圈在复述」的唯一实现。",
              "P1-8 _compute_rephrase_streak docstring")

    # ================================================================
    # 修行层-1 · _stop_reasons 加 stall_is_sat 形参
    # ================================================================
    repl_block(
        '                      view, idles, diag: bool = False,\n'
        '                      defer_vp: bool = False):',
        '                      view, idles, diag: bool = False,\n'
        '                      defer_vp: bool = False,\n'
        '                      stall_is_sat: bool = False):',
        "修行层-1 _stop_reasons 加形参")

    # ================================================================
    # 修行层-2 · docstring 写「修行层适用停止条件显式清单」
    # ================================================================
    repl_block(
        '        返回 `(reasons, idles)`：`idles` 是空转累计（调用方要写回自己的载体）。\n'
        '        这里是**纯判据**：不改任何池、不设 stopped（那是调用方的事）。\n'
        '        """',
        '        返回 `(reasons, idles)`：`idles` 是空转累计（调用方要写回自己的载体）。\n'
        '        这里是**纯判据**：不改任何池、不设 stopped（那是调用方的事）。\n'
        '\n'
        '        ★ 修行层（entry="0"）的**适用停止条件清单**（改条件前先看这张表）：\n'
        '\n'
        '          1. 复述 / 自省点名未消化 —— **适用**（`layer_no < soft_max`\n'
        '             时仍推迟）。文案取 `_LAYER_LABEL`，不借「ing」——\n'
        '             那是**对撞层**的输入名，修行层没有这个输入。\n'
        '          2. 「无新 &」半条 —— **不适用**（`entry != "0"` 把 0 层排除：\n'
        '             修行层的 & 无新增本来就不是它的停止理由）；\n'
        '             「无线头新增」半条 —— **适用**（方向走完了，与层无关）。\n'
        '          3. 有新增但无推进 / sat 推计数 —— **适用**（0 层最常走的\n'
        '             自然停止点）。`stall_is_sat=True` 时印「结构饱和度判定」；\n'
        '             因为 sat 是在 `stalled` 为假时顶的计数，`stall_why`\n'
        '             这时是空串，照搬老模板会印出 `…无推进（）`。\n'
        '          4. / 5. 双通道收敛 / 停滞 —— **不适用**（`entry == "1"`\n'
        '             研究层专属）。\n'
        '          6. 自然安住 + 空转 —— **适用**（0 层空转文案 = 「连续空转」）。\n'
        '        """',
        "修行层-2 docstring 显式清单")

    # ================================================================
    # 修行层-3 · 条件 1 文案按层取词（去「ing」）
    # ================================================================
    repl_block(
        '        _src: List[str] = []\n'
        '        if rephrase_streak >= 2:\n'
        '            _src.append(f"ing 连续 {rephrase_streak} 圈复述（层内空转）")',
        '        _src: List[str] = []\n'
        '        # ★ 「ing」是**对撞层**的输入名；修行/研究/元层没有这个输入，\n'
        '        #   把别的层的词印进它们的停因是借词（以讹传讹）。按层取标签。\n'
        '        _lyr = _LAYER_LABEL.get(entry, entry)\n'
        '        if rephrase_streak >= 2:\n'
        '            _src.append(f"{_lyr}层连续 {rephrase_streak} 圈复述"\n'
        '                        f"（层内空转）")',
        "修行层-3 条件 1 文案去 ing")

    # ================================================================
    # 修行层-4 · 条件 3 补空括号（sat 推计数那一支有自己的说法）
    # ================================================================
    repl_block(
        '        # ---- 3) 有新增但无推进 ----\n'
        '        if (rounds_n > 1 and r_stall_limit > 0\n'
        '                and idle_stall >= r_stall_limit):\n'
        '            reasons.append(\n'
        '                f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")',
        '        # ---- 3) 有新增但无推进（含 sat 顶计数这一支）----\n'
        '        if (rounds_n > 1 and r_stall_limit > 0\n'
        '                and idle_stall >= r_stall_limit):\n'
        '            if stall_is_sat:\n'
        '                # sat 判「无新维度」时把 idle_stall 顶到门槛上 —— 那\n'
        '                # 不是「有新增但无推进」，照搬老模板会把空串印成\n'
        '                # `…无推进（）`。这一支有自己的说法。\n'
        '                reasons.append(\n'
        '                    f"连续 {idle_stall} 轮无新结构维度"\n'
        '                    f"（结构饱和度判定，不是新增停滞）")\n'
        '            else:\n'
        '                reasons.append(\n'
        '                    f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")',
        "修行层-4 条件 3 支路")

    # ================================================================
    # 修行层-5 · 串行侧：stall_is_sat 计算 + 打印 + 调用点
    # ================================================================
    repl_block(
        '            idle_stall = idle_stall + 1 if stalled else 0\n'
        '            sat_override = False',
        '            idle_stall = idle_stall + 1 if stalled else 0\n'
        '            sat_override = False\n'
        '            _stall_is_sat = False',
        "修行层-5a 串行 _stall_is_sat 初值")

    repl_block(
        '                idle_new_amp, idle_stall, sat_override = _sat_override(\n'
        '                    entry, sat_verdict, idle_new_amp, idle_stall,\n'
        '                    r_idle_limit, r_stall_limit)\n'
        '                if sat_verdict is False:',
        '                idle_new_amp, idle_stall, sat_override = _sat_override(\n'
        '                    entry, sat_verdict, idle_new_amp, idle_stall,\n'
        '                    r_idle_limit, r_stall_limit)\n'
        '                # sat 顶了计数、而本圈其实没 stall ⇒ 条件 3 会印空括号。\n'
        '                _stall_is_sat = bool(sat_verdict is False and not stalled)\n'
        '                if sat_verdict is False:',
        "修行层-5b 串行 sat 块")

    repl_block(
        '            if rounds_n > 1:\n'
        '                self.vp(f"   🆕 本圈新增 & {len(new_amps)} 条 / "\n'
        '                        f"线头 {len(new_threads)} 条"\n'
        '                        f"（近似不算，比对池内全部；"\n'
        '                        f"连续无新增 &{idle_new_amp}/线头{idle_new_thread} "\n'
        '                        f"｜连续无推进 {idle_stall}"\n'
        '                        f"{\'（\' + stall_why + \'）\' if stalled else \'\'}）")',
        '            if rounds_n > 1:\n'
        '                _stall_disp = (stall_why if stalled\n'
        '                               else ("结构饱和度判定" if _stall_is_sat\n'
        '                                     else ""))\n'
        '                self.vp(f"   🆕 本圈新增 & {len(new_amps)} 条 / "\n'
        '                        f"线头 {len(new_threads)} 条"\n'
        '                        f"（近似不算，比对池内全部；"\n'
        '                        f"连续无新增 &{idle_new_amp}/线头{idle_new_thread} "\n'
        '                        f"｜连续无推进 {idle_stall}"\n'
        '                        f"{\'（\' + _stall_disp + \'）\' if _stall_disp else \'\'}）")',
        "修行层-5c 串行打印点")

    repl_block(
        '                idle_stall=idle_stall, stall_why=stall_why,\n'
        '                sat_override=sat_override, prev_product=prev_product,\n'
        '                view=view, idles=idles, diag=False)',
        '                idle_stall=idle_stall, stall_why=stall_why,\n'
        '                sat_override=sat_override,\n'
        '                stall_is_sat=_stall_is_sat,\n'
        '                prev_product=prev_product,\n'
        '                view=view, idles=idles, diag=False)',
        "修行层-5d 串行调用点")

    # ================================================================
    # 修行层-6 · 并行侧：同上
    # ================================================================
    repl_block(
        '        idle_stall = state["idle_stall"]\n'
        '        sat_override = False',
        '        idle_stall = state["idle_stall"]\n'
        '        sat_override = False\n'
        '        _stall_is_sat = False',
        "修行层-6a 并行 _stall_is_sat 初值")

    repl_block(
        '            idle_new_amp, idle_stall, sat_override = _sat_override(\n'
        '                entry, sat_verdict, idle_new_amp, idle_stall,\n'
        '                r_idle_limit, r_stall_limit)\n'
        '            state["idle_new_amp"] = idle_new_amp',
        '            idle_new_amp, idle_stall, sat_override = _sat_override(\n'
        '                entry, sat_verdict, idle_new_amp, idle_stall,\n'
        '                r_idle_limit, r_stall_limit)\n'
        '            state["idle_new_amp"] = idle_new_amp\n'
        '            # 同串行侧：sat 顶到门槛而本圈没 stall ⇒ 条件 3 的空括号。\n'
        '            _stall_is_sat = bool(sat_verdict is False and not stalled)',
        "修行层-6b 并行 sat 块")

    repl_block(
        '        if state["total_rounds"] > 1:\n'
        '            self.vp(f"   🆕 {self._parallel_label}{r} 新增 & "\n'
        '                    f"{len(new_amps)} 条 / "\n'
        '                    f"线头 {len(new_threads)} 条"\n'
        '                    f"（连续无新增 &{idle_new_amp}/"\n'
        '                    f"线头{idle_new_thread}"\n'
        '                    f"｜连续无推进 {idle_stall}"\n'
        '                    f"{\'（\' + stall_why + \'）\' if stalled else \'\'}）")',
        '        if state["total_rounds"] > 1:\n'
        '            _stall_disp = (stall_why if stalled\n'
        '                           else ("结构饱和度判定" if _stall_is_sat\n'
        '                                 else ""))\n'
        '            self.vp(f"   🆕 {self._parallel_label}{r} 新增 & "\n'
        '                    f"{len(new_amps)} 条 / "\n'
        '                    f"线头 {len(new_threads)} 条"\n'
        '                    f"（连续无新增 &{idle_new_amp}/"\n'
        '                    f"线头{idle_new_thread}"\n'
        '                    f"｜连续无推进 {idle_stall}"\n'
        '                    f"{\'（\' + _stall_disp + \'）\' if _stall_disp else \'\'}）")',
        "修行层-6c 并行打印点")

    repl_block(
        '            idle_stall=idle_stall, stall_why=stall_why,\n'
        '            sat_override=sat_override,\n'
        '            prev_product=state["prev_product"], view=view,\n'
        '            idles=state["idles"], defer_vp=True)',
        '            idle_stall=idle_stall, stall_why=stall_why,\n'
        '            sat_override=sat_override,\n'
        '            stall_is_sat=_stall_is_sat,\n'
        '            prev_product=state["prev_product"], view=view,\n'
        '            idles=state["idles"], defer_vp=True)',
        "修行层-6d 并行调用点")

    # ================================================================
    # 修行层-7 · 红线表述：从「不追求收敛」改成「本来就能停 / 停得合理」
    #            + 修行层任何停止都补「本轮显形 / 未生质量」
    # ================================================================
    repl_block(
        ' # 修行层不追求收敛：走到了「体力耗尽」不等于\n'
        '        if entry == "0" and (view.stop_reason or "").startswith("体力耗尽") \\\n'
        '                and "未生质量" not in (view.stop_reason or ""):',
        '        # ★ 修行层本来就能停 —— 要的不是「不许停」，是「停得合理」。\n'
        '        #   所以不论它是被停止判据自然停住、还是走满上限被体力耗尽\n'
        '        #   截断，都在停因后补一段「本轮显形 + 未生质量」，让\n'
        '        #   「停得合理」这件事**可核**。\n'
        '        #   （旧文案容易被读成「0 层不该停」，那与设计相悖。）\n'
        '        if entry == "0" and (view.stop_reason or "").strip() \\\n'
        '                and "未生质量" not in (view.stop_reason or ""):',
        "修行层-7 红线表述 + 一律附体检")

    s = "\n".join(lines)
    ast.parse(s)                       # 语法先过

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0, "产出含 CRCRLF"
    assert out.count(b"\n") == out.count(b"\r\n"), "产出不是纯 CRLF"
    assert out.count(b"\r") == out.count(b"\r\n"), "产出有游离 CR"
    TGT.write_bytes(out)
    assert TGT.read_bytes() == out, "回读不一致"

    print("已应用 %d 处编辑：" % len(edits))
    for e in edits:
        print("  · " + e)

    # ================================================================
    # 结构性自检：真加载 + 真调（不是只 parse）
    # ================================================================
    spec = importlib.util.spec_from_file_location("dgtf_selfchk", str(TGT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_selfchk"] = m
    spec.loader.exec_module(m)

    assert str(m.__version__) == "1.23.24", m.__version__
    assert "元 DGTF · v1.23.24" in (m.__doc__ or "")

    cfg = m.load_config(str(HERE / "__nonexistent__.yaml"))
    cfg["api"]["key"] = "sk-selfcheck"
    cfg["output"]["verbose"] = False

    # ① 独立度新键在
    p = m.Pool()
    p.add_undecidable({"structural_amps": ["甲", "乙"], "aligned_amps": [],
                       "clarity": 0.5}, ["丙", "丁"], layer=1)
    ch = p.undecidable_channel
    assert ch.get("last_indep_pool") == 2, ch.get("last_indep_pool")
    assert "indep_history" in ch and len(ch["indep_history"]) == 1
    assert ch.get("last_struct_coverage") == 0.0, "旧键被动了"

    # ② _stop_reasons 新形参在，且 sat 支路不印空括号
    assert "stall_is_sat" in inspect.signature(
        m.MetaDGTF._stop_reasons).parameters
    mr = m.MetaDGTF(cfg)
    _sp = dict(m.DEFAULT_CONFIG["spiral"])

    def _rs(**kw):
        base = dict(entry="0", layer_no=3, rounds_n=3, total_rounds=3,
                    sp=_sp, soft_max=3, sim_thr=0.8, stable_need=2,
                    idle_limit=2, r_idle_limit=2, r_stall_limit=2,
                    rephrase_streak=0, carry_streak=0, idle_new_amp=0,
                    idle_new_thread=0, idle_stall=2, stall_why="",
                    sat_override=False, prev_product="",
                    view=m.View(entry="0"), idles=0)
        base.update(kw)
        with contextlib.redirect_stdout(io.StringIO()):
            r, _ = mr._stop_reasons(**base)
        return " | ".join(str(x) for x in r)

    _sat = _rs(stall_is_sat=True)
    assert "结构饱和度判定" in _sat, _sat
    assert "（）" not in _sat, "空括号还在：" + _sat
    _real = _rs(stall_why="修行层无新增或无推进")
    assert "修行层无新增或无推进" in _real, _real
    assert "（）" not in _real, _real

    # ③ 条件 1 文案按层取词
    _t0 = _rs(rephrase_streak=2, idle_stall=0)
    assert "修行层连续 2 圈复述" in _t0 and "ing" not in _t0, _t0
    _tb = _rs(entry="both", rephrase_streak=2, idle_stall=0,
              view=m.View(entry="both"))
    assert "对撞层连续 2 圈复述" in _tb, _tb

    # ④ 修行层任何停止都附体检；非修行层不附（负对照）
    def _fin(entry, why):
        v = m.View(entry=entry)
        v.stop_reason = why
        st = {"roles_hist": ["摊开"], "total_rounds": 4, "round_log": [],
              "all_rehashed": [], "all_candidates": [], "all_amps": [],
              "all_threads": [], "all_expanded_descs": [],
              "all_dec_products": [], "all_und_products": [],
              "r": 4, "rounds_n": 4, "sp": m._spiral_for(cfg, entry)}
        with contextlib.redirect_stdout(io.StringIO()):
            m.MetaDGTF(cfg)._finalize_layer_common(entry, v, st)
        return v.stop_reason

    assert "未生质量" in _fin("0", "连续 2 轮有新增但无推进（修行层无新增或无推进），螺旋停止")
    assert "未生质量" in _fin("0", "体力耗尽（4 圈走满，未触发任何停止判据，是被截断不是自然停止）")
    assert "未生质量" not in _fin("1", "研究层双通道均收敛，螺旋停止")

    # ⑤ 渲染层：新口径出现、旧口径只在 legacy dict 上出现
    mg = m.MetaDGTF(cfg)
    mg.pools["1"].undecidable_channel = ch
    _line = mg._und_channel_line()
    assert "独立度" in _line and "结构覆盖率" not in _line, _line
    mg2 = m.MetaDGTF(cfg)
    mg2.pools["1"].undecidable_channel = {
        "clarity_history": [0.5], "struct_coverage_history": [0.6],
        "und_aspects": ["面%d" % i for i in range(10)],
        "last_struct_hit": 6, "structural_amps": ["a"], "aligned_amps": [],
    }
    _line2 = mg2._und_channel_line()
    assert "结构覆盖率 0.60" in _line2 and "已对上 6/10" in _line2, _line2

    # ⑥ 源码里再没「修行层不追求收敛」这句话
    _txt = TGT.read_bytes().decode("utf-8")
    assert "修行层不追求收敛" not in _txt
    assert "修行层本来就能停" in _txt

    print("\n✅ 结构性自检全部通过（真加载 + 真调 _stop_reasons / "
          "_und_channel_line / _finalize_layer_common）")


if __name__ == "__main__":
    main()
