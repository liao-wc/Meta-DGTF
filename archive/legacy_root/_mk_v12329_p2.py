#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 2 阶段：产物去重（`## 这一次我是谁`）+ 模式收束。

A1 去重：`self_text` 的每条 = `[<层>] <view.manifest[:900]>`，而完整 manifest
        已在 `## 附：逐层明细` 里渲染过 ⇒ 该节是**截断重复**。
        改成「一句索引」：逐层列出「哪一层、多少字自我记忆」，
        并指向上面的逐层明细。**不再复述全文**。
        可选组：没有 self_text 时整节不渲染（旧行为一致）。

B1 模式收束：`_decide_parallel_mode` 增加**规则优先**前置。
   规则拿不准才调 LLM（省一次调用）；6 个近 80 跑零命中的模式
   （A/D/E/F/G/H）仍可**显式** `--parallel X` 到达，但不进自动分派。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"


def _load(p=SRC):
    b = p.read_bytes()
    crlf, lf, crcrlf = b.count(b"\r\n"), b.count(b"\n"), b.count(b"\r\r\n")
    assert crlf == lf, "非纯 CRLF"
    assert crcrlf == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def repl_text(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


def main():
    s = _load()

    # ── A1 产物去重 ──────────────────────────────────────────
    old = '''        stxt = MemoryChannel.self_text_of(result.get("self_text"))
        if stxt:
            f.write(f"## 这一次我是谁\\n\\n{stxt}\\n\\n---\\n\\n")
'''
    new = '''        # ── 这一次我是谁（**索引**，不复述正文）────────────────
        #   `self_text` 的每条就是 `[<层>] <view.manifest[:900]>`，
        #   而完整 manifest 已在上面 `## 附：逐层明细` 里逐字渲染过。
        #   在这里再印一遍 = **纯重复**（实测占产物 15~35% 行）。
        #   ⇒ 只留一句索引：哪几层、各自多少字自我记忆，正文指向上文。
        _st_blocks = [str(b).strip()
                      for b in (result.get("self_text") or [])
                      if str(b).strip()]
        if _st_blocks:
            f.write("## 这一次我是谁（索引）\\n\\n")
            f.write("<sub>本跑各层已进入自我记忆的正文，见上文"
                    "「附：逐层明细」对应层——此处不重复。</sub>\\n\\n")
            for _b in _st_blocks:
                _tag = _b.split("\\n", 1)[0].strip()
                f.write(f"- {_tag}（自我记忆 {len(_b)} 字）\\n")
            f.write("\\n---\\n\\n")
'''
    s = repl_text(s, old, new, "A1 这一次我是谁去重")

    # ── B1 模式收束：规则优先 ────────────────────────────────
    old2 = '''    def _decide_parallel_mode(self, question: str) -> dict:
        q = question or ""
        feats = {'''
    new2 = '''    #: 自动分派**可达**的模式：只放「规则判得出、且历史上真被选中过」的。
    #: ★ 6 个 stage 模式（A/D/E/F/G/H）**不进自动分派** —— 近 80 份产物
    #:   零命中（实测：serial 71 / B 6 / C 1 / 其余 0），而它们每个都要
    #:   多一次 LLM 调用才可能选中。它们仍可**显式** `--parallel X` 到达。
    _AUTO_REACHABLE_MODES = ("serial", "B", "C")

    #: 规则优先判据的**并列连接词/选择词**（决定 A/B 分岔）。
    _MODE_RULE_OR = ("或", "还是", "或者", "抑或")
    _MODE_RULE_AND = ("和", "与", "以及", "同时", "并")
    _MODE_RULE_PIPE = ("流水", "接力", "时序", "尽快", "尽量快")

    def _mode_rule(self, question: str):
        """规则优先的模式判断。返回 (mode, reason) 或 (None, why_not)。

        ★ 为什么要有规则层：出厂把模式**全权**交给一次 LLM 调用，而
          实测该调用几乎总返回 `serial`（含 `_PARALLEL_CONF_MIN` 门槛
          的兜底）——「花一次调用换一句‘退回保守’」。
          规则层能覆盖的情形就地定案，**不再花调用**；拿不准才回落 LLM。
        ★ 规则只判到 `_AUTO_REACHABLE_MODES` 内（serial/B/C）——
          6 个 stage 模式不参与自动分派（见常量注释）。
        """
        q = question or ""
        _n = len(q)
        _or = any(t in q for t in self._MODE_RULE_OR)
        _and = any(t in q for t in self._MODE_RULE_AND)
        _pipe = any(t in q for t in self._MODE_RULE_PIPE)
        _clauses = (q.count("，") + q.count(",")) >= 3
        # 1) 含「或/还是」⇒ 开放震荡 ⇒ B
        if _or and _n >= 8:
            return "B", "规则：含选择/开放词（或/还是），走轮次并行"
        # 2) 明确要快且层界可接力 ⇒ C
        if _pipe and _clauses:
            return "C", "规则：显式要求压缩时长且多分句，走流水线并行"
        # 3) 单一短问句（无并列/选择）⇒ serial
        if _n <= 24 and not _or and not _and and not _clauses:
            return "serial", "规则：单一短问句，无并列无选择，走严格串行"
        # 4) 两三个并列分句 ⇒ B（层次不分明、需震荡）
        if _clauses and _and:
            return "B", "规则：多分句且含并列，层次不分明，走轮次并行"
        return None, "规则拿不准"

    def _decide_parallel_mode(self, question: str) -> dict:
        q = question or ""
        _m, _r = self._mode_rule(q)
        if _m:
            self.vp(f"\\n🧵 并行模式（规则）：{_m}（{_r}）")
            return {"mode": _m, "reason": _r, "confidence": 0.9,
                    "source": "rule"}
        feats = {'''
    s = repl_text(s, old2, new2, "B1 规则优先 _decide_parallel_mode")

    # 让 feats 里后续复用（原 feats 定义里含 q.count，保持不动）
    _save(s)
    print("OK 第 2 阶段完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "这一次我是谁（索引）" in s2
    assert "_AUTO_REACHABLE_MODES" in s2
    assert s2.count("def _mode_rule") == 1
    print("复读校验通过 · 行数 %d" % s2.count("\n"))


if __name__ == "__main__":
    main()
