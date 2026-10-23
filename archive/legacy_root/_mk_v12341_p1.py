# -*- coding: utf-8 -*-
"""v1.23.41 · P1：修 `crystallize` 读数**时序颠倒**（恒 0.500）。

根因：`view.goal_verdict` 在 `_finalize_layer_common` **前段**（18145）从
`view.goal_now` 渲染，而 `goal_now` 由**圈循环内**的 `_layer_goal_now` 算
（那时元层的 `meta_closure` 还没落，见 18375）⇒ 元层「结晶 + 回看」两件事
永远数不到 ⇒ `crystallize` 恒 2/4 = 0.500。

修法（**零新 AST 符号**）：
  ① 抽 `_LG_LABELS` 模块常量（模块级 dict，**不算 AST 符号**）作唯一真相源；
  ② 删掉 18145 的内联渲染（唯一写入点移到收尾）；
  ③ 在 `_finalize_layer_common` **收尾**（`meta_closure` / 终局 settlement 都落定
     之后、`dump_final` 之前）**重算一次**读数并刷新 `view.goal_now` +
     `view.goal_verdict`。
★ **不动** `goal_trace`（逐圈留痕 = 「当时读到什么」的历史，必须保留）与
  停止判据（须用**当圈**读数才能实时决定）。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.41.py")


def _rw(path: Path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "非纯 CRLF: %s" % path.name
    assert b"\r\r\n" not in raw, "含 CRCRLF"
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s, "补丁后无变化"
    out = s2.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(out)
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return out


# ── ① 抽 _LG_LABELS 常量 ────────────────────────────────────────────
OLD_LBL = '''#: [层目标] 元层「回看」的最小留痕项数（结晶 + 决策 + 行动 + 回看 四件事）。
_LG_META_MIN = 4'''
NEW_LBL = '''#: [层目标] 元层「回看」的最小留痕项数（结晶 + 决策 + 行动 + 回看 四件事）。
_LG_META_MIN = 4
#: [层目标] 各层目标的**中文标签**（`goal_verdict` 渲染用，**唯一真相源**）。
#:   ★ 原先在 `_finalize_layer_common` 里内联了一份；P1 的收尾刷新要用同一份，
#:     故抽出来 —— 「同一语义两处定义 ⇒ 消掉一份」。
_LG_LABELS = {"0": "修行·挖尽", "1": "研究·收敛",
              "both": "对撞·融合", "all": "元·结晶"}'''

# ── ② 删 18145 内联渲染（唯一写入点移到收尾）────────────────────────
OLD_WRITE = '''        try:
            _gn = dict(getattr(view, "goal_now", None) or {})
            if _gn:
                _gk = _LG_KEYS.get(str(entry)) or ""
                _gv = _gn.get(_gk)
                if _gv is not None:
                    view.goal_verdict = "本层目标（%s）：%s=%.3f" % (
                        {"0": "修行·挖尽", "1": "研究·收敛",
                         "both": "对撞·融合", "all": "元·结晶"}.get(str(entry),
                                                                   str(entry)),
                        _gk, float(_gv))
        except Exception:
            pass'''
NEW_WRITE = '''        # ★ [P1 · 时序修正] `goal_verdict` 的**唯一写入点**已挪到本函数**收尾**
        #   （见下方「目标读数收尾刷新」）——理由：此处（前段）时元层的
        #   `meta_closure` 还没落（它在 183xx 才赋），从那时的 `goal_now` 渲染
        #   ⇒ 元层 `crystallize` 恒少数「结晶+回看」两件（恒 2/4=0.500）。'''

# ── ③ 收尾刷新（插在 dump_final 之前）──────────────────────────────
OLD_TAIL = '''        try:
            _dg.verbose = self.verbose
            _dg.dump_final(view)'''
NEW_TAIL = '''        # ★ [P1 · 目标读数收尾刷新] 本层的**全部产物此刻都已落定**（`meta_closure`
        #   在上面 `_settle_meta()` / `settle_research` 里赋过）⇒ 用**最终 view**
        #   重算一次目标读数，刷新 `goal_now` + `goal_verdict`。
        #   ★ 为什么不只在前段渲染：那是「圈循环内」的读数，对元层**结构性偏小**
        #     （结晶/回看两件事还没产生）⇒ 产物恒 `crystallize=0.500`。
        #   ★ 为什么不动 `goal_trace`：逐圈留痕必须保留「当时读到什么」的历史；
        #     为什么不动停止判据：停止必须用**当圈**读数才能实时决定。
        try:
            _vd_f = view.to_dict() if hasattr(view, "to_dict") else {}
            _fresh = layer_goal_readings({str(entry): _vd_f}).get(str(entry)) or {}
            if _fresh:
                view.goal_now = dict(_fresh)
                _gk_f = _LG_KEYS.get(str(entry)) or ""
                _gv_f = _fresh.get(_gk_f)
                if _gv_f is not None:
                    view.goal_verdict = "本层目标（%s）：%s=%.3f" % (
                        _LG_LABELS.get(str(entry), str(entry)), _gk_f,
                        float(_gv_f))
        except Exception:
            pass

        try:
            _dg.verbose = self.verbose
            _dg.dump_final(view)'''


def apply(s):
    for nm, old, new in (("_LG_LABELS", OLD_LBL, NEW_LBL),
                         ("18145 内联渲染", OLD_WRITE, NEW_WRITE),
                         ("收尾刷新", OLD_TAIL, NEW_TAIL)):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（要求 1）" % (nm, n)
        s = s.replace(old, new)
    # 自检
    for tok, want in (("_LG_LABELS = {", 1),
                      ("目标读数收尾刷新] 本层的", 1),
                      ("_fresh = layer_goal_readings({str(entry): _vd_f})", 1)):
        got = s.count(tok)
        assert got == want, "自检 %r 出现 %d 次（要求 %d）" % (tok, got, want)
    # 旧内联渲染必须已消失（只剩注释里的引用）
    assert s.count('{"0": "修行·挖尽", "1": "研究·收敛",') == 1  # 仅 _LG_LABELS
    return s


if __name__ == "__main__":
    out = _rw(TGT, apply)
    print("[ok] P1 补丁已落 | 行数", out.count(b"\n"), "| 纯 CRLF | AST OK")
