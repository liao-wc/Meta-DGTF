# -*- coding: utf-8 -*-
"""CHANGELOG 补「降本真缺陷 + 取向规则」段（v1.23.33 续三）。"""
import io

P = "CHANGELOG.md"
OLD = u"""【验收（第六期）】判据 **㉗~㉜**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +"""
NEW = u"""【★ 降本真缺陷：规则命中「省调用」被自己抵消（本轮真跑逮到）】
  · 现象：`auto_plan(llm=...)` 的 B1 规则命中分支，注释写「命中即定案，
    **不花这次模式调用**」—— 但紧接着为补 `orientation` 又调了
    `plan_orientation(q, cfg)`，而它的签名**只有 `config`**、内部自己
    `new LLM(cfg)` ⇒ **真花掉一次调用**。实测规则命中路径 `LLM.call` = **1**
    （本应 0）。
  · ⇒ 「省调用」的设计意图被自己的补丁吃掉，正是用户点名诉求
    「减少 LLM 调用」的直接违背。★ 形态同「有接线 ≠ 这跑走得到」：
    **成本账目与代码注释不一致，因为没人把「规则命中 ⇒ 0 次调用」当判据跑过**。
  · 修（`_patch_v12333_orientrule.py`）：新增模块级纯函数 `orientation_rule()`
    （零成本，与 `_has_decision_context` **同源** —— 避免「打桩判 decision、
    渲染判 boundary」的双真相）；规则命中时用它，**只有规则拿不准才回落 LLM 版**。
  · 验收：规则命中 ⇒ `LLM.call` **0 次**（构造性证明，spy 计数）；
    取向由本地规则给（决策语汇 ⇒ decision / 否则 boundary）；
    新判据 **㉝** + 变异体 **M52**（方向反）/ **M53**（又偷调 LLM）均判红。

【验收（第六期）】判据 **㉗~㉝**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +"""
OLD2 = u"""  **M51**（产出率缺输入硬给）**均判红**（累计 **51**）。"""
NEW2 = u"""  **M51**（产出率缺输入硬给）/ **M52**（取向规则方向反）/
  **M53**（规则命中又偷调 LLM）**均判红**（累计 **53**）。"""


def main():
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "CHANGELOG 应为 LF-only"
    s = raw.decode("utf-8")
    for old, new in ((OLD, NEW), (OLD2, NEW2)):
        assert s.count(old) == 1, "锚点命中 %d 次：%s" % (s.count(old), old[:30])
        s = s.replace(old, new, 1)
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK CHANGELOG 已补降本段，行数 %d" % s.count("\n"))


main()
