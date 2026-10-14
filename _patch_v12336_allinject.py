# -*- coding: utf-8 -*-
"""按用户指令：**所有层都注入**（去掉修行层的硬豁免）。

## 指令与依据的冲突（显式记档）
  · yaml L1741 原话：「修行层与停止判据默认关 —— **修行层联网会污染
    『输入是形状不是数据』这条宪法级特性**」⇒ 我据此实现了「修行层不注入」的**硬豁免**。
  · 用户指令（本轮）：「**所有层都注入**」⇒ 硬豁免取消。

## 保护怎么变（这才是关键）
  从「**硬豁免**」（修行层永远不许注入）改成「**默认关 + 逐环节开关**」：
    · 各环节开关**出厂全是 false** ⇒ 不打开就不注入 ⇒ **默认行为逐字不变**；
    · 修行层的保护仍在，但变成**可开关的**（用户自主决定）。
  · `practice_term_calibration`（修行层的术语校准）**仍只留痕、不注入** ——
    它与本条是**两条独立路径**，本次不动它。
  ★ 这不是「放弃红线」，是**把红线从硬编码改成可配置**：谁开谁负责，且全程留痕。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

OLD = '''        if callable(_searcher) is False:
            return None
        if str(_llm_ctx_get("entry", "")) == "0":
            return None                       # ★ 红线：修行层不注入'''

# 真实文本（上面那份是我按记忆写的，这里用真实锚点）
OLD_REAL = '''        if not callable(_searcher):
            return None                       # 没接线（如独立调用 LLM）⇒ 不增强
        if str(_llm_ctx_get("entry", "")) == "0":
            return None                       # ★ 红线：修行层不注入'''

NEW_REAL = '''        if not callable(_searcher):
            return None                       # 没接线（如独立调用 LLM）⇒ 不增强
        # ★ [用户口径] **所有层都注入** —— 修行层（entry "0"）的硬豁免已取消。
        #   保护改由**配置**承担：30 个环节的开关出厂全 false ⇒ 不打开就不注入
        #   ⇒ 默认行为逐字不变；要注入就得显式打开（谁开谁负责、全程留痕）。
        #   ★ 修行层的「术语校准」是**另一条路径**（`practice_term_calibration`），
        #     它仍只进 pool + 产物、不注入 prompt —— 本次不动它。'''

OLD_DOC = '''        ★ 默认关：`web_search.enabled=false` ⇒ **立刻返回 None**（零行为差）。
        ★ 红线：**修行层（entry == "0"）不注入** —— 它的输入必须只有形状；
          修行层的联网走 `practice_term_calibration`（只留痕、不注入）。
        ★ 全部经 Gate：授权（`stages.<环节名>`）/ 三层配额 / 失败降级 ⇒ **可控**。'''

NEW_DOC = '''        ★ 默认关：`web_search.enabled=false` ⇒ **立刻返回 None**（零行为差）。
        ★ **所有层都注入**（含修行层）—— 是否注入**完全由配置决定**：
          `web_search.enabled`（总闸）× `web_search.stages.<环节名>`（逐环节）。
          出厂两者都是关 ⇒ 默认零行为差；打开了就注入（谁开谁负责、全程留痕）。
        ★ 全部经 Gate：授权（`stages.<环节名>`）/ 三层配额 / 失败降级 ⇒ **可控**。'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n1 = s.count(OLD_REAL)
    assert n1 == 1, "豁免代码锚点命中 %d 次（应为 1）" % n1
    s = s.replace(OLD_REAL, NEW_REAL, 1)
    n2 = s.count(OLD_DOC)
    assert n2 == 1, "docstring 锚点命中 %d 次（应为 1）" % n2
    s = s.replace(OLD_DOC, NEW_DOC, 1)
    assert 'str(_llm_ctx_get("entry", "")) == "0"' not in s, "硬豁免没删干净"
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 所有层都注入（硬豁免已取消，保护改为配置式）；行数 %d"
          % out.count(b"\n"))


main()
