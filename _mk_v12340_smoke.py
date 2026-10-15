# -*- coding: utf-8 -*-
"""[v1.23.40 补丁] smoke_test.py：SRC 切 V1.23.40 + 加 check_v12340_backfeed_stage。

★ 真跑链已结束（本轮无真跑在跑）⇒ 切 SRC 安全。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"

OLD_SRC = 'SRC = HERE / "元DGTF-V1.23.39.py"'
NEW_SRC = 'SRC = HERE / "元DGTF-V1.23.40.py"'

NEW_FN = '''def check_v12340_backfeed_stage():
    """[v1.23.40] 回喂 stage 兜底：声明入库要带**真实环节名**。

    ★ 为什么要有这条（v1.23.39 真跑 R1 实证）：按需声明**全部**发生在
      `LLM.call(stage=None)`（展开主路径不传 stage）⇒ record 的 stage 为空
      ⇒ 回喂按 stage 匹配**永远匹配不上** ⇒ `[WEB-BACKFEED]` 0 次
      ⇒ v1.23.38 的「回喂」在真实调用图上**从未生效过**。
      ★ 探针能触发是因为探针**显式传了 stage**，掩盖了真实调用点 stage 为空。

    四层验证：① 真跑法（在一个真名 `_expand_from_question` 的函数里走
    `stage=None` ⇒ 兜底必须取到 `expand_from_question`）② 显式 stage
    不受影响 ③ 静态：跳过元组含 `_web_need_report`（不跳会把自己当环节名）
    ④ 端到端：入池 item 的 `stage` 字段真带环节名。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── ③ 静态：跳过元组 ──
    if \'"_web_need_report", "<module>"\' not in src:
        bad.append("[回喂stage] 跳过元组缺 `_web_need_report`"
                   "（会把自己当环节名）")

    # ── 造一个「真名叫 _expand_from_question」的调用者 ──
    _seen = {}

    def _fake_searcher(stage, queries, rn, used_as="evidence", pre_seq=0):
        _seen["stage"] = str(stage)
        return [{"claim": "命中", "url": "http://x", "tier": 3}]

    mod._llm_ctx_set(web_searcher=_fake_searcher, question="题", round=1,
                     entry="1")

    _Q = chr(34)
    _M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
    _BODY = ("产出正文\\n" + _M + "\\n{%squeries%s: [%sX%s]}"
             % (_Q, _Q, _Q, _Q))

    class _LLM:
        def call(self, system, user, **kw):
            return mod.LLM._web_need_report(self, kw.get("stage"), _BODY)

    def _expand_from_question(self, inp):
        """★ 函数名必须**真的是** `_expand_from_question`**（栈推断靠它）。"""
        return self.call("sys", "user", stage=None)

    _llm = _LLM()
    try:
        _n = _expand_from_question(_llm, None)
        _got = _seen.get("stage")
        if _n <= 0:
            bad.append("[回喂stage] 声明未被采纳（返回 %r）" % (_n,))
        if _got in (None, "", "web_need_report"):
            bad.append("[回喂stage] stage 兜底失败：searcher 收到 %r"
                       "（空 ⇒ 回喂匹配不上）" % (_got,))
        elif _got != "expand_from_question":
            bad.append("[回喂stage] stage 兜底取错环节名：%r"
                       "（应 expand_from_question）" % (_got,))
        # ② 显式 stage 不受影响
        _seen.clear()
        _llm.call("sys", "user", stage="ing")
        if _seen.get("stage") != "ing":
            bad.append("[回喂stage] 显式 stage 被兜底覆盖：%r（应 ing）"
                       % (_seen.get("stage"),))
    except Exception as _e:
        bad.append("[回喂stage] 驱动抛错：%r" % (_e,))

    # ── ④ 端到端：入池 item 的 stage 字段 ──
    try:
        class _Gate:
            def __init__(self):
                self._relaxed = set()

            def allow(self, stage, round_no, on_demand=False):
                return True, ""

            def note_call(self, stage, round_no):
                pass

            def note_failure(self, kind=""):
                return False

            def note_success(self):
                pass

        class _Client:
            def search(self, q):
                return ([{"claim": "命中", "url": "http://x", "tier": 3}], "")

        class _Pool:
            web_results = []
            web_errors = []
            meta = []
            _web_cfg = None
            web_as_evidence = False

        class _Owner:
            config = {"web_search": {"enabled": True, "stages": {}}}
            pools = {"1": _Pool()}
            _control = None
            _TICK_WEB_RELAX = ()

        _o = _Owner()
        _o._web_gate, _o._web_client = _Gate(), _Client()
        _r = mod.MetaDGTF._web_search(_o, "expand_from_question",
                                      ["测试查询"], 1, "record", 0)
        if not _r:
            bad.append("[回喂stage] `_web_search` 返回空")
        elif str(_r[0].get("stage")) != "expand_from_question":
            bad.append("[回喂stage] 入池 item 的 stage 不对：%r"
                       % (_r[0].get("stage"),))
    except Exception as _e:
        bad.append("[回喂stage] 端到端抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.40 回喂 stage 兜底（None ⇒ 真实环节名 · 显式不受影响 · "
          "入池带环节名）全过")
    return True


def check_v12339_ondemand():'''

CALL_OLD = """    if not check_v12339_ondemand():
        return 1"""
CALL_NEW = """    if not check_v12340_backfeed_stage():
        return 1
    if not check_v12339_ondemand():
        return 1"""


def _rw(p, fn):
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)


def apply(s):
    n = s.count(OLD_SRC)
    assert n == 1, "SRC 锚点命中 %d 次（要求 1）" % n
    s = s.replace(OLD_SRC, NEW_SRC)
    n = s.count("def check_v12339_ondemand():")
    assert n == 1, "插入锚点命中 %d 次（要求 1）" % n
    s = s.replace("def check_v12339_ondemand():", NEW_FN)
    n = s.count(CALL_OLD)
    assert n == 1, "调用锚点命中 %d 次（要求 1）" % n
    s = s.replace(CALL_OLD, CALL_NEW)
    return s


if __name__ == "__main__":
    _rw(SM, apply)
    raw = SM.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8")
    assert s.count("def check_v12340_backfeed_stage():") == 1
    assert s.count("if not check_v12340_backfeed_stage():") == 1
    assert 'SRC = HERE / "元DGTF-V1.23.40.py"' in s
    import ast
    ast.parse(s)
    print("[ok] smoke_test.py：SRC=V1.23.40 + check_v12340_backfeed_stage + 调用")
    print("[ok] 行数（LF 计）=", s.count("\n"), "| 纯 CRLF | AST OK")