# -*- coding: utf-8 -*-
"""[v1.23.0 W1] 把 check_v123_w1 同步进 smoke_test.py，并把 SRC 指向本版。

规则（照 v1.22.1「接线器」的教训）：
  · 只动自己的守卫名，绝不 GUARD_RE 通删；
  · 新守卫插在**已有守卫之后**；
  · 硬断言：守卫总数不许比基线少；
  · smoke_test.py 保持纯 CRLF。
幂等：v123 检查块以 MARK 为界整段替换。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
NEW_SRC_NAME = "元DGTF-V1.23.4.py"

MARK_A = "# <<<v123 checks>>>"
MARK_B = "# <<<end v123 checks>>>"

CHECKS = r'''
# <<<v123 checks>>>
def check_v123_w1(SRC=None):
    """[v1.23.0 W1] 核心联网基础设施（**不接入任何环节**）。

    ★ 覆盖三处核验后回写的卡点：
      · [修正 B2] logger_web.propagate=False + **父 logger 收不到 [W-** 的功能性证据；
      · [修正 B3] 第 3 次失败必须**真的把 disabled 置位**且理由可读；
      · 缓存目录 cache/websearch 与 cache/anchors 不混用。
    ★ 负对照：默认关 → allow() 恒 False；空结果 empty 是**终态**不重试。
    """
    try:
        import logging as _lg
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)

        # ---------- 1 配置段 ----------
        ws = m.DEFAULT_CONFIG.get("web_search")
        assert isinstance(ws, dict), "web_search 配置段缺失"
        assert ws.get("enabled") is False, "默认必须是关"
        _q = ws.get("quota") or {}
        for _k in ("per_stage_round", "per_stage_total", "per_run_total"):
            assert _k in _q, "配额三层缺 " + _k
        _st = ws.get("stages") or {}
        assert _st.get("practice_term_calibration") is False, "修行层默认没关"
        assert _st.get("stop_criteria") is False, "停止判据默认没关"
        assert _st.get("research_decompose") is True, "研究层默认没开"
        assert ws.get("auto_disable_after_failures") == 3, "降级阈值不是 3"
        # ★ 负对照：external_anchor 一键未动（加性）
        _ea = m.DEFAULT_CONFIG.get("external_anchor") or {}
        for _k in ("answers_min_len", "answers_max_n", "as_evidence",
                   "tier_floor", "triage", "retriever"):
            assert _k in _ea, "external_anchor 被改动：" + _k

        # ---------- 2 独立 logger（修正 B2） ----------
        lw = getattr(m, "logger_web", None)
        assert lw is not None, "logger_web 缺失"
        assert lw.name == "dgtf.websearch", "名字不对：" + lw.name
        assert lw.propagate is False, \
            "★ propagate 必须 False（否则日志同时进主 logger dgtf）"
        _seen = []

        class _H(_lg.Handler):
            def emit(self, rec):
                _seen.append(rec.getMessage())

        _par = _lg.getLogger("dgtf")
        _h = _H()
        _par.addHandler(_h)
        _old = _par.level
        _par.setLevel(_lg.DEBUG)
        try:
            lw.warning("[W-SMOKE] 不许出现在主 logger")
        finally:
            _par.removeHandler(_h)
            _par.setLevel(_old)
        assert not any("[W-SMOKE]" in x for x in _seen), \
            "★ 主 logger 收到了 [W- 记录（propagate 没生效）"

        assert tuple(getattr(m, "WEB_FAIL_KINDS", ())) == (
            "timeout", "rate_limit", "empty", "dirty", "api_error"), \
            "五档失败类型常量不对"

        # ---------- 3 Gate ----------
        def _cfg(**over):
            c = {"web_search": dict(m.DEFAULT_CONFIG["web_search"])}
            c["web_search"]["quota"] = dict(c["web_search"]["quota"])
            c["web_search"]["stages"] = dict(c["web_search"]["stages"])
            c["web_search"].update(over)
            return c

        G = m.WebSearchGate
        g0 = G(_cfg())
        assert g0.allow("research_decompose", 1)[0] is False, \
            "负对照：默认关竟 allow"
        assert g0.disabled is True, "默认关时 disabled 应为 True"

        g = G(_cfg(enabled=True))
        assert g.allow("research_decompose", 1)[0] is True, "授权环节应 allow"
        assert g.allow("stop_criteria", 1)[0] is False, "未授权环节竟 allow"
        assert g.allow("practice_term_calibration", 1)[0] is False, \
            "修行层默认关却 allow"
        g.note_call("research_decompose", 1)
        g.note_call("research_decompose", 1)
        assert g.allow("research_decompose", 1)[0] is False, "本圈配额没拦住"
        assert g.allow("research_decompose", 2)[0] is True, "换圈应恢复"

        g2 = G(_cfg(enabled=True))
        for i in range(8):
            g2.note_call("research_decompose", 100 + i)
        assert g2.allow("research_decompose", 500)[0] is False, \
            "stage 全程配额没拦住"

        g3 = G(_cfg(enabled=True))
        for i in range(30):
            g3.note_call("research_decompose", 1000 + i)
        assert g3.allow("duel_arbitration", 2000)[0] is False, \
            "每跑总配额没拦住"

        # ★ 连续失败降级（修正 B3）
        g4 = G(_cfg(enabled=True))
        assert g4.note_failure("timeout") is False, "第 1 次就降级了"
        assert g4.note_failure("timeout") is False, "第 2 次就降级了"
        assert g4.disabled is False, "第 2 次后不该 disabled"
        assert g4.note_failure("timeout") is True, "第 3 次未触发降级"
        assert g4.disabled is True, "★ disabled 未被置位（修正 B3 退回）"
        assert "连续失败 3 次" in g4.disable_reason, "降级理由不可读"
        _ok, _why = g4.allow("research_decompose", 1)
        assert _ok is False and "降级" in _why, "降级后 allow/reason 不一致"

        g5 = G(_cfg(enabled=True))
        g5.note_failure("timeout")
        g5.note_failure("timeout")
        g5.note_success()
        g5.note_failure("timeout")
        assert g5.consecutive_failures == 1 and g5.disabled is False, \
            "note_success 没清零"

        # ---------- 4 Client + Cache ----------
        C = m.WebSearchClient
        Ca = m.WebSearchCache
        d = _P(_tf.mkdtemp())
        ca = Ca(24, root=str(d / "websearch"))
        c = C("tavily", "k", 1, 2, 0.0, ca)
        c._http = lambda q, n: ([{"claim": "x", "url": "u"}], "")
        c.search("Q1")
        assert c.calls == 1, "首次应打一次网络"
        c.search("Q1")
        assert c.calls == 1 and c.cache_hits == 1, \
            "★ 第二次应命中缓存、不增 calls"

        for _kind, _n in (("timeout", 3), ("rate_limit", 3), ("api_error", 3),
                          ("dirty", 3), ("empty", 1)):
            _c2 = C("tavily", "k", 1, 2, 0.0, None)
            _c2._http = (lambda _k: (lambda q, n: ([], _k)))(_kind)
            _r, _got = _c2.search("Q-" + _kind)
            assert _got == _kind, "分类错：" + repr(_got)
            assert _c2.calls == _n, "%s 重试次数应为 %d，实测 %d" % (
                _kind, _n, _c2.calls)

        _c3 = C("bing", "k", 1, 0, 0.0, None)
        try:
            _c3.search("Q")
            raise AssertionError("未知后端竟未抛错")
        except RuntimeError as _e:
            assert "尚未实现" in str(_e), "未知后端错误信息未写明「尚未实现」"

        assert str(Ca().root).replace("\\", "/").endswith("cache/websearch"), \
            "默认缓存目录不是 cache/websearch"
        _ra = getattr(m, "AnchorRetriever", None)
        if _ra is not None:
            _p = _ra("tavily", "k")._cache_path(["q"])
            assert "anchors" in str(_p), "锚点缓存目录被改动"

        _g, _c = m.build_web_search(_cfg(enabled=True))
        assert isinstance(_g, G) and isinstance(_c, C), "工厂返回类型不对"
        assert _c.calls == 0, "★ 工厂不该发起任何调用"

        print("  ✓ v1.23.0 W1：配置段/独立通道(propagate=False)/Gate 三方向/"
              "连续失败置位/五档失败/缓存命中/空结果终态/未知后端抛错/"
              "锚点目录未混用 —— 全部带负对照")
        return True
    except Exception as e:
        print("  ✗ v1.23.0 W1 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v123_w2(SRC=None):
    """[v1.23.0 W2] 研究层接入 + W# 编号 + 引用门 + W# 硬约束。

    ★ 判据带 **3 个变异体**（结构不变式在现版必然通过 ⇒「通过」不是判别力）：
      M1 抠掉 W# 硬约束 / M2 抠掉 W# 进表 / M3 抠掉 prompt 里的摘要注入。
    ★ 空过防线：每条 apply 判据的初态都必须**与目标态不同**，且断言理由
      不是「与当前判定相同」—— 变异测试在这里抓到过两处空过。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        Pool, View = m.Pool, m.View

        assert all(hasattr(Pool(), _k) for _k in
                   ("web_results", "web_errors", "web_as_evidence")), \
            "Pool 缺 W2 字段"
        assert all(hasattr(m, _k) for _k in
                   ("_next_web_id", "_web_evidence_gate",
                    "_research_decompose_queries", "_research_evidence_queries",
                    "_research_precedent_queries", "_web_digest_block")), \
            "W2 助手函数缺"
        assert all(hasattr(m.MetaDGTF, _k) for _k in
                   ("_web_search", "_research_web_prep",
                    "_research_decompose_with_web", "_web_evidence_hook")), \
            "W2 MetaDGTF 方法缺"
        assert src.count("d0._decompose_from_pool(") == 1, "拆解仍有第二份"
        assert src.count("d0._decompose_question(") == 1, "拆解仍有第二份"
        assert src.count("web_hook=self._web_evidence_hook") == 2, \
            "update_deferrals 两处调用点未接钩子"
        assert src.count('getattr(self, "_web_digest", "")') == 4, \
            "摘要注入点不是 4 处"

        def _mkpool(init_dec="undecidable", **kw):
            o = Pool()
            o.sub_questions = [{"id": 1, "question": "重现期是多少",
                                "decidability": init_dec}]
            for k, v in kw.items():
                setattr(o, k, v)
            return o

        _pa = _mkpool(web_results=[{"id": "W1", "claim": "重现期 3~5 年"}],
                      web_as_evidence=True)
        assert "W1" in dict(m._citation_table(None, _pa)), \
            "★ 授权时 W# 未进引用表（[修正 B1] 的正面证据）"
        assert m._resolve_citation("W1", None, _pa), "W1 解析不到"
        _pb = _mkpool(web_results=[{"id": "W1", "claim": "x"}],
                      web_as_evidence=False)
        assert "W1" not in dict(m._citation_table(None, _pb)), \
            "负对照：未授权时 W# 竟进表"

        for _to, _init, _want in (("partial", "undecidable", "applied"),
                                  ("decidable", "partial", "rejected"),
                                  ("undecidable", "decidable", "rejected")):
            _pp = _mkpool(init_dec=_init,
                          web_results=[{"id": "W1", "claim": "重现期 3~5 年"}],
                          web_as_evidence=True)
            _vv = View(entry="1")
            _r = m.apply_decidability_change(
                _pp, _vv, {1: _pp.sub_questions[0]}, 1, _to, 3, "冒烟", ["W1"])
            assert _r["status"] == _want, \
                "W#→%s 应 %s，实测 %s" % (_to, _want, _r["status"])
            assert "与当前判定相同" not in str(_r.get("why", "")), \
                "★ 空过：W#→%s 走了「无需变更」" % _to
        _pc = _mkpool(init_dec="decidable", amps=[{"desc": "运维断点"}],
                      web_as_evidence=True)
        _rc = m.apply_decidability_change(_pc, View(entry="1"),
                                         {1: _pc.sub_questions[0]}, 1,
                                         "partial", 3, "冒烟", ["A1"])
        assert _rc["status"] == "applied", "负对照：A1 被 W# 规则误伤"

        class _SC:
            def __init__(self, kind=""):
                self.calls = 0
                self.cache_hits = 0
                self.kind = kind

            def search(self, q, max_n=8):
                self.calls += 1
                if self.kind:
                    return [], self.kind
                return [{"claim": "桩：" + q, "url": "u", "source": "s",
                         "tier": 3}], ""

        def _mkmeta(enabled, client=None, **over):
            cfg = {"web_search": dict(m.DEFAULT_CONFIG["web_search"])}
            cfg["web_search"]["quota"] = dict(cfg["web_search"]["quota"])
            cfg["web_search"]["stages"] = dict(cfg["web_search"]["stages"])
            cfg["web_search"].update({"enabled": enabled, **over})
            o = object.__new__(m.MetaDGTF)
            o.config = cfg
            o.pools = {"1": Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = m.WebSearchGate(cfg)
            o._web_client = client or _SC()
            o._web_prep_seq = 0
            o.decidability_result = {
                "undecidable_aspects": ["[外] 上游是否有官方标准"]}
            return o

        _o = _mkmeta(False)
        assert _o._web_search("research_decompose", ["q"], 1) == [], \
            "负对照：默认关竟返回结果"
        assert _o._web_client.calls == 0, "★ 负对照：默认关竟打了网络"

        _o2 = _mkmeta(True, as_evidence="evidence")
        _r2 = _o2._web_search("research_decompose", ["q1", "q2"], 1)
        assert [x["id"] for x in _r2] == ["W1", "W2"], "编号不是 W1/W2"
        assert _o2.pools["1"].web_as_evidence is True, "授权门未同步"
        assert _o2._web_search("research_decompose", ["q3"], 1) == [], \
            "本圈配额没拦住"
        assert any("[W-SKIP]" in str(x) for x in _o2.pools["1"].meta), \
            "配额拒绝未留痕"
        assert any("[W-OK]" in str(x) for x in _o2.pools["1"].meta), \
            "★ 成功未留痕（产物里看不出收了几条）"

        _o3 = _mkmeta(True, _SC("timeout"))
        for _i in range(3):
            _o3._web_search("research_decompose", ["q%d" % _i], 10 + _i)
        assert any("[W-TIMEOUT]" in str(x) for x in _o3.pools["1"].meta), \
            "失败未进 pool.meta"
        assert len(_o3.pools["1"].web_errors) >= 3, "失败未进 web_errors"
        assert _o3._web_gate.disabled is True, "连续失败未降级"

        _o4 = _mkmeta(True, _SC("empty"))
        for _i in range(5):
            _o4._web_search("research_decompose", ["e%d" % _i], 20 + _i)
        assert _o4._web_gate.disabled is False, "★ 空结果竟把本跑降级了"
        assert any("[W-EMPTY]" in str(x) for x in _o4.pools["1"].meta), \
            "空结果未留痕"
        assert not [x for x in _o4.pools["1"].web_errors
                    if x.get("kind") == "empty"], "空结果被记成失败"

        assert m._web_digest_block([]) == "" and m._web_digest_block(None) == "", \
            "空摘要不是空串（加性破了）"
        _dg = m._web_digest_block([{"id": "W1", "stage": "s",
                                    "claim": "重现期", "tier": 3}])
        assert "【外部检索摘要】" in _dg and "参照" in _dg, "摘要块文案缺"
        assert m._research_evidence_queries({"to": "undecidable"}) == [], \
            "evidence 对 →undecidable 也发问（方向反了）"
        assert m._research_precedent_queries(["普通方面"]) == [], \
            "precedent 负对照：非 [外] 竟发问"

        MUT = (
            ("M1 W# 硬约束",
             '    if ent["to"] != "partial" and all(\n'
             '            str(r.get("resolved_to", "")).startswith("W")\n'
             '            for r in resolved):\n'
             '        return _reject("联网编号（W#）只能支撑 →partial，不能支撑 "\n'
             '                       f"→{ent[\'to\']}（网络检索质量不稳；"\n'
             '                       "且「能查到」证明不了「答不出」）")\n', ""),
            # ★ [v1.23.2] 锚点改为**尾段**：本版在这块中间插了 W# tier 门
            #   （`if not _web_enters_citation(...): continue`）⇒ 原来那个
            #   从 `if getattr(pool, ...)` 到 `break` 的连续锚**已不连续**，
            #   命中 0 次（判据随实现更新，不是放宽）。
            #   变异体改为 `pass`：删掉 append 后 W# 同样进不了引用表，
            #   M2 的判据意图（「W# 有没有进表」）一字未改。
            ("M2 W# 进表",
             '            _wi += 1\n'
             '            out.append((str(_w.get("id") or ("W" + str(_wi))),\n'
             '                        str(_w.get("claim", ""))[:120]))\n'
             '            if _wi >= 20:\n'
             '                break\n',
             '            pass\n'),
            ("M3 摘要注入",
             '                # [v1.23.0 W2] 外部检索摘要（**参照**）。未开联网时\n'
             '                #   它是空串 ⇒ prompt 逐字不变（加性）。\n'
             '                + (getattr(self, "_web_digest", "") or ""))\n',
             '                )\n'),
        )
        _td = _P(_tf.mkdtemp())
        for _idx, (_nm, _o_, _n_) in enumerate(MUT):
            _exp = 2 if _nm.startswith("M3") else 1
            if src.count(_o_) != _exp:
                raise AssertionError("变异体 %s 锚点 %d 次（应 %d）"
                                     % (_nm, src.count(_o_), _exp))
            _mp = _td / ("mut_w2_%d.py" % _idx)
            _mp.write_bytes(src.replace(_o_, _n_).replace("\n", "\r\n")
                            .encode("utf-8"))
            _mm = _v1221_mod(str(_mp))
            _red = False
            try:
                if _nm.startswith("M1"):
                    _pm = Pool()
                    _pm.sub_questions = [{"id": 1, "question": "q",
                                          "decidability": "decidable"}]
                    _pm.web_results = [{"id": "W1", "claim": "c"}]
                    _pm.web_as_evidence = True
                    _rm = _mm.apply_decidability_change(
                        _pm, View(entry="1"), {1: _pm.sub_questions[0]}, 1,
                        "undecidable", 3, "冒烟", ["W1"])
                    _red = (_rm["status"] == "applied")
                elif _nm.startswith("M2"):
                    _pm = Pool()
                    _pm.web_results = [{"id": "W1", "claim": "c"}]
                    _pm.web_as_evidence = True
                    _red = "W1" not in dict(_mm._citation_table(None, _pm))
                else:
                    _d = object.__new__(_mm.DGTF)
                    _seen = []

                    class _L:
                        def call(self, s, u, t, mx, json_mode=False,
                                 stage=None, **_k):
                            _seen.append(u or "")
                            return '{"sub_questions": []}'

                        def parse_json(self, raw):
                            import json as _j
                            return _j.loads(raw)
                    _d.llm = _L()
                    _d.verbose = False
                    _d._web_digest = "【外部检索摘要】"
                    _d._self_block = lambda: ""
                    _d.config = {"actions": {}}
                    _d._decompose_normal("Q", ["a"], ["b"])
                    _red = "【外部检索摘要】" not in "\n".join(_seen)
            except Exception:  # noqa: BLE001
                _red = True
            assert _red, "★ 变异体「%s」下判据**没判红**（无判别力）" % _nm

        print("  ✓ v1.23.0 W2：W# 编号/引用门/只许→partial/默认关零调用/"
              "配额/失败留痕/空结果终态/摘要只进 prompt + **3 变异体全判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.0 W2 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v123_pool_export(SRC=None):
    """[v1.23.0 W5-fix] **通用前向守卫**：Pool 的每个 dataclass 字段都必须出口。

    起因：`Pool.to_dict()` 是**显式**白名单，W2/W3 新增的 5 个联网字段没被列
    进去 ⇒ 真跑里 tavily 返回了结果、产物里 W# 却是 0（静默吞掉）。
    这与 `dec_norm` 是同一类坑。

    做法：把 Pool **所有** dataclass 字段填满（bool→True / dict→非空 / list→非空），
    再断言每一个字段名都出现在 `to_dict()` 的键里。任何人以后加字段忘了出口，
    这条立刻红 —— 不需要再靠「想起来」。
    ★ 带变异体：抠掉 `to_dict` 里 web_results 那一行 → 判据必须判红。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        def _miss(pool):
            return [f for f in m.Pool.__dataclass_fields__ if f not in pool.to_dict()]

        p = m.Pool()
        for f in m.Pool.__dataclass_fields__:
            cur = getattr(p, f)
            if isinstance(cur, bool):
                setattr(p, f, True)
            elif isinstance(cur, dict):
                setattr(p, f, {"_probe": 1})
            elif isinstance(cur, list):
                setattr(p, f, [{"_probe": 1}])
        _mo = _miss(p)
        assert not _mo, "★ Pool 字段没出口（to_dict 白名单漏了）：" + repr(_mo)

        # 加性：空 Pool 时联网键一个都不加（关闭态 packed 与前版逐字相同）
        _empty = set(m.Pool().to_dict())
        assert not any(str(k).startswith("web_") for k in _empty), \
            "空 Pool 竟挂了联网键（加性破了）：" + repr(sorted(_empty))

        # ★ 变异体：抠掉 to_dict 里的 web_results 出口
        O = ('        if self.web_results or self.web_errors or '
             'self.web_as_evidence:' + chr(10))
        assert src.count(O) == 1, "to_dict 出口锚点 %d 次" % src.count(O)
        _d = _P(_tf.mkdtemp())
        _mp = _d / "mut_export.py"
        _mp.write_bytes(src.replace(O, "        if False:" + chr(10))
                        .replace("\n", "\r\n").encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        _pm = _mm.Pool()
        _pm.web_results = [{"id": "W1"}]
        _red = "web_results" in _miss(_pm)
        assert _red, "★ 变异体（抠掉 web_results 出口）下判据没判红"

        print("  ✓ v1.23.0 W5-fix：Pool 字段出口前向守卫（全字段填满必须全出口 + "
              "空 Pool 零联网键 + 变异体判红）")
        return True
    except Exception as e:
        print("  ✗ v1.23.0 W5-fix 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v123_left(SRC=None):
    """[v1.23.1 遗留收尾] 真圈号（round_no）+ tier 提案（待审）。

    ★ 两条都带**变异体**：
      · 把提案写进 item["tier"] ⇒ 「提案是纯留痕」判据必须判红；
      · 前置圈号退回拆解序号 ⇒ 「前置=0」判据必须判红。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1 结构
        assert hasattr(m, "_web_tier_proposal"), "缺 tier 提案函数"
        assert hasattr(m, "_web_domain_of"), "缺 _web_domain_of"
        assert all(hasattr(m.WebSearchCache, k)
                   for k in ("domains_load", "domains_save")), "缺域名登记方法"
        assert "web_tier_proposals" in m.Pool.__dataclass_fields__, "Pool 缺字段"
        _wscfg = m.DEFAULT_CONFIG.get("web_search") or {}
        assert "tier_proposal" in _wscfg, "缺配置键 tier_proposal"
        assert "domain_tier_rules" in _wscfg, "缺配置键 domain_tier_rules"
        assert _wscfg["tier_proposal"] is False, "★ tier_proposal 必须默认关"

        # 2 round_no 口径：前置 = 0（且与拆解序号无关）
        _mo = object.__new__(m.MetaDGTF)
        _mo._web_prep_seq = 9
        assert m.MetaDGTF._research_round_no(_mo) == 0, (
            "★ 前置圈号不是 0（退回拆解序号了）")

        class _SC:
            def __init__(self, root, url="https://www.example.gov.cn/a",
                         cls=None):
                self.cache = (cls or m.WebSearchCache)(24, root=str(root))
                self.calls = 0
                self.cache_hits = 0
                self.url = url

            def search(self, q, max_n=8):
                self.calls += 1
                return [{"claim": "c" + str(q), "url": self.url,
                         "source": "s", "tier": 3}], ""

        def _mk(over=None, root=None, mod=None):
            mod = mod or m
            c = {"web_search": dict(mod.DEFAULT_CONFIG["web_search"])}
            for k in ("quota", "stages"):
                c["web_search"][k] = dict(c["web_search"].get(k) or {})
            c["web_search"]["domain_tier_rules"] = list(
                c["web_search"].get("domain_tier_rules") or [])
            c["web_search"].update(over or {"enabled": True,
                                            "as_evidence": "evidence"})
            o = object.__new__(mod.MetaDGTF)
            o.config = c
            o.pools = {"1": mod.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = mod.WebSearchGate(c)
            o._web_client = _SC(root or _P(_tf.mkdtemp()),
                                cls=mod.WebSearchCache)
            o._web_prep_seq = 0
            return o

        # 圈内钩子必须用真圈号（不是前置 0、也不是拆解序号）
        _o = _mk()
        _o._web_evidence_hook({"to": "partial", "_sq_text": "q"}, 3)
        _w = _o.pools["1"].web_results
        assert _w, "证据钩子没产出"
        assert all(int(x.get("round", -1)) == 3 for x in _w), (
            "★ 圈内钩子没用真圈号：" + repr([x.get("round") for x in _w]))
        assert all(x.get("round_kind") == "in" for x in _w), "round_kind 不是 in"
        _o2 = _mk()
        _o2._research_web_prep("Q")
        _w2 = _o2.pools["1"].web_results
        assert _w2, "前置检索没产出"
        assert all(int(x.get("round", -1)) == 0 for x in _w2), "前置 round 不是 0"
        assert all(x.get("round_kind") == "pre" for x in _w2), (
            "前置 round_kind 不是 pre")

        # 3 tier 提案：默认关零副作用 / 开启纯留痕
        _d = _P(_tf.mkdtemp())
        _off = _mk(root=_d)
        _off._web_search("research_evidence", ["a"], 1)
        assert _off.pools["1"].web_tier_proposals == [], "默认关竟挂提案"
        assert not (_d / "_domains.json").exists(), "默认关竟写域名文件"
        _t_off = [x.get("tier") for x in _off.pools["1"].web_results]

        _d2 = _P(_tf.mkdtemp())
        _on = _mk({"enabled": True, "as_evidence": "evidence",
                   "tier_proposal": True}, root=_d2)
        _on._web_search("research_evidence", ["a"], 1)
        _pr = _on.pools["1"].web_tier_proposals
        assert _pr, "开启后没有提案"
        assert any("[W-TIER?]" in str(x) for x in _on.pools["1"].meta), (
            "开启后提案未留痕")
        assert all(x.get("confirmed") is False for x in _pr), "提案被当成生效值"
        assert _pr[0].get("proposed_tier") == 1, (
            "gov.cn 应命中规则取 1（实测 %r）" % _pr[0].get("proposed_tier"))
        assert (_d2 / "_domains.json").is_file(), "域名未登记"
        assert [x.get("tier") for x in _on.pools["1"].web_results] == _t_off, (
            "★ 提案改了 item['tier']（应纯留痕）")

        # 4 变异体：把提案写进 item["tier"] → 上一条判据必须判红
        _o_anchor = "                    if _ck is not None:" + chr(10)
        assert src.count(_o_anchor) == 1, (
            "tier 提案锚点 %d 次" % src.count(_o_anchor))
        _nl, _cr = chr(10), chr(13)
        _mut = (_o_anchor
                + "                        for _it in out:" + _nl
                + "                            if _pr and "
                  "int(_it.get('tier', 3) or 3) == 3:" + _nl
                + "                                _it['tier'] = int("
                  "_pr[0]['proposed_tier'])" + _nl)
        _md = _P(_tf.mkdtemp())
        _mp = _md / "mut_left.py"
        _mp.write_bytes(src.replace(_o_anchor, _mut)
                        .replace(_nl, _cr + _nl).encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        _mo2 = _mk({"enabled": True, "as_evidence": "evidence",
                    "tier_proposal": True},
                   root=_P(_tf.mkdtemp()), mod=_mm)
        _mo2._web_search("research_evidence", ["a"], 1)
        _red = [x.get("tier") for x in _mo2.pools["1"].web_results] != [3]
        assert _red, "★ 变异体（提案写进 item tier）下判据没判红"

        print("  ✓ v1.23.1 遗留收尾：前置圈号=0 / 圈内=真圈号 / round_kind"
              " / tier 提案默认关零副作用 / gov.cn→1 待审 / 提案纯留痕"
              " + **变异体判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.1 遗留收尾失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1232_audit(SRC=None):
    """[v1.23.2 整体审计] 把 `_probe_v1232_audit.py` 当**验收命令**跑。

    ★ 为什么用子进程而不是重抄：审计探针本身就是那批判据的**单一事实源**
      （本项目老坑：同一批判据两处分叉，改一边忘一边）。
    """
    try:
        import subprocess
        import sys as _s
        _pp = HERE / "_probe_v1232_audit.py"
        assert _pp.is_file(), "_probe_v1232_audit.py 不存在"
        # ★ 被测文件取**已加载模块**的 __file__，不写死版本名 ——
        #   否则升版后 C2「smoke SRC 指向本版」必判红。
        _tgt = str(SRC or getattr(globals().get("mod"), "__file__", "")
                   or (HERE / "元DGTF-V1.23.3.py"))
        _r = subprocess.run([_s.executable, str(_pp), _tgt],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=900)
        _out = (_r.stdout or "") + (_r.stderr or "")
        _red = [l.strip() for l in _out.split(chr(10)) if l.strip().startswith("✗")]
        assert not _red, "审计判红 " + str(len(_red)) + " 条：" + _red[0][:110]
        _m = _out.strip().split(chr(10))[-1]
        print("  ✓ v1.23.2 整体审计：" + _m[:120])
        return True
    except Exception as e:
        print("  ✗ v1.23.2 整体审计失败：" + type(e).__name__ + ": " + str(e))
        return False


def check_v1232_tier(SRC=None):
    """[v1.23.2 遗留3] tier **确认**才生效（默认零差异 + 不进判定路径）。

    ★ 带变异体：把确认表读进 `tier_effective` 的那一步换成读**提案**——
      判据必须判红（「从提案到生效没有自动路径」这条红线）。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        def _cfg(**over):
            c = {"web_search": dict(m.DEFAULT_CONFIG.get("web_search") or {})}
            return c

        # ★ 必须显式 enabled —— 出厂默认是**关**，否则 `_web_search` 直接返回
        #   []，后面的「加性」断言会以「挂了 tier_effective」的形态**误报**
        #   （判据自己没被触发，却报成被测代码的问题）。
        _WS = dict(_cfg()["web_search"])
        _WS["enabled"] = True
        _WS["as_evidence"] = "evidence"
        # 1 默认：无确认表 ⇒ tier 3 仍可进表（与 v1.23.1 一致）+ 不挂键
        # ★ 必须有 claim —— `_citation_table` 会跳过 claim 为空的条目（
        #   第一版漏了它，判据以「W1 竟然进不了表」的形态误报）。
        _it = {"id": "W1", "claim": "c",
               "url": "https://www.example.gov.cn/a", "tier": 3}
        _p = m.Pool()
        _p.web_results = [dict(_it)]
        _p.web_as_evidence = True
        _p._web_cfg = dict(_WS)
        assert "W1" in dict(m._citation_table(None, _p)), "默认态 W1 竟进不了表"
        _x = {}
        _x["_web_cfg"] = dict(_WS)
        assert m._web_tier_confirmed(_cfg(), _it["url"]) is None, "空确认表竟有值"

        # 2 确认成 4（博客档）⇒ 挡在引用表外 + 挂 tier_effective + 留痕
        _ws2 = dict(_WS)
        # ★ 域名必须与桩客户端返回的 URL **同域**：桩返回 a.example.com，
        #   这里确认 example.gov.cn 就永远命中不了（第一版即此，判据以
        #   「没挂 tier_effective」的形态误报）。
        # 两张都要：`_it` 的域是 example.gov.cn（纯函数判据用），
        # 桩返回的是 a.example.com（加性/留痕判据用）—— 只写一张，
        # 另一条判据就会以「确认表没读到」的形态误报。
        _ws2["tier_confirmed"] = {"a.example.com": 4,
                                  "example.gov.cn": 4}
        _c2 = {"web_search": _ws2}
        assert m._web_tier_confirmed(_c2, _it["url"]) == 4, "确认表没读到"
        _it2 = dict(_it)
        _it2["tier_effective"] = 4
        assert not m._web_enters_citation(_it2, _ws2), "确认成 4 竟然还进表"
        _p2 = m.Pool()
        _p2.web_results = [_it2]
        _p2.web_as_evidence = True
        _p2._web_cfg = dict(_ws2)
        assert "W1" not in dict(m._citation_table(None, _p2)), "确认后仍在表里"

        # 3 确认成 1（更硬）⇒ 仍进表（floor=3），且摘要显示生效档
        _ws3 = dict(_WS)
        _ws3["tier_confirmed"] = {"example.gov.cn": 1}
        _it3 = dict(_it)
        _it3["tier_effective"] = 1
        assert m._web_enters_citation(_it3, _ws3), "确认成 1 竟进不了表"
        _dg = m._web_digest_block([_it3])
        assert "tier 1" in _dg, "摘要没有显示生效档（实测 " + _dg[:120] + "）"

        # 4 floor 可调：把 floor 降到 0 ⇒ 任何条目都进不了
        _ws4 = dict(_WS)
        _ws4["tier_floor"] = 0
        assert not m._web_enters_citation(_it, _ws4), "floor=0 竟然还放行"

        # 5 加性：无确认时 `_web_search` 不挂 tier_effective
        class _SC:
            def __init__(self):
                self.calls = 0
                self.cache_hits = 0

            def search(self, q, max_n=8):
                self.calls += 1
                return [{"claim": "c", "url": "https://a.example.com/x",
                         "source": "s", "tier": 3}], ""

        def _mk(ws):
            c = {"web_search": dict(ws)}
            o = object.__new__(m.MetaDGTF)
            o.config = c
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = m.WebSearchGate(c)
            o._web_client = _SC()
            o._web_prep_seq = 0
            return o

        _o = _mk(_WS)
        _o._web_search("research_evidence", ["a"], 1)
        _w = _o.pools["1"].web_results
        assert _w, "默认态没检索到任何条目（判据没被触发 —— 先查 enabled）"
        assert all("tier_effective" not in x for x in _w), (
            "默认态竟挂了 tier_effective（破坏加性）")
        _o2 = _mk(_ws2)
        _o2._web_search("research_evidence", ["a"], 1)
        _w2 = _o2.pools["1"].web_results
        assert any("tier_effective" in x for x in _w2), "确认态没挂 tier_effective"
        assert any("[W-TIER" in str(x) for x in _o2.pools["1"].meta), (
            "确认生效未留痕")

        # 6 ★ 变异体：让 `_web_tier_confirmed` 在确认表未命中时**回落读提案**
        _A = "    _conf = _web_cfg_of(cfg).get(\"tier_confirmed\") or {}"
        _B = ("    _conf = (_web_cfg_of(cfg).get(\"tier_confirmed\")\n"
              "             or {d.get(\"domain\"): d.get(\"proposed_tier\")\n"
              "                 for d in (_web_cfg_of(cfg).get(\"tier_proposals\") or [])})")
        _c = src.count(_A)
        assert _c == 1, "变异体锚点 %d 次" % _c
        _tmpd = _P(_tf.mkdtemp())
        _mp = _tmpd / "mut_tier.py"
        _mp.write_bytes(src.replace(_A, _B).replace(chr(10), chr(13) + chr(10))
                        .encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        _wsx = dict(_WS)
        _wsx["tier_proposals"] = [{"domain": "example.gov.cn",
                                   "proposed_tier": 4}]
        _red = _mm._web_tier_confirmed({"web_search": _wsx},
                                      "https://www.example.gov.cn/a") == 4
        assert _red, "★ 变异体（提案当确认用）下判据没判红"

        print("  ✓ v1.23.2 遗留3 tier 确认：默认零差异 / 确认成 4 出门 / 成 1 显示"
              "生效档 / floor 可调 / 加性 / **变异体判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.2 遗留3 tier 确认失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


def check_v1232_retry(SRC=None):
    """[v1.23.2 遗留1] 空票重试：默认 1 次；置 0 退回 v1.23.1 行为。

    ★ 带变异体：把重试关掉（`range(1)`）⇒ 「可用票 3」判据必须判红。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        class _LLM:
            """第 2 票**第一次**返回空 judgments，第二次正常。"""

            def __init__(self):
                self.n = -1
                self.tries = {}

            def call(self, sysp, user, t, mx, json_mode=False, stage=None, **k):
                self.n += 1
                self.tries[self.n] = self.tries.get(self.n, 0) + 1
                if self.n == 1 and self.tries[1] == 1:
                    return '{"judgments": []}'
                return _json.dumps({"judgments": [
                    {"id": 1, "reason": "r", "decidability": "decidable"}]})

            def parse_json(self, raw):
                return _json.loads(raw)

        def _run(retry):
            o = object.__new__(m.MetaDGTF)
            o.llm = _LLM()
            o.config = {"actions": {"tri_vote_retry_empty": retry}}
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = None
            subs = [{"id": 1, "question": "q", "decidability": "partial"}]
            o._adjudicate_sub_tristate_multi(subs, "Q")
            return subs, o

        _s1, _o1 = _run(1)
        _n1 = len(_s1[0].get("votes") or [])
        assert _n1 == 3, "默认重试 1 次后应有 3 票可用（实测 %d）" % _n1
        _s0, _o0 = _run(0)
        _n0 = len(_s0[0].get("votes") or [])
        assert _n0 == 2, "重试置 0 时应退回 v1.23.1 行为（2 票，实测 %d）" % _n0
        assert any("票可用" in str(x) for x in _o0.pools["1"].meta), (
            "空票留痕丢了")
        assert not any("票可用" in str(x) for x in _o1.pools["1"].meta), (
            "重试成功后不该再报空票")

        # 变异体：把重试关掉（1+max(0,_retry) → 1）
        _A = "            for _try in range(1 + max(0, _retry)):"
        _c = src.count(_A)
        assert _c == 1, "变异体锚点 %d 次" % _c
        _tmpd = _P(_tf.mkdtemp())
        _mp = _tmpd / "mut_retry.py"
        _mp.write_bytes(src.replace(_A, "            for _try in range(1):")
                        .replace(chr(10), chr(13) + chr(10)).encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        o = object.__new__(_mm.MetaDGTF)
        o.llm = _LLM()
        o.config = {"actions": {"tri_vote_retry_empty": 1}}
        o.pools = {"1": _mm.Pool()}
        o.vp = lambda *a, **k: None
        o._web_gate = None
        subs = [{"id": 1, "question": "q", "decidability": "partial"}]
        o._adjudicate_sub_tristate_multi(subs, "Q")
        _red = len(subs[0].get("votes") or []) != 3
        assert _red, "★ 变异体（关掉重试）下判据没判红"

        print("  ✓ v1.23.2 遗留1 空票重试：默认 1 次得 3 票 / 置 0 退回 2 票"
              " / 留痕正确 / **变异体判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.2 遗留1 空票重试失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1233_vote_ids(SRC=None):
    """[v1.23.3 遗留1] 三票 id 归一化 + 产物记**真票号**。

    背景：受控投票实验实测某票返回 **0 起** id ⇒ 引擎按 1 起对齐
    ⇒ 该票**整票错位一格**（第 2 条拿到本该给第 1 条的标签），且无声。
    第二处：产物 `votes[].voter` 原先是**位置**，丢一张票就重编号
    ⇒ `agree13` 比的是别的 prompt 对。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        NL = chr(10)

        # 1 纯函数四向
        assert hasattr(m, "_normalize_judgment_ids"), "缺 _normalize_judgment_ids"
        _f = m._normalize_judgment_ids
        assert _f({1: "a", 2: "b"}, 2) == ({1: "a", 2: "b"}, "1起"), "1 起应原样"
        assert _f({0: "a", 1: "b"}, 2) == ({1: "a", 2: "b"}, "0起+1"), "0 起应 +1"
        assert _f({1: "a", 9: "b"}, 2)[0] is None, "越界应判 None"
        assert _f({}, 2)[0] is None, "空应判 None"
        assert _f({0: "a", 2: "b"}, 2)[0] is None, "混合应判 None"
        print("  ✓ v1.23.3 id 归一化：纯函数四向正确")

        # 2 两条生产路径都接了它（防死代码 / 防只改一处）
        #   ★ 抠函数体带**开括号**：`def 名` 会被前缀同名函数截走（老坑）。
        def _body(nm):
            import ast as _a
            i2 = src.find("def " + nm + "(")
            assert i2 >= 0, "找不到函数 " + nm
            ln2 = src[:i2].count(chr(10)) + 1
            L2 = src.split(chr(10))
            for n2 in _a.walk(_a.parse(src)):
                if isinstance(n2, _a.FunctionDef) and n2.lineno == ln2:
                    return chr(10).join(L2[n2.lineno - 1:n2.end_lineno])
            raise AssertionError("抠不出 " + nm + " 的体")

        for _fn in ("_adjudicate_sub_tristate_multi", "_adjudicate_sub_tristate"):
            assert "_normalize_judgment_ids(" in _body(_fn), (
                _fn + " 体里没有归一化调用")
        print("  ✓ v1.23.3 id 归一化：多票 / 单票两条路径都已接线")

        # 3 ★ 端到端：0 起票必须被 +1 归一（逐票逐条对齐）
        LAB = ("decidable", "partial", "undecidable")

        class _Stub:
            def __init__(self, shift=None, bad=None, n=3):
                self.i = -1
                self.shift = shift
                self.bad = bad
                self.n = n

            def call(self, sysp, user, t, mx, json_mode=False, stage=None,
                     **k):
                self.i += 1
                base = 0 if self.i == self.shift else 1
                if self.i == self.bad:
                    base = 50
                return _json.dumps({"judgments": [
                    {"id": base + j, "reason": "r",
                     "decidability": LAB[(j + self.i) % 3]}
                    for j in range(self.n)]})

            def parse_json(self, raw):
                return _json.loads(raw)

        def _run(stub):
            o = object.__new__(m.MetaDGTF)
            o.llm = stub
            o.config = dict(m.DEFAULT_CONFIG)
            o.config["actions"] = dict(o.config["actions"])
            o.config["actions"]["tri_multi_vote"] = True
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = None
            subs = [{"id": i + 1, "question": "q" + str(i + 1),
                     "decidability": "partial"} for i in range(3)]
            o._adjudicate_sub_tristate_multi(subs, "Q")
            return o, subs

        def _lab(subs):
            return [[(v["voter"], v["label"]) for v in sorted(
                (x.get("votes") or []), key=lambda y: y["voter"])]
                for x in subs]

        want = [[(v, LAB[(j + v) % 3]) for v in (0, 1, 2)] for j in range(3)]
        _o1, _s1 = _run(_Stub(shift=1))
        got = _lab(_s1)
        assert got == want, "0 起票未归一到正确位置：" + repr(got)
        # ★ 同时钉「产物记真票号」：三票都要在（0/1/2），不是重编号后的位置
        assert all(x == 3 for x in (len(g) for g in got)), "票数不为 3"
        assert any(("0 起→+1" in str(x)) for x in _o1.pools["1"].meta), (
            "0 起归一没留痕")
        print("  ✓ v1.23.3 端到端：0 起票被 +1 归一，逐票逐条对齐且留痕")

        # 4 负对照：正常票（1 起）结果与上面**逐条相同**，且不留异常痕
        _o2, _s2 = _run(_Stub(shift=None))
        assert _lab(_s2) == want, "正常票结果与归一后不一致（归一改坏了）"
        assert not any(("id 0 起" in str(x) or "越界" in str(x))
                       for x in _o2.pools["1"].meta), "正常票不该留异常痕"
        print("  ✓ v1.23.3 负对照：正常票行为与留痕都未变（加性）")

        # 5 ★ 越界票：弃票（剩**另外两票**，且 `voter` 是真票号）+ 留痕
        _o3, _s3 = _run(_Stub(bad=1))
        want3 = [[(0, LAB[j % 3]), (2, LAB[(j + 2) % 3])] for j in range(3)]
        assert _lab(_s3) == want3, "越界票没有按『弃票 + 真票号』处理：" + repr(
            _lab(_s3))
        assert any(("越界弃票" in str(x)) for x in _o3.pools["1"].meta), (
            "越界没留痕")
        assert any(("2/3" in str(x)) for x in _o3.pools["1"].meta), (
            "可用票数没扣掉弃票")
        print("  ✓ v1.23.3 越界票：弃票 + 真票号 + 可用票数已扣除")

        # 6 变异体：抠掉「0 起 +1」分支 ⇒ 端到端判据必须判红
        _O = ("    if _ks <= set(range(0, _hi)):" + NL
              + "        return {int(k) + 1: v for k, v in judged.items()}, "
              + chr(34) + "0起+1" + chr(34))
        assert src.count(_O) == 1, "变异体锚点命中 %d 次" % src.count(_O)
        _td = _P(_tf.mkdtemp())
        _mp = _td / "mut_voteids.py"
        _mp.write_bytes(src.replace(_O, "    if False:" + NL
                                    + "        return {int(k) + 1: v "
                                    + "for k, v in judged.items()}, "
                                    + chr(34) + "0起+1" + chr(34))
                        .replace(NL, chr(13) + NL).encode("utf-8"))
        _mm = _v1221_mod(_mp)
        _mo = object.__new__(_mm.MetaDGTF)
        _mo.llm = _Stub(shift=1)
        _mo.config = dict(_mm.DEFAULT_CONFIG)
        _mo.config["actions"] = dict(_mo.config["actions"])
        _mo.config["actions"]["tri_multi_vote"] = True
        _mo.pools = {"1": _mm.Pool()}
        _mo.vp = lambda *a, **k: None
        _mo._web_gate = None
        _ms = [{"id": i + 1, "question": "q", "decidability": "partial"}
               for i in range(3)]
        _mo._adjudicate_sub_tristate_multi(_ms, "Q")
        _mg = [[(v["voter"], v["label"]) for v in sorted(
            (x.get("votes") or []), key=lambda y: y["voter"])] for x in _ms]
        assert _mg != want, "变异体『抠掉 0 起 +1』竟然没判红"
        print("  ✓ v1.23.3 变异体：抠掉 0 起 +1 ⇒ 端到端判据判红")
        return True
    except Exception as e:
        print("  ✗ v1.23.3 三票 id 归一化失败：" + type(e).__name__ + ": "
              + str(e))
        import traceback
        traceback.print_exc()
        return False


def check_v1234_runtime(SRC=None):
    """[v1.23.4] 运行期三项总控（联网 / 思考 / 强度）。

    背景：这三项此前只能靠改 `dgtf_config.yaml` 再重跑；交互里问不到、
    命令行也传不了。本版给它们一个顶层 `runtime` 段 + 交互/CLI 两条入口。

    判据重点（都是「不做会静默出错」的地方）：
      · auto 必须**逐字恒等** —— 否则默认出厂就跑偏了；
      · **思考关必须连 stages 整表一起关** —— `LLM.call` 的优先级是
        「显式 > stage > default」，只改 default 会被 stage 表盖住，
        总开关就是一句空话；
      · 非法值**不静默**（不改任何键 + 有告警），空输入(回车)=auto；
      · 纯函数**不改入参**（否则交互第二轮选 auto 会读到第一轮的值）。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        NL = chr(10)
        D = _json.loads(_json.dumps(m.DEFAULT_CONFIG))
        J = lambda o: _json.dumps(o, sort_keys=True, ensure_ascii=False)

        # ---- 1 接口齐全 ----
        for _n in ("_apply_runtime", "_runtime_snapshot",
                   "_runtime_summary_line", "_normalize_runtime_switch",
                   "_normalize_runtime_effort", "_runtime_thinking_on"):
            assert hasattr(m, _n), "缺 " + _n
        assert m._RUNTIME_SWITCHES == ("auto", "on", "off"), "开关集合"
        assert m._RUNTIME_EFFORTS == ("auto", "low", "high", "max"), (
            "强度集合应为 low/high/max（出厂 yaml 记录的实测集）")
        print("  ✓ v1.23.4 总控：6 个符号与两个取值集都对")

        # ---- 2 ★ auto 恒等：不覆盖任何既有键 ----
        c0, n0 = m._apply_runtime(D)
        assert J(c0) == J(D), "runtime 全 auto 竟然改了配置（不是恒等变换）"
        assert n0 == [], "auto 不该产生任何留痕行：" + repr(n0)
        c0b, _ = m._apply_runtime(D, {"web": "auto", "thinking": "auto",
                                      "effort": "auto"})
        assert J(c0b) == J(D), "显式 auto 也必须是恒等"
        print("  ✓ v1.23.4 总控：三项 auto = 配置逐字恒等（与 v1.23.3 同行为）")

        # ---- 3 联网总开关落键 ----
        cw, nw = m._apply_runtime(D, {"web": "on"})
        assert cw["web_search"]["enabled"] is True, "web=on 没开"
        assert any("联网" in x for x in nw), "web=on 没留痕"
        cw2, _ = m._apply_runtime(D, {"web": "off"})
        assert cw2["web_search"]["enabled"] is False, "web=off 没关"
        print("  ✓ v1.23.4 总控：联网 on/off 正确落到 web_search.enabled")

        # ---- 4 ★★ 思考总开关：default + 整张 stages 表 ----
        co, no = m._apply_runtime(D, {"thinking": "off"})
        _t = co["api"]["thinking"]
        assert _t["default"] == "disabled", "thinking=off 的 default 没改"
        _vals = set(_t["stages"].values())
        assert _vals == {"disabled"}, (
            "thinking=off 没有把 stages 整表关掉：剩余取值 " + repr(_vals))
        assert len(_t["stages"]) == len(D["api"]["thinking"]["stages"]), (
            "stages 的键数变了（应当只改值、不改键集）")
        cn, _ = m._apply_runtime(D, {"thinking": "on"})
        _t2 = cn["api"]["thinking"]
        assert _t2["default"] == "enabled", "thinking=on 的 default 没改"
        assert set(_t2["stages"].values()) == {"enabled"}, (
            "thinking=on 没有把 stages 整表打开")
        print("  ✓ v1.23.4 总控：思考 on/off 同时改写 default 与 stages 整表")

        # ---- 5 ★ 与 LLM 的真实解析联动（比只看配置键强一档）----
        #   ★ 这里**不设** process 级环境变量去凑一个假 key —— 冒烟是同进程
        #     跑几十条判据，改 `os.environ` 会污染后面所有环节（本项目
        #     「判据不能有跨条副作用」的纪律）。有 key 就真构造 LLM 核对，
        #     没有就退回「按 call 的优先级模拟解析」——两条路量的是同一件事。
        _L = None
        try:
            _L = m.LLM(co)
            assert str(_L.thinking_default).lower() == "disabled", (
                "LLM 真实解析：thinking=off 的 default 不对")
            assert not [k for k, v in _L.thinking_stages.items()
                        if str(v).lower() == "enabled"], (
                "LLM 真实解析：thinking=off 仍有环节开档")
        except Exception as _e:  # noqa: BLE001
            print("  · LLM 构造不可用（" + type(_e).__name__
                  + "），改用解析顺序模拟")

        def _resolve(cfg, stage=None):
            th = None
            if stage:
                th = ((cfg.get("api") or {}).get("thinking")
                      or {}).get("stages", {}).get(stage)
            if th is None:
                th = ((cfg.get("api") or {}).get("thinking")
                      or {}).get("default")
            return str(th or "").lower() == "enabled"

        assert _resolve(co, "auto_plan") is False, (
            "thinking=off 后 auto_plan（出厂为 enabled）仍然是 True")
        assert _resolve(co, "从未声明过的环节") is False, (
            "thinking=off 后未声明环节（掉 default）仍是 True")
        assert _resolve(cn, "decompose_koan") is True, (
            "thinking=on 后 decompose_koan（出厂为 disabled）仍是 False")
        print("  ✓ v1.23.4 总控：思考关/开后，**按 call 的优先级解析**结果正确")

        # ---- 6 强度落键 + 只在思考开启时有意义 ----
        ce, ne = m._apply_runtime(D, {"effort": "max"})
        assert ce["api"]["thinking"]["effort"] == "max", "effort 没落键"
        ce2, ne2 = m._apply_runtime(D, {"thinking": "off", "effort": "high"})
        assert any("不生效" in x for x in ne2), (
            "思考关时设了强度，却没有提示「不生效」")
        print("  ✓ v1.23.4 总控：强度落键，且思考关时明确提示「不生效」")

        # ---- 7 ★ 非法值不静默：不改任何键 + 有告警 ----
        for _k, _bad in (("web", "yes_please"), ("thinking", "maybe"),
                         ("effort", "mediun")):
            _cb, _nb = m._apply_runtime(D, {_k: _bad})
            assert J(_cb) == J(D), (
                "%s=%r 非法值竟然改了配置（静默回落）" % (_k, _bad))
            assert any("非法" in x for x in _nb), (
                "%s=%r 非法值没有告警" % (_k, _bad))
            # ★ 不变式：`runtime` 段里**永远是合法的归一值**（非法输入由
            #   `⚠️` 留痕报告，不落进配置）。这条是「记录可被下游直接消费」
            #   的前提 —— 也是我第一版把原始输入写回去时**当场判红**的那条。
            assert all(
                ((_cb.get("runtime") or {}).get(_kk)
                 in (m._RUNTIME_EFFORTS if _kk == "effort"
                     else m._RUNTIME_SWITCHES))
                for _kk in ("web", "thinking", "effort")), (
                "runtime 段被写入集合外的值：" + repr(_cb.get("runtime")))
        print("  ✓ v1.23.4 总控：三个非法值都被拒 + 告警，配置一字未改"
              "（且 runtime 段三值恒合法）")

        # ---- 8 ★ 空输入（回车）= auto：交互提示写的就是「回车=auto」 ----
        for _v in ("", None, "  "):
            assert m._normalize_runtime_switch(_v) == "auto", (
                "开关空输入应为 auto：%r" % (_v,))
            assert m._normalize_runtime_effort(_v) == "auto", (
                "强度空输入应为 auto：%r" % (_v,))
        assert m._normalize_runtime_switch("y") == "on"
        assert m._normalize_runtime_switch("关") == "off"
        assert m._normalize_runtime_effort("MAX") == "max"
        assert m._normalize_runtime_effort("medium") is None, (
            "medium 不在实测取值集里，必须被拒（不能悄悄发出去）")
        print("  ✓ v1.23.4 总控：空输入/别名归一正确，集合外的值被拒")

        # ---- 9 ★ 纯函数：不改入参 ----
        _before = J(D)
        m._apply_runtime(D, {"web": "on", "thinking": "on", "effort": "max"})
        assert J(D) == _before, (
            "`_apply_runtime` 改了入参 —— 交互第二轮选 auto 会读到第一轮的值")
        print("  ✓ v1.23.4 总控：纯函数，入参配置一字未改")

        # ---- 10 生效读数与摘要 ----
        cs, _ = m._apply_runtime(D, {"web": "on", "effort": "high"})
        _snap = m._runtime_snapshot(cs)
        assert _snap["web_enabled"] is True, "snapshot.web_enabled 不对"
        assert _snap["effort"] == "high", "snapshot.effort 不对"
        assert isinstance(_snap["thinking_stages_enabled"], list), (
            "snapshot 必须报出开档环节清单")
        _line = m._runtime_summary_line(cs)
        assert ("联网" in _line) and ("思考" in _line) and ("强度" in _line), (
            "摘要行缺字段：" + _line)
        assert _snap["requested"] == {"web": "on", "thinking": "auto",
                                      "effort": "high"}, (
            "snapshot.requested 必须回显本次请求（而不是 yaml 的值）："
            + repr(_snap["requested"]))
        print("  ✓ v1.23.4 总控：生效读数 + 一行摘要都可读")

        # ---- 10b ★ `requested` 必须回显**本次真正请求的**三项 ----
        #   ★ 这条是「产物可复盘」的关键：`_apply_runtime` 会把请求值写回
        #     副本的 `runtime` 段。不这么做的话产物里的 `requested` 永远是
        #     yaml 的值 —— 命令行/交互给的三项在产物里**看不到**。
        assert _snap["requested"] == {"web": "on", "thinking": "auto",
                                      "effort": "high"}, (
            "snapshot.requested 必须回显本次请求（而不是 yaml 的值）："
            + repr(_snap["requested"]))
        _sn0 = m._runtime_snapshot(c0)
        assert _sn0["requested"] == dict(D.get("runtime") or {}), (
            "全 auto 时 requested 应与出厂 runtime 段逐字相同（恒等）")
        print("  ✓ v1.23.4 总控：`requested` 回显请求值（全 auto 时仍恒等）")

        # ---- 11 ★ load_config 外层套对了（四个出口都过它）----
        _dr = _P(_tf.mkdtemp())
        _y1 = _dr / "rt.yaml"
        _y1.write_bytes(("runtime:" + NL + "  web: off" + NL
                         + "  thinking: off" + NL + "  effort: max"
                         + NL).encode("utf-8"))
        _lc = m.load_config(str(_y1))
        assert _lc["web_search"]["enabled"] is False, "yaml 的 runtime.web 没生效"
        assert _lc["api"]["thinking"]["default"] == "disabled", "yaml 没关思考"
        assert _lc["api"]["thinking"]["effort"] == "max", "yaml 没设强度"
        # 缺路径 / 空路径 / 坏 yaml 三个出口也必须不炸（且仍恒等）
        assert J(m.load_config(str(_dr / "no_such.yaml"))) == J(D), "缺路径出口变了"
        assert J(m.load_config("")) == J(D), "空路径出口变了"
        _y2 = _dr / "bad.yaml"
        _y2.write_bytes(b"a: [1, 2" + bytes([10]))
        assert isinstance(m.load_config(str(_y2)), dict), "坏 yaml 出口炸了"
        print("  ✓ v1.23.4 总控：load_config 四个出口都过总控且不炸")

        # ---- 12 ★ CLI 三个开关真的接上了 ----
        for _flag, _opt in (("--web", "--web {auto,on,off}"),
                            ("--thinking", "--thinking {auto,on,off}"),
                            ("--effort", "--effort {auto,low,high,max}")):
            assert _flag in src, "CLI 缺 " + _flag
        assert "choices=list(_RUNTIME_SWITCHES)" in src, "CLI 开关没收紧取值"
        assert "choices=list(_RUNTIME_EFFORTS)" in src, "CLI 强度没收紧取值"
        assert "cfg, _rt_notes = _apply_runtime(cfg, {" in src, (
            "CLI 没有把三个开关应用下去")
        # 交互侧
        assert "def _ask_runtime(cfg):" in src, "缺 _ask_runtime"
        assert "runtime = _ask_runtime(" in src, "_ask_runtime 没被调用"
        assert ("(route_str, rounds_str, channels_str, parallel_str,"
                + NL + "         runtime) = cfg_result") in src, (
            "_ask_config 的返回值没扩成 5 元组 / 没解包")
        assert "run_cfg, _rt_notes = _apply_runtime(cfg, runtime)" in src, (
            "交互没有在**深拷副本**上应用（会污染跨轮的 cfg）")
        assert "meta = MetaDGTF(run_cfg)" in src, "交互还在用未应用的 cfg"
        print("  ✓ v1.23.4 总控：CLI 三开关 + 交互询问 + 深拷副本都已接线")

        # ---- 13 ★ 产物留痕 ----
        assert '"_runtime": _runtime_snapshot(self.config)' in src, (
            "产物没有 `_runtime` 生效读数（「这跑到底联网没有」又成黑箱）")
        print("  ✓ v1.23.4 总控：产物带 `_runtime` 生效读数")

        # ================= 变异体 =================
        _td = _P(_tf.mkdtemp())

        def _mut(name, old, new):
            assert src.count(old) == 1, (
                "变异体 " + name + " 锚点命中 " + str(src.count(old)) + " 次")
            _p = _td / ("mut_rt_" + name + ".py")
            _p.write_bytes(src.replace(old, new).replace(
                NL, chr(13) + NL).encode("utf-8"))
            return _v1221_mod(_p)

        # M1 ★ 把 auto 当成 on ⇒ auto 恒等判据必须判红
        _M1 = _mut("auto_as_on",
                   '"": "auto", "a": "auto", "auto": "auto",',
                   '"": "auto", "a": "auto", "auto": "on",')
        _c1, _n1 = _M1._apply_runtime(_json.loads(_json.dumps(
            _M1.DEFAULT_CONFIG)))
        assert J(_c1) != J(_M1.DEFAULT_CONFIG), (
            "变异体 M1『auto 当 on』没被判红（auto 恒等判据失效）")
        print("  ✓ v1.23.4 变异体 M1：把 auto 当 on ⇒ auto 恒等判据判红")

        # M2 ★ 思考总开关只改 default、不碰 stages ⇒ 必须判红
        #   ★ 内含双引号的锚点一律用 `chr(34)` 拼：这段代码本身是包在
        #     三引号单引号字符串里的，写反斜杠加引号会被**吃掉一层反斜杠**
        #     ⇒ 生成出来的 smoke 里引号裸奔 ⇒ 整个文件 SyntaxError。
        #     （本轮实踩；v1.23.3 的注入器同样用 chr(34) 绕开。）
        #   ★ 也别在本字符串里写「三个单引号」本身 —— 那会**提前闭合**外层。
        _Q = chr(34)
        _old2 = NL.join([
            "        _stages = _thc.get(" + _Q + "stages" + _Q + ") or {}",
            "        for _k in list(_stages):",
            "            _stages[_k] = _val",
            "        _thc[" + _Q + "stages" + _Q + "] = _stages",
        ])
        _M2 = _mut("default_only", _old2,
                   "        _stages = _thc.get(" + _Q + "stages" + _Q
                   + ") or {}")
        _c2, _ = _M2._apply_runtime(_json.loads(_json.dumps(
            _M2.DEFAULT_CONFIG)), {"thinking": "off"})
        _v2 = set(_c2["api"]["thinking"]["stages"].values())
        assert _v2 != {"disabled"}, (
            "变异体 M2『只改 default』没被判红（总开关成了空话却测不出来）")
        print("  ✓ v1.23.4 变异体 M2：只改 default 不改 stages ⇒ 判红")

        # M3 ★ effort 不做集合校验 ⇒ 非法值静默通过 ⇒ 必须判红
        _M3 = _mut("effort_nocheck",
                   "    return v if v in _RUNTIME_EFFORTS else None",
                   "    return v if v else None")
        assert _M3._normalize_runtime_effort("mediun") is not None, (
            "变异体 M3『effort 不校验』没被判红")
        _c3, _n3 = _M3._apply_runtime(_json.loads(_json.dumps(
            _M3.DEFAULT_CONFIG)), {"effort": "mediun"})
        assert J(_c3) != J(_M3.DEFAULT_CONFIG), (
            "变异体 M3 下非法值竟然改了配置却没被拦住")
        print("  ✓ v1.23.4 变异体 M3：effort 不校验 ⇒ 非法值静默通过，判红")

        # M4 ★ 抠掉「把请求值写回副本」⇒ 产物 requested 只剩 yaml 的值
        _M4 = _mut("no_request_echo", "    cfg[" + _Q + "runtime"
                   + _Q + "] = _rec", "    pass")
        _c4, _ = _M4._apply_runtime(_json.loads(_json.dumps(
            _M4.DEFAULT_CONFIG)), {"web": "on", "thinking": "off",
                                   "effort": "high"})
        _r4 = _M4._runtime_snapshot(_c4)["requested"]
        assert _r4 != {"web": "on", "thinking": "off", "effort": "high"}, (
            "变异体 M4『不写回请求值』没被判红")
        print("  ✓ v1.23.4 变异体 M4：不写回请求值 ⇒ requested 只剩 yaml，判红")

        return True
    except Exception as e:
        print("  ✗ v1.23.4 运行期总控失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


# <<<end v123 checks>>>
'''

# ---- 过期打桩同步：生产侧 update_deferrals 多了 web_hook 形参 ----
# ★ 桩的签名落后于生产代码 → 调用点 TypeError 被吞掉 → 检查静默失败
#   （本项目在 fake_call 的 thinking/stage 参数上踩过同款）。
STALE_HOOK = (
    '            def _patched_ud(pool, view, layer, cfg,\n'
    '                            _o=_orig_ud, _c=_n):\n'
    '                st = _o(pool, view, layer, cfg)\n',
    '            # [v1.23.0 W2] 生产侧 update_deferrals 多了 web_hook 形参。\n'
    '            def _patched_ud(pool, view, layer, cfg, web_hook=None,\n'
    '                            _o=_orig_ud, _c=_n):\n'
    '                st = _o(pool, view, layer, cfg, web_hook=web_hook)\n',
)

# ---- 过期配置登记同步（[v1.23.2] 15 个 thinking stage 的值改为 disabled
#      后，它们在 CONFIG_TUNED 里的登记就成了**过期条目** ⇒ 配置判据会判红。
#      ★ 这正是「登记表两向对账」设计出来的效果：改值就必须销账。）----
STALE_CONFIG = tuple(
    ("    \"api.thinking.stages.%s\": \"thinking 分阶段全开（§档位刻意不覆盖这里）\","
     % _k) + chr(10)
    for _k in ("ask_missing_polarity", "check_input_sanity",
               "check_structure_saturation", "decide_parallel_mode",
               "decompose_from_pool", "decompose_hybrid", "decompose_koan",
               "decompose_normal", "phase_probe", "probe_duel", "probe_meta",
               "probe_research", "re_anchor", "self_check", "settle_research"))

# ---- [v1.23.2] 过期区域判据同步：`check_v1221_p2b` 第 7 步（triage 组装逻辑
#      已抽成 `_triage_suggestions` ⇒ 区域要扩成两处之和 + 钉调用关系）。
#      ★ 这段文本在 **smoke 正文**里，所以必须像 STALE_HOOK 那样
#        对 `src` 做**运行时**替换（上一版对生成器文件本身替换 ⇒ 命中 0）。
# ---- [v1.23.2] 过期区域判据同步：`check_v1221_p2b` 第 7 步（triage 组装逻辑
#      已抽成 `_triage_suggestions` ⇒ 区域要扩成两处之和 + 钉调用关系）。
#      ★ 这段文本在 **smoke 正文**里，必须像 STALE_HOOK 那样对 `src`
#        做**运行时**替换（对生成器文件本身替换 = 命中 0，已踩过）。
_P2B_OLD = '        # 7 crosscheck：两条路都在 + tier 门仍在 + 旧单路径已撤\n        _k0 = src.find("def _anchor_crosscheck")\n        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1\n        _xc = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]\n        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"\n        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"\n        assert \'x.get("answers")\' in _xc, "crosscheck 未读 answers 字段"\n        assert \'if int(x.get("tier", 3) or 3) <= _floor_c\' in _xc, "tier 门丢了"'
_P2B_NEW = '        # 7 [v1.23.2] crosscheck 路径：两条路都在 + tier 门仍在 + 旧单路径已撤\n        #   ★ 组装逻辑已抽成纯函数 `_triage_suggestions` ⇒ 区域 = 两处之和，\n        #     并**钉住调用关系**（否则「搬走了」与「删掉了」看起来一样）。\n        _k0 = src.find("def _anchor_crosscheck")\n        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1\n        _xc0 = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]\n        _t0 = src.find("def _triage_suggestions")\n        _t1 = src.find(NL + "def ", _t0 + 10) if _t0 >= 0 else -1\n        _ts = src[_t0:_t1] if _t0 >= 0 and _t1 > _t0 else ""\n        _xc = _xc0 + NL + _ts\n        assert "_triage_suggestions(" in _xc0, \\\n            "crosscheck 未调 _triage_suggestions（组装逻辑搬走后没接上）"\n        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"\n        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"\n        assert \'x.get("answers")\' in _xc, "crosscheck 未读 answers 字段"\n        assert \'int(x.get("tier", 3) or 3) <= _floor\' in _xc, "tier 门丢了"'
STALE_P2B = ((_P2B_OLD, _P2B_NEW),)

GUARD_RE = re.compile(r"^    if not (check_v123\d*_\w+)\(\):\n        return 1\n", re.M)
GUARD_BLOCK = ("    if not check_v123_w1():\n        return 1\n"
               "    if not check_v123_w2():\n        return 1\n"
               "    if not check_v123_pool_export():\n        return 1\n"
               "    if not check_v123_left():\n        return 1\n"
               "    if not check_v1232_audit():\n        return 1\n"
               "    if not check_v1232_tier():\n        return 1\n"
               "    if not check_v1232_retry():\n        return 1\n"
               "    if not check_v1233_vote_ids():\n        return 1\n"
               "    if not check_v1234_runtime():\n        return 1\n")

raw = SMOKE.read_bytes()
src = raw.decode("utf-8")
if src.count("\r\n") != src.count("\n"):
    print("!! smoke_test.py 不是纯 CRLF，中止"); sys.exit(1)
src = src.replace("\r\n", "\n")

# --- SRC 指向本版 ---
_src_re = re.compile(r'SRC = HERE / "元DGTF-V1\.2\d\.\d+\.py"')
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

# --- 过期区域判据同步（check_v1221_p2b 第 7 步）---
for _o, _n in STALE_P2B:
    if _o in src:
        assert src.count(_o) == 1, "过期区域判据出现 %d 次" % src.count(_o)
        src = src.replace(_o, _n)
        print("  已同步过期区域判据（check_v1221_p2b 第 7 步）")

# --- 过期配置登记同步 ---
for _sc in STALE_CONFIG:
    if _sc in src:
        assert src.count(_sc) == 1, "过期登记行出现 %d 次" % src.count(_sc)
        src = src.replace(_sc, "")
        print("  已销账过期配置登记（thinking stage 改 disabled）")

# --- 过期打桩同步 ---
for _o, _n in (STALE_HOOK,):
    if _o in src:
        assert src.count(_o) == 1, "过期打桩出现 %d 次" % src.count(_o)
        src = src.replace(_o, _n)
        print("  已同步过期打桩（update_deferrals 的 web_hook 形参）")

# --- 守卫：只动自己那一个 ---
n_before = len(re.findall(r"^    if not (check_\w+)\(\):$", src, re.M))
src = GUARD_RE.sub("", src)
hits = list(re.finditer(
    r"^    if not (check_\w+)\(\):\n        return 1\n", src, re.M))
assert hits, "找不到任何守卫行"
_p = hits[-1].end()
src = src[: _p] + GUARD_BLOCK + src[_p:]
n_after = len(re.findall(r"^    if not (check_\w+)\(\):$", src, re.M))
assert n_after == n_before, (
    "守卫数变了：%d -> %d（非幂等！剥的那侧没覆盖插的那侧全集）"
    % (n_before, n_after))

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"
SMOKE.write_bytes(out)
print("OK: v123 冒烟判据已注入（守卫 %d -> %d）；SRC -> %s"
      % (n_before, n_after, NEW_SRC_NAME))
