#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 补丁第 4 段：⑫ 多样性预算（Ashby）+ ⑬ nogoods 矛盾档案（ftl-beliefs）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.32.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


def main():
    s = _load()

    # ⑫ 多样性预算：落 packed（放在 _pack_result 尾部，dispatch 已填）
    s = rep(s, '''        _ar = self._anchor_report_for_pack(results)
        if _ar is not None:
            _pack["external_anchor"] = _ar
        return _pack''',
            '''        _ar = self._anchor_report_for_pack(results)
        if _ar is not None:
            _pack["external_anchor"] = _ar
        # ★ [多样性预算 · Ashby 必要多样性定律] 本跑实际动用的「层 × 通道」组合数。
        #   固定层×通道的多样性**有上限** —— 踩到上限时「跑得不好」不是工程缺陷，
        #   而是控制论上不可能。它是**读数**（提示谨慎读结论），不是分数。
        try:
            _mode_now = str((_pack.get("dispatch") or {})
                            .get("_parallel_mode") or "serial")
            _pack["diversity"] = diversity_budget(
                results, getattr(self, "channels", None), _mode_now)
        except Exception:
            _pack["diversity"] = {}
        return _pack''',
            "多样性预算落 pack")

    # ⑬ nogoods 文件名常量
    s = rep(s, '_EML_MEMORY_MD = "MEMORY.md"',
            '_EML_MEMORY_MD = "MEMORY.md"\n'
            '#: [nogoods 矛盾档案] **append-only 的矛盾库** —— 印证「矛盾不覆盖、只累积」\n'
            '#:   （ftl-beliefs 的 nogoods；本项目老坑：静默覆盖 = 下次没人知道发生过矛盾）。\n'
            '_EML_NOGOODS = "nogoods.jsonl"',
            "nogoods 常量")

    # ⑬ 写 nogoods：闸拒的候选 + 用了但读数不达标
    s = rep(s, '''            for _cd in _cands:
                _ok, _why = gate_check(_cd, _pb, promote_n=_pn)
                if not _ok:
                    _blk["gated_out"].append({"cand": _cd.get("action"),
                                              "why": _why})
                    continue''',
            '''            for _cd in _cands:
                _ok, _why = gate_check(_cd, _pb, promote_n=_pn)
                if not _ok:
                    _blk["gated_out"].append({"cand": _cd.get("action"),
                                              "why": _why})
                    # ★ [nogoods] 被闸拒的原因**留档**（append-only）——
                    #   矛盾/红线/无证据这三类如果只留在本次产物里，
                    #   下次没人知道它们发生过。
                    if _why in ("redline", "evidence", "verifiable",
                                "contradiction"):
                        eml_append_jsonl(_dir / _EML_NOGOODS, {
                            "t": _now, "run": _ep.get("run_id"),
                            "kind": "gate_reject", "why": _why,
                            "cand": _cd.get("action") or {},
                        })
                    continue''',
            "nogoods 写入")

    # ⑬ 用了但读数不达标 ⇒ 也进 nogoods
    s = rep(s, '''            _blk["strengthen"] = self._eml_note_use(_pb, result)''',
            '''            _blk["strengthen"] = self._eml_note_use(_pb, result)
            try:
                _st = _blk.get("strengthen") or {}
                if int(_st.get("negative", 0) or 0) > 0:
                    eml_append_jsonl(_dir / _EML_NOGOODS, {
                        "t": _now, "run": _ep.get("run_id"),
                        "kind": "used_but_below_floor",
                        "n": int(_st.get("negative", 0) or 0),
                        "duty_med": _st.get("duty_med"),
                    })
            except Exception:
                pass''',
            "nogoods 记录负面使用")

    # ⑫ 产物渲染：多样性预算行（跟在成本两分之后）
    s = rep(s, '''        if _oc or _ec:
            f.write(f"**成本两分**: 跑本身 {_oc} 次 / "''',
            '''        # ★ [多样性预算] 读数：层 × 通道 组合数（Ashby 必要多样性定律）。
        _dv = result.get("diversity") or {}
        if _dv.get("combos"):
            f.write(f"**多样性预算**: 层 {_dv.get('layers')} × 通道 "
                    f"{_dv.get('channels')} = {_dv.get('combos')} 组合"
                    f"（模式 {_dv.get('mode')}）｜{_dv.get('note', '')}\\n")
        if _oc or _ec:
            f.write(f"**成本两分**: 跑本身 {_oc} 次 / "''',
            "多样性渲染")

    _save(s)
    print("OK 第 4 段（多样性预算 + nogoods）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert '_pack["diversity"] = diversity_budget(' in s2
    assert "_EML_NOGOODS" in s2
    assert "多样性预算" in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
