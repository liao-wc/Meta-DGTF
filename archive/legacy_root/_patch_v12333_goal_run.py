# -*- coding: utf-8 -*-
"""补丁 A：四层目标读数**进入每层每圈运行**（第一期 · 停止判据）。

背景（只读核查结论）：`layer_goal_readings` 原先只在 `episode_from_result`
（事后出口）被调用，**主循环零引用** ⇒ 四层目标只是「事后读数」，没有落到
「每层每圈的运行」里。本补丁把它接进**唯一停止判据实现** `_stop_reasons`
（与 `duty_streak` / `anytime_ok` 同构：调用方算 → 传参 → 内部加一条理由）。

四层目标停因（依据见 `layer_goal_readings` 的注释）：
  · 0 修行：`excavate` 边际新增率 < 0.1（Heaps 饱和 ⇒ 层面挖尽）
  · 1 研究：`settle` 连续 2 圈不涨（确定率不再涨）
  · both 对撞：`fuse` 连续 2 圈不涨 或 `sem_stagnation` ≥ 0.8（CORE 罚触顶）
  · all 元：`crystallize` == 1.0（四件事齐 = 结晶完成）

★ 红线遵守：
  · 没读数 ⇒ **不表态**（回 (False,"")，与「没测 ≠ 测出来差」同规）；
  · 只**加停止理由**，不改象限、不设 stopped（停止与清算分开）；
  · 逐圈序列全部留在 `view.goal_trace`（失败留痕）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

# ─────────────────────────────────────────────────────────────
# 1) 新纯函数：插在 `layer_goal_summary` 之后（模块级函数区）
# ─────────────────────────────────────────────────────────────
ANCHOR_1 = '''def layer_goal_summary(views: dict) -> dict:'''

PURE_FN = '''_LG_STOP_MARGIN = 0.1      # 修行层：边际新增率 < 此值 ⇒ 判「挖尽」
_LG_STOP_FLAT_N = 2        # 研究/对撞：连续 N 圈读数不涨 ⇒ 判「不再涨」
_LG_STOP_STAG = 0.8        # 对撞：语义停滞率 >= 此值 ⇒ 判「复读」


def layer_goal_stop_signal(entry: str, goal: dict, prev: list = None):
    """[四层目标 → 停因] 把「本层目标读数」转成一条**停止信号**。

    这是把四层目标**接进运行**的那一步：读数不再只是事后统计，而是每层每圈
    判断「这层还有没有必要再跑」的一条依据。

    返回 `(hit, why)`：
      · `hit=True` ⇒ 调用方给 `_stop_reasons` 加一条理由（**只加理由**）；
      · **没读数 ⇒ `(False, "")`** —— 不表态（「没测」与「测出来差」两回事）。

    逐层判据（依据见 `layer_goal_readings`）：
      · `0`  修行：`excavate` < `_LG_STOP_MARGIN`（Heaps 饱和 = 层面挖尽）
      · `1`  研究：`settle` 连续 `_LG_STOP_FLAT_N` 圈不涨（确定率不再涨）
      · `both` 对撞：`fuse` 连续不涨 **或** `sem_stagnation` >= 阈值（CORE 罚触顶）
      · `all` 元：`crystallize` >= 1.0（四件事齐 = 结晶完成）
    """
    g = goal or {}
    _e = str(entry or "")
    if _e == "0":
        _v = _lg_num(g.get("excavate"))
        if _v is None:
            return False, ""
        # ★ 只在「确有逐圈序列」时才对边际率下结论；n_aspects 缺 ⇒ 不表态。
        if _v < _LG_STOP_MARGIN and (_lg_num(g.get("n_aspects")) or 0) > 0:
            return True, ("修行目标已达成（层面边际新增率 %.3f < %.2f，"
                          "Heaps 饱和 ⇒ 挖到不能再挖）" % (_v, _LG_STOP_MARGIN))
        return False, ""
    if _e == "1":
        _v = _lg_num(g.get("settle"))
        if _v is None:
            return False, ""
        if _lg_flat(prev, "settle", _LG_STOP_FLAT_N):
            return True, ("研究目标已达成（确定率连续 %d 圈不涨 = %.3f，"
                          "各层面已有答案）" % (_LG_STOP_FLAT_N, _v))
        return False, ""
    if _e == "both":
        _stag = _lg_num(g.get("sem_stagnation"))
        if _stag is not None and _stag >= _LG_STOP_STAG:
            return True, ("对撞目标受阻（语义停滞率 %.2f >= %.2f，"
                          "只剩复读上游，没融合出新的层面）"
                          % (_stag, _LG_STOP_STAG))
        _v = _lg_num(g.get("fuse"))
        if _v is None:
            return False, ""
        if _lg_flat(prev, "fuse", _LG_STOP_FLAT_N):
            return True, ("对撞目标已达成（融合分连续 %d 圈不涨 = %.3f）"
                          % (_LG_STOP_FLAT_N, _v))
        return False, ""
    if _e == "all":
        _v = _lg_num(g.get("crystallize"))
        if _v is None:
            return False, ""
        if _v >= 1.0 - 1e-9:
            return True, ("元层目标已达成（记忆结晶/回看/决策/行动 四件齐备 "
                          "= %.2f）" % _v)
        return False, ""
    return False, ""


def _lg_flat(prev, key, n):
    """读数序列 `prev`（含当圈）里 `key` **连续 n 圈不涨** ⇒ True。

    · 序列不足 n+1 条 ⇒ False（**样本不足不表态**）；
    · 有任一读数为 None ⇒ False（缺读数不参与「不涨」判断）。
    """
    if not prev or len(prev) < int(n) + 1:
        return False
    _xs = []
    for row in prev[-(int(n) + 1):]:
        _x = _lg_num((row or {}).get(key))
        if _x is None:
            return False
        _xs.append(_x)
    return all(_xs[i + 1] <= _xs[i] + 1e-12 for i in range(len(_xs) - 1))


def _lg_num(x):
    """把读数转 float；**非数 ⇒ None**（不是 0 —— 没测 ≠ 测出来 0）。"""
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def layer_goal_summary(views: dict) -> dict:'''

# ─────────────────────────────────────────────────────────────
# 2) View 增 goal_trace 字段
# ─────────────────────────────────────────────────────────────
ANCHOR_2 = '''    duty_trace: List[dict] = field(default_factory=list)'''
REPLACE_2 = '''    duty_trace: List[dict] = field(default_factory=list)
    # ★ [四层目标] 逐圈目标读数序列（与 `duty_trace` 同构）。停因判据读它
    #   （连续不涨 = 该层目标不再推进）。
    goal_trace: List[dict] = field(default_factory=list)'''

# ─────────────────────────────────────────────────────────────
# 3) 新方法 _layer_goal_now（插在 _layer_duty_now 之前）
# ─────────────────────────────────────────────────────────────
ANCHOR_3 = '''    def _layer_duty_now(self, entry: str, view) -> dict:'''

METHOD = '''    def _layer_goal_now(self, entry: str, view) -> dict:
        """[四层目标] 在**停止/收敛处**算该层目标读数并记账（逐圈进
        `view.goal_trace`）。

        ★ 与 `_layer_duty_now` 同构：读数是**信号**不是分数；
          缺读数回 None（不假装 0）。**不改停止行为** —— 那由
          `layer_goal_stop_signal` 在 `_stop_reasons` 里决定。
        """
        if view is None:
            return {}
        try:
            from types import SimpleNamespace
            _vd = view.to_dict() if hasattr(view, "to_dict") else {}
            _d = layer_goal_readings({str(entry): _vd}).get(str(entry)) or {}
        except Exception:
            _d = {}
        _rec = {"round": int(getattr(view, "rounds_run", 0) or 0)}
        for _k in ("excavate", "settle", "fuse", "crystallize", "fuse_raw",
                   "sem_stagnation", "n_aspects", "n_new", "n_hits",
                   "pseudo_convergence", "converging", "conv_state"):
            if _k in _d:
                _rec[_k] = _d.get(_k)
        view.goal_trace.append(_rec)
        try:
            view.goal_now = dict(_d)
        except Exception:
            pass
        return _d

    def _goal_stop_signal(self, entry: str, view):
        """[四层目标 → 停因] 读 `view.goal_trace`，返回 `(hit, why)`。"""
        _tr = list(getattr(view, "goal_trace", None) or [])
        _now = _tr[-1] if _tr else {}
        return layer_goal_stop_signal(str(entry), _now, _tr)

    def _layer_duty_now(self, entry: str, view) -> dict:'''

# ─────────────────────────────────────────────────────────────
# 4) _stop_reasons 加入参 + 加理由
# ─────────────────────────────────────────────────────────────
ANCHOR_4 = '''                      duty_streak: int = 0,
                      anytime_ok: bool = False):'''
REPLACE_4 = '''                      duty_streak: int = 0,
                      goal_hit: bool = False,
                      goal_why: str = "",
                      anytime_ok: bool = False):'''

ANCHOR_5 = '''            _dpat = int(getattr(self, "_duty_patience", _DUTY_PATIENCE))
            if int(duty_streak or 0) >= _dpat:
                reasons.append(
                    f"职责增益收敛（连续 {int(duty_streak)} 圈 "
                    f"ΔS<{_DUTY_TAU}，对问题的贡献不再增长）")'''
REPLACE_5 = '''            _dpat = int(getattr(self, "_duty_patience", _DUTY_PATIENCE))
            if int(duty_streak or 0) >= _dpat:
                reasons.append(
                    f"职责增益收敛（连续 {int(duty_streak)} 圈 "
                    f"ΔS<{_DUTY_TAU}，对问题的贡献不再增长）")
            # ★ [四层目标 → 停因] 本层**目标读数**已达标/受阻 ⇒ 允许停。
            #   与上面两条的区别：duty 问「对问题的贡献」、anytime 问
            #   「结构是否还在长」；这条问的是**这层自己的目标**（修行=挖尽 /
            #   研究=收敛 / 对撞=融合 / 元=结晶）—— 三件事分开报。
            #   ★ 没读数 ⇒ goal_hit 恒 False ⇒ 零行为差（旧产物不受影响）。
            if goal_hit and goal_why:
                reasons.append(str(goal_why))'''

# ─────────────────────────────────────────────────────────────
# 5) 两条通道：算 → 传参
# ─────────────────────────────────────────────────────────────
ANCHOR_6 = '''            self._layer_duty_now(entry, view)
            _duty_streak = self._duty_marginal_streak(view)
            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。'''
REPLACE_6 = '''            self._layer_duty_now(entry, view)
            _duty_streak = self._duty_marginal_streak(view)
            # ★ [四层目标 → 每圈运行] 算本层目标读数并逐圈留痕，再转停止信号。
            self._layer_goal_now(entry, view)
            _goal_hit, _goal_why = self._goal_stop_signal(entry, view)
            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。'''

ANCHOR_7 = '''                duty_streak=_duty_streak, anytime_ok=_any_ok)
            if stop_reasons and rounds_n > 1:'''
REPLACE_7 = '''                duty_streak=_duty_streak,
                goal_hit=_goal_hit, goal_why=_goal_why,
                anytime_ok=_any_ok)
            if stop_reasons and rounds_n > 1:'''

ANCHOR_8 = '''        # ★ [LDG] 同上：先算职责读数，再把边际增益停滞圈数喂进判据。
        self._layer_duty_now(entry, view)
        _duty_streak = self._duty_marginal_streak(view)'''
REPLACE_8 = '''        # ★ [LDG] 同上：先算职责读数，再把边际增益停滞圈数喂进判据。
        self._layer_duty_now(entry, view)
        _duty_streak = self._duty_marginal_streak(view)
        # ★ [四层目标 → 每圈运行] 并行通道同样算（两通道一处实现）。
        self._layer_goal_now(entry, view)
        _goal_hit, _goal_why = self._goal_stop_signal(entry, view)'''

ANCHOR_9 = '''            duty_streak=_duty_streak, anytime_ok=_any_ok)
        state["prev_product"] = view.manifest or ""'''
REPLACE_9 = '''            duty_streak=_duty_streak,
            goal_hit=_goal_hit, goal_why=_goal_why,
            anytime_ok=_any_ok)
        state["prev_product"] = view.manifest or ""'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 主文件非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    pairs = [
        ("A1 纯函数", ANCHOR_1, PURE_FN),
        ("A2 View 字段", ANCHOR_2, REPLACE_2),
        ("A3 方法", ANCHOR_3, METHOD),
        ("A4 stop 入参", ANCHOR_4, REPLACE_4),
        ("A5 stop 加理由", ANCHOR_5, REPLACE_5),
        ("A6 串行算", ANCHOR_6, REPLACE_6),
        ("A7 串行传参", ANCHOR_7, REPLACE_7),
        ("A8 并行算", ANCHOR_8, REPLACE_8),
        ("A9 并行传参", ANCHOR_9, REPLACE_9),
    ]
    for name, old, new in pairs:
        n = s.count(old)
        if n != 1:
            print("X %s 锚点命中 %d 次（应为 1）" % (name, n)); sys.exit(1)
    for name, old, new in pairs:
        s = s.replace(old, new, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X 产物含 r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 补丁 A 已打：9 处锚点各命中 1 次")


if __name__ == "__main__":
    main()
