# -*- coding: utf-8 -*-
"""[v1.23.38 补丁5] CHANGELOG.md：加 v1.23.38 段（最新在最前）。

★ CHANGELOG 是 LF 文件（不是纯 CRLF 主文件）⇒ 用 LF 写。
★ 段落位置：插在 `v1.23.37 相对 v1.23.36` 之前。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "CHANGELOG.md"

ANCHOR = "v1.23.37 相对 v1.23.36"

NEW_SEC = """v1.23.38 相对 v1.23.37

【主题】**联网按需「回喂」**（池复用式）+ 圈级心跳**放宽目标表扩展**（4 → 8）。
—— 把 v1.23.37 只做了一半的按需协议补完：声明 ⇒ 检索 ⇒ **后续环节真的用上**。

【① 联网按需「回喂」（池复用式）】
v1.23.37 做到「声明 ⇒ 检索 ⇒ 进池 + 留痕」，但结果**只躺在池里**，
下一环节经 `_web_augment` 时**又查一遍**、且拿不到池里那份。
本版让 `_web_augment` 在检索**之前**先扫池：
· 命中（`used_as == "record"` 且 `stage` 匹配）⇒ **直接复用**，不再调 `_searcher`
  ⇒ 回喂路径下 `_searcher` 调用次数 = **0**（成本判据：省钱真发生）。
· 复用**安全**：这些条目当年进池时**已过 Gate**（授权 + 三层配额 + 失败降级），
  这里只是取出来用，**不产生任何新的外部调用**。
· **留痕**：`logger.info("[WEB-BACKFEED] stage=… 复用池内按需结果 N 条 ⇒ 注入")`。

改动**只两处、都在既有函数体内、不新增任何 AST 符号**：
① 注入侧（`MetaDGTF.run` 的 `_llm_ctx_set`）多注入一个线程上下文键
   `backfeed_pool=self.pools.get("1")` ⇒ `LLM` 侧能读到池。
② 消费侧（`LLM._web_augment`）检索前先扫池，命中就复用 + 留痕。

**零行为差**：不带池（老调用方）/ 池里没有 record / `stage` 不匹配 / 无注入器
⇒ **全部原路不变**（四条负对照各有判据）。

【② 圈级心跳放宽目标表扩展（4 → 8）】
`MetaDGTF._TICK_WEB_RELAX` 原表 `("ing", "probe_research", "probe_duel",
"probe_meta")` —— 只挑「最需要外部刺激」的那一类。本版按**同族补漏**：
· `he` —— 「和」环节，与表内 `ing`（推理）**对偶**（缺它不对称）
· `phase_probe` —— 阶段探针，与表内三类 `probe_*` **同族**
· `expand_pair` / `expand_pair_merged_once` —— 展开对撞对：
  停滞（池零增量）= 没有新对 ⇒ 正是该问外面的时刻。
★ 只在「上一圈零增量 + 联网总闸已开」时经 `ControlSurface` 放宽 ⇒ 默认零行为差。
★ **两向对账**：每个成员必须在 `web_search.stages` 里存在，否则「放宽」是
  **死配置**（放宽一个引擎不认的 stage，永远不生效且**不报错**）
  ⇒ 新判据 `check_v12338_relax_targets` 钉住（8/8 全在 30 个环节里）。

【验收】
· 主文件 `元DGTF-V1.23.38.py`：25772 行 / 纯 CRLF（`\\r\\r\\n` = 0）/ AST OK。
· 冒烟 `smoke_test.py`：**232 ✓ / 0 ✗**（比上版 +2 = 两条新判据）。
· 变异体 `_mut_v12332.py`：**80 条**（新增 M80/M81/M82），全量判红见 `_mut_v12338full.log`。
· 前置探针 `_probe_v12338_backfeed.py`（改前/改后同支对表）：
  | 场景 | v1.23.37 | v1.23.38 |
  | A 池里有本 stage 的 record | `_searcher` 调 1 次 / 用新检索结果 | 调 **0** 次 / 用**池内原文** |
  | B 池里没有（负对照） | 调 1 次 | 调 **1** 次 |
  | C 无注入器 | None | None |
· **无新增配置键**（回喂与放宽表都是行为侧改动）⇒ `load_config` 逐字差异 **0 项**。

【判据纪律】
· 新判据 `check_v12338_backfeed` 走**真实入口产出**：真驱动 `_web_augment` 看它
  到底注入了什么（正 = 复用且 `_searcher` 零调用；负 = 池空仍检索 / `stage`
  不匹配不复用 / 无注入器 `None` / 不带池退回原行为）。
· 新判据 `check_v12338_relax_targets` 定位/解析**一律用纯字符串操作**
  （`find` / `endswith` / `split`）**不用正则** —— 本项目在「脚本 → 落盘 → 解析」
  三层里数错反斜杠已踩多次（本轮 `r"...\\\\(..."` 写成双反斜杠 ⇒ 正则匹配字面
  反斜杠 ⇒ 判据恒报「找不到定义」，且**不报错**）。
· 版次批注**不许进代码注释**（要落本文件）—— 本轮实测踩到：把 `[v1.23.38]`
  写进 `_TICK_WEB_RELAX` 的注释 ⇒ 冒烟 `[v1236] 正文注释里仍有版次批注` 判红。

---

v1.23.37 相对 v1.23.36
"""


def main():
    raw = P.read_bytes()
    crlf = raw.count(b"\n") == raw.count(b"\r\n") and raw.count(b"\n") > 0
    print("[info] CHANGELOG 换行：%s" % ("CRLF" if crlf else "LF"))
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = s.count(ANCHOR)
    assert n == 1, "锚点命中 %d 次（要求 1）" % n
    s2 = s.replace(ANCHOR, NEW_SEC)

    out = s2.replace("\n", "\r\n").encode("utf-8") if crlf else s2.encode("utf-8")
    P.write_bytes(out)

    # 回读自检
    chk = P.read_bytes().decode("utf-8")
    assert "v1.23.38 相对 v1.23.37" in chk
    assert "v1.23.37 相对 v1.23.36" in chk
    assert chk.count("v1.23.38 相对 v1.23.37") == 1
    # 段序：38 段必须在 37 段之前
    assert chk.find("v1.23.38 相对 v1.23.37") < chk.find("v1.23.37 相对 v1.23.36")
    print("[ok] CHANGELOG 已加 v1.23.38 段（最新在最前，段序 OK）")
    print("[ok] 行数 =", chk.count("\n"))


if __name__ == "__main__":
    main()
