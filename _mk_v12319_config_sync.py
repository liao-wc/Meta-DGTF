# -*- coding: utf-8 -*-
"""v1.23.19 配置同步：头部版本 + 升级段 + retriever 注释块（两处）。

★ 幂等：升级段用 MARK 判重。
"""
from pathlib import Path

HERE = Path(".").resolve()
YML = HERE / "dgtf_config.yaml"
MARK = "# 【v1.23.18 → v1.23.19】"

UP = '''# 【v1.23.18 → v1.23.19】锚点「真检索」这条路够得到（修一条死路 + 一处过期前提）
#   ★ **默认行为逐字不变**：出厂 `retriever` 仍是 `snapshot`（零额外调用）。
#   改的是什么：
#     ① ★★ **死路**：`_retrieve_anchors` 全篇只有 `_anchor_round` 里一处调用，
#        而它在 `not self._anchors` 这道早退**之后** ⇒ **没挂快照文件时真检索
#        一次都不会被调用**；连「后端未实现」该有的抛错留痕也发生不了
#        （承诺了「非 snapshot 抛错留痕」，实际够不到）。
#        实测改前：`retriever="tavily"` + 空锚点 ⇒ 检索调用 **0** 次、
#        「未实现后端」的留痕为空。现在把那一项移到位（snapshot 模式仍要求已
#        读入锚点；真检索模式自己填）⇒ 检索调用 1 次、锚点被填、按 `per_round`
#        投池；未实现后端**真抛错留痕**。
#     ② **过期前提**：`_anchor_round` 的 docstring 写着「引擎现在没有联网能力」
#        —— 这句早已不成立（联网在 `web_search`；锚点另有 `AnchorRetriever`）。
#        已重写，并写明两条来源的分工。
#     ③ `unconfigured` 只对 **snapshot** 模式置位：真检索模式不读 `path`，
#        它不是「未挂文件」，是**已配置**（改前 tavily 模式也被误标「未挂文件」）。
#     ④ 文案：「开（未挂锚点文件）」与产物明细「未做」都把**两条接入路**写全
#        （`path` 指快照 JSON / `retriever: tavily` 按圈真检索）。
#   ★★ **为什么不把 `web_search` 收到的结果直接当锚点**：那批进的是
#     `pool.web_results`，是**喂给各层的证据**（`used_as`）；拿它回头量各层的
#     结论是**自证**，不是校验。锚点对照要的是**独立**的尺子（运行前落盘的
#     快照，或另一路按池内问题发起的检索）。两者互相独立是**故意**的。
#   ★ 判据：`check_v12319_anchor_retrieval_reachable`（可达性 + 三条负对照 +
#     `unconfigured` 范围 + 两处文案）+ 4 个变异体。
#
'''

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    print("%-40s 改 %d 处" % (what, len(hits)))


repl("# 元 DGTF · v1.23.18 配置文件", "# 元 DGTF · v1.23.19 配置文件", "头部版本")

if MARK in "\n".join(lines):
    print("%-40s 已存在，跳过" % "升级段")
else:
    ANCHOR = "# 【v1.23.17 → v1.23.18】外部锚点默认打开"
    _hit = [k for k, l in enumerate(lines) if l.startswith(ANCHOR)]
    assert len(_hit) == 1, "升级段锚点命中 %d 次" % len(_hit)
    lines[_hit[0]:_hit[0]] = UP.split("\n")
    print("%-40s 已插入" % "升级段")

repl('''  # 【用途】锚点检索后端（v1.22 引入）。
  #   "snapshot" —— **零调用**：直接读上面 path 指的快照 JSON（默认）。
  #   其它取值    —— 走真检索：当前实现 `tavily`，结果按 queries 的
  #                  sha256 落 `cache/anchors/`，TTL 内不再打网络；
  #                  未知取值**抛错留痕**，不静默降级。
  retriever: "snapshot"''',
     '''  # 【用途】锚点检索后端。
  #   "snapshot" —— **零调用**：读上面 `path` 指的快照 JSON（默认）。
  #                  ★ 必须给 `path`；没给就是「开（未挂锚点文件）」那个干净态。
  #   其它取值    —— 走真检索：当前实现 `tavily`，按池内问题
  #                  （`_build_anchor_queries`）逐圈检索，结果按 queries 的
  #                  sha256 落 `cache/anchors/`，TTL 内不再打网络；需要 key
  #                  （见 `api_key_env`）。
  #                  ★ 这条**不读 `path`** —— 没有快照文件也能独立工作。
  #   未知取值    —— **抛错留痕**，不静默降级。
  # 【注】真检索此前**够不到**（`_anchor_round` 的早退条件里有「已有锚点」，
  #   而检索调用在它后面）⇒ 没挂快照文件时一次都不会发生。已修。
  retriever: "snapshot"''',
     "retriever 注释块")

out = "\n".join(lines)
enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
YML.write_bytes(enc)
import yaml
d = yaml.safe_load(enc.decode("utf-8"))
ea = d["external_anchor"]
print("yaml 语法 OK；enabled=%r retriever=%r path=%r | 行数 %d"
      % (ea.get("enabled"), ea.get("retriever"), ea.get("path"), out.count("\n")))
