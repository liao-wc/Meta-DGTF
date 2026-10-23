# -*- coding: utf-8 -*-
"""[v1.23.38 补丁] 在 LLM._web_augment 里加「池复用式回喂」。

做三件事：
  ① 注入侧（MetaDGTF.run）：多注入一个 `backfeed_pool`（= self.pools.get("1")）
     —— 让 LLM 侧能读到池里已收的按需结果。★ 只加一个线程上下文键，
     不改任何既有键 ⇒ 不带池时行为逐字不变。
  ② LLM._web_augment：检索**之前**先看池里有没有 used_as=record 的条目
     （且 stage 匹配）⇒ 有就直接复用（**不重复检索**）⇒ 留痕。
  ③ 复用走的是「池里已有的条目」，不再过 Gate（当初进池时已过）
     ⇒ 回喂路径下 **_searcher 调用次数必须为 0**（成本判据）。

协议：纯 CRLF；read_bytes→断言→转 LF→改→转回→write_bytes；锚点断言 ==1。
    ★ 一律用 Write 工具写本脚本（shell heredoc 会污染转义）。
    ★ 插入前重扫锚点，不复用开头算好的索引。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.38.py"

# ═══════════════════════════════════════════════════════════════════════
# ① 注入侧：给 run() 的 _llm_ctx_set 加 backfeed_pool
# ═══════════════════════════════════════════════════════════════════════
ANCHOR_OLD = '''            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""),
                         control=self._control)'''
ANCHOR_NEW = '''            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""),
                         control=self._control,
                         # ★ [回喂] 把**本层的池**也递进去：`LLM._web_augment`
                         #   据此复用「按需声明时已查回来」的结果（不再重复检索）。
                         #   不带这个键 ⇒ 上下文中取不到 ⇒ 退回原行为（零变化）。
                         backfeed_pool=self.pools.get("1"))'''

# ═══════════════════════════════════════════════════════════════════════
# ② LLM._web_augment：检索前先复用池里的 record 条目
# ═══════════════════════════════════════════════════════════════════════
# 精确锚（从 Read 出来的原文，逐字）：
AUG_OLD = '''        _rn = int(_llm_ctx_get("round", 0) or 0)
        _qs = ["%s %s" % (_q[:100], _st.replace("_", " ")[:60])]
        try:
            _res = _searcher(_st, _qs, _rn, "evidence")
        except Exception:
            return None
        if not _res:
            return None                       # 空结果 = 「外部确实没有」⇒ 不注入
        _lines = []
        for _it in _res[:3]:'''

AUG_NEW = '''        _rn = int(_llm_ctx_get("round", 0) or 0)
        # ★ [回喂] **先看池里有没有「本环节声明过、已经查回来」的按需结果**
        #   —— 有就**直接复用**，不再重复检索（省钱、且让声明真的抵达后续环节）。
        #   ★ 复用是安全的：这些条目当年进池时**已过 Gate**（授权 + 配额），
        #     这里只是把它们**取出来用**，不产生任何新的外部调用。
        #   ★ 不是本环节的就不要（避免串台）；不带池 / 池里没有 ⇒ 原路检索。
        _res = None
        _from_pool = False
        _bf = _llm_ctx_get("backfeed_pool")
        if _bf is not None:
            try:
                _pool_rec = [
                    _it for _it in (getattr(_bf, "web_results", None) or [])
                    if str((_it or {}).get("used_as") or "") == "record"
                    and str((_it or {}).get("stage") or "") == _st
                    and str((_it or {}).get("claim") or "").strip()
                ]
                if _pool_rec:
                    _res = _pool_rec
                    _from_pool = True
            except Exception:
                _res = None
        if _res is None:
            _qs = ["%s %s" % (_q[:100], _st.replace("_", " ")[:60])]
            try:
                _res = _searcher(_st, _qs, _rn, "evidence")
            except Exception:
                return None
        if not _res:
            return None                       # 空结果 = 「外部确实没有」⇒ 不注入
        if _from_pool:
            # ★ 留痕：回喂是**另一条来源**（不是本次新检索的）⇒ 读者要能分辨。
            try:
                logger.info("[WEB-BACKFEED] stage=%s 复用池内按需结果 %d 条 ⇒ 注入"
                            % (_st, len(_res)))
            except Exception:
                pass
        _lines = []
        for _it in _res[:3]:'''


def _rw(p, fn):
    """纯 CRLF 往返：read_bytes → 断言 → 转 LF → fn → 转回 → write_bytes + 自检。"""
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)
    return out


def apply(s):
    # ── ① 注入侧 ──────────────────────────────────────────────────
    n1 = s.count(ANCHOR_OLD)
    assert n1 == 1, "注入侧锚点命中 %d 次（要求 1）" % n1
    s = s.replace(ANCHOR_OLD, ANCHOR_NEW)

    # ── ② _web_augment ────────────────────────────────────────────
    n2 = s.count(AUG_OLD)
    assert n2 == 1, "_web_augment 锚点命中 %d 次（要求 1）" % n2
    s = s.replace(AUG_OLD, AUG_NEW)

    # ── 自检：新增记号各出现恰一次 ────────────────────────────────
    for tok, want in (("backfeed_pool=self.pools.get", 1),
                      ("_from_pool = True", 1),
                      ("[WEB-BACKFEED]", 1)):
        got = s.count(tok)
        assert got == want, "自检 %r 出现 %d 次（要求 %d）" % (tok, got, want)
    return s


_rw(TGT, apply)

# ── 回读 + AST 自检 ──────────────────────────────────────────────────
raw = TGT.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "回读：不是纯 CRLF"
assert b"\r\r\n" not in raw, "回读：含 CRLF 双写"
src = raw.decode("utf-8")
import ast
tree = ast.parse(src)

# 结构性自检：_web_augment 确实引用了 backfeed_pool，且 return 之后无死代码
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_web_augment":
        body_src = ast.get_source_segment(src, node) or ""
        assert "backfeed_pool" in body_src, "_web_augment 未引用 backfeed_pool"
        assert "[WEB-BACKFEED]" in body_src, "_web_augment 缺回喂留痕"
        # 「return 之后还有语句」的 AST 检查（v1.23.17 §1）
        for sub in ast.walk(node):
            b = getattr(sub, "body", None)
            if isinstance(b, list):
                for i, st in enumerate(b[:-1]):
                    if isinstance(st, ast.Return):
                        raise AssertionError("return 之后还有语句 ⇒ 死代码")

print("[ok] 补丁已写入 %s" % TGT.name)
print("[ok] 行数（LF 计）=", src.count("\n"))
print("[ok] AST OK / 纯 CRLF / 无 CRCRLF / 无死代码")
