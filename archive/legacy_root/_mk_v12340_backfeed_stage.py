# -*- coding: utf-8 -*-
"""[v1.23.40 补丁] 修「回喂在真实调用图上匹配不上」。

【真跑逮到的缺口（v1.23.39 真跑 R1 实证）】
  回喂按 `record["stage"] == 当前环节名` 匹配，而**按需声明全部发生在
  `LLM.call(stage=None)`**（展开主路径不传 stage；日志 4 次全是
  `[WEB-NEED] stage=None`）⇒ 进池 record 的 `stage` 为空串
  ⇒ **回喂永远匹配不上** ⇒ `[WEB-BACKFEED]` 0 次。
  ⇒ v1.23.38 的「回喂」在真实调用图上**从未生效过**（探针能触发是因为
    探针**显式传了 stage**，掩盖了真实调用点 stage 为空的事实）。

【修法（两处）】
  ① `_infer_stage_from_stack` 的跳过元组加 `_web_need_report`
     —— 否则从 `_web_need_report` 里调它会**把自己当成环节名**
     （frame(1) 就是它自己 ⇒ 返回 "web_need_report"）。
  ② `_web_need_report`：`stage` 为空时用 `_infer_stage_from_stack()` 兜底
     取**真实环节名**再入库 ⇒ 回喂按 stage 匹配得上。
     ★ 兜底只在**真有声明**时算（`parse_web_need` 返回非空之后），
       不声明 ⇒ 零开销（99% 的调用）。

协议：纯 CRLF 往返；锚点命中 == 1；写完 AST + 自检。
"""
from pathlib import Path

TGT = Path(__file__).resolve().parent / "元DGTF-V1.23.40.py"

# ── ① 跳过元组加 _web_need_report ───────────────────────────────────
OLD_SKIP = '''            # 跳过 LLM 自身与 `_call_long` 这类包装
            if _n not in ("call", "_call_long", "_web_augment", "<module>") \\
                    and not _n.startswith("_llm_"):'''

NEW_SKIP = '''            # 跳过 LLM 自身与 `_call_long` 这类包装
            # ★ `_web_need_report` 也要跳：它在 stage 为空时会调本函数取
            #   真实环节名，若不跳，frame(1) 就是它自己 ⇒ 会把环节名
            #   误判成 "web_need_report"（真跑实证的坑）。
            if _n not in ("call", "_call_long", "_web_augment",
                          "_web_need_report", "<module>") \\
                    and not _n.startswith("_llm_"):'''

# ── ② _web_need_report：stage 兜底 + docstring 更正 ─────────────────
OLD_REPORT = '''        ★ 返回「真的收进来几条」（0 = 没声明 / 没授权 / 配额尽 / 外部真没有）。
        ★ 本批**不回喂**：回喂要在同一环节再调一次（成本翻倍），留作下一步。
        """
        _qs = parse_web_need(text)
        if not _qs:
            return 0
        _searcher = _llm_ctx_get("web_searcher")
        if not callable(_searcher):
            return 0
        _rn = int(_llm_ctx_get("round", 0) or 0)
        try:
            _res = _searcher(str(stage or ""), _qs, _rn, "record")
        except Exception:
            return 0
        _n = len(_res or [])
        if _n:
            # ★ 留痕：**同一件事既进 logger 又进池**（W# 由 `_web_search` 编）。
            try:
                logger.info("[WEB-NEED] stage=%s 声明 %d 条 ⇒ 采纳 %d 条"
                            % (stage, len(_qs), _n))
            except Exception:
                pass
        return _n'''

NEW_REPORT = '''        ★ 返回「真的收进来几条」（0 = 没声明 / 没授权 / 配额尽 / 外部真没有）。
        ★ **stage 兜底**：调用点（`LLM.call`）常常**不传** stage（展开主路径
          就是如此，真跑实证 4 次声明全是 `stage=None`）⇒ 若原样入库，
          record 的 `stage` 为空 ⇒ **回喂按 stage 匹配永远匹配不上**
          （v1.23.38 的回喂因此在真实调用图上从未生效过）。
          ⇒ 这里用 `_infer_stage_from_stack()` 取**真实环节名**兜底。
          ★ 兜底**只在真有声明时算**（不声明零开销）；取不到就仍用空串
            （宁可匹配不上，不许猜错环节名）。
        """
        _qs = parse_web_need(text)
        if not _qs:
            return 0
        _searcher = _llm_ctx_get("web_searcher")
        if not callable(_searcher):
            return 0
        _rn = int(_llm_ctx_get("round", 0) or 0)
        _st = str(stage or "").strip()
        if not _st:
            try:
                _st = str(_infer_stage_from_stack() or "").strip()
            except Exception:
                _st = ""
        try:
            _res = _searcher(_st, _qs, _rn, "record")
        except Exception:
            return 0
        _n = len(_res or [])
        if _n:
            # ★ 留痕：**同一件事既进 logger 又进池**（W# 由 `_web_search` 编）。
            try:
                logger.info("[WEB-NEED] stage=%s 声明 %d 条 ⇒ 采纳 %d 条"
                            % (_st or "(未命名环节)", len(_qs), _n))
            except Exception:
                pass
        return _n'''


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
    n = s.count(OLD_SKIP)
    assert n == 1, "skip 元组锚点命中 %d 次（要求 1）" % n
    s = s.replace(OLD_SKIP, NEW_SKIP)

    n = s.count(OLD_REPORT)
    assert n == 1, "_web_need_report 锚点命中 %d 次（要求 1）" % n
    s = s.replace(OLD_REPORT, NEW_REPORT)

    for tok, want in (('_st = str(_infer_stage_from_stack() or "").strip()', 1),
                      ('"_web_need_report", "<module>"', 1),
                      ('_res = _searcher(_st, _qs, _rn, "record")', 1)):
        got = s.count(tok)
        assert got == want, "自检 %r 出现 %d 次（要求 %d）" % (tok, got, want)
    return s


_rw(TGT, apply)

raw = TGT.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
src = raw.decode("utf-8")
import ast
ast.parse(src)
print("[ok] 补丁已写入 %s" % TGT.name)
print("[ok] 行数（LF 计）=", src.count("\n"), "| 纯 CRLF | AST OK")