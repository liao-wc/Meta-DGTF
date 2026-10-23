# -*- coding: utf-8 -*-
"""[v1.23.2] 冒烟注入器扩展：SRC → v1.23.2，并加 3 档判据。

  · `check_v1232_audit` —— 把整体审计探针当**验收命令**跑（单一事实源）；
  · `check_v1232_tier`  —— tier 确认生效（默认零差异 + 确认后进/出门 + 变异体）；
  · `check_v1232_retry` —— 空票重试（默认 1 次；置 0 退回旧行为 + 变异体）。

★ 注入的代码里**不用反斜杠**：换行一律 chr(10)/chr(13) 拼，断行用括号。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_mk_v1230_smoke_checks.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

NEW_CHECK = '''def check_v1232_audit(SRC=None):
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
        _A = "    _conf = _web_cfg_of(cfg).get(\\"tier_confirmed\\") or {}"
        _B = ("    _conf = (_web_cfg_of(cfg).get(\\"tier_confirmed\\")\\n"
              "             or {d.get(\\"domain\\"): d.get(\\"proposed_tier\\")\\n"
              "                 for d in (_web_cfg_of(cfg).get(\\"tier_proposals\\") or [])})")
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

'''

# ★ 就地替换，不是「有就跳过」：本轮改了 NEW_CHECK 的内容（样例补 claim），
#   若写成「有就跳过」，注入器自己的改动**永远不会生效**（判据还是旧的）。
_HEAD = "def check_v1232_audit"
_MARK = "# <<<end v123 checks>>>"
if _HEAD in s:
    # ★ 用 **rindex** —— `_MARK` 在本文件里出现两次（变量定义 + 字面量内），
    #   `index` 会取到变量定义那一处（在 _HEAD **前面**）⇒ 切片反向、文件被撕。
    _i, _j = s.index(_HEAD), s.rindex(_MARK)
    s = s[: _i] + NEW_CHECK + s[_j:]
    print("  · CHECKS 里的 v1232 三档已**就地更新**")
else:
    # ★ 锚点要带**空行**：v1.23.1 注入器加 check_v123_left 时在末尾多留了一个
    #   空行（`return False` 与 MARK 之间）—— 用不带空行的锚点命中 0 次。
    O = "        return False\n\n# <<<end v123 checks>>>"
    assert s.count(O) == 1, s.count(O)
    s = s.replace(O, "        return False\n" + NEW_CHECK
                  + "# <<<end v123 checks>>>")
    print("  · CHECKS 已加 3 档")

O2 = 'NEW_SRC_NAME = "元DGTF-V1.23.1.py"'
if O2 in s:
    s = s.replace(O2, 'NEW_SRC_NAME = "元DGTF-V1.23.2.py"')
    print("  · SRC -> v1.23.2")

O3 = '               "    if not check_v123_left():\\n        return 1\\n")'
if "check_v1232_audit()" not in s:
    assert s.count(O3) == 1, s.count(O3)
    s = s.replace(O3,
                  '               "    if not check_v123_left():\\n'
                  '        return 1\\n"\n'
                  '               "    if not check_v1232_audit():\\n'
                  '        return 1\\n"\n'
                  '               "    if not check_v1232_tier():\\n'
                  '        return 1\\n"\n'
                  '               "    if not check_v1232_retry():\\n'
                  '        return 1\\n")')
    print("  · 守卫块 +3 档")

P.write_bytes(s.encode("utf-8"))
import ast  # noqa: E402
ast.parse(s)
print("[done] 冒烟注入器已扩展")
