# -*- coding: utf-8 -*-
"""[v1.23.40 判据] 回喂 stage 兜底：声明入库要带**真实环节名**。

【为什么要有这条】v1.23.39 真跑（R1）实证：按需声明全部发生在
`LLM.call(stage=None)` ⇒ record 的 stage 为空 ⇒ 回喂按 stage 匹配
**永远匹配不上** ⇒ `[WEB-BACKFEED]` 0 次（v1.23.38 的回喂在真实调用图上
从未生效过）。★ 探针能触发是因为探针**显式传了 stage**，掩盖了这个事实。

四层验证：
  ① 构造性·真跑法：在一个**真名叫 `_expand_from_question` 的函数**里
     经 `LLM.call` 路径调 `_web_need_report(None, 有声明的文本)`
     ⇒ searcher 收到的 stage 必须是 `expand_from_question`（**不是空、
     也不是 `web_need_report`**）。
  ② 构造性·显式 stage 不受影响：传 `stage="ing"` ⇒ searcher 收到 `ing`。
  ③ 静态：`_infer_stage_from_stack` 的跳过元组含 `_web_need_report`
     （不跳就会把自己当环节名）。
  ④ 端到端：入池 item 的 `stage` 字段真带环节名 ⇒ 回喂匹配得上。
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.39.py"


def main():
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("tgt40", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tgt40"] = mod
    spec.loader.exec_module(mod)

    # ── ③ 静态：跳过元组 ──
    if '"_web_need_report", "<module>"' not in src:
        bad.append("[回喂stage] 跳过元组缺 `_web_need_report`（会把自己当环节名）")

    # ── 造一个「真名叫 _expand_from_question」的调用者 ──
    class _LLM:
        def call(self, system, user, **kw):
            # 复刻真实路径：`LLM.call` 出口处把 stage 原样传下去
            return self._web_need_report(kw.get("stage"), _BODY)

        def _web_need_report(self, stage, text):
            # ★ 直接调引擎里的真实实现（不重写逻辑）
            return mod.LLM._web_need_report(self, stage, text)

    # 真跑法：把 _infer_stage_from_stack 的调用栈构造成
    #   _web_need_report → call → _expand_from_question → _run_layer
    seen = {}

    def _fake_searcher(stage, queries, rn, used_as="evidence", pre_seq=0):
        seen["stage"] = str(stage)
        seen["queries"] = list(queries)
        seen["used_as"] = str(used_as)
        return [{"claim": "命中", "url": "http://x", "tier": 3}]

    mod._llm_ctx_set(web_searcher=_fake_searcher, question="题", round=1,
                     entry="1")

    Q = chr(34)
    M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
    _BODY = ("产出正文\n" + M + "\n{%squeries%s: [%sX%s]}"
             % (Q, Q, Q, Q))

    def _expand_from_question(self, inp):
        """★ 函数名必须**真的是** `_expand_from_question`**（栈推断靠它）。"""
        return self.call("sys", "user", stage=None)

    llm = _LLM()
    try:
        # ① 真跑法：stage=None 来自一个真名函数
        try:
            n = _expand_from_question(llm, None)
        except Exception as e:
            n = -1
            bad.append("[回喂stage] 真跑法驱动抛错：%r" % (e,))
        got = seen.get("stage")
        if n <= 0:
            bad.append("[回喂stage] 声明未被采纳（返回 %r）" % (n,))
        if got in (None, "", "web_need_report"):
            bad.append("[回喂stage] stage 兜底失败：searcher 收到 %r"
                       "（空 ⇒ 回喂匹配不上；'web_need_report' ⇒ 跳过元组漏了）"
                       % (got,))
        elif got != "expand_from_question":
            bad.append("[回喂stage] stage 兜底取错环节名：%r（应 expand_from_question）"
                       % (got,))

        # ② 显式 stage 不受影响
        seen.clear()
        try:
            llm.call("sys", "user", stage="ing")
        except Exception as e:
            bad.append("[回喂stage] 显式 stage 路径抛错：%r" % (e,))
        if seen.get("stage") != "ing":
            bad.append("[回喂stage] 显式 stage 被兜底覆盖了：%r（应 'ing'）"
                       % (seen.get("stage"),))
    except Exception as e:
        bad.append("[回喂stage] 驱动抛错：%r" % (e,))

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

        o = _Owner()
        o._web_gate, o._web_client = _Gate(), _Client()
        r = mod.MetaDGTF._web_search(o, "expand_from_question",
                                     ["测试查询"], 1, "record", 0)
        if not r:
            bad.append("[回喂stage] `_web_search` 返回空")
        elif str(r[0].get("stage")) != "expand_from_question":
            bad.append("[回喂stage] 入池 item 的 stage 字段不对：%r"
                       % (r[0].get("stage"),))
    except Exception as e:
        bad.append("[回喂stage] 端到端驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.40 回喂 stage 兜底（stage=None ⇒ 取真实环节名 · "
          "显式 stage 不受影响 · 跳过元组含本函数 · 入池 item 带环节名）全过")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)