#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打补丁：元DGTF-V1.21.69.py → 元DGTF-V1.21.70.py（F/K/G/H/I/J 六项）

铁律：
  · 不覆盖源文件（先 copy）；
  · 纯 CRLF 往返，改完双向断言；
  · 每次替换前断言**查找块出现次数 == 1**（重复插入是真实事故）；
  · 新增 docstring 文本里**不许有反斜杠**（会让 __doc__ 与源码原文不等，
    破坏「摘 docstring 再扫源码」的断言）；
  · 改完打印各版本段的起始行号序列。
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.69.py"
DST = HERE / "元DGTF-V1.21.70.py"

shutil.copy2(SRC, DST)
raw = DST.read_bytes()
s = raw.decode("utf-8")

# ---- 进入前：纯 CRLF 自检 ----
assert s.count("\r\n") == s.count("\n"), "源文件不是纯 CRLF（有其他换行）"
assert s.count("\r") == s.count("\r\n"), "源文件里混进了裸 CR"
n_crlf_before = s.count("\r\n")
s = s.replace("\r\n", "\n")

EDITS = []          # (名称, 查找块, 替换块)


def add(name, old, new):
    EDITS.append((name, old, new))


# ======================================================================
# [F] 位置一：Pool.add_undecidable 尾部
# ======================================================================
add("[F-1] 轨迹拆两条", '''        # [v1.21.57] 记轨迹 + 首次命中圈号（只记第一次，后面再命中不改）
        _first = self.undecidable_channel.setdefault("aspect_first_hit", {})
        _newly: List[str] = []
        for asp in hit_aspects:
            if asp not in _first:
                _first[asp] = layer
                _newly.append(asp)
        self.undecidable_channel.setdefault("struct_trace", []).append({
            "layer": layer, "hit": len(hit_aspects),
            "total": len(aspects), "cov": round(struct_cov, 3),
            "newly": _newly,
        })
''', '''        # [v1.21.70 F修] 轨迹与 B 口径对齐：B 把覆盖率拆成「独立
        #   （structural_amps）/ 对齐（aligned_amps）」两个数，**轨迹也得跟着
        #   拆成两条** —— 否则产物里会同时出现
        #     「结构覆盖率 0.00（独立结构）｜对齐覆盖率 0.38（对齐结构）」
        #     「覆盖轨迹：L1 0/8 → L2 0/8」                 ← 只有独立版
        #   两个数打架，读者以为哪里出错了。
        #   ★ struct_trace / aspect_first_hit **原样保留**（历史对比），
        #     新增 aligned_trace / aligned_first_hit；两者同构，只是输入不同。
        def _append_trace(_pool, _hits, _trace_key, _first_key):
            _first = self.undecidable_channel.setdefault(_first_key, {})
            _newly: List[str] = []
            for _asp in _hits:
                if _asp not in _first:
                    _first[_asp] = layer
                    _newly.append(_asp)
            _cov = (len(_hits) / len(aspects)) if aspects else 0.0
            self.undecidable_channel.setdefault(_trace_key, []).append({
                "layer": layer, "hit": len(_hits),
                "total": len(aspects), "cov": round(_cov, 3),
                "newly": _newly,
            })

        _append_trace(self.undecidable_channel["structural_amps"],
                      hit_aspects, "struct_trace", "aspect_first_hit")
        _append_trace(self.undecidable_channel.get("aligned_amps") or [],
                      aligned_hits, "aligned_trace", "aligned_first_hit")
''')

# ======================================================================
# [F] 位置二：save_result 渲染 struct_trace
# ======================================================================
add("[F-2] 轨迹渲染拆两条", '''            _trace = uc.get("struct_trace") or []
            if _trace:
                _segs = []
                _prev = 0
                for _t in _trace:
                    _h = int(_t.get("hit", 0) or 0)
                    _delta = _h - _prev
                    _segs.append(
                        f"L{_t.get('layer', '?')} {_h}/"
                        f"{int(_t.get('total', 0) or 0)}"
                        + (f"（+{_delta}）" if _delta > 0 else ""))
                    _prev = _h
                f.write("- 📘 不可判定覆盖轨迹："
                        + " → ".join(_segs) + "\\n")
                _first = uc.get("aspect_first_hit") or {}
                if _first:
                    _fl = "、".join(
                        f"{str(_a)[:40]}（L{_l}）"
                        for _a, _l in list(_first.items())[:6])
                    if len(_first) > 6:
                        _fl += f" 等 {len(_first)} 项"
                    f.write(f"- 📘 首次对上的方面：{_fl}\\n")
''', '''            # [v1.21.70 F修] 两条轨迹分开渲染，与 B 的两个覆盖率口径同源：
            #   · 独立结构轨迹（structural_amps，常为 0，供历史对比）
            #   · 对齐结构轨迹（aligned_amps，**真正**能回答"有没有对上
            #     und_aspects"的那个）
            #   ★ 加性：老产物 / 老 dict 里没有 aligned_trace 时那一行不出现。
            def _render_trace(_trace, _first, _label):
                if not _trace:
                    return
                _segs = []
                _prev = 0
                for _t in _trace:
                    _h = int(_t.get("hit", 0) or 0)
                    _delta = _h - _prev
                    _segs.append(
                        f"L{_t.get('layer', '?')} {_h}/"
                        f"{int(_t.get('total', 0) or 0)}"
                        + (f"（+{_delta}）" if _delta > 0 else ""))
                    _prev = _h
                f.write(f"- 📘 不可判定{_label}覆盖轨迹："
                        + " → ".join(_segs) + "\\n")
                if _first:
                    _fl = "、".join(
                        f"{str(_a)[:40]}（L{_l}）"
                        for _a, _l in list(_first.items())[:6])
                    if len(_first) > 6:
                        _fl += f" 等 {len(_first)} 项"
                    f.write(f"- 📘 首次对上的方面（{_label}）：{_fl}\\n")

            _render_trace(uc.get("struct_trace") or [],
                          uc.get("aspect_first_hit") or {}, "独立结构")
            _render_trace(uc.get("aligned_trace") or [],
                          uc.get("aligned_first_hit") or {}, "对齐结构")
''')

# ======================================================================
# [K] _finalize_layer_common 第 6 步
# ======================================================================
add("[K] 覆盖率段触发时机", '''        # ---- 6. 元层：闭环清算 + 覆盖率段 ----
        if entry == "all":
            clo = self._settle_meta()
            view.meta_closure = clo
            if clo["clean"]:
                self.vp(f"   🌀 闭环清算：clean=True"
                        f"（对撞 {clo['total']} 类张力全部有交代）")
            else:
                _unc = clo.get("uncovered") or []
                _unc_s = "；".join(str(u)[:40] for u in _unc[:5])
                view.closure_reason = (
                    f"meta_unsettled（{clo['unsettled']}/{clo['total']} "
                    f"类张力未交代：{_unc_s}）")
                self.vp(f"   ⚠️ 闭环清算：{clo['unsettled']}/{clo['total']} "
                        f"类张力未交代（不是停止理由）")
                for _u in _unc[:5]:
                    self.vp(f"      · 未交代：{_u}")
            _cov_seg = self._coverage_segment()
            if _cov_seg:
                view.manifest = (view.manifest or "") + _cov_seg
                _ch = (list(self.dec_tracker.coverage_history)
                       if self.dec_tracker else [])
                _uh = (list(self.und_tracker.und_clarity_history)
                       if self.und_tracker else [])
                if _ch:
                    self.vp(f"   📈 元层追加覆盖率段：{_ch[-1]:.2f}")
                elif _uh:
                    self.vp(f"   📈 元层追加覆盖率段"
                            f"（fallback 到 und clarity）：{_uh[-1]:.2f}")
''', '''        # ---- 6. 元层：闭环清算 + 覆盖率段 ----
        # [v1.21.70 K修] 覆盖率段**不再只挂 all 层**。原来只有 all 层收尾
        #   时追加，于是 route 不含 all 的运行（例如 V68 的 route=0,1）里
        #   `_coverage_segment()` **一次都不会被调**——B 项改好的「对齐覆盖率」
        #   在那种 route 下根本没有出口。V69 changelog 自己记过这条可达性
        #   限制（"V68/V69 产物实测都是 0 行"），这里补上。
        #   ★ 为什么不是"改 `_coverage_segment` 的触发条件"：它是**渲染**函数，
        #     不该承担"什么时候渲染"的调度职责。触发时机是收尾的事。
        #   ★ route 含 all 时两处都追加（研究层 view 一份、all 层 view 一份），
        #     内容一致，**不是 bug** —— 覆盖率本来就是研究层的东西。
        #     两处的追加时机都与原先的 all 层**完全相同**（都在 _apply_keep /
        #     _settle_research 之前），所以不会一个是一个不是。
        def _append_coverage(_v, _where):
            _seg = self._coverage_segment()
            if not _seg:
                return
            _v.manifest = (_v.manifest or "") + _seg
            _ch = (list(self.dec_tracker.coverage_history)
                   if self.dec_tracker else [])
            _uh = (list(self.und_tracker.und_clarity_history)
                   if self.und_tracker else [])
            if _ch:
                self.vp(f"   📈 {_where}追加覆盖率段：{_ch[-1]:.2f}")
            elif _uh:
                self.vp(f"   📈 {_where}追加覆盖率段"
                        f"（fallback 到 und clarity）：{_uh[-1]:.2f}")

        if entry == "all":
            clo = self._settle_meta()
            view.meta_closure = clo
            if clo["clean"]:
                self.vp(f"   🌀 闭环清算：clean=True"
                        f"（对撞 {clo['total']} 类张力全部有交代）")
            else:
                _unc = clo.get("uncovered") or []
                _unc_s = "；".join(str(u)[:40] for u in _unc[:5])
                view.closure_reason = (
                    f"meta_unsettled（{clo['unsettled']}/{clo['total']} "
                    f"类张力未交代：{_unc_s}）")
                self.vp(f"   ⚠️ 闭环清算：{clo['unsettled']}/{clo['total']} "
                        f"类张力未交代（不是停止理由）")
                for _u in _unc[:5]:
                    self.vp(f"      · 未交代：{_u}")
            _append_coverage(view, "元层")
        elif entry == "1":
            # [v1.21.70 K修] 研究层收尾也追加一份。route 不含 all 时
            #   这是覆盖率段**唯一**的出口。
            _append_coverage(view, "研究层")
''')

# ======================================================================
# [G] _re_anchor 的 _clean
# ======================================================================
add("[G] 锚点占位符闸门", '''            def _clean(key, n=4):
                v = data.get(key, [])
                if not isinstance(v, list):
                    return []
                return [str(x).strip()[:60] for x in v
                        if str(x).strip()][:n]
''', '''            # [v1.21.70 G修] 占位符要挡在门外。V68 真跑产物里 touched/
            #   untouched 出现过 {"desc":"此处未生","source":"anchor"}，
            #   原样进【未决缺口】段，显示成「〔修行〕尚未触及：此处未生」
            #   —— 一条占位符被当成一条"方面"。
            #   ★ 同类闸门在候选侧已有（`_parse_candidate_line` 挡「（无）」
            #     「(无)」「无」三种写法），只有锚点重述这条路没设闸 ——
            #     又一处「同一件事两处各写一份」的变体。
            #   ★ 全角/半角归一后匹配：`（无）` 与 `(无)` 都算占位符。
            #   ★ 只挡**完全相等**的占位符，不做子串匹配 ——
            #     否则会把「无仲裁规则」这类正常方面误杀。
            _ANCHOR_PLACEHOLDERS = (
                "此处未生", "（此处未生）", "(此处未生)",
                "无", "（无）", "(无)", "暂无", "未知", "n/a", "N/A",
            )

            def _clean(key, n=4):
                v = data.get(key, [])
                if not isinstance(v, list):
                    return []
                out = []
                for x in v:
                    s = str(x).strip()[:60]
                    if not s:
                        continue
                    if s in _ANCHOR_PLACEHOLDERS:
                        continue
                    if s.replace("（", "(").replace("）", ")") \\
                            in _ANCHOR_PLACEHOLDERS:
                        continue
                    out.append(s)
                return out[:n]
''')

# ======================================================================
# [H] dump_view_fields 的字段循环
# ======================================================================
add("[H] 超大覆盖字段只打长度", '''    _keys = sorted(_d.keys())
    if prev is not None:
        _same = [k for k in _keys if _canon(_d[k]) == prev.get(k)]
        _keys = [k for k in _keys if _canon(_d[k]) != prev.get(k)]
        emit(f"   （增量模式：{len(_same)}/{len(_d)} 个字段与上一圈留痕"
             f"完全相同、已省略；下面只列**变了的**）")
    for _k in _keys:
        _v = _d[_k]
        if isinstance(_v, (list, tuple, dict, set)):
''', '''    _keys = sorted(_d.keys())
    if prev is not None:
        _same = [k for k in _keys if _canon(_d[k]) == prev.get(k)]
        _keys = [k for k in _keys if _canon(_d[k]) != prev.get(k)]
        emit(f"   （增量模式：{len(_same)}/{len(_d)} 个字段与上一圈留痕"
             f"完全相同、已省略；下面只列**变了的**）")
    # [v1.21.70 H修] **覆盖型超大文本字段**只打长度，正文不落日志。
    #   E 项只处理了"累积型"（靠差分省略），但日志体量的大头在
    #   `rendered`（修行 4551 字 / 研究 6378 字）与 `manifest` —— 它们
    #   每圈覆盖、每圈都变，差分**省不掉**。
    #   ★ 内容与同圈已打的 candidates / amps / threads / collision
    #     高度重复（它们本就是 rendered 的"零件"）；正文完整留在产物 md。
    #   ★ 与 E 同一条哲学：不维护"该不该打"的清单，字段名硬编码在这
    #     一个集合里 —— 新增字段不会被误伤，因为它们不叫 rendered/manifest。
    #   ★ 仍用 `├ ` 前缀 ⇒ 字段覆盖计数（v1.21.68 冒烟那条）不受影响。
    _OVERSIZED = {"rendered", "manifest"}
    for _k in _keys:
        _v = _d[_k]
        if _k in _OVERSIZED and isinstance(_v, str):
            emit(f"   ├ {_k}：str {len(_v)} 字"
                 f"（超大覆盖字段，正文见产物 md）")
            continue
        if isinstance(_v, (list, tuple, dict, set)):
''')

# ======================================================================
# [I] dump_round 顶部说明
# ======================================================================
add("[I] 本圈留痕说明", '''        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 圈全量留痕 · entry={self.entry} · 第 {_rnd} 圈"
                f" · {_role or '（无角色）'}")
        self.vp("╚" + "═" * 58 + "╝")
        dump_view_fields(view, self.vp, remember=True)
''', '''        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 圈全量留痕 · entry={self.entry} · 第 {_rnd} 圈"
                f" · {_role or '（无角色）'}")
        self.vp("╚" + "═" * 58 + "╝")
        # [v1.21.70 I修] 一句提示：跨圈回填的字段在本圈 dump 时**还没发生**，
        #   所以这里看到的是"本圈值"。不提示的话，读日志的人会把
        #   `roles_run：0 项` 误读成"整层为空"——实测 V68 每圈都是 0 项，
        #   而收尾后是 2 项。收尾留痕（E 项）会补全，这里只说明白。
        self.vp("   ℹ️ 本段是**本圈**留痕；跨圈回填字段（roles_run / "
                "round_log / rounds_cap / carry_* 等）此处可能为空或仅本圈，"
                "最终值见该层收尾留痕。")
        dump_view_fields(view, self.vp, remember=True)
''')

# ======================================================================
# [J] _merge_decidability 复用 _und_untraced
# ======================================================================
add("[J] 复用 _und_untraced", '''        _untraced_pool = set(_untraced_undecidable(
            pool_res.get("undecidable_aspects", []),
            pool_res.get("evidence", [])))
''', '''        # [v1.21.70 J修] 复用池评估时已经算好的结果，不再重算一遍。
        #   `_assess_decidability_from_pool_view` 返回值里已经带了
        #   `_und_untraced`（v1.21.61 起）—— 重算等于「同一逻辑两处各写
        #   一份」，本项目反复栽的坑：D 项改了 `_untraced_undecidable` 的
        #   阈值（`_UNTRACED_OVERLAP`），两处要么都改、要么都不改，迟早
        #   分叉。用现成的。
        #   ★ 兜底：万一调用方给的 pool_res 没带这个字段（历史数据 /
        #     手造桩 / external-only 路径），退回重算一次，不静默吞。
        _cached = pool_res.get("_und_untraced")
        if isinstance(_cached, list):
            _untraced_pool = set(_cached)
        else:
            _untraced_pool = set(_untraced_undecidable(
                pool_res.get("undecidable_aspects", []),
                pool_res.get("evidence", [])))
''')

# ---- 执行：逐块断言唯一性并替换 ----
for _name, _old, _new in EDITS:
    _n = s.count(_old)
    if _n != 1:
        print(f"!! [{_name}] 查找块出现 {_n} 次（应为 1）—— 停止，不改。")
        sys.exit(2)
    s = s.replace(_old, _new, 1)
    print(f"   ok [{_name}] 命中 1 次，已替换")

# ======================================================================
# docstring：标题 / 索引 / 新增版本段
# ======================================================================
_old_title = "元 DGTF · v1.21.69\n"
assert s.count(_old_title) == 1, "版本标题锚点不唯一"
s = s.replace(_old_title, "元 DGTF · v1.21.70\n", 1)
print("   ok [docstring 标题] v1.21.69 → v1.21.70")

_old_idx = ('  冒烟带负对照；外部评审有两项诊断与实际不符，照实写。\n')
assert s.count(_old_idx) == 1, "索引锚点不唯一"
_new_idx = _old_idx + (
    "  v1.21.70 是本轮收尾版：F/K 补齐 v1.21.69 [B] 的两个出口（轨迹口径\n"
    "  + 触发时机）、G 修锚点占位符闸门（仅剩的真 bug）、H/I/J 是 [E] 的\n"
    "  延伸与卫生。\n")
s = s.replace(_old_idx, _new_idx, 1)
print("   ok [docstring 索引] 追加 v1.21.70 一行")

_old_sec = ("  ════════════════════════════════════════════════════════════\n"
            "v1.21.68 相对 v1.21.67 的改动（每层每圈全量留痕 + ing 正文可见）\n"
            "════════════════════════════════════════════════════════════\n")
assert s.count(_old_sec) == 1, "版本段锚点不唯一"

NEW_SEC = '''  ════════════════════════════════════════════════════════════
v1.21.70 相对 v1.21.69 的改动（F~J 六项修复）
════════════════════════════════════════════════════════════

  来源：一份**外部任务书**（针对 v1.21.69 的 F/K/G/H/I/J 六项补丁清单）。
  六项前提逐条复核过，并在下面改正了任务书自身的两处笔误（标 ★）。
  F/K 是 v1.21.69 [B] 项的**必然收尾**（B 拆了两个覆盖率口径，轨迹与
  触发时机没跟上）；G 是唯一还没修的真 bug；H/I/J 是 v1.21.69 [E] 的
  自然延伸与卫生。

  ────────────────────────────────────────────────────────
  [F] 不可判定轨迹与 B 的双口径对齐（补 aligned_trace）
  ────────────────────────────────────────────────────────

  **位置**：`Pool.add_undecidable` 尾部（记轨迹处）+ `save_result` 里
  渲染 `struct_trace` 的那一段。

  **根因**（v1.21.69 [B] 的收尾没做）：B 把覆盖率拆成两个数 ——
  `last_struct_coverage`（撞 `structural_amps`，受 prompt 约束"不得直接
  复述 und_aspects 的原话"，**结构性必为 0**）与 `last_aligned_coverage`
  （撞 `aligned_amps`，真正能回答"有没有对上 und_aspects"）。但**轨迹
  只有一条**：产物里会同时出现「结构覆盖率 0.00（独立结构）｜对齐覆盖率
  0.38（对齐结构）」与「覆盖轨迹：L1 0/8 → L2 0/8」—— 两个数打架。
  改前实测（`_probe_v70_six.py`）：`aligned_trace` / `aligned_first_hit`
  **都不存在**，`last_aligned_coverage` 已经是 0.5，而轨迹行仍只印
  `L1 0/2 → L2 0/2`。

  **做法**：轨迹记录抽成内部函数 `_append_trace`；`struct_trace` /
  `aspect_first_hit` **原样保留**（历史对比），**新增**
  `aligned_trace` / `aligned_first_hit` 一对同构的，只是输入换成
  `aligned_hits`。渲染同样抽成 `_render_trace`，两条轨迹分别渲染为
  「不可判定独立结构覆盖轨迹」与「不可判定对齐结构覆盖轨迹」。

  **★ 任务书笔误一**：任务书写「加性 …… 旧断言（"不可判定覆盖轨迹：
  L1 …"）原样成立」。**不成立** —— 结构那条的标签从「不可判定覆盖轨迹」
  变成「不可判定独立结构覆盖轨迹」，是**破坏性文案改动**、不是加性。
  仓库里没有任何断言依赖这串字（实测只命中文档与历史产物），所以照改；
  但必须记在案，不能写成"加性"。

  **★ 任务书笔误二**：任务书要求断言 `aligned_first_hit == {"A 的复述": 1}`
  —— 键是**方面**、不是 amp（`_hit_of` 返回的是 `und_aspects` 的条目）。
  正确断言是 `aligned_first_hit == {方面: 圈号}`。另外样例若用单字方面
  （"A"）也撞不上：`_kw("A")` 是**空集**（单字被分词器滤掉），
  `_overlap_coef` 直接返回 0.0 —— 冒烟样例一律用长句方面。

  ────────────────────────────────────────────────────────
  [K] 覆盖率段的触发时机（route 不含 all 时给研究层也调一次）
  ────────────────────────────────────────────────────────

  **位置**：`MetaDGTF._finalize_layer_common` 第 6 步（元层闭环 + 覆盖率段）。

  **根因**：`_coverage_segment()` 原来**只挂 `entry == "all"` 的收尾**。
  于是 route 不含 `all` 的运行（例如 V68 的 route=0,1）里它**一次都不会
  被调** —— v1.21.69 [B] 改好的「对齐覆盖率」在那种 route 下根本没有
  出口。v1.21.69 changelog 自己把这条记成「可达性限制（既有行为）」，
  本版补上。改前实测（`_probe_v70_six.py`，把 `_coverage_segment` 换成
  返回哨兵）：`entry=1` 收尾后 manifest **不含**覆盖率段，`entry=all` 含。

  **做法**：把「追加覆盖率段」抽成内部函数 `_append_coverage(view, where)`；
  `entry == "all"` 分支照旧调它；**新增 `elif entry == "1"`**，研究层收尾
  也调一次 —— route 不含 all 时这就是**唯一**出口。

  **★ 为什么不是改 `_coverage_segment` 的触发条件**：它是**渲染**函数，
  不该承担"什么时候渲染"的调度职责。触发时机是收尾的事。

  **★ 口径说明（不是 bug）**：route 含 all 时两处都追加（研究层 view 一份、
  all 层 view 一份），内容一致 —— 覆盖率本来就是研究层的东西。两处的
  追加时机都与原先的 all 层**完全相同**（都在 `_apply_keep` /
  `_settle_research` 之前），所以不会"一个是一个不是"。

  ────────────────────────────────────────────────────────
  [G] 锚点重述的占位符闸门（仅剩的真 bug）
  ────────────────────────────────────────────────────────

  **位置**：`DGTF._re_anchor` 里的 `_clean` 闭包。

  **根因**：候选侧早有占位符闸门（`_parse_candidate_line` 挡「（无）」
  「(无)」「无」三种写法），**锚点重述这条路没设闸** —— 本项目
  「同一件事两处各写一份」的又一处变体。V68 真跑产物里的实际案例：
  `/views/0/untouched[0].desc == "此处未生"`（source=anchor），渲染成
  「尚未触及的方面：💭 此处未生（anchor）」—— **一条占位符被当成一条
  方面**。

  **做法**：在 `_clean` 前定义 `_ANCHOR_PLACEHOLDERS`（「此处未生」
  「无」「暂无」「未知」「n/a」等，含全角 / 半角两种括号写法），逐条比对；
  全角括号先归一成半角再比。空串照旧丢。
  只挡**完全相等**的占位符，不做子串匹配 —— 否则会把「无仲裁规则」
  这类正常方面误杀。

  ────────────────────────────────────────────────────────
  [H] `rendered` / `manifest` 只打长度（超大覆盖字段）
  ────────────────────────────────────────────────────────

  **位置**：`dump_view_fields` 的字段循环。

  **根因**：v1.21.69 [E] 用**差分**压掉了"累积型"字段的重复，但
  `rendered`（修行约 4551 字 / 研究约 6378 字）与 `manifest` 是
  **每圈覆盖、每圈都变** —— 差分对它们**无效**，每圈都得整段打出来。
  V68 日志 3696 行的大头就在这两个字段上。改前实测（`_probe_v70_six.py`，
  rendered=5000 字 / manifest=3000 字）：单圈留痕 **9499 字符**，
  两个字段的正文**全文都在**。

  **做法**：字段名硬编码成集合 `_OVERSIZED = {"rendered", "manifest"}`，
  命中且是 str 时只写一行 `├ rendered：str 5000 字（超大覆盖字段，
  正文见产物 md）`。
  · 仍用 `├ ` 前缀 ⇒ 字段覆盖计数（v1.21.68 那条 ≥ 字段数）不受影响；
  · 正文**完整留在产物 md**（与 [E] 同一条哲学）；
  · 不维护"该打什么"的清单，只钉**字段名** —— 新增字段不会被误伤。

  ────────────────────────────────────────────────────────
  [I] `dump_round` 顶部加「本圈留痕」说明
  ────────────────────────────────────────────────────────

  **位置**：`DGTF.dump_round` 顶部（`╚…╝` 之后、`dump_view_fields` 之前）。

  **根因**：跨圈**回填**的字段（`roles_run` / `round_log` / `rounds_cap` /
  `carry_*`）在本圈 dump 时**还没发生**，所以每圈都打 0 项 —— V68 日志里
  每圈 `roles_run：list 0 项`，而收尾后是 2 项。不是 bug（每圈新建 view），
  但读日志的人会把 0 项误读成"整层为空"。

  **做法**：加一句提示 ——「本段是**本圈**留痕；跨圈回填字段……最终值见
  该层收尾留痕」。不改变任何数据，只说明白。

  ────────────────────────────────────────────────────────
  [J] `_merge_decidability` 复用 `_und_untraced`
  ────────────────────────────────────────────────────────

  **位置**：`MetaDGTF._merge_decidability` 里算 `_untraced_pool` 那段。

  **根因**：池评估（`_assess_decidability_from_pool_view`）**已经**算好
  并把 `_und_untraced` 放进返回值（v1.21.61 起），合并路径又拿
  `undecidable_aspects` + `evidence` **重算了一遍** —— 「同一逻辑两处
  各写一份」，本项目反复栽的坑。v1.21.69 [D] 刚改了
  `_untraced_undecidable` 的阈值（`_UNTRACED_OVERLAP`），两处要么都改、
  要么都不改，迟早分叉。

  **做法**：优先读 `pool_res["_und_untraced"]`；**兜底** —— 调用方没带这个
  键时（历史数据 / 手造桩 / external-only 路径）退回重算一次，不静默吞。
  改前实测（`_probe_v70_six.py`，故意给一个与 evidence 矛盾的缓存值
  `["CACHED_SENTINEL"]`）：改前合并结果用的是**重算值**，改后用**缓存值**。

  **★ 一处顺带的语义修正（不是本项目标，但必须记）**：缓存值是用
  `_assess_decidability_from_pool_view` 里的**完整 evidence** 算的，而重算
  路径读的是 `pool_res["evidence"]` = `evidence[:8]`（**截断到 8 条**）。
  两者在 evidence 多于 8 条时会不一致 —— 复用缓存更准，方向上是对的。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **前置量化**：`_probe_v70_six.py`（接受目标 py 作参数），改前 / 改后各跑
  一次对表（`_probe_v70_before.txt` / `_probe_v70_after.txt`）—— 没有对照
  的"修好了"不算数。判据：F 的 trace 键从 1 组变 2 组、渲染行从 1 行变
  2 行；K 的 `entry=1` 从 false 变 true 且 `entry=all` 保持 true（不许
  回归）；G 的占位符从穿透变被挡；H 的单圈留痕字符数掉下来且正文不再
  泄漏；I 的提示出现；J 的 `cached_used` 从 false 变 true。

  **冒烟**：`SRC` → v1.21.70；新增 6 条（F/K/G/H/I/J），每条带**负对照**：
    · F：`struct_trace` 必须**仍有 2 条**（原样保留），且渲染断言要求两条
      轨迹行**同时**出现；
    · K：`entry=all` 的路径不许被改坏（两个方向都锁）；
    · G：全占位符时返回空表（不留残渣）+ 正常方面不被误杀；
    · H：超大字段只留长度 + **非超大字段（collision）正文仍必须在**；
    · I：说明文字在源码与输出里都在；
    · J：缓存被用 + 不带缓存时退回重算且**不崩**。

  ────────────────────────────────────────────────────────
  ★ v1.21.70 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.70.py（纯 CRLF）；smoke_test.py 加 6 条 check；
    `_probe_v70_six.py`（改前 / 改后同一支探针）；`v70_报告.md`；
    真跑 sidecar（`verif_V70.log/.json/.full.json`）。

  **改了 6 处代码**：F 轨迹拆两条 + 渲染拆两条；K 触发时机（抽
    `_append_coverage`）；G 占位符黑名单；H `_OVERSIZED`；I 一句提示；
    J 复用缓存 + 兜底。

  **刻意不做**：不动 `last_struct_coverage` 的语义（保模型输入不变）、
    不改 `_render_trace` 之外的产物结构、不动 docstring 里 v1.21.68 与
    v1.21.69 两段的**段序**（已知这两段次序颠倒 —— 68 在 69 前面，
    是 v1.21.69 引入的既有瑕疵；本版只**记录**不代改）。

'''

assert "\\" not in NEW_SEC, "新增 docstring 段里出现反斜杠，会让 __doc__ 断言失效"
s = s.replace(_old_sec, NEW_SEC + _old_sec, 1)
print("   ok [docstring 版本段] 已在最前插入 v1.21.70 段")

# ---- __version__ ----
_v_old = '__version__ = "1.21.69"'
assert s.count(_v_old) == 1, "__version__ 锚点不唯一"
s = s.replace(_v_old, '__version__ = "1.21.70"', 1)
print("   ok [__version__] 1.21.69 → 1.21.70")

# ---- 回写：LF → CRLF，双向断言 ----
assert s.count("\r") == 0, "替换后冒出裸 CR"
n_lf = s.count("\n")
assert n_lf > n_crlf_before, "补丁后行数没有增加（补丁没落地？）"
s = s.replace("\n", "\r\n")
assert s.count("\r\n") == s.count("\n") == n_lf, "CRLF 计数自检失败"
assert s.count("\r") == s.count("\r\n"), "回写后有裸 CR"
DST.write_bytes(s.encode("utf-8"))

# ---- 复核 ----
out = DST.read_bytes().decode("utf-8")
print(f"\n写盘：{DST.name}  {len(out.encode('utf-8'))} 字节 "
      f"/ {out.count(chr(13)+chr(10))} 行（CRLF）")
assert out.count("\r\n") == out.count("\n") == out.count("\r"), "行尾不纯"

print("\n各版本段起始行号序列（最新在最前）：")
for m in re.finditer(r"^v(1\.21\.\d+) 相对", out.replace("\r\n", "\n"), re.M):
    line = out.replace("\r\n", "\n")[:m.start()].count("\n") + 1
    print(f"   L{line:>6}  {m.group(0)}")

print("\n完成。")
