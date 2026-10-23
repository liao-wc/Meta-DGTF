#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 第二档] 把 `phase_p4` / `phase_p5` / `phase_p6` 接进 `_v122_verify.py`。

做法：三处 `phase_pN = _phase_todo("pN")` 占位**直接替换**成真实现
（占位函数名与真函数名同名，PHASES 里那三行不用动）。
★ 这样既保住了「未开档判红」的机制（p7 仍是占位），又不会漏注册。

★ 本文件不写反斜杠：换行用 chr(10)，引号用 chr(34)。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGET = Path("_v122_verify.py")
NL = chr(10)
CRLF = chr(13) + chr(10)
Q = chr(34)
SENTINEL = "def phase_p4(src, mod):"

P4 = '''def phase_p4(src, mod):
    """[v1.22.1 P4] 一致率 ON/OFF 对照。

    ★ P4.1 的「运行时开关」**在本引擎里早已存在**（v1.22.0 加的
      `_action_on(config, "tri_multi_vote")` + `DEFAULT_CONFIG.actions
      .tri_multi_vote`），本档因此**不需要改引擎**（rc2 与 rc1b 逐字节相同）。
      本函数只判「对照跑完了没 + 结论有没有如实给出」。
    """
    runs = HERE / "runs" / "v1221"
    rows = {}
    for arm in ("ON", "OFF"):
        vs = []
        for i in (1, 2, 3):
            mf = runs / ("p4_" + arm + "_" + str(i)) / "meta.json"
            if not mf.is_file():
                vs.append(None)
                continue
            try:
                d = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                vs.append(None)
                continue
            vs.append(d if d.get("ok") else None)
        rows[arm] = vs
    _ok = [d for arm in rows for d in rows[arm] if d]
    check("P4.1.a", len(_ok) == 6,
          "ON/OFF 各 3 次跑完（实测 " + str(len(_ok)) + "/6）")

    jf = HERE / "_v1221_p4_consistency.json"
    check("P4.1.b", jf.is_file(),
          "_v1221_p4_consistency.json 存在（先跑 `python _v1221_p4_agg.py`）")
    if not (_ok and jf.is_file()):
        return
    d = json.loads(jf.read_text(encoding="utf-8"))
    _on = [x["consistency"] for x in (d.get("ON") or [])]
    _off = [x["consistency"] for x in (d.get("OFF") or [])]
    check("P4.1.c", len(_on) == 3 and len(_off) == 3,
          "两条臂各 3 条一致率读数（" + str(len(_on)) + "/" + str(len(_off)) + "）")
    if not (_on and _off):
        return

    def _spread(v):
        return round(max(v) - min(v), 4)

    on_avg = sum(_on) / len(_on)
    off_avg = sum(_off) / len(_off)
    diff = on_avg - off_avg
    sp_on, sp_off = _spread(_on), _spread(_off)
    no_concl = max(sp_on, sp_off) >= abs(diff)
    if diff >= 0.10:
        verdict = "多票更好"
    elif abs(diff) < 0.05:
        verdict = "多票没做坏，也没做出改善"
    elif diff <= -0.05:
        verdict = "多票拖后腿"
    else:
        verdict = "落在 +5%~+10% 的灰带（P4.4 未给档）"
    if no_concl:
        verdict = "无结论（组内极差 ≥ 组间差）"
    print("  · P4 读数：ON 平均 " + format(on_avg, ".1%") + " / OFF 平均 "
          + format(off_avg, ".1%") + " / 差 " + format(diff, "+.1%"))
    print("  · P4 离散：ON 组内极差 " + format(sp_on, ".1%") + " / OFF 组内极差 "
          + format(sp_off, ".1%") + " → " + ("组内 ≥ 组间，无结论" if no_concl
                                            else "组间更大，差值可读"))
    print("  · P4 四档判定：" + verdict)

    rep = HERE / "v1221_p4_报告.md"
    if not rep.is_file():
        check("P4.2.a", False, "缺 v1221_p4_报告.md")
    else:
        t = rep.read_text(encoding="utf-8")
        check("P4.2.a", ("组内极差" in t) and ("组间差" in t),
              "报告含组内极差与组间差")
        _words = ("多票更好", "多票没做坏", "多票拖后腿", "无结论", "灰带")
        check("P4.2.b", any(w in t for w in _words),
              "报告给出四档之一（本档判定：" + verdict + "）")
    check("P4.3.a", all((x.get("md_reading") for x in _ok)),
          "6 份产物都取到了 md 口径的「三态多票」读数")


'''

P5 = '''def phase_p5(src, mod):
    """[v1.22.1 P5] auto 取向回填：判定写入产物头部 + 错配可查。"""
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)

    check("P5.1.a", "_auto_plan_used" in txt, "run() 记 _auto_plan_used")
    check("P5.1.b", "取向判定（plan_orientation）" in txt and "取向错配" in txt,
          "头部两行（取向判定 / 取向错配）都在")
    check("P5.1.c", Q + "_auto_plan_used" + Q in txt,
          "_pack_result 挂 _auto_plan_used")

    # auto_plan 的单调用分支必须带出 orientation（P5 的**前提**）
    _i0 = txt.find("def auto_plan(")
    _i1 = txt.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
    _body = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P5.2.a", ("data.get(" + Q + "orientation" + Q) in _body,
          "auto_plan 解析 orientation")
    check("P5.2.b", _body.count(Q + "orientation" + Q + ": _ori") >= 2,
          "auto_plan 的早退分支也带出 orientation")

    # 打桩行为：一次调用带出取向 + 只调一次 + 非法取向归一
    class _Stub:
        def __init__(self, ori):
            self.calls = []
            self.ori = ori

        def call(self, system, user, *a, **kw):
            self.calls.append((system, user))
            import json as _j
            return _j.dumps({"mode": "serial", "orientation": self.ori,
                             "rounds": {"0": 4, "1": 4, "both": 4, "all": 5},
                             "reason": "桩", "confidence": 0.9})

        def parse_json(self, raw):
            import json as _j
            return _j.loads(raw)

    try:
        _s1 = _Stub("boundary")
        _p1 = mod.auto_plan("地铁运营效率该怎么衡量？",
                            dict(mod.DEFAULT_CONFIG), llm=_s1)
        _s2 = _Stub("随便")
        _p2 = mod.auto_plan("x", dict(mod.DEFAULT_CONFIG), llm=_s2)
        check("P5.2.c", _p1.get("orientation") == "boundary"
              and len(_s1.calls) == 1 and not _p2.get("orientation")
              and "orientation" in _s1.calls[0][0],
              "打桩：带出 boundary / 只调一次 / prompt 要了取向 / 非法归一")
    except Exception as e:  # noqa: BLE001
        check("P5.2.c", False, type(e).__name__ + ": " + str(e))

    # 真跑证据
    _a = HERE / "outputs" / "p5_auto" / "meta.json"
    _b = HERE / "outputs" / "p5_boundary" / "meta.json"
    if not (_a.is_file() and _b.is_file()):
        check("P5.3.a", False, "缺 outputs/p5_auto 或 p5_boundary（先跑 _run_v1221_p56.py P5）")
        check("P5.3.b", False, "同上")
        check("P5.3.c", False, "同上")
        return
    _da = json.loads(_a.read_text(encoding="utf-8"))
    _db = json.loads(_b.read_text(encoding="utf-8"))
    _ha = _da.get("hits") or {}
    _hb = _db.get("hits") or {}
    check("P5.3.a", bool(_ha.get("取向判定（plan_orientation）")),
          "auto 真跑产物含「取向判定」（实测 " + json.dumps(_ha, ensure_ascii=False) + "）")
    check("P5.3.b", not _hb.get("取向错配"),
          "负对照：显式 boundary 时不含「取向错配」")
    _ori = ((_da.get("auto_plan_used") or {}).get("orientation") or "")
    _expect = (_ori not in ("", "decision"))
    check("P5.3.c", (not _expect) or bool(_ha.get("取向错配")),
          "auto 判为 " + repr(_ori) + " → 错配告警 "
          + ("应出现且已出现" if _expect else "不应出现（判成 decision）"))


'''

P6 = '''def phase_p6(src, mod):
    """[v1.22.1 P6] tier 全缺省时的显式提示（+ 红线：无 tier 不入引用表）。"""
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)
    check("P6.1.a", "_anchor_tier_warning" in txt and "锚点 tier 警告" in txt,
          "字段 + 头部行都在")
    check("P6.1.b", Q + "_anchor_tier_warning" + Q in txt,
          "_pack_result 挂 _anchor_tier_warning")

    # 关键：必须在**原始条目**上判「谁显式声明了 tier」，否则恒为 0
    check("P6.1.c", "_n_explicit_tier" in txt,
          "按原始条目计数显式 tier（任务书骨架在补过默认值的 out 上数，恒 0）")
    _i0 = txt.find("def _load_anchors")
    _i1 = txt.find(NL + "    def ", _i0 + 10) if _i0 >= 0 else -1
    _lb = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P6.1.d", "_n_explicit_tier" in _lb,
          "计数发生在 _load_anchors 内")

    _notier = HERE / "_verify_p6_notier.json"
    _onetier = HERE / "_verify_p6_onetier.json"
    _notier.write_bytes(json.dumps(
        {"anchors": [{"id": "a1", "claim": "x"},
                     {"id": "a2", "claim": "y"}]}, ensure_ascii=False)
        .encode("utf-8"))
    _onetier.write_bytes(json.dumps(
        {"anchors": [{"id": "a1", "claim": "x"},
                     {"id": "a2", "claim": "y", "tier": 1}]},
        ensure_ascii=False).encode("utf-8"))

    def _load(path):
        cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG, default=str))
        cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
        cfg["external_anchor"].update({"enabled": True, "path": str(path)})
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["verbose"] = False
        mm = mod.MetaDGTF(cfg)
        mm._load_anchors()
        return getattr(mm, "_anchor_tier_warning", "<无属性>")

    try:
        w_all, w_one = _load(_notier), _load(_onetier)
        check("P6.2.a", isinstance(w_all, str) and bool(w_all),
              "全缺省 → 有警告（正对照）")
        check("P6.2.b", not w_one, "有显式 tier → 无警告（负对照）")
    except Exception as e:  # noqa: BLE001
        check("P6.2.a", False, type(e).__name__ + ": " + str(e))
        check("P6.2.b", False, "同上")
    finally:
        for _f in (_notier, _onetier):
            try:
                _f.unlink(missing_ok=True)
            except OSError:
                pass

    # 红线：无 tier 的锚点即便挂 evidence 档也不进引用表
    try:
        _p1 = mod.Pool()
        _p1.anchors = [{"id": "a1", "claim": "X"}]
        _p1.anchor_as_evidence = True
        _t1 = mod._citation_table(None, _p1)
        _p2 = mod.Pool()
        _p2.anchors = [{"id": "a2", "claim": "Y", "tier": 1}]
        _p2.anchor_as_evidence = True
        _t2 = mod._citation_table(None, _p2)
        check("P6.3.a", (not any(c.startswith("X") for c, _ in _t1))
              and any(c.startswith("X") for c, _ in _t2),
              "红线：无 tier 不入表 / tier=1 入表")
    except Exception as e:  # noqa: BLE001
        check("P6.3.a", False, type(e).__name__ + ": " + str(e))

    # 真跑证据
    _a = HERE / "outputs" / "p6_notier" / "meta.json"
    _b = HERE / "outputs" / "p6_tier" / "meta.json"
    if not (_a.is_file() and _b.is_file()):
        check("P6.4.a", False, "缺 outputs/p6_notier 或 p6_tier（先跑 _run_v1221_p56.py P6）")
        check("P6.4.b", False, "同上")
        return
    _ha = (json.loads(_a.read_text(encoding="utf-8")).get("hits") or {})
    _hb = (json.loads(_b.read_text(encoding="utf-8")).get("hits") or {})
    check("P6.4.a", bool(_ha.get("锚点 tier 警告")),
          "真跑：全缺省锚点 → 产物含警告")
    check("P6.4.b", not _hb.get("锚点 tier 警告"),
          "负对照：有 tier 的锚点 → 产物不含警告")


'''

REPS = [
    ("phase_p4", 'phase_p4 = _phase_todo("p4")' + NL, P4),
    ("phase_p5", 'phase_p5 = _phase_todo("p5")' + NL, P5),
    ("phase_p6", 'phase_p6 = _phase_todo("p6")' + NL, P6),
]


def main() -> int:
    raw = TARGET.read_bytes()
    s = raw.decode("utf-8")
    if SENTINEL in s:
        print("  · 已应用（幂等跳过）")
        return 0
    assert s.count(CRLF) == s.count(NL), "行尾不纯"
    assert b"\r\r\n" not in raw, "含 CRCRLF"
    s = s.replace(CRLF, NL)
    for name, old, new in REPS:
        got = s.count(old)
        assert got == 1, "[" + name + "] 锚点命中 " + str(got) + " 次，期望 1"
        s = s.replace(old, new, 1)
        print("  ✓ " + name)
    ast.parse(s)
    out = s.replace(NL, CRLF)
    assert out.count(NL) == out.count(CRLF)
    assert "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    print("  ✓ 写回 " + TARGET.name + "（纯 CRLF）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
