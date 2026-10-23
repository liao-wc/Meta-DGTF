# -*- coding: utf-8 -*-
"""[v1.22.2] 给 _v122_verify.py 加四档验收（v1222_p1~p4）。幂等：整段替换。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VF = HERE / "_v122_verify.py"
MARK_A = "# <<<v1222 phases>>>"
MARK_B = "# <<<end v1222 phases>>>"

BLOCK = r'''
# <<<v1222 phases>>>
def phase_v1222_p1(src, mod):
    """[v1.22.2 P1] P4 两臂口径统一。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    check("P1.1.a", hasattr(mod, "_single_vote_stability") if mod else False,
          "_single_vote_stability 存在")
    check("P1.1.b",
          bool(mod) and hasattr(mod.MetaDGTF, "_write_tri_stability"),
          "MetaDGTF._write_tri_stability 存在")
    check("P1.2.a", "三态判决（" in t, "头部标题按 _vote_mode 分口径")
    check("P1.2.b", "_voted = _hi + _me + _lo" in t, "分母只数已判条")
    check("P1.2.c", '== "abstained"' in t, "弃权独立成档")
    check("P1.3 负对照", "**三态多票**：high {_hi} / medium {_me} / low {_lo}"
          not in t, "旧「无条件三态多票」渲染已撤")
    # 口径函数四向
    if mod and hasattr(mod, "_single_vote_stability"):
        _f = mod._single_vote_stability
        check("P1.4.a", _f({}) == "abstained", "未判条 → abstained")
        check("P1.4.b", _f({"_tri_judged": True, "decidability": "partial"})
              == "medium", "有判无原标签 → medium")
        check("P1.4.c", _f({"_tri_judged": True, "first_label": "decidable",
                            "decidability": "partial"}) == "low",
              "不一致 → low")
        check("P1.4.d", _f({"_tri_judged": True, "first_label": "partial",
                            "decidability": "partial"}) == "high",
              "一致 → high")
    else:
        for k in ("P1.4.a", "P1.4.b", "P1.4.c", "P1.4.d"):
            check(k, False, "口径函数缺失")
    check("P1.5", (HERE / "v1222_p1_报告.md").is_file(), "v1222_p1_报告.md 存在")


def phase_v1222_p2(src, mod):
    """[v1.22.2 P2] schema 加 not_do（四处打通）。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    _reg = t[t.find('"decidable_product": {'):t.find('"undecidable_product": {')]
    check("P2.1", '"not_do"' in _reg, "prompt schema 含 not_do")
    check("P2.2", "not_do 段 · decision 取向必须产出" in t, "prompt 约束段存在")
    check("P2.3 ★", '"not_do": _norm_schema_not_do(dec.get("not_do")),' in t,
          "dec_norm 白名单含 not_do（不加会静默吞字段）")
    check("P2.4", bool(mod) and hasattr(mod, "_norm_schema_not_do"),
          "_norm_schema_not_do 存在")
    check("P2.5", bool(mod) and hasattr(mod, "_extract_not_do_lexical"),
          "_extract_not_do_lexical 保留（词法兜底）")
    check("P2.6", "_nd_schema = [x for x in _nd_d" in t,
          "not_do_missing 只认 schema 来源")
    if mod and hasattr(mod, "_norm_schema_not_do"):
        _n = mod._norm_schema_not_do
        check("P2.7.a 负对照", _n(None) == [] and _n("x") == [], "非 list → 空")
        check("P2.7.b 负对照", _n([{"what": ""}, {"what": " "}]) == [],
              "空 what 被过滤")
        check("P2.7.c", len(_n([{"what": "w%d" % i} for i in range(9)])) == 6,
              "上限 6 条")
    if mod and hasattr(mod, "_extract_not_do"):
        _v = {"decidable_product": {"not_do": [
            {"what": "不在成因未定时动工", "why": "判据未立"}]}}
        _g = mod._extract_not_do(_v)
        check("P2.8", len(_g) == 1 and _g[0]["_source"] == "schema",
              "schema 路径命中 + _source")
        _e = type("V", (), {"decidable_product": {}})()
        check("P2.9 负对照", mod._extract_not_do(_e) == [], "空 view → 0 条")
    try:
        sys.path.insert(0, str(HERE / "bench"))
        from bench_score import score_actions
        _a3 = [{"fallback": "退路%d" % i} for i in range(3)]
        check("P2.10.a 负对照", score_actions([], [])["score"] == 0,
              "空/空 → 0/3")
        check("P2.10.b", score_actions(_a3, [])["score"] == 2,
              "actions 满 + not_do 空 → 2/3")
        check("P2.10.c", score_actions(_a3, [{"what": "x"}])["score"] == 3,
              "actions 满 + not_do 非空 → 3/3")
        check("P2.10.d", score_actions(_a3, [{"what": "x"}])["max"] == 3,
              "rubric max 未变（没改判据）")
    except Exception as e:  # noqa: BLE001
        check("P2.10 rubic", False, type(e).__name__ + ": " + str(e))
    check("P2.11", (HERE / "v1222_p2_报告.md").is_file(), "v1222_p2_报告.md 存在")


def phase_v1222_p3(src, mod):
    """[v1.22.2 P3] answers 最短长度 + 双告警分离。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    _ea = (getattr(mod, "DEFAULT_CONFIG", {}) or {}).get("external_anchor") or {}
    check("P3.1", _ea.get("answers_min_len") == 6, "answers_min_len 默认 6")
    check("P3.2", _ea.get("answers_max_n") == 5, "answers_max_n 默认 5")
    check("P3.3", '"answers": _ans_kept' in t, "answers = 过滤后结果")
    check("P3.4", "_answers_dropped" in t, "被丢项留痕")
    check("P3.5", "**锚点 answers 警告**" in t, "产物渲染已加")
    check("P3.6 ★ 双告警分离",
          t.count("self._anchor_answers_warning = (") == 1
          and "_anchor_answers_filtered" in t,
          "「未声明」与「被过滤」两条告警不混用同一属性")
    check("P3.7 负对照", "return inter / min(len(ka), len(kb))" in t,
          "_overlap_coef 分母仍 min（阈值未动）")
    # 行为：短丢长留
    if mod:
        import json as _j
        import tempfile as _tf
        p = Path(_tf.mkdtemp()) / "a.json"
        p.write_text(_j.dumps({"anchors": [{
            "id": "a1", "claim": "x",
            "answers": ["重现期", "老城区现有排水管网的设计标准是多少年一遇"]}]},
            ensure_ascii=False), encoding="utf-8")
        cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
        cfg["external_anchor"] = dict(cfg["external_anchor"])
        cfg["external_anchor"].update({"enabled": True, "path": str(p)})
        o = object.__new__(mod.MetaDGTF)
        o.config = cfg
        o.vp = lambda *a, **k: None
        o._load_anchors()
        _ans = o._anchors[0].get("answers") or []
        check("P3.8.a", "重现期" not in _ans, "短 answer 被丢弃")
        check("P3.8.b", any("老城区" in x for x in _ans), "长 answer 保留")
        check("P3.8.c", bool(getattr(o, "_anchor_answers_filtered", "")),
              "过滤留痕非空")
        check("P3.8.d 负对照", getattr(o, "_anchor_answers_warning", None) == "",
              "「未声明」告警未被误触发")
    check("P3.9", (HERE / "v1222_p3_报告.md").is_file(), "v1222_p3_报告.md 存在")


def phase_v1222_p4(src, mod):
    """[v1.22.2 P4] W 系列启动检查清单（只出清单，不出代码）。"""
    doc = HERE / "docs" / "W系列启动检查清单-v1222.md"
    check("P4.1", doc.is_file(), "docs/W系列启动检查清单-v1222.md 存在")
    if doc.is_file():
        dt = doc.read_text(encoding="utf-8")
        for k in ("A. v1.22.2 前置", "B. W 系列任务书核验", "C. 四条宪法级特性",
                  "D. 独立通道", "E. 配额三层", "F. 锚点与联网的边界"):
            check("P4.2." + k.split(".")[0], k in dt, "清单含 " + k)
        check("P4.3 结论二选一",
              ("可以启动" in dt) or ("不启动" in dt), "结论有启动/不启动判定")
        check("P4.4 每条有依据",
              dt.count("断言") + dt.count("命令") + dt.count("文件") >= 6,
              "条目带断言/命令/文件路径依据")
    check("P4.5", (HERE / "v1222_p4_报告.md").is_file(), "v1222_p4_报告.md 存在")
# <<<end v1222 phases>>>
'''

raw = VF.read_bytes()
s = raw.decode("utf-8")
nl = "\r\n" if s.count("\r\n") == s.count("\n") else "\n"
s = s.replace("\r\n", "\n")

if MARK_A in s:
    i = s.index(MARK_A)
    j = s.index(MARK_B) + len(MARK_B)
    s = s[:i] + BLOCK.strip("\n") + s[j:]
else:
    anchor = "\n\nPHASES = {"
    assert s.count(anchor) == 1, "PHASES 锚点不是 1 处"
    s = s.replace(anchor, "\n\n" + BLOCK.strip("\n") + anchor)

# 注册进 PHASES
_old = ('PHASES = {"1": phase1, "2": phase2, "3": phase3, "4": phase4,\n'
        '          "5": phase5, "6": phase6,\n'
        '          "p1": phase_p1, "p2": phase_p2, "p3": phase_p3,\n'
        '          "p2b": phase_p2b,\n'
        '          "p4": phase_p4, "p5": phase_p5, "p6": phase_p6,'
        ' "p7": phase_p7}\n')
_new = ('PHASES = {"1": phase1, "2": phase2, "3": phase3, "4": phase4,\n'
        '          "5": phase5, "6": phase6,\n'
        '          "p1": phase_p1, "p2": phase_p2, "p3": phase_p3,\n'
        '          "p2b": phase_p2b,\n'
        '          "p4": phase_p4, "p5": phase_p5, "p6": phase_p6,\n'
        '          "p7": phase_p7,\n'
        '          "v1222_p1": phase_v1222_p1, "v1222_p2": phase_v1222_p2,\n'
        '          "v1222_p3": phase_v1222_p3, "v1222_p4": phase_v1222_p4}\n')
if "v1222_p1" not in s:
    assert s.count(_old) == 1, "PHASES 字面块不是 1 处"
    s = s.replace(_old, _new)

out = s.replace("\n", nl).encode("utf-8")
if nl == "\r\n":
    assert out.count(b"\r\r\n") == 0
    assert out.count(b"\r") == out.count(b"\r\n")
VF.write_bytes(out)
print("OK: _v122_verify.py 已加 v1222_p1~p4（换行 %r）" % nl)
