#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2b] 把 `phase_p2b` 接进 `_v122_verify.py` 并注册到 PHASES。

★ 为什么必须显式注册：`main()` 里 `fn = PHASES.get(k); if not fn: continue`
  —— 没注册的 phase 会以 `PASS 0 / FAIL 0` 退出（**假绿**）。P2b 是本轮的
  主判据，绝不能以「没实现」混过去。

★ 一律用 chr(13)/chr(10) 拼行尾，**不在本文件里写反斜杠**
  （本项目反复踩过「多级转义吃掉一层反斜杠」的坑）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGET = Path("_v122_verify.py")
NL = chr(10)
CRLF = chr(13) + chr(10)
SENTINEL = "def phase_p2b"

FUNC = '''def phase_p2b(src, mod):
    """[v1.22.1 P2b] triage 端到端：answers 匹配路径（第二条门）。

    P2a 打通了「触发条件」，P2b 打通「匹配对象」：拿「缺什么」与锚点自己
    声明的「我能回答什么」比（`answers`），claim 老路径一字不动、取 OR。
    """
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)

    # ---------- P2b.1 锚点快照 ----------
    af = HERE / "_test_anchors.json"
    if not af.is_file():
        check("P2b.1.a", False, "_test_anchors.json 缺失")
    else:
        d = json.loads(af.read_text(encoding="utf-8"))
        ans = d.get("anchors") or []
        n_ans = sum(1 for a in ans if a.get("answers"))
        check("P2b.1.a", n_ans >= 2,
              "有 answers 的锚点 " + str(n_ans) + "/" + str(len(ans)) + " ≥ 2")
        over5 = [a.get("id") for a in ans if len(a.get("answers") or []) > 5]
        check("P2b.1.b", not over5, "单锚点 answers ≤ 5（超限 " + str(over5) + "）")
        over40 = [(a.get("id"), x) for a in ans
                  for x in (a.get("answers") or []) if len(x) > 40]
        check("P2b.1.c", not over40, "单条 answer ≤ 40 字（超长 " + str(over40) + "）")
        # 1.d 静态能力：≥1 条 answer 能在 tier 门内对上一条 [外] 侧面。
        #   参照集 = P2a 三题真跑的 14 条侧面（P2b 的立论依据就是这批读数）。
        _ref = []
        for i in (1, 2, 3):
            _mf = HERE / "outputs" / ("p2_run" + str(i)) / "meta.json"
            if _mf.is_file():
                try:
                    _ref += (json.loads(_mf.read_text(encoding="utf-8"))
                             .get("und_aspects") or [])
                except Exception:
                    pass
        if not _ref:
            check("P2b.1.d", False, "参照集为空（缺 P2a 的 outputs/p2_runN/meta.json）")
        else:
            _hits = []
            for a in ans:
                if int(a.get("tier", 3) or 3) > 2:
                    continue
                for x in (a.get("answers") or []):
                    for s0 in _ref:
                        if mod._hit_by_answers(str(s0), [x]):
                            _hits.append((a.get("id"), x))
            check("P2b.1.d", bool(_hits),
                  "tier 门内 ≥1 条 answer 能对上 [外] 侧面（实测 " + str(len(_hits))
                  + " 条；参照集 " + str(len(_ref)) + " 条）")
            for h in _hits[:3]:
                print("  · P2b.1.d 命中：" + str(h[0]) + " 的 " + repr(h[1]))

    # ---------- P2b.2 两个匹配函数 ----------
    check("P2b.2.a", hasattr(mod, "_hit_by_answers"), "_hit_by_answers 存在")
    check("P2b.2.b", hasattr(mod, "_hit_by_claim"), "_hit_by_claim 存在")
    _i0 = txt.find("def _hit_by_claim")
    _i1 = txt.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
    _bc = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P2b.2.c", "_similar(" in _bc and "0.6" in _bc,
          "claim 路径字面 0.6 未改（宪法级禁令）")
    _j0 = txt.find("def _hit_by_answers")
    _j1 = txt.find(NL + "def ", _j0 + 10) if _j0 >= 0 else -1
    _ba = txt[_j0:_j1] if _j0 >= 0 and _j1 > _j0 else txt[_j0:]
    check("P2b.2.d", "_overlap_coef" in _ba and "_UNTRACED_OVERLAP" in _ba,
          "answers 路径用 _overlap_coef + _UNTRACED_OVERLAP（未新造阈值）")

    def _try(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return "ERR " + type(e).__name__ + ": " + str(e)

    _pos = _try(lambda: mod._hit_by_answers(
        "老城区现有排水管网的设计标准是多少年一遇",
        ["管网设计重现期", "老城区现有排水管网的设计标准"]))
    _neg1 = _try(lambda: mod._hit_by_answers("本地微观数据", ["管网设计重现期"]))
    _neg2 = _try(lambda: mod._hit_by_answers("任意", []))
    _neg3 = _try(lambda: mod._hit_by_answers("任意", None))
    check("P2b.2.e", _pos is True and _neg1 is False and _neg2 is False
          and _neg3 is False,
          "正向命中 + 三类负对照（实测 " + str([_pos, _neg1, _neg2, _neg3]) + "）")

    # ---------- P2b.3 _load_anchors 读 answers ----------
    _tmp = HERE / "_verify_p2b_ans.json"
    _tmp.write_bytes(json.dumps(
        {"anchors": [{"id": "a1", "claim": "X", "tier": 1,
                      "answers": ["问题A", "问题B"]}]},
        ensure_ascii=False).encode("utf-8"))
    try:
        _cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG, default=str))
        _cfg["external_anchor"] = dict(_cfg.get("external_anchor") or {})
        _cfg["external_anchor"].update({"enabled": True, "path": str(_tmp)})
        _cfg["output"] = dict(_cfg.get("output") or {})
        _cfg["output"]["verbose"] = False
        _m = mod.MetaDGTF(_cfg)
        _m._load_anchors()
        _got = (_m._anchors[0].get("answers")
                if getattr(_m, "_anchors", None) else None)
        check("P2b.3", _got == ["问题A", "问题B"],
              "answers 键在且值读对（实测 " + repr(_got) + "）")
    except Exception as e:  # noqa: BLE001
        check("P2b.3", False, type(e).__name__ + ": " + str(e))
    finally:
        try:
            _tmp.unlink()
        except Exception:
            pass

    # ---------- P2b.4 crosscheck 双路径 ----------
    _k0 = txt.find("def _anchor_crosscheck")
    _k1 = txt.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1
    _xc = txt[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else txt[_k0:]
    check("P2b.4.a", "_hit_by_answers(str(" in _xc, "crosscheck 调 _hit_by_answers")
    check("P2b.4.b", "_hit_by_claim(str(" in _xc, "crosscheck 调 _hit_by_claim")
    check("P2b.4.a2", 'x.get("answers")' in _xc, "crosscheck 读 anchors 的 answers 字段")
    check("P2b.4.a3", "<= _floor_c" in _xc, "tier 门仍在双路径之内")

    def _hit_sim(aspect, anchors, floor):
        """与 crosscheck 内联谓词同构（源码字面串由 P2b.4.a/b/a3 锁住）。"""
        return next((x for x in anchors
                     if int(x.get("tier", 3) or 3) <= floor
                     and (mod._hit_by_answers(str(aspect), x.get("answers") or [])
                          or mod._hit_by_claim(str(aspect),
                                               str(x.get("claim", ""))))),
                    None)

    _h1 = _try(lambda: _hit_sim("管网设计重现期 3~5 年",
                                [{"id": "n1", "tier": 1,
                                  "claim": "管网设计重现期 3~5 年"}], 2))
    check("P2b.4.c", isinstance(_h1, dict) and _h1.get("id") == "n1",
          "负对照：无 answers → 走 claim 路径（实测 " + str(_h1) + "）")
    _h2 = _try(lambda: _hit_sim("管网设计重现期 3~5 年",
                                [{"id": "n2", "tier": 1, "answers": [],
                                  "claim": "管网设计重现期 3~5 年"}], 2))
    check("P2b.4.d", isinstance(_h2, dict) and _h2.get("id") == "n2",
          "负对照：answers=[] → 也走 claim 路径（实测 " + str(_h2) + "）")
    _h3 = _try(lambda: _hit_sim("重建还是局部改造加海绵",
                                [{"id": "n3", "tier": 4,
                                  "answers": ["重建还是局部改造加海绵"]}], 2))
    check("P2b.4.e", _h3 is None,
          "负对照：tier 超 floor → 即便 answers 命中也不选（实测 " + str(_h3) + "）")

    # ---------- P2b.7 真跑（主判据） ----------
    _tags = ("老城区内涝", "中小制造", "社区医院")
    _rows = []
    for t in _tags:
        _mf = HERE / "outputs" / ("p2b_" + t) / "meta.json"
        _n = None
        _calls = None
        if _mf.is_file():
            try:
                _dd = json.loads(_mf.read_text(encoding="utf-8"))
                _v = _dd.get("triage_downgrades")
                _n = (len(_v) if isinstance(_v, list)
                      else (int(_v) if isinstance(_v, int) else None))
                _calls = _dd.get("calls")
            except Exception:
                pass
        _rows.append((t, _n, _calls))
    _have = [r for r in _rows if r[1] is not None]
    if not _have:
        check("P2b.7.a", False, "三题产物未齐（先跑 `python _run_v1221_p2b.py`）")
    else:
        check("P2b.7.a", any(isinstance(r[1], int) and r[1] >= 1 for r in _have),
              "≥1 题 triage ≥ 1 条（实测 " + str([r[1] for r in _rows])
              + "）-- 主判据")
        print("  · P2b.7 详情：" + "；".join(
            str(r[0]) + " triage=" + str(r[1]) + " calls=" + str(r[2])
            for r in _rows))
        for r in _rows:
            _mf = HERE / "outputs" / ("p2b_" + str(r[0])) / "meta.json"
            if not _mf.is_file():
                continue
            try:
                _dr = (json.loads(_mf.read_text(encoding="utf-8"))
                       .get("drift") or {})
            except Exception:
                _dr = {}
            print("  · P2b.8 漂移观察[" + str(r[0]) + "]（不判 pass/fail）："
                  + json.dumps(_dr, ensure_ascii=False))

    # ---------- P2b.9 不删机制 ----------
    _b1 = HERE / "元DGTF-V1.22.1-rc1.py"
    if _b1.is_file():
        _n_del = count_del_lines(str(_b1), src)
        check("P2b.9.a", _n_del == 0, "rc1 → rc1b 纯删除行 " + str(_n_del) + "（红线 0）")
        _gone = mechanism_removed(str(_b1), src)
        check("P2b.9.b", not _gone,
              "rc1 → rc1b 符号消失 " + str(len(_gone)) + " 项")
    else:
        check("P2b.9.a", False, "缺 rc1 基线")
        check("P2b.9.b", False, "缺 rc1 基线")


'''

REPS = [
    ("phase_p2b 函数体", "\ndef phase_p3(src, mod):", NL + FUNC + "def phase_p3(src, mod):"),
    ("PHASES 注册 p2b",
     '          "p4": phase_p4, "p5": phase_p5, "p6": phase_p6, "p7": phase_p7}',
     '          "p2b": phase_p2b,' + NL +
     '          "p4": phase_p4, "p5": phase_p5, "p6": phase_p6, "p7": phase_p7}'),
]


def main() -> int:
    raw = TARGET.read_bytes()
    s = raw.decode("utf-8")
    if SENTINEL in s:
        print("  · 已应用（幂等跳过）")
        return 0
    assert s.count(CRLF) == s.count(NL), "_v122_verify.py 行尾不纯"
    assert b"\r\r\n" not in raw, "_v122_verify.py 含 CRCRLF"
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
