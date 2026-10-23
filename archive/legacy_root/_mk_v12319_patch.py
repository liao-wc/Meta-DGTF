# -*- coding: utf-8 -*-
"""v1.23.19 补丁：锚点「真检索」这条路够得到（并把过期前提与文案一并修）。

★ 单一真相源：全部编辑在 `lines` 上做，最后一次 join / 一次 CRLF / 一次写盘。
  ★ 默认路径（`retriever: "snapshot"`）**零行为变化** —— 这是本版的硬约束。
"""
import ast
from pathlib import Path

HERE = Path(".").resolve()
P = HERE / "元DGTF-V1.23.19.py"

raw = P.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
LOG = []


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    LOG.append("%-40s 改 %d 处" % (what, len(hits)))


# ① 文档串：过期的前提（「引擎现在没有联网能力」）+ 说明早退为什么要挪
repl('''        为什么不做成真联网：引擎现在没有联网能力。**假装搜过比承认没搜
        更糟** —— 所以非 snapshot 的取值一律抛错留痕，不静默降级。

        ★ [v1.21.76 B4] 检索层的返回值当前**不消费**：走真后端时
          `_retrieve_anchors(queries)` 只作"接口位 + 失败留痕"，
          真正入池的锚点是下面按 `per_round` 从已加载快照里挑的那批。
          这不是遗漏 —— snapshot 与真检索的入池路径目前是两条，
          等真后端落地时再合并（已在 changelog 的"刻意不做"里点名）。''',
     '''        ★ 锚点有两个来源，按 `retriever` 分流：
          · `snapshot`（默认）：锚点在 run 开头一次性读进来（`_load_anchors`），
            这里只按 `per_round` 配额**分圈投放**；
          · 其它取值（当前实现 `tavily`）：本圈先按池内问题**真检索**
            （`_retrieve_anchors` → `AnchorRetriever`，结果并进 `self._anchors`），
            再走同一套配额投放。失败**一律留痕**，不静默降级。

        ★ **早退条件里不再要求「已有锚点」**：原来 `not self._anchors` 挡在最前，
          而 `_retrieve_anchors` 就在它**后面** —— 于是真检索只有在**先挂了快照
          文件**时才可能被调用；没挂文件时连「后端未实现」的留痕都发生不了
          （承诺了「非 snapshot 抛错留痕」，实际上够不到）。现在这一项移到
          模式分流**之后**：snapshot 模式仍要求已读入锚点；真检索模式自己填。

        ★ 与 `web_search` 的分工（**别混**）：`web_search` 收的进
          `pool.web_results`，是喂给各层的**证据**（`used_as`）；本函数入的是
          `pool.anchors`，是收尾「结论 vs 外部事实」对照的**标尺**。
          两者互不喂 —— 拿本次喂进层里的东西回头量层的结论，是自证不是校验。''',
     "文档串（前提已过期 + 早退说明）")

# ② 早退：把「已有锚点」这一项摘出来
repl('        if not cfg.get("enabled") or entry == "all" or not self._anchors:',
     '        if not cfg.get("enabled") or entry == "all":',
     "早退去掉「已有锚点」")

# ③ 把它放到模式分流之后（配额投放前）
repl('''        already = {str(a.get("id")) for a in (pool.anchors or [])}
        rest = [a for a in self._anchors
                if str(a.get("id")) not in already]''',
     '''        # ★ 到这里 `self._anchors` 的来源已经定：snapshot 读进来的，或上面
        #   真检索刚并进来的。两边都空 = 本圈没事可做。
        if not self._anchors:
            return
        already = {str(a.get("id")) for a in (pool.anchors or [])}
        rest = [a for a in self._anchors
                if str(a.get("id")) not in already]''',
     "「已有锚点」移到分流之后")

# ④ unconfigured 只在 snapshot 模式置位
repl('''        if not path:
            # ★ 通道开着但没挂文件 —— **不是错误**：记 error 会让每一次默认
            #   运行都写「⚠️ 接入失败」，把「没挂文件」读成「接失败了」。
            self._anchor_unconfigured = True
            logger.info("外部锚点：已开启但未配置 path（未挂锚点文件）")
            return self._anchors''',
     '''        if not path:
            # ★ 通道开着但没挂文件 —— **不是错误**：记 error 会让每一次默认
            #   运行都写「⚠️ 接入失败」，把「没挂文件」读成「接失败了」。
            #   ★ 但只有 **snapshot** 模式才叫「未挂文件」：真检索模式
            #     （retriever 非 snapshot）本来就不读文件，它是**已配置**的。
            _mode0 = str(cfg.get("retriever") or "snapshot").strip().lower()
            if _mode0 == "snapshot":
                self._anchor_unconfigured = True
                logger.info("外部锚点：已开启但未配置 path（未挂锚点文件）")
            else:
                logger.info("外部锚点：retriever=%s —— 不读快照文件，按圈真检索",
                            _mode0)
            return self._anchors''',
     "unconfigured 只在 snapshot 置位")

# ⑤ 报告 dict：加有效检索模式
repl('''            "unconfigured": bool(getattr(
                self, "_anchor_unconfigured", False)),
            "as_evidence": _anchor_tier(''',
     '''            "unconfigured": bool(getattr(
                self, "_anchor_unconfigured", False)),
            # ★ 有效检索模式（配置里那个）—— 渲染要用它区分「文件」与「真检索」。
            "retriever_mode": str(
                ((self.config.get("external_anchor") or {})
                 .get("retriever") or "snapshot")).strip().lower(),
            "as_evidence": _anchor_tier(''',
     "报告 dict 加 retriever_mode")

# ⑥ 渲染：未挂文件那句给两条路 + 真检索后端标注
repl('''        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**开（未挂锚点文件）** —— 把 `external_anchor.path` 指向"
                   "锚点快照 JSON 即自动接入；本次结论只取决于池内材料")''',
     '''        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**开（未挂锚点文件）** —— 两条接入路二选一："
                   "① `external_anchor.path` 指向锚点快照 JSON；"
                   "② `external_anchor.retriever: tavily` 按圈真检索"
                   "（读 `TAVILY_API_KEY`）。本次结论只取决于池内材料")''',
     "渲染：未挂文件给两条路")

repl('''        if _ea.get("source_file"):
            _l += ("（" + str(_ea.get("source_file"))
                   + "，检索于 " + str(_ea.get("retrieved_at", "?")) + "）")
        if _ea.get("error"):
            _l += "；⚠️ 接入失败（明细见下方「锚点异常」）"''',
     '''        if _ea.get("source_file"):
            _l += ("（" + str(_ea.get("source_file"))
                   + "，检索于 " + str(_ea.get("retrieved_at", "?")) + "）")
        elif str(_ea.get("retriever_mode") or "snapshot") != "snapshot":
            _l += "（真检索后端 `" + str(_ea.get("retriever_mode")) + "`）"
        if _ea.get("error"):
            _l += "；⚠️ 接入失败（明细见下方「锚点异常」）"''',
     "渲染：真检索后端标注")

# ⑦ 明细「未做」同样给两条路
repl('''                f.write("**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**"
                        "（设 `external_anchor.path` 即接入）\\n\\n")''',
     '''                f.write("**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**"
                        "（两条接入路二选一：`external_anchor.path` 指快照 JSON；"
                        "或 `external_anchor.retriever: tavily` 按圈真检索）\\n\\n")''',
     "明细：未做给两条路")

# ═════════════════════════════════════ 结构自检
out = "\n".join(lines)
ast.parse(out)
# ★ 核心不变量：`_anchor_round` 里「真检索」必须排在「已有锚点」早退**之前**
_i0 = out.index("    def _anchor_round(")
_i1 = out.index("\n    def ", _i0 + 10)
_body = out[_i0:_i1]
_p_ret = _body.index("self._retrieve_anchors(queries)")
_p_grd = _body.index("        if not self._anchors:")
assert _p_ret < _p_grd, "真检索仍排在早退之后（死路没修好）"
assert '\'_mode != "snapshot"\'' not in _body and '_mode != "snapshot"' in _body
assert "_mode0 == \"snapshot\"" in out
assert '"retriever_mode"' in out
assert out.count("tavily") >= 3, out.count("tavily")
assert '"enabled": True,' in out
# 正文注释不许带版次批注
import re as _re
_TAG = _re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
_i = out.index('"""'); _j = out.index('"""', _i + 3)
_de = out[:_j].count("\n")
_hits = [k + 1 for k, l in enumerate(out.split("\n"))
         if k > _de and l.lstrip().startswith("#") and _TAG.search(l)]
assert not _hits, "正文注释有版次批注：%s" % _hits

enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
P.write_bytes(enc)
print("\n".join(LOG))
print("行数：%d → %d" % (len(raw.decode("utf-8").replace("\r\n", "\n").split("\n")) - 1,
                         out.count("\n")))
print("CRLF %d | CRCRLF %d" % (enc.count(b"\r\n"), enc.count(b"\r\r\n")))
print("★ 不变量：真检索在早退之前（偏置 %d < %d）" % (_p_ret, _p_grd))
