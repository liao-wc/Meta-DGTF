# -*- coding: utf-8 -*-
"""v1.23.43 · P-2：早停 —— 单标量 refinement_gain + 配置式阈值。

SOTA：最优停止 = **单一、阶段无关阈值 α⋆**（arXiv:2608.10729）—— 把策略搜索降到一个标量。
本版给那条标量提**信号** `refinement_gain`（各层用自己的目标读数，增量方向统一成「越大越有进展」），
并以**配置式**阈值 `stop.gain_floor`（**默认 0 = 关 ⇒ 逐字零行为差**）当停止判据。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.43.py")

NEW_FNS = '''

def refinement_gain(entry: str, goal: dict, prev: list = None):
    """[P-2 早停] 单标量**增益**：本轮相对上轮，本层目标读数的**独立进度增量**。

    SOTA（arXiv:2608.10729「Optimal Stopping of Self-Refining FMs」）证明：自反式
    迭代的最优停止策略是**单一、阶段无关的阈值** α⋆（把策略搜索降到一个标量）。
    本函数给那条标量提**信号**：各层用**自己**的目标读数，增量方向统一成
    「越大 = 越有进展」——
      · `excavate`（修行，越小越接近挖尽）⇒ 增益 = 上一圈 − 本圈；
      · `settle` / `fuse` / `crystallize`（越大越好）⇒ 增益 = 本圈 − 上一圈。
    返回 0–1 标量；**没读数 / 没有上一圈 ⇒ None**（不表态，不假装 0）。
    """
    _e = str(entry or "")
    _k = _LG_KEYS.get(_e)
    if not _k:
        return None
    _cur = _lg_num((goal or {}).get(_k))
    if _cur is None:
        return None
    _tr = list(prev or [])
    _pv = _lg_num((_tr[-1] or {}).get(_k)) if _tr else None
    if _pv is None:
        return None
    _d = (_pv - _cur) if _e == "0" else (_cur - _pv)
    return round(max(0.0, min(1.0, _d)), 4)


def layer_gain_stop_signal(entry: str, goal: dict, prev: list = None,
                           gain_floor: float = 0.0):
    """[P-2 早停] `refinement_gain` < `gain_floor`**连续 `_LG_STOP_FLAT_N` 圈** ⇒ 停。

    ★ 配置式：`gain_floor = 0`（默认）⇒ 直接 `(False, "")` —— **逐字零行为差**。
    """
    _gf = float(gain_floor or 0.0)
    if _gf <= 0:
        return False, ""
    _tr = list(prev or [])
    if len(_tr) < int(_LG_STOP_FLAT_N) + 1:
        return False, ""
    for _k in range(int(_LG_STOP_FLAT_N)):
        _i = len(_tr) - 1 - _k
        _g = refinement_gain(str(entry), _tr[_i], _tr[:_i] or None)
        if _g is None or _g >= _gf:
            return False, ""
    return True, ("本层再跑增益趋零（单标量 refinement_gain < %.3f 连续 %d 圈，"
                  "迭代已饱和）" % (_gf, int(_LG_STOP_FLAT_N)))

'''

METH_OLD = '''    def _goal_stop_signal(self, entry: str, view):
        """[四层目标 → 停因] 读 `view.goal_trace`，返回 `(hit, why)`。"""
        _tr = list(getattr(view, "goal_trace", None) or [])
        _now = _tr[-1] if _tr else {}
        return layer_goal_stop_signal(str(entry), _now, _tr)'''

METH_NEW = '''    def _goal_stop_signal(self, entry: str, view):
        """[四层目标 → 停因] 读 `view.goal_trace`，返回 `(hit, why)`。

        ★ [P-2] 先问**逐层**判据；未命中再看**单标量**早停（`stop.gain_floor`，
          默认 0 = 关 ⇒ 零行为差）。
        """
        _tr = list(getattr(view, "goal_trace", None) or [])
        _now = _tr[-1] if _tr else {}
        _hit, _why = layer_goal_stop_signal(str(entry), _now, _tr)
        if _hit:
            return _hit, _why
        _gf = 0.0
        try:
            _gf = float((self.config.get("stop") or {}).get(
                "gain_floor", 0.0) or 0.0)
        except Exception:
            _gf = 0.0
        if _gf > 0:
            return layer_gain_stop_signal(str(entry), _now, _tr, _gf)
        return _hit, _why'''


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    path.write_bytes(s2.replace("\n", "\r\n").encode("utf-8"))
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return chk.decode("utf-8")


def apply(s):
    # ① 新函数：插在 `layer_goal_stop_signal` 定义**之前**（同区，模块级）
    a = "def layer_goal_stop_signal(entry: str, goal: dict, prev: list = None):"
    assert s.count(a) == 1, "锚点 %d" % s.count(a)
    s = s.replace(a, NEW_FNS.strip("\n") + "\n\n\n" + a, 1)
    # ② 接线
    assert s.count(METH_OLD) == 1, "方法锚点 %d" % s.count(METH_OLD)
    s = s.replace(METH_OLD, METH_NEW)
    # ③ 配置键 stop.gain_floor
    ca = '    "stop": {\n'
    assert s.count(ca) == 1, "stop 锚点 %d" % s.count(ca)
    s = s.replace(ca, ca
                  + '        # [P-2] 单标量早停阈值：refinement_gain < 它连续 N 圈 ⇒ 停。\n'
                    '        #   0 = 关（默认，逐字不变）。依据 arXiv:2608.10729（最优停止）。\n'
                    '        "gain_floor": 0.0,\n', 1)
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    for tok, want in (("def refinement_gain(entry: str", 1),
                      ("def layer_gain_stop_signal(entry: str", 1),
                      ('"gain_floor": 0.0,', 1),
                      ("layer_gain_stop_signal(str(entry), _now, _tr, _gf)", 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] P-2 补丁已落 | 纯 CRLF | AST OK")
