# -*- coding: utf-8 -*-
"""CHANGELOG 补「候选产出率时序缺陷修复」段。"""
import io

P = "CHANGELOG.md"
OLD = u"""【★ 降本真缺陷：规则命中「省调用」被自己抵消（本轮真跑逮到）】"""
NEW = u"""【★ 时序缺陷：候选产出率读数**永不落盘**（真实入口探针逮到）】
  · 现象：收尾按铁律补「真实入口产出」验证（`_probe_v12333_candyield.py`，
    复用冒烟 mock ⇒ **零花费**、走真实 `MetaDGTF.run`）。四问结果：
    `candidate_yield` 被调 **2 次**（接线在），但两次 `verdict` 都是 `''`、
    `quant_readings` 里**没有这个键** ⇒ **读数永不落盘**。
  · 根因（本项目第 3 类失败：**时序颠倒**）：`MetaDGTF` 圈循环里每圈
    `dg = DGTF(entry, ...)` + `view = dg.run(inp)` ⇒ **DGTF 实例与 view 都每圈新建**；
    我把「上一圈候选」写在 `view._prev_cand_descs` 上 ⇒ **下一圈必然读不到**
    ⇒ 恒 `None` ⇒ 永久走「缺输入不表态」分支。
  · 修（`_patch_v12333_candyield_ts.py`，不动任何签名）：`inp.pool`
    （= `self.pools[entry]`）**每层一个、跨圈复用** ⇒ 历史改挂 `inp.pool`。
  · 验收：修后第 1 圈 `verdict=''`（无历史，正确）/ 第 2 圈
    `n_new=0 new_ratio=0.0 max_sim=1.0 verdict='collapsed'`（mock 两圈相同，正确）；
    **serial / B / C 三通道**落盘层都是 `['0','1']` 且值逐字相同（**无漂移**）。
  · 新判据 **㉞**（真实入口产出：断言 `quant_readings` 里真有键 + 形态含 verdict
    + mock 下必须判 collapsed + 源码守卫「`view._prev_cand_descs` 不许出现」）；
    新变异体 **M54**（历史挂回 view ⇒ 判红）。
  · ★ 同期修 ㉜ 的**锚过脆**：原判据钉了整行字面，参数一折行即失配（干净基线判红）
    ⇒ 改成**压掉全部空白后查语义**。通则：**锚不能钉在会变的东西上**。

【★ 降本真缺陷：规则命中「省调用」被自己抵消（本轮真跑逮到）】"""
OLD2 = u"""  **M53**（规则命中又偷调 LLM）**均判红**（累计 **53**）。"""
NEW2 = u"""  **M53**（规则命中又偷调 LLM）/ **M54**（候选历史挂回每圈重建的 view）
  **均判红**（累计 **54**）；判据 **㉞**（真实入口产出）。"""


def main():
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "CHANGELOG 应为 LF-only"
    s = raw.decode("utf-8")
    for old, new in ((OLD, NEW), (OLD2, NEW2)):
        assert s.count(old) == 1, "锚点命中 %d 次：%s" % (s.count(old), old[:30])
        s = s.replace(old, new, 1)
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK CHANGELOG 已补时序缺陷段，行数 %d" % s.count("\n"))


main()
