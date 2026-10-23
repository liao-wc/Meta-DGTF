# -*- coding: utf-8 -*-
"""v1.23.47 · P-2b：让早停阈值 α 由 AutoTune **跨跑学习**（只建议，不执行）。

依据：SOTA 点名 `static thresholds` 是学习回路的失败模式（ReasoningBank / MemRL）。
可行数据：episodes 带 `cut_layers`（哪些层被截断）+ `duty`（当时质量）。
判据：**被截断的层多、而当时质量不差 ⇒ 说明停得太晚**（白跑的圈）⇒ 建议**抬高** α。
★ 红线「建议与执行分开」：本函数**只出建议**；采纳仍走既有 `autotune_apply_to_cfg`。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.47.py")

FN = '''

def autotune_suggest_gain_floor(episodes: list, base: float = 0.0,
                                step: float = 0.01, min_n: int = 2,
                                quality_floor: float = _DUTY_FLOOR) -> dict:
    """[P-2b] 从历史跑**建议**一个早停阈值 α（`stop.gain_floor`）。

    逻辑（可解释、零猜测）：
      · 取**有截断记录**的 episodes（`cut_layers` 非空）；
      · 若这类 episode 的中位质量（`duty` 的 S）**不低于** `quality_floor`
        ⇒ 「被截断了但质量并没差」= 那些圈是**白跑**的 ⇒ 建议把 α **抬 `step`**；
      · 证据不足（< `min_n`）⇒ `ok=False` + why，**不建议**（不表态）。
    ★ 返回的 `suggested` **不是配置**，要采纳必须显式 `autotune_apply_to_cfg`
      （红线「建议与执行分开」）。
    """
    eps = list(episodes or [])
    _cut = []
    for e in eps:
        try:
            if e.get("cut_layers"):
                _s = None
                _d = e.get("duty") or {}
                if isinstance(_d, dict):
                    _s = _d.get("S")
                    if _s is None:
                        _ss = [v.get("S") for v in _d.values()
                               if isinstance(v, dict) and v.get("S") is not None]
                        _s = (sum(_ss) / len(_ss)) if _ss else None
                if _s is not None:
                    _cut.append(float(_s))
        except Exception:
            continue
    if len(_cut) < int(min_n):
        return {"ok": False, "suggested": None, "n": len(_cut),
                "why": "有截断且有质量读数的 episode 仅 %d < %d（不表态）"
                       % (len(_cut), int(min_n))}
    _cut.sort()
    _med = _cut[len(_cut) // 2]
    if _med >= float(quality_floor):
        return {"ok": True, "suggested": round(float(base) + float(step), 4),
                "n": len(_cut), "quality_med": round(_med, 4),
                "why": ("%d 次截断的中位质量 %.3f >= %.3f ⇒ 那些圈是白跑的，"
                        "建议 α 抬 %.3f" % (len(_cut), _med, quality_floor, step))}
    return {"ok": True, "suggested": round(float(base), 4), "n": len(_cut),
            "quality_med": round(_med, 4),
            "why": ("%d 次截断的中位质量 %.3f < %.3f ⇒ 截断伤了质量，"
                    "α 保持 %.3f" % (len(_cut), _med, quality_floor, base))}

'''

RET_OLD = '''    return {"phase": "learn", "ok": True, "corrections": corrections,
            "conclusion": conclusion, "evidence_strength": _strength,
            "archive_diversity": arc["diversity"],
            "open_ended": arc["open_ended"], "n_arms": len(arms)}'''
RET_NEW = '''    # ★ [P-2b] 顺带给一条**阈值建议**（只建议，不执行）。
    try:
        _sgf = autotune_suggest_gain_floor(episodes)
    except Exception:
        _sgf = {"ok": False, "suggested": None, "why": "算不出"}
    return {"phase": "learn", "ok": True, "corrections": corrections,
            "conclusion": conclusion, "evidence_strength": _strength,
            "archive_diversity": arc["diversity"],
            "open_ended": arc["open_ended"], "n_arms": len(arms),
            "suggested_gain_floor": _sgf.get("suggested"),
            "gain_floor_why": _sgf.get("why")}'''


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    ast.parse(s2)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


def apply(s):
    a = "def autotune_phase_learn(episodes: list, min_n: int = 2) -> dict:"
    assert s.count(a) == 1, "函数锚点 %d" % s.count(a)
    s = s.replace(a, FN.strip("\n") + "\n\n\n" + a, 1)
    n = s.count(RET_OLD)
    assert n == 1, "返回锚点 %d" % n
    s = s.replace(RET_OLD, RET_NEW)
    # ★ `learn` 的形参是 `episodes`（不是 `eps`）—— 用错会 NameError，且只在运行时炸
    assert "autotune_suggest_gain_floor(episodes)" in s
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    assert "autotune_suggest_gain_floor(eps)" not in t, "learn 段变量名写错"
    for tok, want in (("def autotune_suggest_gain_floor(episodes: list", 1),
                      ('"suggested_gain_floor": _sgf.get("suggested"),', 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] P-2b 补丁已落 | 纯 CRLF | AST OK")
