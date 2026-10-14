# -*- coding: utf-8 -*-
"""P1c：`ControlSurface` **接线**（把 EML 的两处写入改经它）—— 顺带修审计 A2。

## 为什么必须接线（不是登记豁免）
审计判据「A2 死类已登记」抓到 `ControlSurface` **定义后零引用**。
登记豁免 = 把死代码合法化；而它本来就是**可控性的本体**（用户口径
「所有行为逻辑都有追溯和可控性」）⇒ **正确修法是让它真的被用**。

## 接哪里（唯一收口）
`_eml_apply` 已经在改 `rounds_plan` / `self._duty_floor` —— 那是 EML 的生效面。
把它们**改经 `self._control.write(...)`**：
  · 每次写入**必须带 `why` + `trace_ref`** ⇒ 可追溯；
  · **边界检查**（如 `rounds.<layer>` 不得超 `hard_max`）⇒ 可控；
  · 被拒也**留痕**（`refused`）⇒ 失败可见，不静默。

★ 行为差异（有意、且更安全）：原先 `+delta` 可以**超过** `hard_max`，
  现在**越界即拒并有留痕** —— 属「收紧到正确」而非「放宽」。
★ 仍**不写配置**（红线：建议与执行分开）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A：`MetaDGTF` 持有控制面（锚在它的 `__init__` 里一个唯一语句）──
#   先找 `_eml_apply` 定义处的类内位置，用「同类里已有的、唯一的赋值」做锚更稳；
#   这里锚在 `_eml_apply` 自身第一行，把创建放在它的**调用前**不可靠 ⇒
#   改为：锚 `_eml_apply` 定义行，在其**上方**插入一个惰性属性访问器（见 C）。
ANCHOR_APPLY = '''    def _eml_apply(self, rounds_plan: dict) -> list:'''

# ── B：`_eml_apply` 内部两处写入改经控制面 ──
OLD_ROUNDS = '''            if _key == "rounds_delta" and isinstance(rounds_plan, dict):
                _lyr = str(_a.get("layer") or "")
                _d = int(_a.get("delta", 1) or 1)
                if _lyr in rounds_plan:
                    _old = int(rounds_plan.get(_lyr) or 1)
                    rounds_plan[_lyr] = max(1, _old + _d)
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layer": _lyr, "rounds": "%d→%d"
                                     % (_old, rounds_plan[_lyr])})'''
NEW_ROUNDS = '''            if _key == "rounds_delta" and isinstance(rounds_plan, dict):
                _lyr = str(_a.get("layer") or "")
                _d = int(_a.get("delta", 1) or 1)
                if _lyr in rounds_plan:
                    _old = int(rounds_plan.get(_lyr) or 1)
                    _new = max(1, _old + _d)
                    # ★ 经**控制面**（唯一收口）：边界检查 + 必留痕（why/ref）。
                    #   越界/缺理由 ⇒ 拒 + 记 refused（**不静默**）。
                    if self._control.write(
                            "rounds.%s" % _lyr, _new,
                            why="EML rounds_delta（条目 %s）" % _it.get("id"),
                            trace_ref=_it.get("id")):
                        rounds_plan[_lyr] = _new
                        _it["applied"] = True
                        _applied.append({"id": _it["id"], "key": _key,
                                         "layer": _lyr, "rounds": "%d→%d"
                                         % (_old, _new)})'''
OLD_DUTY = '''            elif _key == "duty_floor":
                _fl = _a.get("floor")
                try:
                    self._duty_floor = float(_fl)
                except (TypeError, ValueError):
                    continue
                _it["applied"] = True
                _applied.append({"id": _it["id"], "key": _key,
                                 "floor": self._duty_floor})'''
NEW_DUTY = '''            elif _key == "duty_floor":
                try:
                    _fl = float(_a.get("floor"))
                except (TypeError, ValueError):
                    continue
                # ★ 同上：经控制面（0..1 边界 + 必留痕）。
                if self._control.write(
                        "duty_floor", _fl,
                        why="EML duty_floor（条目 %s）" % _it.get("id"),
                        trace_ref=_it.get("id")):
                    self._duty_floor = _fl
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "floor": self._duty_floor})'''

# ── C：惰性创建控制面（属性访问器，避免去碰 `__init__`）──
NEW_APPLY = '''    @property
    def _control(self) -> "ControlSurface":
        """[显式控制面] 惰性创建（挂在实例上，全程复用）。

        ★ 为什么用属性而不是在 `__init__` 里建：`__init__` 是热点路径且有多个
          早退分支，插错位置会「某些路径没有它」；属性访问器**天然覆盖所有路径**，
          且不改变 `__init__` 的既有行为（零行为差）。
        """
        _c = getattr(self, "_control_surf", None)
        if _c is None:
            _c = ControlSurface(self)
            self._control_surf = _c
        return _c

    def _eml_apply(self, rounds_plan: dict) -> list:'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((ANCHOR_APPLY, NEW_APPLY, "A 控制面属性"),
                          (OLD_ROUNDS, NEW_ROUNDS, "B rounds 接线"),
                          (OLD_DUTY, NEW_DUTY, "C duty 接线")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert s.count("self._control.write(") == 2, \
        "控制面写入点应为 2（实得 %d）" % s.count("self._control.write(")
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK ControlSurface 已接线（EML 两处写入改经它）；行数 %d"
          % out.count(b"\n"))


main()
