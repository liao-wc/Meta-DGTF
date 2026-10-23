# -*- coding: utf-8 -*-
"""[v1.22.2] 把 v1222 的冒烟判据同步进 smoke_test.py（唯一事实源，可重跑）。

规则（据 skill「v1.22.1 追加：接线器」的教训）：
  · 只动**自己那几个**守卫名，绝不 GUARD_RE 通删；
  · 新守卫插在**已有守卫之后**；
  · 硬断言：守卫总数不许比基线少；
  · smoke_test.py 保持纯 CRLF。
幂等：v1222 检查块以 MARK 为界整段替换；守卫行先删自己那几个再重插。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
NEW_SRC_NAME = "元DGTF-V1.22.2.py"

MARK_A = "# <<<v1222 checks>>>"
MARK_B = "# <<<end v1222 checks>>>"

CHECKS = r'''
# <<<v1222 checks>>>
def check_v1222_p1(SRC=None):
    """[v1.22.2 P1] P4 两臂口径统一：两条路径都写 stability（含早退）。

    ★ 负对照（写进判据）：
      · 判决失败 / 空 judgments → 每条都必须 `abstained`（不许静默无键）；
      · 未被判到的条**不许**落 high/low（弃权≠稳定）。
    """
    try:
        NL = chr(10)
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        assert hasattr(m, "_single_vote_stability"), "_single_vote_stability 缺失"
        assert hasattr(m.MetaDGTF, "_write_tri_stability"), \
            "MetaDGTF._write_tri_stability 缺失"

        class _LLM:
            def __init__(self, fail=False, empty=False):
                self.fail, self.empty = fail, empty
            def call(self, s, u, t, mx, json_mode=False, stage=""):
                if self.fail:
                    raise RuntimeError("打桩失败")
                if self.empty:
                    return '{"judgments": []}'
                import json as _j
                return _j.dumps({"judgments": [
                    {"id": 1, "reason": "x", "decidability": "decidable"},
                    {"id": 2, "reason": "x", "decidability": "undecidable"}]})
            def parse_json(self, raw):
                import json as _j
                return _j.loads(raw)

        def _mk(llm, multi):
            o = object.__new__(m.MetaDGTF)
            o.llm = llm
            o.config = {"actions": {"tri_multi_vote": multi}}
            o.vp = lambda *a, **k: None
            return o

        def _subs():
            return [{"id": 1, "question": "a", "decidability": "decidable"},
                    {"id": 2, "question": "b", "decidability": "decidable"},
                    {"id": 3, "question": "c", "decidability": "partial"}]

        # 1 单票臂
        _s = _subs()
        _mk(_LLM(), False)._adjudicate_sub_tristate(_s, "Q")
        assert all("stability" in x for x in _s), "单票臂有子问题没写 stability"
        assert {x["_vote_mode"] for x in _s} == {"single"}, "单票臂 _vote_mode 错"
        _st = [x["stability"] for x in _s]
        assert _st == ["high", "low", "abstained"], "单票口径错：" + repr(_st)

        # 2 多票臂
        _s2 = _subs()
        _mk(_LLM(), True)._adjudicate_sub_tristate(_s2, "Q")
        assert all("stability" in x for x in _s2), "多票臂有子问题没写 stability"
        assert {x["_vote_mode"] for x in _s2} == {"multi"}, "多票臂 _vote_mode 错"

        # 3 负对照：失败 / 空 judgments → 全 abstained（早退也写）
        for _multi in (False, True):
            _s3 = _subs()
            _mk(_LLM(fail=True), _multi)._adjudicate_sub_tristate(_s3, "Q")
            assert all(x["stability"] == "abstained" for x in _s3), \
                "失败路径未写 abstained（多票=%s）" % _multi
        _s4 = _subs()
        _mk(_LLM(empty=True), False)._adjudicate_sub_tristate(_s4, "Q")
        assert all(x["stability"] == "abstained" for x in _s4), \
            "空 judgments 未写 abstained"

        # 4 口径函数负对照
        assert m._single_vote_stability({}) == "abstained", "未判条应为 abstained"
        assert m._single_vote_stability({"_tri_judged": True,
                                         "decidability": "partial"}) == "medium"
        assert m._single_vote_stability(
            {"_tri_judged": True, "first_label": "decidable",
             "decidability": "partial"}) == "low"
        assert m._single_vote_stability(
            {"_tri_judged": True, "first_label": "partial",
             "decidability": "partial"}) == "high"
        # [v1.22.2 P1b] 真跑暴露的一格：分歧落点恰好 == 原标签 partial
        #   时，只看两者相等会误判 high。必须看 label_disagreed。
        assert m._single_vote_stability(
            {"_tri_judged": True,
             "label_disagreed": ["partial", "decidable"],
             "first_label": "partial",
             "decidability": "partial"}) == "low", \
            "分歧落 partial 且原标签 partial → 应 low（曾误判 high）"

        # 5 渲染：分口径 + 分母只数已判 + 弃权单列
        assert "三态判决（" in src, "头部标题未分口径"
        assert '"abstained"' in src, "渲染未认 abstained"
        assert "_voted = _hi + _me + _lo" in src, "分母未改成已判条"
        # 负对照：旧的「无条件三态多票 high/medium/low」那一行必须已不在渲染里
        assert "**三态多票**：high {_hi} / medium {_me} / low {_lo}" not in src, \
            "旧渲染仍在"
        assert '"stability" == "high"' not in src or "_voted" in src, "口径未变"

        print("  ✓ v1.22.2 P1：两臂都写 stability / 弃权独立 / "
              "早退也写 / 口径函数 4 向负对照")
        return True
    except Exception as e:
        print("  ✗ v1.22.2 P1 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1222_p2(SRC=None):
    """[v1.22.2 P2] not_do 四处打通：schema → 白名单 → 抽取 → 渲染。

    ★ 负对照：
      · 空 what 必须被过滤（否则 rubric 第三项假通过）；
      · 空 view → 0 条（否则 not_do_missing 永不亮）；
      · `not_do_missing` 只认 schema 来源，词法兜底**不算**；
      · rubric max=3 没改（本阶段不是改判据，是补产出）。
    """
    try:
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        # 1 四处齐备
        assert hasattr(m, "_norm_schema_not_do"), "_norm_schema_not_do 缺失"
        assert hasattr(m, "_norm_schema_actions"), "_norm_schema_actions 被误删"
        assert hasattr(m, "_extract_not_do"), "_extract_not_do 缺失"
        assert hasattr(m, "_extract_not_do_lexical"), "_extract_not_do_lexical 缺失"
        reg = src[src.find('"decidable_product": {'):
                  src.find('"undecidable_product": {')]
        assert '"not_do"' in reg, "prompt schema 没加 not_do"
        assert "not_do 段 · decision 取向必须产出" in src, "约束段缺失"
        assert '"not_do": _norm_schema_not_do(dec.get("not_do")),' in src, \
            "★ dec_norm 白名单没加 not_do（会静默吞掉模型产出）"

        # 2 归一化：四向
        _n = m._norm_schema_not_do
        assert _n(None) == [] and _n("x") == [], "非 list 未返回空"
        assert _n(["x", 1]) == [], "非 dict 条目未丢弃"
        assert _n([{"what": "", "why": "y"}, {"what": " "}]) == [], \
            "空 what 未过滤"
        assert len(_n([{"what": "w%d" % i} for i in range(9)])) == 6, "上限非 6"

        # 3 抽取：schema 优先 + 词法兜底带标签 + 空 view 归零
        got = m._extract_not_do({"decidable_product": {"not_do": [
            {"what": "不在成因未定时动工", "why": "判据未立"},
            {"what": "", "why": "空 what"}]}})
        assert len(got) == 1 and got[0]["_source"] == "schema", \
            "schema 路径错：" + repr(got)
        assert all(x["what"] for x in got), "空 what 混进结果"
        _v3 = type("V", (), {"decidable_product": {}})()
        assert m._extract_not_do(_v3) == [], "空 view 未归零"
        got2 = m._extract_not_do(_v3)
        assert all(x.get("_source") == "lexical" for x in got2), \
            "兜底结果缺 _source=lexical"

        # 4 not_do_missing 只认 schema
        assert "_nd_schema = [x for x in _nd_d" in src, \
            "not_do_missing 未改成只认 schema 来源"

        # 5 rubric 三段负对照 + max 未变
        import sys as _s
        _s.path.insert(0, "bench")
        from bench_score import score_actions
        _a3 = [{"fallback": "退路%d" % i} for i in range(3)]
        assert score_actions([], [])["score"] == 0, "空/空 竟给分"
        assert score_actions(_a3, [])["score"] == 2, "actions 满 + not_do 空 ≠ 2/3"
        assert score_actions(_a3, [{"what": "不做X"}])["score"] == 3, \
            "not_do 非空 未给第 3 分"
        assert score_actions(_a3, [{"what": "x"}])["max"] == 3, "max 被改了"

        print("  ✓ v1.22.2 P2：schema/白名单/抽取/渲染四处打通 + "
              "空 what 过滤 + 空 view 归零 + rubric 三段负对照")
        return True
    except Exception as e:
        print("  ✗ v1.22.2 P2 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1222_p3(SRC=None):
    """[v1.22.2 P3] answers 最短长度约束 + **两条告警分离**。

    ★ 负对照：
      · min_len=0 → 不过滤（退回旧行为）；
      · 真「未声明 answers」走另一条告警，两条不许互相覆盖；
      · 0.6 / `_overlap_coef` 分母 min 一律没动（任务书禁令）。
    """
    try:
        import json as _j
        import tempfile as _tf
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        ea = m.DEFAULT_CONFIG.get("external_anchor") or {}
        assert ea.get("answers_min_len") == 6, "answers_min_len 默认不是 6"
        assert ea.get("answers_max_n") == 5, "answers_max_n 默认不是 5"
        assert "_anchor_answers_filtered" in src, "过滤留痕属性缺失"
        assert '"answers": _ans_kept' in src, "answers 未改成过滤后的结果"
        # ★ 两条告警不许混用同一个属性
        assert src.count('self._anchor_answers_warning = (') == 1, \
            "「未声明」告警被复制/覆盖"
        assert "**锚点 answers 警告**" in src, "产物渲染缺失"

        def _load(anchors, **over):
            p = Path(_tf.mkdtemp()) / "a.json"
            p.write_text(_j.dumps({"anchors": anchors}, ensure_ascii=False),
                         encoding="utf-8")
            cfg = m.load_config(str(Path("__nonexistent__.yaml")))
            cfg["external_anchor"] = dict(cfg["external_anchor"])
            cfg["external_anchor"].update({"enabled": True, "path": str(p)})
            cfg["external_anchor"].update(over)
            o = object.__new__(m.MetaDGTF)
            o.config = cfg
            o.vp = lambda *a, **k: None
            o._load_anchors()
            return o

        o1 = _load([{"id": "a1", "claim": "x",
                     "answers": ["重现期", "老城区现有排水管网的设计标准是多少年一遇"]}])
        ans = o1._anchors[0].get("answers") or []
        assert "重现期" not in ans, "短 answer 未被丢弃"
        assert any("老城区" in x for x in ans), "长 answer 被误丢"
        assert o1._anchors[0].get("_answers_dropped") == ["重现期"], "丢弃项未留痕"
        assert o1._anchor_answers_filtered, "过滤未留痕"
        # ★ 负对照：声明过 → 「未声明」告警不许亮
        assert o1._anchor_answers_warning == "", "「未声明」告警被误触发"

        o0 = _load([{"id": "a1", "claim": "x", "answers": ["重现期", "短"]}],
                   answers_min_len=0)
        a0 = o0._anchors[0].get("answers") or []
        assert "重现期" in a0 and "短" in a0, "min_len=0 竟还在过滤"
        assert o0._anchor_answers_filtered == "", "不过滤却留了痕"

        o2 = _load([{"id": "a1", "claim": "x"}])
        assert o2._anchor_answers_warning, "真未声明 未告警"
        assert o2._anchor_answers_filtered == "", "两条告警混用了"

        # 阈值负对照
        assert "return inter / min(len(ka), len(kb))" in src, \
            "_overlap_coef 分母被改"
        print("  ✓ v1.22.2 P3：短 answer 过滤 + 留痕 + 两条告警分离 + "
              "min_len=0 不过滤 + 阈值未动")
        return True
    except Exception as e:
        print("  ✗ v1.22.2 P3 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
# <<<end v1222 checks>>>
'''

# ---- 过期断言同步（判据随实现更新，不是放宽阈值）----
# 1) P3 改了 _load_anchors 里 answers 的写法（字面串变了）
STALE = (
    '        assert \'"answers": [str(x)[:60]\' in src, "_load_anchors 未加 answers 键"\n',
    '        assert \'"answers": _ans_kept\' in src and "_answers_dropped" in src, \\\n'
    '            "_load_anchors 的 answers 键（v1.22.2 P3 起 = 过滤后 _ans_kept）"\n',
)
# 2) P2b 的样例答案只有 3 字 → 被新的最短长度过滤吃掉。
#    检查的**意图**（answers 真读进来）不变，只把样例换成长句，
#    并顺带把「短答案被过滤」也钉进同一条断言（更强，不是更弱）。
STALE2 = (
    '            {"anchors": [{"id": "a1", "claim": "X", "tier": 1,\n'
    '                          "answers": ["问题A", "问题B"]}]},\n',
    '            {"anchors": [{"id": "a1", "claim": "X", "tier": 1,\n'
    '                          "answers": ["短", "老城区管网设计重现期标准"]}]},\n',
)
STALE3 = (
    '            assert _got == ["问题A", "问题B"], "answers 未读进来：" + repr(_got)\n',
    '            # [v1.22.2 P3] 样本须满足最短长度：短的应被过滤，长的必须\n'
    '            #   真读进来（原样本 3 字，会被新过滤器吃掉 —— 判据随实现更新）。\n'
    '            assert _got == ["老城区管网设计重现期标准"], \\\n'
    '                "answers 未读进来（或短答案未过滤）：" + repr(_got)\n',
)

GUARD_RE = re.compile(r"^    if not (check_v1222_p\d)\(\):\n        return 1\n",
                      re.M)
# 只为**本文件里真的定义了**的检查接守卫（避免 NameError）
_DEFINED = sorted(re.findall(r"^def (check_v1222_p\d)\(", CHECKS, re.M),
                  key=lambda s: int(s.rsplit("p", 1)[1]))
GUARD_BLOCK = "".join(
    "    if not %s():\n        return 1\n" % n for n in _DEFINED)

raw = SMOKE.read_bytes()
src = raw.decode("utf-8")
if src.count("\r\n") != src.count("\n"):
    print("!! smoke_test.py 不是纯 CRLF，中止"); sys.exit(1)
src = src.replace("\r\n", "\n")

# --- SRC 指向本版 ---
_src_re = re.compile(r'SRC = HERE / "元DGTF-V1\.22\.\d+\.py"')
assert len(_src_re.findall(src)) == 1, "SRC 行不是 1 行"
src = _src_re.sub('SRC = HERE / "%s"' % NEW_SRC_NAME, src)

# --- 检查块整段替换 / 首插 ---
if MARK_A in src:
    i = src.index(MARK_A)
    j = src.index(MARK_B) + len(MARK_B)
    src = src[:i] + CHECKS.strip("\n") + src[j:]
else:
    anchor = "\n\ndef main():"
    assert src.count(anchor) == 1, "`def main():` 锚点不是 1 处"
    src = src.replace(anchor, "\n\n" + CHECKS.strip("\n") + anchor)

# --- 过期断言同步（P3 改了 _load_anchors 的 answers 写法）---
for _o, _n in (STALE, STALE2, STALE3):
    if _o in src:
        assert src.count(_o) == 1, "过期断言出现 %d 次" % src.count(_o)
        src = src.replace(_o, _n)

# --- 守卫：只动自己那几个 ---
n_before = len(re.findall(r"^    if not (check_\w+)\(\):$", src, re.M))
src = GUARD_RE.sub("", src)
# 插在**最后一个已有守卫之后**
hits = list(re.finditer(
    r"^    if not (check_\w+)\(\):\n        return 1\n", src, re.M))
assert hits, "找不到任何守卫行"
_p = hits[-1].end()
src = src[: _p] + GUARD_BLOCK + src[_p:]
n_after = len(re.findall(r"^    if not (check_\w+)\(\):$", src, re.M))
assert n_after >= n_before, "守卫数掉了：%d -> %d" % (n_before, n_after)

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"
SMOKE.write_bytes(out)
print("OK: v1222 冒烟判据已注入（守卫 %d -> %d）" % (n_before, n_after))
print("    SRC -> %s" % NEW_SRC_NAME)
