# -*- coding: utf-8 -*-
"""v1.23.48 · P-3b：EML **commit 前语义近重合并**。

实测：`eml_merge_candidate` 只按**精确** `(kind, cond, action)` 去重（JSON 逐字相等）
⇒ 同一条经验只要**值差一点**（`delta=1` vs `2`、`rate=0.30` vs `0.31`）就另开一条
⇒ **冗余堆积**（SOTA 点名的 failure mode：noisy accumulation / redundancy）。

修法（配置式，**默认关 ⇒ 逐字零行为差**）：`semantic_merge=True` 时，精确键不中
再按**粗键**（`kind` + `cond.issue` + `action.key`）找已有条目 ⇒ 命中则并入（证据累加），
不再新开。★ 只影响「**要不要新开一条**」，不改任何学到的内容。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.48.py")

SIG_OLD = 'def eml_merge_candidate(playbook: list, cand: dict, now: float) -> dict:'
SIG_NEW = ('def eml_merge_candidate(playbook: list, cand: dict, now: float,\n'
           '                        semantic_merge: bool = False) -> dict:')

BODY_OLD = '''    _key = (cand.get("kind"),
            json.dumps(cand.get("cond") or {}, sort_keys=True),
            json.dumps(cand.get("action") or {}, sort_keys=True))
    for e in (playbook or []):
        _ek = (e.get("kind"),
               json.dumps(e.get("cond") or {}, sort_keys=True),
               json.dumps(e.get("action") or {}, sort_keys=True))
        if _ek == _key:'''
BODY_NEW = '''    _key = (cand.get("kind"),
            json.dumps(cand.get("cond") or {}, sort_keys=True),
            json.dumps(cand.get("action") or {}, sort_keys=True))
    # ★ [P-3b] 粗键（语义近重）：`kind` + `cond.issue` + `action.key` ——
    #   只比「这条经验是关于什么问题的、要动哪个开关」，不比**值**。
    #   `semantic_merge=True` 时，精确键不中再按它找 ⇒ 命中则并入（防冗余堆积）。
    #   ★ 默认 False ⇒ 下面这行等于 None，循环体与改前**逐字相同**（零行为差）。
    _coarse = None
    if semantic_merge:
        _coarse = (cand.get("kind"),
                   str((cand.get("cond") or {}).get("issue") or ""),
                   str((cand.get("action") or {}).get("key") or ""))
    for e in (playbook or []):
        _ek = (e.get("kind"),
               json.dumps(e.get("cond") or {}, sort_keys=True),
               json.dumps(e.get("action") or {}, sort_keys=True))
        if _ek != _key and _coarse is not None:
            _ck = (e.get("kind"),
                   str((e.get("cond") or {}).get("issue") or ""),
                   str((e.get("action") or {}).get("key") or ""))
            if _ck == _coarse:
                _ek = _key          # 粗键命中 ⇒ 当成「同一条」并入
        if _ek == _key:'''


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
    for nm, old, new in (("签名", SIG_OLD, SIG_NEW), ("去重体", BODY_OLD, BODY_NEW)):
        n = s.count(old)
        assert n == 1, "%s 锚点 %d" % (nm, n)
        s = s.replace(old, new)
    # 接线：读配置并传参
    c = '            _n0 = len(_pb)\n'
    assert s.count(c) == 1, "接线锚点 %d" % s.count(c)
    s = s.replace(c, c + '            _smerge = bool(_c.get("eml_semantic_merge", False))\n', 1)
    d = '                _ent = eml_merge_candidate(_pb, _cd, _now)\n'
    assert s.count(d) == 1, "merge 调用锚点 %d" % s.count(d)
    s = s.replace(d, '                _ent = eml_merge_candidate(\n'
                     '                    _pb, _cd, _now, semantic_merge=_smerge)\n', 1)
    # 配置键
    e = '        "eml_adaptive": False,\n'
    assert s.count(e) == 1, "配置锚点 %d" % s.count(e)
    s = s.replace(e, e + '        # [P-3b] commit 前语义近重合并（防冗余堆积）：默认 false = 关。\n'
                        '        "eml_semantic_merge": False,\n', 1)
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    for tok, want in (("semantic_merge: bool = False) -> dict:", 1),
                      ("_coarse = None", 1),
                      ('"eml_semantic_merge": False,', 1),
                      ("semantic_merge=_smerge)", 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] P-3b 补丁已落 | 纯 CRLF | AST OK")
