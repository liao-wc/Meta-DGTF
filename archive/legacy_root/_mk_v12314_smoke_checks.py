# -*- coding: utf-8 -*-
"""把 v1.23.14 的判据注入 smoke_test.py，并把 SRC 指到新版。

新增 `check_v12314_history_corpus`：
  · 三类来源都接上、真实语料样本量 > 100；关掉两源只剩 packed（负对照）；
  · md 抽取正/负对照；packed 抽取**必须读 `rounds_run`**（字段名 bug 回归守卫）；
  · 按题型取历史 + 无同型退全语料；
  · 圈数三级回退 + 「实际停圈需 ≥3 份样本」门槛（两向）；
  · 成本档**相对判据**（同类偏贵降档 / 不贵不降 / 一致率低不降）；
  · 「实际停圈」渲染 + 产物里真的有这一行；空输入不崩。
"""
import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
raw = SK.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

NEWFN = '''def check_v12314_history_corpus():
    """[v1.23.14] 用真实历史语料校准调度：三源取样 + 字段名 + 相对判据。

    ★ 背景（本版的两个真问题）：
      ① `_auto_history` 只读 `**/*.packed.json` —— 而 `outputs/` 里有 368 份
         产物 md、只落 1 份 packed ⇒ 历史几乎为空，十二项自适应形同虚设；
      ② 它把「实际停圈」的字段名读成了 `rounds`，真实字段是 `rounds_run`
         ⇒ `dict.get` 静默返回 None，「实际停圈」**永远取不到**。
    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 关掉 md / 跑批两个源 ⇒ 样本必须掉回 1（证明样本量靠扩源拿到）；
      · md 抽取给空串 / 无资源行 ⇒ 必须 `{}`；
      · packed 里同时放 `rounds_run` 与 `rounds`：只准认前者；
      · 「实际停圈」样本不足（1 份）⇒ 必须退回种子上限（不能被单条噪声带跑）；
      · 成本档两向：同类偏贵降档 / 不贵不降 / 一致率低不降。
    """
    import json as _j
    import tempfile as _tf
    m = globals().get("mod")
    bad = []
    if m is None or not hasattr(m, "_hist_from_md"):
        print("  \\u2717 [v12314] 命名空间里没有历史三源函数")
        return False
    _F = "新中国的成立时间是什么时候"
    _D = "这份方案怎么落地"
    cfg0 = m.load_config("")

    # ── A 三源 + 样本量 ───────────────────────────────────────
    h = m._auto_history("outputs", 200, cfg=cfg0)
    if h["n"] <= 100:
        bad.append("历史样本仍太少（%d）—— 扩源没生效" % h["n"])
    for _k in ("packed", "md", "batch"):
        if not (h.get("sources") or {}).get(_k):
            bad.append("缺历史来源：%s" % _k)
    if not h.get("tokens_p75") or not h.get("calls_p75"):
        bad.append("缺少 p75 分位读数")
    if not h.get("cap_rounds"):
        bad.append("缺少种子上限读数")
    if not (h.get("by_type") or {}).get("fact", {}).get("n"):
        bad.append("分题型桶为空（事实型）")
    _p = m._auto_history("outputs", 200, cfg=cfg0,
                         want_md=False, want_batch=False)
    if _p["n"] != (h.get("sources") or {}).get("packed", 0):
        bad.append("关掉两源后样本没掉回 packed 数（%d）" % _p["n"])

    # ── B md 抽取 正/负对照 ──────────────────────────────────
    HEAD = ("# 元 DGTF · 测试题\\n\\n**调度**：修行(4圈) → 研究(5圈) → "
            "对撞(6圈)\\n\\n**并行模式**：A · 四层独立并行 + 汇流\\n\\n"
            "**成本档位**：economy（再省调用次数）\\n\\n"
            "**取向**：boundary（要边界清单）\\n\\n"
            "**停止**：自然 2 层 / 被截断（体力耗尽）2 层\\n\\n"
            "**资源**: 137 次 LLM | 654321 tokens\\n")
    r = m._hist_from_md(HEAD)
    for _k, _v in (("calls", 137), ("tokens", 654321), ("mode", "A"),
                   ("profile", "economy"), ("orientation", "boundary")):
        if r.get(_k) != _v:
            bad.append("md 抽取 %s 错：%r" % (_k, r.get(_k)))
    if (r.get("cap_rounds") or {}).get("all") != 6:
        bad.append("md 抽取种子上限错：%r" % (r.get("cap_rounds"),))
    if [r.get("nat"), r.get("cut")] != [2, 2]:
        bad.append("md 抽取停止分层错")
    if m._hist_from_md("") != {} or m._hist_from_md("# 标题\\n正文\\n") != {}:
        bad.append("md 抽取负对照失效（空输入该返回 {}）")

    # ── C packed 抽取：只认 `rounds_run` ──────────────────────
    P = {"question": _F, "llm_calls": 88, "llm_tokens": 123456,
         "cost_profile": "balanced", "orientation": "boundary",
         "dispatch": {"_parallel_mode": "B"}, "tri_state": [3, 4],
         "views": {"0": {"rounds_run": 3, "rounds_cap": 6,
                         "stop_reason": "连续 2 轮无新 &，螺旋停止"},
                   "1": {"rounds": 5, "rounds_cap": 6,
                         "stop_reason": "体力耗尽（6 圈走满）"}},
         "pools": {"1": {"web_results": [{"id": "W1"}], "web_errors": [],
                         "meta": ["[W-EMPTY] x"]}}}
    rc = m._hist_from_packed(P)
    if (rc.get("actual_rounds") or {}).get("0") != 3:
        bad.append("packed 没读到实际停圈（rounds_run）：%r"
                   % (rc.get("actual_rounds"),))
    if "1" in (rc.get("actual_rounds") or {}):
        bad.append("packed 认了错字段 `rounds`（实际字段是 `rounds_run`）")
    if rc.get("tri") != 0.75:
        bad.append("tri_state 读数错：%r" % rc.get("tri"))

    # ── D 按题型取历史 ───────────────────────────────────────
    f, d = m._auto_features(_F), m._auto_features(_D)
    _bt = h.get("by_type") or {}
    if m._hist_for(f, h) is not _bt.get("fact"):
        bad.append("事实型没取 fact 桶")
    if m._hist_for(d, h) is not _bt.get("nonfact"):
        bad.append("决策型没取 nonfact 桶")
    if m._hist_for(f, {"n": 9, "by_type": {"fact": {"n": 0}}})["n"] != 9:
        bad.append("无同型样本时没退回全语料")

    # ── E 圈数：三级回退 + 样本门槛（两向）──────────────────
    _cap = {"n": 50, "cap_rounds": {"0": 2, "1": 2, "both": 5, "all": 6},
            "cap_rounds_n": {"0": 40, "1": 40, "both": 10, "all": 10}}
    _v, _why = m._auto_pick_rounds(f, _cap, cfg0)
    if "种子上限" not in _why:
        bad.append("只有种子上限时没报出来源")
    _few = {"n": 50, "layer_rounds": {"0": 1}, "layer_rounds_n": {"0": 1},
            "cap_rounds": {"0": 4}, "cap_rounds_n": {"0": 30}}
    if m._auto_pick_rounds(f, _few, cfg0)[0]["0"] != 4:
        bad.append("实际停圈只有 1 份样本时不该采纳（应退回种子上限）")
    _many = {"n": 50, "layer_rounds": {"0": 5}, "layer_rounds_n": {"0": 9},
             "cap_rounds": {"0": 2}, "cap_rounds_n": {"0": 30}}
    if m._auto_pick_rounds(f, _many, cfg0)[0]["0"] != 6:
        bad.append("实际停圈样本足够时应采纳（5+1=6）")
    for _e in m._ENTRIES:
        if _e not in m._auto_pick_rounds(f, {}, cfg0)[0]:
            bad.append("零历史时没给全四层的圈数")

    # ── F 成本档：相对判据（两向 + 质量优先）────────────────
    _base = {"n": 99, "tokens_p75": 500000, "calls_p75": 100}
    _hi = dict(_base, by_type={"nonfact": {"n": 20, "tokens_med": 900000,
                                          "calls_med": 50, "tri_n": 6,
                                          "tri_rate": 0.9}})
    _lo = dict(_base, by_type={"nonfact": {"n": 20, "tokens_med": 100000,
                                          "calls_med": 10, "tri_n": 6,
                                          "tri_rate": 0.9}})
    _badq = dict(_base, by_type={"nonfact": {"n": 20, "tokens_med": 900000,
                                            "calls_med": 50, "tri_n": 6,
                                            "tri_rate": 0.2}})
    if m._auto_pick_cost_profile(d, _hi, cfg0)[0] != "economy":
        bad.append("同类题成本中位 ≥ 全语料 p75 时没降档")
    if m._auto_pick_cost_profile(d, _lo, cfg0)[0] != "balanced":
        bad.append("同类题不贵时不该降档（负对照失效）")
    if m._auto_pick_cost_profile(d, _badq, cfg0)[0] != "balanced":
        bad.append("同类题三态一致率低时不该降档（质量优先）")
    if m._auto_pick_cost_profile(f, _lo, cfg0)[0] != "economy":
        bad.append("事实型短题应恒为 economy")

    # ── G 「实际停圈」渲染 + 产物里真的有 ─────────────────────
    _line = m._rounds_run_line({"1": {"rounds_run": 3, "rounds_cap": 6}})
    if "**实际停圈**" not in _line or "研究 3 圈" not in _line:
        bad.append("实际停圈渲染不对：%r" % _line)
    if m._rounds_run_line({}) != "" or m._rounds_run_line(None) != "":
        bad.append("空 views 时实际停圈行该为空串")
    _pk = sorted((HERE / "outputs").glob("*.packed.json"),
                 key=lambda q: q.stat().st_mtime)
    if _pk:
        try:
            _real = _j.loads(_pk[-1].read_text(encoding="utf-8"))
            _real["_auto_dispatch"] = m.auto_dispatch(
                str(_real.get("question") or _F), cfg0, history=h)
            with _tf.TemporaryDirectory() as td:
                _t = Path(m.save_result(_real, save_dir=td)).read_text(
                    encoding="utf-8")
            if "**实际停圈**：" not in _t:
                bad.append("产物里没有「实际停圈」行（信号落不了地）")
            if "历史读数：**" not in _t or "p75" not in _t:
                bad.append("产物的历史读数行没报来源数与 p75")
        except Exception as _e:  # noqa: BLE001
            bad.append("产物渲染异常：%s: %s" % (type(_e).__name__, _e))

    # ── H 空/坏输入不崩 ─────────────────────────────────────
    if m._auto_history(str(HERE / "__nope__"), 5, cfg=cfg0)["n"] >= 0:
        pass
    try:
        m._hist_from_batch(None)
        m._hist_from_batch({})
        m._hist_from_packed(None)
    except Exception as _e:  # noqa: BLE001
        bad.append("历史抽取对空输入抛异常：%s" % type(_e).__name__)

    if bad:
        for _x in bad:
            print("  \\u2717 [v12314] %s" % _x)
        return False
    print("  \\u2713 [v12314] 历史三源（%d 份）· rounds_run 字段 · 按题型分桶 · "
          "圈数三级回退+样本门槛 · 成本档相对判据 · 实际停圈落产物"
          % h["n"])
    return True


'''
ANCHOR = "def check_v12310_render_ops():"
assert s.count(ANCHOR) == 1, "check_v12310_render_ops 命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, NEWFN + ANCHOR, 1)

OLD_REG = '''    if not check_v12313_auto_dispatch():
        return 1
'''
NEW_REG = OLD_REG + '''    if not check_v12314_history_corpus():
        return 1
'''
assert s.count(OLD_REG) == 1, "runner 注册点命中 %d 次" % s.count(OLD_REG)
s = s.replace(OLD_REG, NEW_REG, 1)

pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(pat.findall(s)) == 1, "SRC 行不是 1 行"
s = pat.sub('SRC = HERE / "元DGTF-V1.23.14.py"', s, count=1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
ast.parse(out.decode("utf-8"))
SK.write_bytes(out)
print("smoke_test.py 已更新：新增 check_v12314_history_corpus 并挂进 runner；SRC ->",
      re.findall(r"SRC = HERE / .*", out.decode("utf-8"))[:1])
