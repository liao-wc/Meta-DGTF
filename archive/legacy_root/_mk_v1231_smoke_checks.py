# -*- coding: utf-8 -*-
"""[v1.23.1] 把 check_v123_left 加进冒烟注入器，并把 SRC 指向 v1.23.1。

★ 插入的代码里**一个反斜杠都没有**：
  · 换行一律用 chr(10)/chr(13) 拼（工具链会把 `\\n` 吃成 `/n`，已踩 5 次）；
  · 断行一律用括号，不用行尾续行符（注入器自身是 ''' 字面量，`\\\\` 的
    层数极易算错 —— 干脆不用）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_mk_v1230_smoke_checks.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

NEW_CHECK = '''def check_v123_left(SRC=None):
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

'''

O = "        return False\n# <<<end v123 checks>>>"
if "def check_v123_left" in s:
    print("  已存在，跳过插入")
else:
    assert s.count(O) == 1, "CHECKS 尾锚点 %d 次" % s.count(O)
    s = s.replace(O, "        return False\n" + NEW_CHECK
                  + "# <<<end v123 checks>>>")
    print("  · CHECKS 已加 check_v123_left")

O2 = 'NEW_SRC_NAME = "元DGTF-V1.23.0.py"'
if O2 in s:
    assert s.count(O2) == 1
    s = s.replace(O2, 'NEW_SRC_NAME = "元DGTF-V1.23.1.py"')
    print("  · SRC -> v1.23.1")

O3 = '               "    if not check_v123_pool_export():\\n        return 1\\n")'
if "if not check_v123_left()" in s:
    print("  · 守卫已含 left，跳过")
else:
    assert s.count(O3) == 1, "守卫块锚点 %d 次" % s.count(O3)
    s = s.replace(O3,
                  '               "    if not check_v123_pool_export():\\n'
                  '        return 1\\n"\n'
                  '               "    if not check_v123_left():\\n'
                  '        return 1\\n")')
    print("  · 守卫块 +check_v123_left")

P.write_bytes(s.encode("utf-8"))
import ast  # noqa: E402
ast.parse(s)
print("[done] 注入器已更新")
