# -*- coding: utf-8 -*-
"""v1.23.44 · P-3：学习闭环 —— 阈值**自适应**（冷启感知），修「升级/遗忘恒 0」。

实测根因：playbook 3 条 `shadow` 卡在 `n_evidence=1 < _EML_PROMOTE_N(3)` ⇒ 永不升级；
`_EML_RETIRE_RECENCY=0.05` + halflife 14d ⇒ 需 age>60 天才遗忘 ⇒ 年轻库永不遗忘。
两者都是 SOTA 点名的失败模式（cold start / static thresholds，见 ReasoningBank、MemRL 综述）。

修法（配置式，**默认关 ⇒ 逐字零行为差**）：
  · `eml_promote(..., adaptive=False)`：adaptive 且库 < `_EML_COLD_LIB` ⇒ 晋升门槛降到 1
    （冷启期先让学到的条目能生效；质量闸 `quality_delta>=0` / contra 闸不变）；
  · `eml_sweep_forget(..., adaptive=False)`：adaptive 时退休门槛随库规模放大（大库才清得多）；
  · 新配置键 `memory.eml_adaptive`（默认 false）。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.44.py")

# ① 常量
C_OLD = '_EML_RETIRE_RECENCY = 0.05'
C_NEW = ('_EML_RETIRE_RECENCY = 0.05\n'
         '#: [P-3] 冷启阈值：库小于它时，adaptive 模式下晋升门槛降到 1\n'
         '#:   （否则早期条目永远停在 n_evidence=1 < 静态阈值 ⇒ 学习不闭环）。\n'
         '_EML_COLD_LIB = 20')

# ② eml_promote
P_SIG_OLD = ('def eml_promote(playbook: list, promote_n: int = _EML_PROMOTE_N) '
             '-> list:')
P_SIG_NEW = ('def eml_promote(playbook: list, promote_n: int = _EML_PROMOTE_N,\n'
             '                adaptive: bool = False) -> list:')
P_BODY_OLD = ('    changes = []\n'
              '    for e in (playbook or []):\n'
              '        if e.get("status") != "shadow":\n'
              '            continue')
P_BODY_NEW = ('    # ★ [P-3] 冷启自适应：`adaptive` 且库还小 ⇒ 晋升门槛降到 1。\n'
              '    #   SOTA：`cold start` + `static thresholds` 是学习回路的失败模式\n'
              '    #   （ReasoningBank / MemRL 综述）。默认 `adaptive=False` ⇒ 逐字不变。\n'
              '    _eff_n = int(promote_n)\n'
              '    if adaptive:\n'
              '        try:\n'
              '            if len(playbook or []) < int(_EML_COLD_LIB):\n'
              '                _eff_n = 1\n'
              '        except Exception:\n'
              '            _eff_n = int(promote_n)\n'
              '    changes = []\n'
              '    for e in (playbook or []):\n'
              '        if e.get("status") != "shadow":\n'
              '            continue')
P_CMP_OLD = '        if _n < int(promote_n):\n            continue'
P_CMP_NEW = '        if _n < _eff_n:\n            continue'

# ③ eml_sweep_forget
F_SIG_OLD = ('def eml_sweep_forget(playbook: list, now: float,\n'
             '                     halflife: float = _EML_HALFLIFE_DAYS,\n'
             '                     retire_recency: float = _EML_RETIRE_RECENCY,\n'
             '                     promote_n: int = _EML_PROMOTE_N) -> list:')
F_SIG_NEW = ('def eml_sweep_forget(playbook: list, now: float,\n'
             '                     halflife: float = _EML_HALFLIFE_DAYS,\n'
             '                     retire_recency: float = _EML_RETIRE_RECENCY,\n'
             '                     promote_n: int = _EML_PROMOTE_N,\n'
             '                     adaptive: bool = False) -> list:')
F_BODY_OLD = ('    out = []\n'
              '    for e in (playbook or []):\n'
              '        if e.get("status") not in ("shadow", "active"):\n'
              '            continue')
F_BODY_NEW = ('    # ★ [P-3] adaptive：库越大退休门槛越高（大库才该多清）。\n'
              '    #   默认 `adaptive=False` ⇒ `_rr` 逐字等于传进来的 `retire_recency`。\n'
              '    _rr = float(retire_recency)\n'
              '    if adaptive:\n'
              '        try:\n'
              '            _rr = min(0.5, float(retire_recency)\n'
              '                      * (1.0 + len(playbook or [])\n'
              '                         / float(_EML_COLD_LIB)))\n'
              '        except Exception:\n'
              '            _rr = float(retire_recency)\n'
              '    out = []\n'
              '    for e in (playbook or []):\n'
              '        if e.get("status") not in ("shadow", "active"):\n'
              '            continue')
F_CMP_OLD = '        if _rec >= float(retire_recency):\n            continue'
F_CMP_NEW = '        if _rec >= _rr:\n            continue'


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    # ★ 先校验（AST + CRLF）再写 —— 免得写坏了才发现（本轮栽过一次）
    ast.parse(s2)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


def apply(s):
    for nm, old, new in (("常量", C_OLD, C_NEW),
                         ("promote 签名", P_SIG_OLD, P_SIG_NEW),
                         ("promote 体", P_BODY_OLD, P_BODY_NEW),
                         ("promote 比较", P_CMP_OLD, P_CMP_NEW),
                         ("forget 签名", F_SIG_OLD, F_SIG_NEW),
                         ("forget 体", F_BODY_OLD, F_BODY_NEW),
                         ("forget 比较", F_CMP_OLD, F_CMP_NEW)):
        n = s.count(old)
        assert n == 1, "%s 锚点 %d" % (nm, n)
        s = s.replace(old, new)
    # ④ 接线：读配置 + 传参
    a = '            _pn = int(_c.get("promote_n", _EML_PROMOTE_N) or 3)\n'
    assert s.count(a) == 1
    s = s.replace(a, a + '            _ad = bool(_c.get("eml_adaptive", False))\n', 1)
    b = '            _blk["promoted"] = eml_promote(_pb, promote_n=_pn)\n'
    assert s.count(b) == 1
    s = s.replace(b, '            _blk["promoted"] = eml_promote(\n'
                     '                _pb, promote_n=_pn, adaptive=_ad)\n', 1)
    c = '                               eml_sweep_forget(_pb, _now, promote_n=_pn)]\n'
    assert s.count(c) == 1
    s = s.replace(c, '                               eml_sweep_forget(\n'
                     '                                   _pb, _now, promote_n=_pn,\n'
                     '                                   adaptive=_ad)]\n', 1)
    # ⑤ 配置键
    d = '    "memory": {\n'
    assert s.count(d) == 1, "memory 锚点 %d" % s.count(d)
    s = s.replace(d, d
                  + '        # [P-3] 学习闭环阈值自适应（冷启感知）：默认 false = 关 ⇒ 逐字不变。\n'
                    '        "eml_adaptive": False,\n', 1)
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    for tok, want in (("_EML_COLD_LIB = 20", 1),
                      ("adaptive: bool = False) -> list:", 2),
                      ('"eml_adaptive": False,', 1),
                      ("_eff_n = 1", 1),
                      ("adaptive=_ad", 2)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] P-3 补丁已落 | 纯 CRLF | AST OK")
