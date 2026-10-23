# -*- coding: utf-8 -*-
"""[v1.23.0 W1] 给 _v122_verify.py 加 `v123_w1` 档。幂等：整段替换 + 精确注册守卫。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VF = HERE / "_v122_verify.py"
MARK_A = "# <<<v123 phase>>>"
MARK_B = "# <<<end v123 phase>>>"
REG_KEY = '"v123_w5": phase_v123_w5'   # ★ 用**最后一项**当哨兵：
#   用第一项会在「已注册 w1、要补 w2~w5」时静默跳过（本轮踩到）。

BLOCK = r'''
# <<<v123 phase>>>
def phase_v123_w1(src, mod):
    """[v1.23.0 W1] 核心联网基础设施（不接入任何环节）。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    ws = (getattr(mod, "DEFAULT_CONFIG", {}) or {}).get("web_search") or {}
    check("W1.1", ws.get("enabled") is False, "web_search.enabled 默认 False")
    _q = ws.get("quota") or {}
    check("W1.2", all(k in _q for k in ("per_stage_round", "per_stage_total",
                                        "per_run_total")),
          "配额三层齐（" + str(sorted(_q)) + "）")
    _st = ws.get("stages") or {}
    check("W1.3", _st.get("practice_term_calibration") is False
          and _st.get("stop_criteria") is False, "修行层/停止判据默认关")
    lw = getattr(mod, "logger_web", None)
    check("W1.4.a", lw is not None and lw.name == "dgtf.websearch",
          "logger_web 名字 dgtf.websearch")
    check("W1.4.b ★", lw is not None and lw.propagate is False,
          "propagate=False（修正 B2）")
    check("W1.5", tuple(getattr(mod, "WEB_FAIL_KINDS", ())) ==
          ("timeout", "rate_limit", "empty", "dirty", "api_error"),
          "五档失败类型常量")
    for k in ("WebSearchCache", "WebSearchClient", "WebSearchGate",
              "build_web_search"):
        check("W1.6." + k, hasattr(mod, k), k + " 存在")

    if not (hasattr(mod, "WebSearchGate") and mod.WebSearchGate):
        return
    _def = {"web_search": dict(ws)}
    _def["web_search"]["quota"] = dict(_q)
    _def["web_search"]["stages"] = dict(_st)

    def _cfg(**over):
        c = {"web_search": dict(ws)}
        c["web_search"]["quota"] = dict(_q)
        c["web_search"]["stages"] = dict(_st)
        c["web_search"].update(over)
        return c

    G = mod.WebSearchGate
    check("W1.7 负对照", G(_cfg()).allow("research_decompose", 1)[0] is False,
          "默认关 → allow False")
    g = G(_cfg(enabled=True))
    check("W1.8", g.allow("research_decompose", 1)[0] is True, "授权环节 allow")
    check("W1.9", g.allow("stop_criteria", 1)[0] is False, "未授权环节拒")
    g.note_call("research_decompose", 1)
    g.note_call("research_decompose", 1)
    check("W1.10", g.allow("research_decompose", 1)[0] is False, "本圈配额拦住")
    g2 = G(_cfg(enabled=True))
    for i in range(8):
        g2.note_call("research_decompose", 100 + i)
    check("W1.11", g2.allow("research_decompose", 5)[0] is False, "全程配额拦住")
    g4 = G(_cfg(enabled=True))
    g4.note_failure("timeout")
    g4.note_failure("timeout")
    _r3 = g4.note_failure("timeout")
    check("W1.12.a ★", _r3 is True and g4.disabled is True,
          "第 3 次失败真的置 disabled（修正 B3）")
    check("W1.12.b", "连续失败 3 次" in g4.disable_reason
          and "降级" in g4.allow("research_decompose", 1)[1],
          "降级理由可读且 allow 与 disabled 状态一致")
    g5 = G(_cfg(enabled=True))
    g5.note_failure("t")
    g5.note_failure("t")
    g5.note_success()
    g5.note_failure("t")
    check("W1.13", g5.consecutive_failures == 1 and g5.disabled is False,
          "note_success 清零")

    if hasattr(mod, "WebSearchClient") and hasattr(mod, "WebSearchCache"):
        import tempfile as _tf
        C, Ca = mod.WebSearchClient, mod.WebSearchCache
        d = Path(_tf.mkdtemp())
        ca = Ca(24, root=str(d / "websearch"))
        c = C("tavily", "k", 1, 2, 0.0, ca)
        c._http = lambda q, n: ([{"claim": "x", "url": "u"}], "")
        c.search("Q1")
        c.search("Q1")
        check("W1.14", c.calls == 1 and c.cache_hits == 1,
              "缓存命中不增 calls（" + str([c.calls, c.cache_hits]) + "）")
        for kind, want in (("timeout", 3), ("rate_limit", 3), ("api_error", 3),
                           ("dirty", 3), ("empty", 1)):
            _c2 = C("tavily", "k", 1, 2, 0.0, None)
            _c2._http = (lambda _k: (lambda q, n: ([], _k)))(kind)
            _r, _got = _c2.search("Q-" + kind)
            check("W1.15." + kind, _got == kind and _c2.calls == want,
                  "%s → 分类 %s / 重试 %d" % (kind, _got, _c2.calls))
        _c3 = C("bing", "k", 1, 0, 0.0, None)
        try:
            _c3.search("Q")
            check("W1.16 负对照", False, "未知后端竟未抛错")
        except RuntimeError as e:
            check("W1.16 负对照", "尚未实现" in str(e), "未知后端抛错不降级")
        check("W1.17", str(Ca().root).replace("\\", "/").endswith(
            "cache/websearch"), "默认缓存目录 cache/websearch")
        _ra = getattr(mod, "AnchorRetriever", None)
        if _ra is not None:
            check("W1.18", "anchors" in str(_ra("tavily", "k")._cache_path(["q"])),
                  "锚点缓存目录未动（不与联网混用）")
        _g, _c = mod.build_web_search(_cfg(enabled=True))
        check("W1.19", _c.calls == 0 and isinstance(_g, G),
              "工厂不发起任何调用")
    check("W1.20", (HERE / "v1230_w1_报告.md").is_file(), "v1230_w1_报告.md 存在")

def _run_probe(name, src):
    """把探针当**验收命令**跑（子进程）：探针本身就是该档的判据集合，
    不在这里重抄一遍 —— 重抄必然两处分叉（本项目的老坑）。"""
    import subprocess
    import sys as _s
    _pp = HERE / name
    check("X." + name, _pp.is_file(), name + " 存在")
    if not _pp.is_file():
        return
    _r = subprocess.run([_s.executable, str(_pp), str(src)],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=900)
    _tail = (_r.stdout or "").strip().splitlines()[-1:] or [""]
    check("X." + name + ".exit", _r.returncode == 0,
          name + " exit=" + str(_r.returncode) + " " + _tail[0][:90])
    for _ln in (_r.stdout or "").splitlines():
        if _ln.strip().startswith("✗"):
            check("X." + name + ".fail", False, _ln.strip()[:150])


def phase_v123_w2(src, mod):
    """[W2] 研究层接入 + W# 引用门 + W# 硬约束（判据在探针里，含 3 变异体）。"""
    _run_probe("_probe_v123_w2.py", src)
    check("W2.rep", (HERE / "v1230_w2_报告.md").is_file(),
          "v1230_w2_报告.md 存在")


def phase_v123_w34(src, mod):
    """[W3+W4] 对撞/元层接入 + 三票正交化 + 宪法 C3/C4（含 2 变异体）。"""
    _run_probe("_probe_v123_w34.py", src)
    check("W34.rep", (HERE / "v1230_w34_报告.md").is_file(),
          "v1230_w34_报告.md 存在")


def phase_v123_w5(src, mod):
    """[W5] 缩减版全量回归：真后端单点 + ON/OFF 各 1 跑 + 报告。"""
    _j = HERE / "_v1230_w5_consistency.json"
    check("W5.1", _j.is_file(), "_v1230_w5_consistency.json 存在")
    if _j.is_file():
        import json as _json
        _d = _json.loads(_j.read_text(encoding="utf-8"))
        _rb = _d.get("real_backend") or {}
        check("W5.2 真后端单点跑通",
              _rb.get("kind") == "" and _rb.get("n", 0) > 0,
              "真 tavily 返回 %s 条（kind=%r）" % (_rb.get("n"), _rb.get("kind")))
        # ★ 口径放宽到「缓存**确实**命中过」：若该 query 在上一轮已被缓存，
        #   本次 calls_total 会是 0（直接命中），那不是缺陷。
        check("W5.3 真后端缓存生效", _rb.get("cache_hits", 0) >= 1,
              "命中缓存 %s 次；本次真打网络 %s 次"
              % (_rb.get("cache_hits"), _rb.get("calls_total")))
        _runs = {x["arm"]: x for x in (_d.get("runs") or [])}
        check("W5.4 ON/OFF 两跑都在", {"WON", "WOFF"} <= set(_runs),
              repr(sorted(_runs)))
        if "WOFF" in _runs:
            check("W5.5 负对照：OFF 臂零检索",
                  _runs["WOFF"]["web_results"] == 0
                  and _runs["WOFF"].get("gate", {}).get("run_total", 0) == 0,
                  "OFF 臂 web_results=%s" % _runs["WOFF"]["web_results"])
        if "WON" in _runs:
            check("W5.6 ON 臂真的检索了（W# 或失败留痕）",
                  _runs["WON"]["web_results"] > 0
                  or _runs["WON"]["web_errors"] > 0,
                  "W#=%s errors=%s stages=%s"
                  % (_runs["WON"]["web_results"], _runs["WON"]["web_errors"],
                     _runs["WON"]["web_stages"]))
            check("W5.7 ON 臂 stability 口径可读",
                  all(x in ("high", "medium", "low", "abstained")
                      for x in _runs["WON"]["stability"]),
                  repr(_runs["WON"]["stability"]))
    check("W5.8", (HERE / "v123_报告.md").is_file(), "v123_报告.md 存在")

# <<<end v123 phase>>>
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

if REG_KEY not in s:
    # ★ 精确注册守卫：不许用「子串在某处出现过」当判断（v1.22.2 已踩过：)
    #   插入块里含 `v123_w1_报告.md` 这类文件名，子串判断恒假 → 静默不注册。
    _old1 = ('          "v1222_p3": phase_v1222_p3, "v1222_p4": '
            'phase_v1222_p4}\n')
    _old2 = ('          "v1222_p3": phase_v1222_p3, "v1222_p4": '
             'phase_v1222_p4,\n'
             '          "v123_w1": phase_v123_w1}\n')
    _new2 = ('          "v1222_p3": phase_v1222_p3, "v1222_p4": '
             'phase_v1222_p4,\n'
             '          "v123_w1": phase_v123_w1,\n'
             '          "v123_w2": phase_v123_w2,\n'
             '          "v123_w34": phase_v123_w34,\n'
             '          "v123_w5": phase_v123_w5}\n')
    if s.count(_old2) == 1:
        s = s.replace(_old2, _new2)
    else:
        assert s.count(_old1) == 1, "PHASES 注册块（无 w1）命中 %d 次" % s.count(_old1)
        s = s.replace(_old1, _new2)
    print("已注册 v123_w1/w2/w34/w5")
else:
    print("v123_w1 已注册，跳过")

out = s.replace("\n", nl).encode("utf-8")
if nl == "\r\n":
    assert out.count(b"\r\r\n") == 0
    assert out.count(b"\r") == out.count(b"\r\n")
VF.write_bytes(out)
print("OK: _v122_verify.py 已加 v123_w1")
