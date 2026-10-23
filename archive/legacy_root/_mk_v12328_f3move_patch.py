# -*- coding: utf-8 -*-
"""v1.23.28 补丁 · F3 回填时序修正。

【问题】F3 把 `View.belief_items` 的回填放在 `_apply_view_to_pool_locked`
  **中部**，而信念条目是**在其后的 `pool.add_undecidable(...)` 里才 upsert
  进池的** ⇒ 回填读 `pool.belief_items` 时池还是空的 ⇒ `view.belief_items`
  恒 `[]`（真跑 6 条信念全部落在池里，但两个 view 都写着 0 条）。

【真跑证据】outputs/20261013_152451_*.packed.json
  pools.1.belief_items n=6（text 完整）
  views.1.amps[0].desc 与 belief_items[0].text **逐字相同**
  但 views.1.belief_items n=0
  ⇒ 不是「匹配键对不上」，是「回填时条目还没进池」= **时序颠倒**。

【修法】**搬移**，不改逻辑：
  ① 从方法中部整块删除回填；
  ② 在 `pool.add_undecidable(...)` 之后（方法末尾 `return` 之前）重新插入。
  ⇒ 唯一变化是执行时点。匹配键、判据、异常兜底一律不变。

【红线自检】CRLF 往返 / 锚点命中 == 1 / write_bytes / CRCRLF=0 / AST。
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.28.py"


def _load(p):
    b = p.read_bytes()
    n_crlf = b.count(b"\r\n")
    n_lf = b.count(b"\n")
    assert n_crlf == n_lf, "非纯 CRLF：CRLF=%d LF_total=%d" % (n_crlf, n_lf)
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n"), b


def _save(p, txt, orig_bytes):
    assert "\r\r\n" not in txt
    out = txt.replace("\n", "\r\n").encode("utf-8")
    p.write_bytes(out)
    b2 = p.read_bytes()
    assert b2.count(b"\r\n") == b2.count(b"\n"), "回写后非纯 CRLF"
    assert b2.count(b"\r\r\n") == 0, "回写后含 CRCRLF"
    print("  [write] %s  %d -> %d bytes" % (p.name, len(orig_bytes), len(b2)))


def _once(txt, anchor, tag):
    n = txt.count(anchor)
    assert n == 1, "[%s] 锚点命中 %d 次（要求 == 1）" % (tag, n)
    return n


def main():
    txt, ob = _load(TGT)

    # ---------- ① 删除中部回填块 ----------
    BLK = (
        '        # [D1 回填] `View.belief_items` 之前是**声明了、也出口了、但从不\n'
        '        #   被赋值**的死字段（`View.to_dict = asdict(self)` ⇒ 该键恒 []）。\n'
        '        #   这里把该层**本轮产出**的信念条目回填给 view：\n'
        '        #   ★ 只回填**与本次 view 相关**的条目（按 text 精确命中），\n'
        '        #     不是把全池倒给每个 view —— view 是「这一圈看到了什么」。\n'
        '        #   ★ 命中不到就保持 []（不猜、不兜底）。\n'
        '        try:\n'
        '            _seen_keys = set()\n'
        '            for _a in (view.amps or []):\n'
        '                _t0 = str(_a.get("desc") or _a.get("text") or "").strip()\n'
        '                if _t0:\n'
        '                    _seen_keys.add(_t0)\n'
        '            for _t0 in (view.anchor_touched or []):\n'
        '                _t0 = str(_t0.get("text") or _t0.get("desc") or "").strip()\n'
        '                if _t0:\n'
        '                    _seen_keys.add(_t0)\n'
        '            if _seen_keys:\n'
        '                _bind = []\n'
        '                for _it in (pool.belief_items or []):\n'
        '                    if str(_it.get("text", "")).strip() in _seen_keys:\n'
        '                        _bind.append(_it)\n'
        '                if _bind:\n'
        '                    view.belief_items = _bind\n'
        '        except Exception:\n'
        '            pass\n'
    )
    _once(txt, BLK, "F3-move-remove")
    txt = txt.replace(BLK, "", 1)
    print("  [F3-move] 已从方法中部删除回填块")

    # ---------- ② 在 add_undecidable 之后重新插入 ----------
    A2 = (
        '            pool.add_undecidable(\n'
        '                _und_prod,\n'
        '                und_aspects=und_aspects, layer=layer,\n'
        '                covered_aspects=list(\n'
        '                    getattr(view, "covered_aspects", None) or []))\n'
        '        return rephrased_streak, meta_idle_streak\n'
    )
    _once(txt, A2, "F3-move-insert-after-add-undecidable")

    NEW = (
        '            pool.add_undecidable(\n'
        '                _und_prod,\n'
        '                und_aspects=und_aspects, layer=layer,\n'
        '                covered_aspects=list(\n'
        '                    getattr(view, "covered_aspects", None) or []))\n'
        '        # [D1 回填 · 时序修正] `View.belief_items` 之前是**声明了、也出口了、\n'
        '        #   但从不被赋值**的死字段（`View.to_dict = asdict(self)` ⇒ 键恒 []）。\n'
        '        #   ★ 回填**必须放在 `add_undecidable` 之后** —— 信念条目是那一步才\n'
        '        #     upsert 进池的；放前面读到的池还是空的（真跑实测恒 []，\n'
        '        #     见 v12328_报告.md §2.5）。这是「有接线 ≠ 这跑走得到」的时序版。\n'
        '        #   ★ 只回填**与本次 view 相关**的条目（按 text 精确命中），\n'
        '        #     不是把全池倒给每个 view —— view 是「这一圈看到了什么」。\n'
        '        #   ★ 命中不到就保持 []（不猜、不兜底）。\n'
        '        try:\n'
        '            _seen_keys = set()\n'
        '            for _a in (view.amps or []):\n'
        '                _t0 = str(_a.get("desc") or _a.get("text") or "").strip()\n'
        '                if _t0:\n'
        '                    _seen_keys.add(_t0)\n'
        '            for _t0 in (view.anchor_touched or []):\n'
        '                _t0 = str(_t0.get("text") or _t0.get("desc") or "").strip()\n'
        '                if _t0:\n'
        '                    _seen_keys.add(_t0)\n'
        '            if _seen_keys:\n'
        '                _bind = []\n'
        '                for _it in (pool.belief_items or []):\n'
        '                    if str(_it.get("text", "")).strip() in _seen_keys:\n'
        '                        _bind.append(_it)\n'
        '                if _bind:\n'
        '                    view.belief_items = _bind\n'
        '        except Exception:\n'
        '            pass\n'
        '        return rephrased_streak, meta_idle_streak\n'
    )
    txt = txt.replace(A2, NEW, 1)
    print("  [F3-move] 已在 add_undecidable 之后重新插入回填块")

    # ---------- AST 自检 ----------
    ast.parse(txt)
    print("  [AST] parse OK")

    _save(TGT, txt, ob)
    print("补丁完成。")


if __name__ == "__main__":
    main()
