# -*- coding: utf-8 -*-
"""[v1.23.38 补丁] smoke_test.py：SRC 切 V1.23.38 + 加 check_v12338_backfeed。

判据三件（本项目铁律：源码级只能证「接线写了」）：
  ① 源码级：注入侧有 backfeed_pool、_web_augment 里有回喂分支与留痕；
  ② 构造性（正）：池里有本 stage 的 record 条目 ⇒ 复用，**_searcher 零调用**；
  ③ 构造性（负对照）：池里没有 / stage 不匹配 / 无注入器 ⇒ 原路检索或返回 None。

★ 探针教训：池必须走 `_llm_ctx_set(backfeed_pool=...)` 的**真实通道**，
  挂在实例上观测不到（v1.23.36 通则 #1 翻版）。
★ 一律 Write 工具写脚本；纯 CRLF 往返。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"

OLD_SRC = 'SRC = HERE / "元DGTF-V1.23.37.py"'
NEW_SRC = 'SRC = HERE / "元DGTF-V1.23.38.py"'

# 新判据（插在 check_v12337_roundtick 之前 —— 保持「最新在前」）
NEW_FN = '''def check_v12338_backfeed():
    """[v1.23.38] 联网**按需回喂**：声明查回来的结果，后续环节**直接复用**。

    ★ 与 v1.23.37「按需协议」的关系：
      v1.23.37 只做到「声明 ⇒ 检索 ⇒ 进池 + 留痕」，结果**没回到后续环节**；
      本版补上回喂 —— 下一环节经 `_web_augment` 时**优先复用池内 `used_as=record`
      的条目**（且 stage 匹配）⇒ **不再重复检索**（省钱 + 让声明真正抵达）。
    ★ 复用安全：这些条目当年进池时**已过 Gate**（授权 + 配额），
      这里只是取出来用，不产生任何新的外部调用。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── ① 源码级 ──
    if "backfeed_pool=self.pools.get" not in src:
        bad.append("[回喂] 注入侧没有 `backfeed_pool`（LLM 拿不到池 ⇒ 不可达）")
    _ai = src.find("def _web_augment")
    if _ai < 0:
        bad.append("[回喂] 找不到 `def _web_augment`")
    else:
        _aj = src.find("\\n    def ", _ai + 10)
        _abody = src[_ai:_aj if _aj > 0 else _ai + 4000]
        if "backfeed_pool" not in _abody:
            bad.append("[回喂] `_web_augment` 体里没有回喂分支（只在外层写了）")
        if "used_as" not in _abody or "record" not in _abody:
            bad.append("[回喂] 回喂分支没按 `used_as=record` 筛选（来源不明）")
    if "[WEB-BACKFEED]" not in src:
        bad.append("[回喂] 缺留痕记号 `[WEB-BACKFEED]`（回喂来源不可分辨）")
    #   ★ 两向对账：注入侧写的键名与消费侧读的键名必须一致
    if '_llm_ctx_get("backfeed_pool")' not in src:
        bad.append("[回喂] 消费侧没读 `backfeed_pool`（键名对不上）")

    # ── ②③ 构造性：真驱动 `_web_augment` ──
    try:
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)

        def _mk_record(stage):
            return {"id": "W9", "stage": stage, "query": "q",
                    "claim": "回喂事实：X 是 Y", "url": "http://e/x",
                    "source": "s", "tier": 2, "used_as": "record",
                    "round": 1, "round_kind": "in", "pre_seq": 0}

        class _Pool:
            def __init__(self, recs):
                self.web_results = list(recs)

        _calls = []

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            _calls.append(str(used_as))
            return [{"claim": "新检索结果", "url": "http://new", "tier": 2}]

        _ST = "research_evidence"
        _u = "原始 user"

        # ② 正：池里有**本 stage** 的 record ⇒ 复用，且 searcher **零调用**
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1",
                         backfeed_pool=_Pool([_mk_record(_ST)]))
        _r = llm._web_augment(_ST, _u)
        if not _r:
            bad.append("[回喂] 池里有按需结果却没注入（回喂没生效）")
        else:
            if "回喂事实" not in str(_r):
                bad.append("[回喂] 注入的内容**不是**池里那条（拿错了）")
            if "新检索结果" in str(_r):
                bad.append("[回喂] 竟然又检索了（复用失败 ⇒ 成本翻倍）")
        if _calls:
            bad.append("[回喂] 复用路径下游**仍调了 searcher** %d 次"
                       "（省钱没真发生）" % len(_calls))

        # ③a 负对照：池里**没有** record ⇒ 必须原路检索
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1", backfeed_pool=_Pool([]))
        _r2 = llm._web_augment(_ST, _u)
        if not _calls:
            bad.append("[回喂] 池里没有记录却也**不检索**了（该走的路被堵）")
        if not _r2 or "新检索结果" not in str(_r2):
            bad.append("[回喂] 负对照下没拿到新检索结果：%r" % (str(_r2)[:60],))

        # ③b 负对照：池里有 record 但 **stage 不匹配** ⇒ 不该复用（防串台）
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1",
                         backfeed_pool=_Pool([_mk_record("另一个环节")]))
        _r3 = llm._web_augment(_ST, _u)
        if "回喂事实" in str(_r3 or ""):
            bad.append("[回喂] 复用了**别的环节**的结果（串台）")
        if not _calls:
            bad.append("[回喂] stage 不匹配时该检索却没检索")

        # ③c 无注入器 ⇒ None（零变化）
        mod._llm_ctx_set(web_searcher=None, question="题", round=2, entry="1",
                         backfeed_pool=_Pool([_mk_record(_ST)]))
        if llm._web_augment(_ST, _u) is not None:
            bad.append("[回喂] 没注入器却仍返回了增强文本（该 None）")

        # ③d 不带 backfeed_pool（老调用方）⇒ 退回原行为（零变化）
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1")
        try:
            delattr(mod._LLM_CTX, "backfeed_pool")
        except Exception:
            pass
        llm._web_augment(_ST, _u)
        if not _calls:
            bad.append("[回喂] 不带池时该原路检索，却没检索（老行为被改）")
    except Exception as _e:
        bad.append("[回喂] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.38 联网按需回喂（池复用 · searcher 零调用 · "
          "stage 不匹配不复用 · 无池退回原行为）全过")
    return True


def check_v12337_roundtick():'''

# 调用锚点
CALL_OLD = """    if not check_v12337_roundtick():
        return 1"""
CALL_NEW = """    if not check_v12338_backfeed():
        return 1
    if not check_v12337_roundtick():
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

    n = s.count("def check_v12337_roundtick():")
    assert n == 1, "check_v12337_roundtick 定义锚点命中 %d 次（要求 1）" % n
    s = s.replace("def check_v12337_roundtick():", NEW_FN)

    n = s.count(CALL_OLD)
    assert n == 1, "调用锚点命中 %d 次（要求 1）" % n
    s = s.replace(CALL_OLD, CALL_NEW)
    return s


_rw(SM, apply)

# ── 自检 ─────────────────────────────────────────────────────────────
raw = SM.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "回读：不是纯 CRLF"
assert b"\r\r\n" not in raw, "回读：含 CRLF 双写"
src = raw.decode("utf-8")
assert src.count("def check_v12338_backfeed():") == 1
assert src.count("if not check_v12338_backfeed():") == 1
assert 'SRC = HERE / "元DGTF-V1.23.38.py"' in src
import ast
ast.parse(src)
print("[ok] smoke_test.py 已更新：SRC=V1.23.38 + check_v12338_backfeed + 调用")
print("[ok] 行数（LF 计）=", src.count("\n"))
print("[ok] AST OK / 纯 CRLF / 无 CRCRLF")
