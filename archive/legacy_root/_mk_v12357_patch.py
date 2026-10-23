# -*- coding: utf-8 -*-
"""v1.23.56 → v1.23.57：把 `goal_trace` **跨圈接上**（`stop.gain_floor` 才能走到）。

问题：
  引擎**每圈新建 view**（`view = dg.run(inp)`），而 `_layer_goal_now` 把当圈读数
  append 到**当圈那个 view** 的 `goal_trace` 上 ⇒ 下一圈换对象，上一圈就丢。
  产物实测：跑 4~7 圈，`goal_trace` 每层只有 **1** 条。

  后果：`layer_gain_stop_signal` 的第一道门是 `len(prev) >= _LG_STOP_FLAT_N+1`（=3），
  而它拿到的 `prev = view.goal_trace` **恒 1 条** ⇒ 门恒关 ⇒
  **`stop.gain_floor` 在任何取值下都不会触发**（不是阈值太严，是通道断了）。

修法（**只搬数据，不动判据**）：
  · 引擎级每层历史 `self._goal_hist[entry]`，`_layer_goal_now` 追加到它；
  · 每圈把**完整历史**挂回当前 view（`view.goal_trace = list(_h)`）⇒ 判据才看得到 3 条。
  · `run()` 起跑时清空 `_goal_hist`（同一实例可能被复用；跨窗口从快照重新积累）。

无新配置键；`gain_floor` 默认 0（关）⇒ 出厂行为**逐字不变**（判据根本不去看那条历史）。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.56.py"
DST = HERE / "元DGTF-V1.23.57.py"

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


# ── 1) 每层历史 + 挂回当前 view ────────────────────────────────────
rep('        view.goal_trace.append(_rec)\n'
    '        try:\n'
    '            view.goal_now = dict(_d)\n'
    '        except Exception:\n'
    '            pass\n'
    '        return _d\n',
    '        # ★ [跨圈携带] 引擎**每圈新建 view**（`view = dg.run(inp)`），把读数只\n'
    '        #   append 到当圈那个 view 上 ⇒ 下一圈换对象、历史就丢。产物实测：跑 4~7 圈，\n'
    '        #   `goal_trace` 每层只有 1 条。而「早停单标量」判据的第一道门要求 ≥3 条历史\n'
    '        #   ⇒ `stop.gain_floor` **在任何取值下都不会触发**（通道断了，不是阈值严）。\n'
    '        #   所以历史挂在**引擎**上（每层一条 list），每圈把完整历史挂回当前 view。\n'
    '        _hist = getattr(self, "_goal_hist", None)\n'
    '        if _hist is None:\n'
    '            _hist = {}\n'
    '            self._goal_hist = _hist\n'
    '        _h = _hist.setdefault(str(entry), [])\n'
    '        _h.append(_rec)\n'
    '        try:\n'
    '            view.goal_trace = list(_h)\n'
    '        except Exception:\n'
    '            view.goal_trace.append(_rec)\n'
    '        try:\n'
    '            view.goal_now = dict(_d)\n'
    '        except Exception:\n'
    '            pass\n'
    '        return _d\n',
    "_layer_goal_now 跨圈携带")

# ── 2) run() 起跑清空历史 ─────────────────────────────────────────
rep('        self._ck_base = {"calls": 0, "tokens": 0}\n',
    '        self._ck_base = {"calls": 0, "tokens": 0}\n'
    '        # ★ [跨圈携带] 每层目标读数历史（`_layer_goal_now` 追加）；同一实例可能\n'
    '        #   被复用跑多次，起跑必须清空 —— 否则上一跑的读数会污染本跑的早停判据。\n'
    '        self._goal_hist = {}\n',
    "run() 清空 _goal_hist")

# ── 3) 版本号 ─────────────────────────────────────────────────────
rep("元 DGTF · v1.23.56\n", "元 DGTF · v1.23.57\n", "docstring 标题")
rep('__version__ = "1.23.56"\n', '__version__ = "1.23.57"\n', "__version__")

ast.parse(s)
assert s.count("self._goal_hist = _hist") == 1
assert s.count("view.goal_trace = list(_h)") == 1
assert s.count("self._goal_hist = {}") == 1
# 旧的一行 append 只应留在兜底分支里（1 处）
assert s.count("view.goal_trace.append(_rec)") == 1, s.count("view.goal_trace.append(_rec)")
print("  [OK] 结构性自检：历史挂引擎 · 每圈挂回 view · 起跑清空")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
