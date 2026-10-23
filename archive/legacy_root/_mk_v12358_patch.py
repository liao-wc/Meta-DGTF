# -*- coding: utf-8 -*-
"""v1.23.57 → v1.23.58：把**晋升门槛 `_eff_n` 与每个 shadow 的拦截原因**出口。

问题（§十 审计留下的洞）：
  `eml_promote` 里 `_eff_n`（自适应后的实际门槛）只活在函数内部，产物里没有。
  于是「库 11 < 冷启 20 ⇒ 门槛降到 1，但被质量闸挡下」这句话**只是推断**，
  产物里查不到。**"我推断它降到了 1" 和 "产物里写着 1" 是两件事。**

修法（**不动返回值，只多收一个 trace**）：
  · `eml_promote(..., trace=None)`：传了就填 `eff_n` / `promote_n` / `adaptive` /
    `n_lib` / `cold_lib` / `shadow`（逐条 verdict）/ `shadow_verdicts`（分类计数）；
  · 调用方把它挂成 `_blk["promote_trace"]`（进产物）；
  · 产物 md 正文加一行「晋升门槛 + shadow 拦截分类」（四出口之一）。

无新配置键；不传 `trace` ⇒ 行为逐字不变（默认 None）。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.57.py"
DST = HERE / "元DGTF-V1.23.58.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


# ── 1) 签名加 trace ───────────────────────────────────────────────
rep('def eml_promote(playbook: list, promote_n: int = _EML_PROMOTE_N,\n'
    '                adaptive: bool = False) -> list:\n',
    'def eml_promote(playbook: list, promote_n: int = _EML_PROMOTE_N,\n'
    '                adaptive: bool = False, trace: dict = None) -> list:\n',
    "eml_promote 签名加 trace")

# ── 2) 函数体：记录每个 shadow 的去向 ─────────────────────────────
OLD_BODY = '''    changes = []
    for e in (playbook or []):
        if e.get("status") != "shadow":
            continue
        _n = int(e.get("n_evidence", 0) or 0)
        _qd = float(e.get("quality_delta", 0.0) or 0.0)
        _cd = float(e.get("cost_delta", 0.0) or 0.0)
        if _n < _eff_n:
            continue
        if int(e.get("contra", 0) or 0) >= int(promote_n):
            continue
        # ★ 只省成本 / 质量下降 ⇒ 不许升级（防「学坏」）
        if _qd < 0:
            continue
        if _qd == 0.0 and _cd < 0.0:
            changes.append({"id": e.get("id"), "to": "blocked_cost_only"})
            continue
        e["status"] = "active"
        e["weight"] = min(1.0, 0.5 + 0.25 * _n)
        changes.append({"id": e.get("id"), "to": "active"})
    return changes
'''
NEW_BODY = '''    changes = []
    _sh = []
    for e in (playbook or []):
        if e.get("status") != "shadow":
            continue
        _n = int(e.get("n_evidence", 0) or 0)
        _qd = float(e.get("quality_delta", 0.0) or 0.0)
        _cd = float(e.get("cost_delta", 0.0) or 0.0)
        # ★ [拦截留痕] 每条 shadow 都记下"它卡在哪"，否则「0 升级」这个结果
        #   看起来像是"没有东西可升"，实际可能是"有 3 条但都被质量闸挡住"。
        _row = {"id": e.get("id"), "n_evidence": _n,
                "contra": int(e.get("contra", 0) or 0),
                "quality_delta": round(_qd, 3), "cost_delta": round(_cd, 3)}
        if _n < _eff_n:
            _row["verdict"] = "n_short"
            _sh.append(_row)
            continue
        if int(e.get("contra", 0) or 0) >= int(promote_n):
            _row["verdict"] = "contra"
            _sh.append(_row)
            continue
        # ★ 只省成本 / 质量下降 ⇒ 不许升级（防「学坏」）
        if _qd < 0:
            _row["verdict"] = "quality_down"
            _sh.append(_row)
            continue
        if _qd == 0.0 and _cd < 0.0:
            _row["verdict"] = "cost_only"
            _sh.append(_row)
            changes.append({"id": e.get("id"), "to": "blocked_cost_only"})
            continue
        e["status"] = "active"
        e["weight"] = min(1.0, 0.5 + 0.25 * _n)
        _row["verdict"] = "promoted"
        _sh.append(_row)
        changes.append({"id": e.get("id"), "to": "active"})
    if trace is not None:
        # ★ 只读汇总，不改任何判定；不传 trace ⇒ 这段不执行 ⇒ 逐字零行为差。
        try:
            _cnt = {}
            for _r in _sh:
                _k = str(_r.get("verdict") or "?")
                _cnt[_k] = _cnt.get(_k, 0) + 1
            trace["eff_n"] = int(_eff_n)
            trace["promote_n"] = int(promote_n)
            trace["adaptive"] = bool(adaptive)
            trace["n_lib"] = len(list(playbook or []))
            trace["cold_lib"] = int(_EML_COLD_LIB)
            trace["shadow"] = _sh
            trace["shadow_verdicts"] = _cnt
        except Exception:
            pass
    return changes
'''
rep(OLD_BODY, NEW_BODY, "eml_promote 逐条留痕 + 汇总")

# ── 3) 调用方挂进产物 ─────────────────────────────────────────────
rep('''            _blk["promoted"] = eml_promote(
                _pb, promote_n=_pn, adaptive=_ad)
''',
    '''            _pt = {}
            _blk["promoted"] = eml_promote(
                _pb, promote_n=_pn, adaptive=_ad, trace=_pt)
            # ★ [读数出口] 门槛与拦截分类进产物；空 dict 也留着（= 没有 shadow）
            _blk["promote_trace"] = _pt
''',
    "调用方挂 promote_trace")

# ── 4) 产物 md 正文加一行（四出口） ───────────────────────────────
rep('''            f.write(f"  - 跑后过闸新增 {len(_pbk.get('merged') or [])} 条 / "
                    f"被闸拒 {len(_pbk.get('gated_out') or [])} 条 / "
                    f"升级 {len(_pbk.get('promoted') or [])} / "
                    f"遗忘 {len(_pbk.get('retired') or [])} / "
                    f"库内 {_pbk.get('n_playbook', 0)} 条\\n")
''',
    '''            f.write(f"  - 跑后过闸新增 {len(_pbk.get('merged') or [])} 条 / "
                    f"被闸拒 {len(_pbk.get('gated_out') or [])} 条 / "
                    f"升级 {len(_pbk.get('promoted') or [])} / "
                    f"遗忘 {len(_pbk.get('retired') or [])} / "
                    f"库内 {_pbk.get('n_playbook', 0)} 条\\n")
            # ★ [晋升门槛] 说明「0 升级」到底是"没东西可升"还是"有但被挡住"。
            _pt = _pbk.get("promote_trace") or {}
            if _pt:
                _dn = int(_pt.get("eff_n") or 0)
                _pn2 = int(_pt.get("promote_n") or 0)
                _note = "（名义 %d" % _pn2
                if bool(_pt.get("adaptive")) and _dn != _pn2:
                    _note += "；自适应：库 %s < 冷启 %s ⇒ 降到 %d" % (
                        _pt.get("n_lib"), _pt.get("cold_lib"), _dn)
                _note += "）"
                _vs = _pt.get("shadow_verdicts") or {}
                _vtx = "、".join("%s×%d" % (k, v)
                                for k, v in sorted(_vs.items())) or "无 shadow"
                f.write("      ↳ 晋升门槛 ≥%d%s｜shadow 拦截：%s\\n"
                        % (_dn, _note, _vtx))
''',
    "产物 md 加晋升门槛行")

# ── 5) 版本号 ─────────────────────────────────────────────────────
rep("元 DGTF · v1.23.57\n", "元 DGTF · v1.23.58\n", "docstring 标题")
rep('__version__ = "1.23.57"\n', '__version__ = "1.23.58"\n', "__version__")

ast.parse(s)
assert s.count("trace: dict = None") == 1
assert s.count('_blk["promote_trace"] = _pt') == 1
assert s.count('_row["verdict"] = "n_short"') == 1
assert s.count("晋升门槛 ≥%d%s") == 1
print("  [OK] 结构性自检：trace 参数 · 五类 verdict · 产物挂载 · md 出口")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
