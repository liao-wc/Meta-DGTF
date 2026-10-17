# -*- coding: utf-8 -*-
"""v1.23.53 → v1.23.54：并行跑次也能被**墙钟预算**截住、也能**续跑**。

问题：
  · `max_minutes` 只在 `_run_serial` 的**层间**判 ⇒ 并行模式（A/B/C + D~H）
    **完全不受墙钟约束**：设了预算也照跑到天亮（宿主一回收就全丢）。
  · `load_resume_snapshot` 硬拒非 serial ⇒ 并行跑次被强杀后**没法续**。

修法：
  1) 新增 `_wall_clock_over()`，serial 层间守卫改用它（**一处实现**）。
  2) **三个**单层执行器的圈边界都判墙钟（漏一个，那些模式就还是裸跑）：
       · `_run_layer`（serial + A/B）
       · C 模式自己的圈循环
       · `_run_layer_stage`（D~H）
     到点 ⇒ 该层进 `_paused_rest` + `stop_reason` 带「墙钟预算」标记。
     ★ `stop_reason` 是**逐圈在循环体末尾**拼的，圈首 break 会跳过那一步
       ⇒ 标记必须**直接盖到 view 上**（第一版漏了，判据当场逮到：续跑什么都不重跑）。
  3) serial 层间守卫从「重绑」改「**并集**」：截断层有 view 但仍未跑完，
     重绑会把它丢掉（续跑就当它完成了）。
  4) `load_resume_snapshot`：不再拒绝并行快照，改记源模式；并把 `stop_reason`
     带「墙钟预算」的层从 views/pools **摘掉**（截断层不算完成，续跑重跑它）。
  5) `run()` 派发：**并行续跑一律按 serial 跑剩余层**，产物记 `resumed_serial`。
     理由：`_run_parallel_stage` 的 `_results` 由并发填，没有"半个"状态可续；
     复用已完成层才是目的。**降级留痕，不静默。**

无新配置键；`max_minutes` 默认 0 / 不传 `resume_ckpt` ⇒ 逐字零行为差。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.53.py"
DST = HERE / "元DGTF-V1.23.54.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


MARK = '"墙钟预算到点（第 %d 圈截断，续跑会重跑这一层）"'

# ── 1) 唯一实现：墙钟到点 ───────────────────────────────────────────
rep('    def _budget_exhausted(self) -> bool:\n',
    '    def _wall_clock_over(self) -> bool:\n'
    '        """墙钟预算是否到点（`max_minutes` 默认 0 ⇒ 恒 False）。\n'
    '\n'
    '        ★ 与 `_budget_exhausted`（**调用次数**）不是一把尺子：那个是钱，\n'
    '          这个是时间 —— 防的是"宿主把进程回收掉"。\n'
    '        ★ 为什么收成一个方法：原来 serial 里内联了一份，各层执行器再各写一份\n'
    '          就会漂（本项目"同一语义两处定义"的老毛病）。\n'
    '        """\n'
    '        _mx = float(getattr(self, "_max_minutes", 0.0) or 0.0)\n'
    '        if _mx <= 0:\n'
    '            return False\n'
    '        return (time.time() - float(getattr(self, "_t0", 0.0) or 0.0)\n'
    '                ) >= _mx * 60.0\n'
    '\n'
    '    def _budget_exhausted(self) -> bool:\n',
    "新增 _wall_clock_over")

# ── 2) serial 层间守卫改用它 ────────────────────────────────────────
rep('            _mx = float(getattr(self, "_max_minutes", 0.0) or 0.0)\n'
    '            if _mx > 0 and (time.time() - float(getattr(self, "_t0", 0.0) or 0.0)\n'
    '                            ) >= _mx * 60.0:\n',
    '            _mx = float(getattr(self, "_max_minutes", 0.0) or 0.0)\n'
    '            if self._wall_clock_over():\n',
    "serial 层间改用统一判据")

# ── 3a) `_run_layer`（serial + A/B）圈边界 ──────────────────────────
rep('            if r > 0 and self._budget_exhausted():\n'
    '                self._note_budget_stop(f"本层跑到第 {r} 圈")\n'
    '                break\n',
    '            if r > 0:\n'
    '                _wc = self._wall_clock_over()\n'
    '                if _wc or self._budget_exhausted():\n'
    '                    # ★ 墙钟与调用次数**不是一把尺子**；墙钟到点必须能被续跑认出来。\n'
    '                    #   ★ `_budget_stop_note` 是实例级（并发下可能串到别的层），\n'
    '                    #     与既有"调用次数预算"口径一致，不额外引入新语义。\n'
    '                    if _wc:\n'
    '                        self._budget_stop_note = (\n'
    '                            ' + MARK + ' % (r + 1))\n'
    '                        self.vp(f"\\n   ⏸ {self._budget_stop_note}，提前收尾"\n'
    '                                f"（不是自然停止）")\n'
    '                        if entry not in self._paused_rest:\n'
    '                            self._paused_rest.append(entry)\n'
    '                        # ★ [截断标记] `stop_reason` 是**逐圈在循环体末尾**拼的，\n'
    '                        #   圈首 break 会跳过那一步 ⇒ 必须直接盖到 view 上，\n'
    '                        #   否则续跑认不出这一层被截断（第一版就这么假修了）。\n'
    '                        if view is not None:\n'
    '                            _pv = str(getattr(view, "stop_reason", "") or "")\n'
    '                            view.stop_reason = (\n'
    '                                (_pv + "；") if _pv else ""\n'
    '                            ) + self._budget_stop_note\n'
    '                    else:\n'
    '                        self._note_budget_stop(f"本层跑到第 {r} 圈")\n'
    '                    break\n',
    "_run_layer 圈边界判墙钟（serial + A/B）")

# ── 3b) C 模式单层圈边界 ────────────────────────────────────────────
rep('                if r > start_r and self._budget_exhausted():\n'
    '                    self._note_budget_stop(f"C 模式 {entry} 跑到第 {r} 圈")\n'
    '                    state["stopped"] = True\n'
    '                    break\n',
    '                if r > start_r:\n'
    '                    _wc = self._wall_clock_over()\n'
    '                    if _wc or self._budget_exhausted():\n'
    '                        self._note_budget_stop(\n'
    '                            f"C 模式 {entry} 跑到第 {r} 圈"\n'
    '                            + ("（墙钟预算到点）" if _wc else ""))\n'
    '                        if _wc:\n'
    '                            state["stop_reason"] = (\n'
    '                                ' + MARK + ' % r)\n'
    '                            if entry not in self._paused_rest:\n'
    '                                self._paused_rest.append(entry)\n'
    '                            if state.get("view") is not None:\n'
    '                                state["view"].stop_reason = state["stop_reason"]\n'
    '                        state["stopped"] = True\n'
    '                        break\n',
    "C 模式圈边界判墙钟")

# ── 3c) D~H 单层圈边界 ──────────────────────────────────────────────
rep('                if r > start_r and self._budget_exhausted():\n'
    '                    self._note_budget_stop(\n'
    '                        f"{self._parallel_label} 模式 {entry} 跑到第 {r} 圈")\n'
    '                    state["stopped"] = True\n'
    '                    break\n',
    '                if r > start_r:\n'
    '                    _wc = self._wall_clock_over()\n'
    '                    if _wc or self._budget_exhausted():\n'
    '                        self._note_budget_stop(\n'
    '                            f"{self._parallel_label} 模式 {entry} 跑到第 {r} 圈"\n'
    '                            + ("（墙钟预算到点）" if _wc else ""))\n'
    '                        if _wc:\n'
    '                            state["stop_reason"] = (\n'
    '                                ' + MARK + ' % r)\n'
    '                            if entry not in self._paused_rest:\n'
    '                                self._paused_rest.append(entry)\n'
    '                            if state.get("view") is not None:\n'
    '                                state["view"].stop_reason = state["stop_reason"]\n'
    '                        state["stopped"] = True\n'
    '                        break\n',
    "D~H 圈边界判墙钟")

# ── 3d) serial 层间守卫：并集而非重绑 ───────────────────────────────
rep('                self._paused_rest = [e for e in dispatch["order"]\n'
    '                                     if e not in self._results]\n',
    '                _rest = [e for e in dispatch["order"]\n'
    '                         if e not in self._results]\n'
    '                # ★ 截断层**有 view 但仍未跑完** ⇒ 必须并进待续（重绑会丢掉它，\n'
    '                #   续跑于是把它当"已完成"复用 —— 分片跑永远跑不完整）。\n'
    '                for _x in list(getattr(self, "_paused_rest", None) or []):\n'
    '                    if _x not in _rest:\n'
    '                        _rest.append(_x)\n'
    '                self._paused_rest = _rest\n',
    "serial 层间守卫改并集")

# ── 4) 续跑入口：允许并行快照 + 摘掉截断层 ──────────────────────────
rep('    _m0 = str(_d.get("mode") or "")\n'
    '    if mode and mode != "serial":\n'
    '        _out["why"] = "本版只支持 serial 的续跑（本次 mode=%s）" % mode\n'
    '        return _out\n'
    '    if _m0 and _m0 != "serial":\n'
    '        _out["why"] = "快照来自 mode=%s（本版只支持 serial）" % _m0\n'
    '        return _out\n',
    '    # ★ [并行续跑] 并行模式的快照**也能续**：剩余层一律按 serial 跑\n'
    '    #   （`run()` 里降级并记 `resumed_serial`）。`_run_parallel_stage` 的\n'
    '    #   `_results` 由并发填、没有"半个"状态可续；而复用已完成层才是目的。\n'
    '    #   这里不再拒绝，只把源模式**记下来**（留痕用）。\n'
    '    _m0 = str(_d.get("mode") or "")\n'
    '    _out["src_mode"] = _m0 or "serial"\n',
    "续跑入口放开并行")

rep('    _out["ok"] = True\n'
    '    if _bad:\n',
    '    # ★ [截断层不算完成] 墙钟预算截断的层带标记 ⇒ 从 views/pools 里摘掉，\n'
    '    #   续跑时重跑它。不摘的话"分片跑"永远跑不完整：每次都复用那个半层。\n'
    '    _tr = []\n'
    '    for _e in list(_out["views"]):\n'
    '        _v = _out["views"][_e]\n'
    '        if "墙钟预算" in str(getattr(_v, "stop_reason", "") or ""):\n'
    '            _tr.append(_e)\n'
    '    for _e in _tr:\n'
    '        _out["views"].pop(_e, None)\n'
    '        _out["pools"].pop(_e, None)\n'
    '    if _tr:\n'
    '        _out["truncated"] = _tr\n'
    '        _out["why"] = ("墙钟预算截断的层不算完成（续跑会重跑）：%s"\n'
    '                       % "、".join(_tr))\n'
    '    _out["ok"] = True\n'
    '    if _bad:\n',
    "摘掉截断层")

# ── 5) 派发：并行续跑降级为 serial ─────────────────────────────────
rep('        if mode == "A":\n'
    '            packed = self._run_parallel_A(question, route, keep,\n'
    '                                          rounds_plan, channels)\n',
    '        # ★ [续跑] 并行模式续跑**一律按 serial 跑剩余层**：复用已完成层才是\n'
    '        #   续跑的目的；`_run_parallel_stage` 的 `_results` 由并发填、没有\n'
    '        #   "半个"状态可续。产物记 `resumed_serial` —— **降级留痕，不静默**。\n'
    '        _resume_serial = bool(\n'
    '            (getattr(self, "_resume", None) or {}).get("views")) \\\n'
    '            and mode != "serial"\n'
    '        if _resume_serial:\n'
    '            packed = self._run_serial(question, route, keep,\n'
    '                                      rounds_plan, channels)\n'
    '        elif mode == "A":\n'
    '            packed = self._run_parallel_A(question, route, keep,\n'
    '                                          rounds_plan, channels)\n',
    "派发：续跑降级 serial")

rep('        # ★ 停心跳 + 落最后一份（dispatch 已返回 ⇒ 这一跑有了结果）\n',
    '        if isinstance(packed, dict) and _resume_serial:\n'
    '            packed["resumed_serial"] = mode\n'
    '        # ★ 停心跳 + 落最后一份（dispatch 已返回 ⇒ 这一跑有了结果）\n',
    "产物记 resumed_serial")

# ── 6) 版本号两处 ───────────────────────────────────────────────────
rep("元 DGTF · v1.23.53\n", "元 DGTF · v1.23.54\n", "docstring 标题")
rep('__version__ = "1.23.53"\n', '__version__ = "1.23.54"\n', "__version__")

# ── 结构性自检 ──────────────────────────────────────────────────────
ast.parse(s)
assert s.count("def _wall_clock_over(self) -> bool:") == 1
assert s.count("self._wall_clock_over()") == 4, s.count("self._wall_clock_over()")
assert 'if _mx > 0 and (time.time()' not in s, "serial 还留着内联版本"
assert s.count("_resume_serial") == 3, s.count("_resume_serial")
assert '"truncated"' in s
# 写侧三处、读侧一处，且都认同一个标记词
assert s.count(MARK) == 3, s.count(MARK)
assert s.count('"墙钟预算" in str(getattr(_v, "stop_reason"') == 1
# 三处都必须把标记**盖到 view 上**（只写 note 不进产物 = 假修）
assert s.count('_pv = str(getattr(view, "stop_reason", "") or "")') == 1
assert s.count('state["view"].stop_reason = state["stop_reason"]') == 2
print("  [OK] 结构性自检：判据唯一 · 三处执行器全部覆盖 · 标记盖到 view")

n1 = s.count("\n")
assert n1 > n0
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
