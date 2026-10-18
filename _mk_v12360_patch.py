# -*- coding: utf-8 -*-
"""v1.23.59 → v1.23.60：快照记**层内进度**（只记录，不改续跑行为）。

问题：
  现在检查点只在**层完成**时才有该层状态 ⇒ 一层跑到第 5 圈被杀，快照里只知道
  "这层没完成"，**不知道死在第几圈**，也拿不到该层的中途读数。
  估值时只能按"层"算，不能按"圈"算（而实测一层 4~7 圈，时长差 2 倍）。

修法（**只记不恢复**，`docs/圈内检查点-设计.md` 第 1 步）：
  · `_layer_goal_now`（三个执行器每圈都会走到这一处）顺手记 `_layer_progress[entry]`：
    `rounds_done` / `amps` / `threads` / `candidates` / `goal`（本圈读数）；
  · `_ckpt_snapshot` 把它与 `goal_hist`（跨圈目标读数历史）一起写进快照；
  · `run()` 起跑清空 `_layer_progress`。
  ★ **续跑一个字不改**：`load_resume_snapshot` 不读这两个字段，
    截断层照旧"整层重跑"。为什么不做圈内恢复 —— 见设计文档 §三
    （`seeds`/`carry` 由上一圈 View 派生、不是纯函数 ⇒ 续跑会得到另一条轨迹）。

无新配置键；只是多写两个字段。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.59.py"
DST = HERE / "元DGTF-V1.23.60.py"

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


# ── 1) 每圈记层内进度（一处挂载，三个执行器共用）────────────────────
rep('''        try:
            view.goal_trace = list(_h)
        except Exception:
            view.goal_trace.append(_rec)
''',
    '''        try:
            view.goal_trace = list(_h)
        except Exception:
            view.goal_trace.append(_rec)
        # ★ [层内进度] 三个执行器（serial / 并行 / 分层阶段）**每圈都会走到这里**
        #   ⇒ 在这一处记，一处覆盖全部。**只记录，不参与任何判定**。
        #   用途：被杀之后能看见"死在第几圈"，以及按圈而不是按层估预算。
        try:
            _prog = getattr(self, "_layer_progress", None)
            if _prog is None:
                _prog = {}
                self._layer_progress = _prog
            _prog[str(entry)] = {
                "rounds_done": int(getattr(view, "rounds_run", 0) or 0),
                "candidates": len(getattr(view, "candidates", None) or []),
                "amps": len(getattr(view, "amps", None) or []),
                "threads": len(getattr(view, "threads", None) or []),
                "goal": dict(_d or {}),
            }
        except Exception:
            pass
''',
    "_layer_goal_now 记层内进度")

# ── 2) 快照带上这两个字段 ─────────────────────────────────────────
rep('''           "n_views": len(views), "views": views, "pools": pools,
           "t": time.time()}''',
    '''           "n_views": len(views), "views": views, "pools": pools,
           # ★ [层内进度] 只给读的人看，**续跑不读它**（见 `docs/圈内检查点-设计.md`）
           "layer_progress": dict(getattr(engine, "_layer_progress", None) or {}),
           "goal_hist": {str(_k): list(_v or [])
                         for _k, _v in
                         (getattr(engine, "_goal_hist", None) or {}).items()},
           "t": time.time()}''',
    "_ckpt_snapshot 写层内进度 + goal_hist")

# ── 3) run() 起跑清空 ────────────────────────────────────────────
rep('''        self._goal_hist = {}
''',
    '''        self._goal_hist = {}
        # ★ [层内进度] 与 goal_hist 同源同清：同一实例可能被复用跑多次。
        self._layer_progress = {}
''',
    "run() 起跑清空 _layer_progress")

# ── 4) 版本号 ────────────────────────────────────────────────────
rep("元 DGTF · v1.23.59\n", "元 DGTF · v1.23.60\n", "docstring 标题")
rep('__version__ = "1.23.59"\n', '__version__ = "1.23.60"\n', "__version__")

ast.parse(s)
assert s.count('"layer_progress": dict(getattr(engine, "_layer_progress", None) or {})') == 1
assert s.count('"goal_hist": {str(_k): list(_v or [])') == 1
assert s.count("self._layer_progress = {}") == 1
assert s.count('_prog[str(entry)] = {') == 1
# ★ 续跑侧一个字没动：不读 layer_progress / goal_hist
assert s.count('_out["llm_calls"] = int(_d.get("llm_calls") or 0)') == 1
assert 'layer_progress' not in s.split("def load_resume_snapshot")[1].split("def ")[0]
print("  [OK] 结构性自检：写侧两字段 · 每圈记录 · 起跑清空 · 续跑侧未读")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
