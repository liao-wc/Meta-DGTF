# -*- coding: utf-8 -*-
"""v1.23.19 CHANGELOG 段（幂等：先抠旧的同版段再插）。"""
from pathlib import Path

P = Path(".").resolve() / "CHANGELOG.md"
raw = P.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

HEAD = "v1.23.19 相对 v1.23.18"
NEXT = "v1.23.18 相对 v1.23.17"

NEW = '''v1.23.19 相对 v1.23.18

【要解决的问题】回答「锚点对照为什么没做」时查出一条**真缺陷**：
  `external_anchor` 自称有「真检索」后端（`retriever: tavily`），
  但 `_retrieve_anchors` 全篇**只有一处调用**，而它在 `_anchor_round` 的
  `not self._anchors` 早退**之后** —— 而 `self._anchors` 非空的唯一来源是
  **快照文件** ⇒ **没挂文件时真检索一次都不会被调用**；连「后端未实现」该有的
  抛错留痕也发生不了（承诺了「非 snapshot 抛错留痕」，实际够不到）。
  同时它的 docstring 还写着「引擎现在没有联网能力」—— 这句**早已不成立**。

【改了什么】（引擎 8 处编辑；★ 默认路径逐字不变，`load_config` 差异 ∅）
- `_anchor_round`：早退里**摘掉「已有锚点」**，把它放到**模式分流之后**
  （snapshot 模式仍要求已读入锚点；真检索模式由它自己填 `self._anchors`）⇒
  真检索可独立启动。实测：tavily + 空锚点 → 检索调用 **0 → 1** 次、
  `_anchors` **0 → 2** 条、按 `per_round` 投池；未实现后端**真抛错留痕**
  （改前留痕为空：`False → True`）。
- `_anchor_round` 的 docstring 重写：写清**两条来源**、**为什么早退条件要挪**、
  以及**与 `web_search` 的边界**（拿本次喂进层里的东西回头量层结论 = 自证）。
- `_load_anchors`：`unconfigured` **只对 snapshot 模式**置位 —— 真检索模式不读
  `path`，它是**已配置**（改前 tavily 模式也被误标「未挂文件」，`True → False`）。
- `_anchor_crosscheck` 的 base dict 加 `retriever_mode`；渲染两处（头部通道行 /
  产物明细「未做」）把**两条接入路**写全（`path` 指快照 JSON / `retriever: tavily`
  按圈真检索），真检索模式在头部标注后端。

【为什么**不**把 `web_search` 收到的结果直接当锚点】
  那批进的是 `pool.web_results`，是**喂给各层的证据**（带 `used_as`）；
  拿它回头量各层的结论是**自证**，不是校验。锚点对照要的是**独立**的尺子
  （运行前落盘的快照，或另一路按池内问题发起的检索）。两者互相独立是**故意**的。

【验收】
- 探针 9 项读数变化 + 3 条负对照（含**不桩**的那条：未实现后端的抛错留痕
  `False → True`）；默认路径 `B_snapshot_*` **前后一致**（0 调用 / 0 条）。
- 变异体 **4/4 判红**（早退复活 / `unconfigured` 对所有模式 / 渲染只提一条路 /
  检索结果不并池），control 判绿。
- ★ **真联网**（这条代码**有史以来第一次执行**）：未知后端抛错；snapshot 返回 `[]`；
  **tavily 真检索返回 6 条**（`id/claim/url/tier` 齐备、内容相关）；
  同 queries 第二次 **0.01 s** 命中 `cache/anchors/`。
- 冒烟 `exit 0 / ✗ 0 / ✓ @@SMOKE@@`；整体审计 **@@AUDIT@@**；
  配置三向：`load_config` 差异 **∅**（本版不改任何生效值，出厂 `retriever` 仍 `snapshot`）。
- 主文件 18287 → **18316** 行 / 纯 CRLF；AST 符号新增/消失 **0 / 0**。

【未做 / 遗留（如实记账）】
- **没有**把 `web_search` 的结果接进锚点对照（理由见上）；出厂 `retriever` 仍
  是 `snapshot`（真检索要显式打开 —— 每圈最多 2 次网络调用，「默认零调用」是硬约束）。
- `_tavily` 的 `id` 每轮从 `t1` 重新编号 ⇒ 跨圈同 id 会被 `already` 去重（少投几条）；
  既有实现，本版未改。
- 默认路径（snapshot）**未重复真跑**：本版对它逐字不变（探针前后一致），
  所以只跑了真检索那一态。
- 锚点仍不是 auto 调度项（v1.23.13 的排除决定不变）。

'''

if HEAD in s:
    i = s.index(HEAD)
    j = s.index(NEXT, i)
    s = s[:i] + s[j:]
    print("已抠掉旧的 v1.23.19 段")

assert s.count(NEXT) == 1, "下一段锚点命中 %d 次" % s.count(NEXT)
s = s.replace(NEXT, NEW + NEXT, 1)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
t = out.decode("utf-8")
print("v1.23.19 段数:", t.count("v1.23.19 相对 v1.23.18"),
      "| 段序前 3:", [x for x in t.split("\n") if x.startswith("v1.23.1")][:3])
