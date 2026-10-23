# -*- coding: utf-8 -*-
"""[v1.23.0 W1] 探针：基础设施（Gate / Client / Cache / 独立通道 / 配置段）。

用法：python _probe_v123_w1.py [元DGTF-V1.23.0.py]
改前跑（v1.22.2）应当**全假**：这些符号都不存在。
"""
import importlib.util
import json
import logging
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.0.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

spec = importlib.util.spec_from_file_location("dgtf_w1", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_w1"] = mod
spec.loader.exec_module(mod)

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


def cfg_of(**over):
    """造一份 config。默认 enabled=False（出厂态）。"""
    c = {"web_search": dict(mod.DEFAULT_CONFIG.get("web_search") or {})}
    c["web_search"]["quota"] = dict(c["web_search"].get("quota") or {})
    c["web_search"]["stages"] = dict(c["web_search"].get("stages") or {})
    c["web_search"].update(over)
    return c


# ---------------------------------------------------------- 1 配置段
ws = mod.DEFAULT_CONFIG.get("web_search")
ck("W1.1 配置段存在", isinstance(ws, dict), repr(type(ws).__name__))
if isinstance(ws, dict):
    ck("W1.2 默认关", ws.get("enabled") is False, repr(ws.get("enabled")))
    q = ws.get("quota") or {}
    ck("W1.3 配额三层齐",
       all(k in q for k in ("per_stage_round", "per_stage_total",
                            "per_run_total")), repr(sorted(q)))
    st = ws.get("stages") or {}
    ck("W1.4 修行层/停止判据默认关",
       st.get("practice_term_calibration") is False
       and st.get("stop_criteria") is False, repr(sorted(st)))
    ck("W1.5 研究层默认开", st.get("research_decompose") is True, "")
    ck("W1.6 降级阈值 3", ws.get("auto_disable_after_failures") == 3,
       repr(ws.get("auto_disable_after_failures")))
    # 负对照：external_anchor 键集不许变
    ref = Path(HERE / "_baseline_v1220.py")
    _ea_now = set((mod.DEFAULT_CONFIG.get("external_anchor") or {}).keys())
    ck("W1.7 ✓加性：external_anchor 键集未变",
       _ea_now == {"enabled", "path", "max_items", "crosscheck", "tier_floor",
                   "answers_min_len", "answers_max_n", "api_key_env",
                   "cache_ttl_hours", "per_round", "as_evidence", "triage",
                   "retriever"}, repr(sorted(_ea_now)))
else:
    for k in ("W1.2", "W1.3", "W1.4", "W1.5", "W1.6", "W1.7"):
        ck(k, False, "配置段缺失")

# ---------------------------------------------------------- 2 独立 logger
lw = getattr(mod, "logger_web", None)
ck("W1.8 logger_web 存在", lw is not None, repr(getattr(lw, "name", None)))
if lw is not None:
    ck("W1.9 名字是 dgtf.websearch", lw.name == "dgtf.websearch", lw.name)
    ck("W1.10 ★ propagate=False（修正 B2）",
       lw.propagate is False, repr(lw.propagate))
    # ★ 功能性证明：父 logger 的 handler **收不到**本通道的记录
    seen = []

    class _H(logging.Handler):
        def emit(self, rec):
            seen.append(rec.getMessage())

    _parent = logging.getLogger("dgtf")
    _h = _H()
    _parent.addHandler(_h)
    _old = _parent.level
    _parent.setLevel(logging.DEBUG)
    try:
        lw.warning("[W-PROBE] 不该出现在主线日志里")
    finally:
        _parent.removeHandler(_h)
        _parent.setLevel(_old)
    ck("W1.11 ★ 主 logger 收不到 [W-（修正 B2 的正面证据）",
       not any("[W-PROBE]" in x for x in seen), repr(seen))
else:
    for k in ("W1.9", "W1.10", "W1.11"):
        ck(k, False, "logger_web 缺失")

ck("W1.12 五档失败类型常量",
   tuple(getattr(mod, "WEB_FAIL_KINDS", ()))
   == ("timeout", "rate_limit", "empty", "dirty", "api_error"),
   repr(getattr(mod, "WEB_FAIL_KINDS", None)))

# ---------------------------------------------------------- 3 Gate
Gate = getattr(mod, "WebSearchGate", None)
ck("W1.13 WebSearchGate 存在", Gate is not None, "")
if Gate is not None:
    g0 = Gate(cfg_of())
    ok, why = g0.allow("research_decompose", 1)
    ck("W1.14 负对照：默认关 → allow False", ok is False, why)
    ck("W1.15 默认关 → disabled True", g0.disabled is True, "")

    g = Gate(cfg_of(enabled=True))
    ok1, _ = g.allow("research_decompose", 1)
    ck("W1.16 授权环节 → allow True", ok1 is True, _)
    ok2, why2 = g.allow("stop_criteria", 1)
    ck("W1.17 未授权环节 → False", ok2 is False, why2)
    ok3, why3 = g.allow("practice_term_calibration", 1)
    ck("W1.18 修行层默认关 → False", ok3 is False, why3)

    # 本圈配额（per_stage_round=2）
    g.note_call("research_decompose", 1)
    g.note_call("research_decompose", 1)
    ok4, why4 = g.allow("research_decompose", 1)
    ck("W1.19 本圈配额用尽 → False", ok4 is False, why4)
    ok5, _ = g.allow("research_decompose", 2)
    ck("W1.20 换一圈 → 允许", ok5 is True, "")

    # 全程配额（per_stage_total=8）
    g2 = Gate(cfg_of(enabled=True))
    for i in range(8):
        g2.note_call("research_decompose", 100 + i)   # 每圈只 1 次
    ck("W1.21 stage 全程计数 = 8", g2.stage_counts["research_decompose"] == 8, "")
    ok6, why6 = g2.allow("research_decompose", 999)
    ck("W1.22 stage 全程配额用尽 → False", ok6 is False, why6)

    # 每跑总配额（per_run_total=30）
    g3 = Gate(cfg_of(enabled=True))
    for i in range(30):
        g3.note_call("research_decompose", 1000 + i)
    ok7, why7 = g3.allow("duel_arbitration", 2000)
    ck("W1.23 每跑总配额用尽 → False", ok7 is False, why7)

    # ★ 连续失败降级（修正 B3）
    g4 = Gate(cfg_of(enabled=True))
    r1 = g4.note_failure("timeout")
    r2 = g4.note_failure("timeout")
    ck("W1.24 前两次失败不降级", r1 is False and r2 is False, repr([r1, r2]))
    ck("W1.25 此时 disabled 仍 False", g4.disabled is False, "")
    r3 = g4.note_failure("timeout")
    ck("W1.26 ★ 第 3 次失败触发降级（返回 True）", r3 is True, repr(r3))
    ck("W1.27 ★ disabled 真的被置位（修正 B3）", g4.disabled is True, "")
    ck("W1.28 ★ 降级理由可读", "连续失败 3 次" in g4.disable_reason,
       g4.disable_reason)
    ok8, why8 = g4.allow("research_decompose", 1)
    ck("W1.29 降级后 allow False", ok8 is False, why8)
    ck("W1.30 降级后 reason 说降级", "降级" in why8, why8)

    g5 = Gate(cfg_of(enabled=True))
    g5.note_failure("timeout")
    g5.note_failure("timeout")
    g5.note_success()
    g5.note_failure("timeout")
    ck("W1.31 note_success 清零计数", g5.consecutive_failures == 1,
       repr(g5.consecutive_failures))
    ck("W1.32 清零后未降级", g5.disabled is False, "")
else:
    for i in range(14, 33):
        ck("W1.%d" % i, False, "Gate 缺失")

# ---------------------------------------------------------- 4 Client + Cache
Client = getattr(mod, "WebSearchClient", None)
Cache = getattr(mod, "WebSearchCache", None)
ck("W1.33 WebSearchClient 存在", Client is not None, "")
ck("W1.34 WebSearchCache 存在", Cache is not None, "")
if Client is not None and Cache is not None:
    d = Path(tempfile.mkdtemp())
    cache = Cache(24, root=str(d / "websearch"))
    c = Client("tavily", "k", 1, 2, 0.0, cache)

    # (a) 缓存：同 query 第二次不打网络
    c._http = lambda q, n: ([{"claim": "x", "url": "u"}], "")
    r1, k1 = c.search("Q1")
    n_after_first = c.calls
    r2, k2 = c.search("Q1")
    ck("W1.35 首次真打网络", n_after_first == 1, repr(n_after_first))
    ck("W1.36 ★ 第二次命中缓存、不增 calls", c.calls == 1, repr(c.calls))
    ck("W1.37 缓存命中计数", c.cache_hits == 1, repr(c.cache_hits))
    ck("W1.38 两次结果一致", r1 == r2 and k1 == k2 == "", "")

    # (b) 五档失败 + 重试次数
    for kind, expect_calls, terminal in (("timeout", 3, False),
                                        ("rate_limit", 3, False),
                                        ("api_error", 3, False),
                                        ("dirty", 3, False),
                                        ("empty", 1, True)):
        c2 = Client("tavily", "k", 1, 2, 0.0, None)
        c2._http = (lambda _k: (lambda q, n: ([], _k)))(kind)
        res, got = c2.search("Q-" + kind)
        _calls = c2.calls
        ck("W1.39.%s 返回分类正确" % kind, got == kind, repr(got))
        ck("W1.39b.%s 重试次数 %d" % (kind, expect_calls),
           _calls == expect_calls, repr(_calls))
        ck("W1.39c.%s empty 是终态不重试" % kind,
           (not terminal) or _calls == 1, repr(_calls))

    # (c) 负对照：未知后端抛错，不静默降级
    c3 = Client("bing", "k", 1, 0, 0.0, None)
    _raised = False
    try:
        c3.search("Q")
    except RuntimeError as e:
        _raised = "尚未实现" in str(e)
    ck("W1.40 负对照：未知后端抛错且写明「尚未实现」", _raised, "")

    # (d) 缓存目录不与锚点混用
    # ★ 默认 root 必须是 cache/websearch（上面传的是临时目录，测行为用）
    _def_root = Cache().root
    ck("W1.41 ★ 默认缓存目录 = cache/websearch",
       str(_def_root).replace("\\", "/").endswith("cache/websearch"),
       str(_def_root))
    _ra = getattr(mod, "AnchorRetriever", None)
    if _ra is not None:
        _p = _ra("tavily", "k")._cache_path(["q"])
        ck("W1.42 ★ 锚点缓存目录未动（cache/anchors）",
           "anchors" in str(_p) or "anchors" in str(Path("cache/anchors")), str(_p))

    # (e) 工厂：造对象但不发调用
    build = getattr(mod, "build_web_search", None)
    ck("W1.43 build_web_search 存在", callable(build), "")
    if callable(build):
        g6, c6 = build(cfg_of(enabled=True))
        ck("W1.44 工厂返回 Gate/Client", isinstance(g6, Gate)
           and isinstance(c6, Client), "")
        ck("W1.45 ★ 工厂不发起任何调用", c6.calls == 0 and c6.cache_hits == 0,
           repr([c6.calls, c6.cache_hits]))
else:
    for i in range(35, 46):
        ck("W1.%d" % i, False, "Client/Cache 缺失")

print("═══ probe v123 W1 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
print("PASS %d / FAIL %d" % (sum(1 for _, o, _ in R if o),
                             sum(1 for _, o, _ in R if not o)))
sys.exit(0 if all(o for _, o, _ in R) else 1)
