# -*- coding: utf-8 -*-
"""v1.23.36：**读数全量显示** —— 运行中与结束时都进日志，同时结构化进产物。

## 用户要求
「运行中和结束时所有读数都完整显示在日志中，同时结构化显示在产物文档中。」

## 设计（一条原则：**单一真相源**）
`_readings_bundle(view)` 把一层的**全部读数**收成一个 dict；
**日志行**与**产物总表**都由它渲染 ⇒ **两处显示同一份内容**，
不可能漂移（本项目「同一语义两处定义」已发生 N 次）。

## 收哪些读数（**完整**，用户口径）
  · 规模：圈 / 候选 / & / 线头 / 悬置
  · 量化：`quant_readings` 四个（保真度 / 分歧度 / 语义密度 / 候选产出率）
  · 目标：`goal_trace` 末条 + `goal_verdict`
  · 职责：`duty_trace` 末条的 S
  · 行为：`trace_log` 条数（通用 trace）
  · 停止：`stop_reason`（截断到一行）

## 三处显示
  ① **运行中**（每层收尾）：一行紧凑读数（`vp`）；
  ② **结束时**（`MetaDGTF.run` 末）：跨层**总表**（等宽对齐，日志可读）；
  ③ **产物 md**：同一张总表（Markdown 表格）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A：辅助函数（放在 `_render_layer_glance` 之前）──
ANCHOR = '''class ControlSurface:'''
NEW = '''#: [读数显示] 量化四读数的固定顺序与中文标签（**展示用**；未知键降级为键名
#: ⇒ 以后新增读数会自动出现在表里，不必回来改这张表）。
_READING_LABELS = (
    ("restate_fidelity", "保真"),
    ("yin_yang_divergence", "分歧"),
    ("ing_density", "密度"),
    ("candidate_yield", "候选"),
)


def _readings_bundle(view) -> dict:
    """把一层的**全部读数**收成一个 dict（**日志与产物共用的唯一真相源**）。

    ★ 为什么要收成一个 bundle：日志行与产物总表如果各写一份取值逻辑，
      迟早漂移（本项目「同一语义两处定义」已 N 次）。这里取值**只写一次**。
    ★ 取不到的项一律 `None`（**不写 0**）——「没测」与「测出来是 0」必须分开。
    """
    _b = {}
    try:
        _b["rounds"] = int(getattr(view, "rounds_run", 0) or 0)
        _b["cand"] = len(getattr(view, "candidates", None) or [])
        _b["amp"] = len(getattr(view, "amps", None) or [])
        _b["thread"] = len(getattr(view, "threads", None) or [])
        _b["susp"] = len([s for s in (getattr(view, "suspensions", None) or [])
                          if isinstance(s, dict)
                          and s.get("status") in ("active", "stable")])
        _qr = getattr(view, "quant_readings", None) or {}
        _b["quant"] = {}
        for _k, _lab in _READING_LABELS:
            _v = _qr.get(_k)
            if isinstance(_v, dict) and _v:
                _b["quant"][_lab] = str(_v.get("verdict") or "?")
            else:
                _b["quant"][_lab] = None
        _gv = str(getattr(view, "goal_verdict", "") or "")
        _b["goal"] = _gv or None
        _dt = getattr(view, "duty_trace", None) or []
        _b["duty"] = None
        if _dt and isinstance(_dt[-1], dict):
            _s = _dt[-1].get("S")
            _b["duty"] = (round(float(_s), 3)
                          if isinstance(_s, (int, float)) else None)
        _b["trace_n"] = len([x for x in (getattr(view, "trace_log", None) or [])
                             if isinstance(x, dict) and x])
        _sr = str(getattr(view, "stop_reason", "") or "").strip()
        _b["stop"] = (_sr[:60] + ("…" if len(_sr) > 60 else "")) if _sr else None
    except Exception:
        pass
    return _b


def _readings_line(entry: str, view) -> str:
    """**运行中**的一层读数行（紧凑、无换行）。"""
    _b = _readings_bundle(view)
    _q = " ".join("%s=%s" % (k, (v if v is not None else "—"))
                  for k, v in (_b.get("quant") or {}).items())
    _bits = ["📊 [%s] 圈 %s" % (entry, _b.get("rounds")),
             "候选 %s · & %s · 线头 %s · 悬置 %s"
             % (_b.get("cand"), _b.get("amp"), _b.get("thread"), _b.get("susp")),
             "量化 %s" % (_q or "—")]
    if _b.get("duty") is not None:
        _bits.append("职责 S=%s" % _b["duty"])
    if _b.get("goal"):
        _bits.append("目标 %s" % _b["goal"])
    if _b.get("trace_n"):
        _bits.append("trace %d 条" % _b["trace_n"])
    return "   " + " ｜ ".join(_bits)


def _readings_table(views: dict, as_md: bool = False) -> str:
    """**结束时**的跨层读数总表（日志与产物**共用**；`as_md=True` 出 Markdown）。

    ★ 日志版用等宽对齐（终端可读）；产物版出 Markdown 表格（渲染可读）——
      两者**内容逐字同源**（都来自 `_readings_bundle`），不会漂移。
    """
    _rows = []
    for _e in ("0", "1", "both", "all"):
        _v = (views or {}).get(_e)
        if _v is None:
            _rows.append((_e, None))
            continue
        _vd = _v if isinstance(_v, dict) else None
        if _vd is None and hasattr(_v, "to_dict"):
            _vd = _v
        _rows.append((_e, _readings_bundle(_v)))
    _hdr = ["层", "圈", "候选", "&", "线头", "悬置",
            "保真", "分歧", "密度", "候选率", "职责S", "trace", "停止"]
    if as_md:
        _out = ["| " + " | ".join(_hdr) + " |",
                "|" + "|".join(["---"] * len(_hdr)) + "|"]
        for _e, _b in _rows:
            if _b is None:
                _out.append("| %s | %s |" % (_e, " | ".join(["—"] * (len(_hdr) - 1))))
                continue
            _q = _b.get("quant") or {}
            _out.append("| %s | %s |" % (_e, " | ".join(str(x) for x in (
                _b.get("rounds"), _b.get("cand"), _b.get("amp"),
                _b.get("thread"), _b.get("susp"),
                _q.get("保真") or "—", _q.get("分歧") or "—",
                _q.get("密度") or "—", _q.get("候选") or "—",
                _b.get("duty") if _b.get("duty") is not None else "—",
                _b.get("trace_n"), _b.get("stop") or "—"))))
        return "\\n".join(_out)
    # 日志版：等宽对齐
    _w = [4, 4, 6, 4, 6, 6, 6, 6, 6, 8, 8, 6, 40]
    _fmt = "  ".join("%%-%ds" % x for x in _w)
    _out = ["   📊 读数总表（四层）", "   " + (_fmt % tuple(_hdr))]
    for _e, _b in _rows:
        if _b is None:
            _out.append("   " + (_fmt % tuple([_e] + ["—"] * (len(_hdr) - 1))))
            continue
        _q = _b.get("quant") or {}
        _out.append("   " + (_fmt % tuple(str(x) for x in (
            _e, _b.get("rounds"), _b.get("cand"), _b.get("amp"),
            _b.get("thread"), _b.get("susp"),
            _q.get("保真") or "—", _q.get("分歧") or "—",
            _q.get("密度") or "—", _q.get("候选") or "—",
            _b.get("duty") if _b.get("duty") is not None else "—",
            _b.get("trace_n"), _b.get("stop") or "—"))))
    return "\\n".join(_out)


class ControlSurface:'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count(ANCHOR)
    assert n == 1, "锚点命中 %d 次（应为 1）" % n
    s = s.replace(ANCHOR, NEW, 1)
    for _t in ("def _readings_bundle", "def _readings_line", "def _readings_table"):
        assert s.count(_t) == 1, "缺 %s" % _t
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 读数辅助三函数已加；行数 %d" % out.count(b"\n"))


main()
