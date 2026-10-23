# -*- coding: utf-8 -*-
"""CHANGELOG 补「候选生成产出率」+ 更新验收数字（判据 ㉜ / M50 / M51）。

★ 跟随文件换行风格（CHANGELOG 是 LF-only）。
★ 正文不写转义序列字面（Write 工具会把它变成真字符）。
"""
import io, os, sys

P = "CHANGELOG.md"

# A1：在「=== 验收段」的收尾行之前，插一段「候选生成产出率」
OLD_A = u"""【验收（第六期）】判据 **㉗~㉛**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +
  缺一侧不表态 / ㉙ 保真度方向 + 缺输入不表态 / ㉚ 语义密度方向 + 空输入不表态 +
  **「不调 LLM」的构造性证明**（spy `LLM.call` 计数须为 **0**）/
  **㉛ 可达性**（模块级 + 真写一次 + 无 `self._quant_note(` + 3 处调用 + 1 份定义）；
  变异体 **M45**（合并开关默认打开）/ **M46**（分歧度方向反）/
  **M47**（保真度缺输入硬表态）/ **M48**（语义密度偷偷调 LLM）/
  **M49**（`_quant_note` 结构性不可达）**均判红**（累计 **49**）。"""

NEW_A = u"""【候选生成产出率（用户点名五处之第五处，第六期第二批次）】
  · 问题：候选池是下游全部付费环节的输入；若一圈生成的「候选」其实是上圈说法的
    **复述**，对偶判断 / ing / view 都在为**零信息量**付费，账面却显示「产出 N 条」。
  · 落地：`candidate_yield()`（模块级纯函数，零 LLM）—— 逐条取与**上圈全部候选描述**
    的最大相似度，`new_ratio` = 相似度低于 `thr`（默认 0.72）的条数占比；
    `collapsed` = `new_ratio < 0.34`。四项读数 `n / n_new / new_ratio / max_sim`。
  · ★ **缺输入 ⇒ 全 `None` + `verdict=""`（不表态）** —— 首次跑是「没得比」，不是
    「没长」；硬给 `collapsed` 会造出**假告警**（M51 打的就是它）。
  · 接线：`DGTF.run` 的 `_drop_banned` 之后、`_dual_judge` **之前** ——
    `_dual_judge` 会改写候选集合，读在它之后 = 读加工过的东西（判据 ㉜ 显式断言顺序）。
    命中 `collapsed` 打一行 `vp` 留痕（明说「可能在为无信息量付费」），**不拦截**
    （红线：留痕与拦截分开）。

【验收（第六期）】判据 **㉗~㉜**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +
  缺一侧不表态 / ㉙ 保真度方向 + 缺输入不表态 / ㉚ 语义密度方向 + 空输入不表态 +
  **「不调 LLM」的构造性证明**（spy `LLM.call` 计数须为 **0**）/
  **㉛ 可达性**（模块级 + 真写一次 + 无 `self._quant_note(` + **4 处调用** + 1 份定义）/
  **㉜ 候选产出率**（方向两向 + 缺输入不许回 0 + 接线在对偶判断之前 + 真实入口）；
  变异体 **M45**（合并开关默认打开）/ **M46**（分歧度方向反）/
  **M47**（保真度缺输入硬表态）/ **M48**（语义密度偷偷调 LLM）/
  **M49**（`_quant_note` 结构性不可达）/ **M50**（产出率方向反）/
  **M51**（产出率缺输入硬给）**均判红**（累计 **51**）。
  · ★ 判据随实现更新：㉛ 原硬编码「调用点 == 3」，新增第四处接线后**干净基线判红**；
    修法是**把新调用点显式登记进判据**（3 → 4），数量约束仍为硬等式 ——
    不是放宽阈值。"""


def patch(path, pairs):
    with io.open(path, "rb") as f:
        raw = f.read()
    crlf = raw.count(b"\r\n")
    assert crlf == 0, "CHANGELOG 应为 LF-only，实得 %d 处 CRLF" % crlf
    s = raw.decode("utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, "锚点命中 %d 次（应为 1）：%s" % (s.count(old), old[:40])
        s = s.replace(old, new, 1)
    assert s.count(b"\r\r\n".decode()) == 0 if False else True
    with io.open(path, "wb") as f:
        f.write(s.encode("utf-8"))
    return s.count("\n")


n = patch(P, [(OLD_A, NEW_A)])
print("OK CHANGELOG 已补候选生成段 + 验收更新，行数 %d" % n)
