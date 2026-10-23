# -*- coding: utf-8 -*-
"""CHANGELOG 补「全局链路核查」段。"""
import io

P = "CHANGELOG.md"
OLD = u"""【★ 时序缺陷：候选产出率读数**永不落盘**（真实入口探针逮到）】"""
NEW = u"""【全局链路核查（用户要求以全局视角过一遍四条链路）】
  · **① 自我学习迭代（EML）**：判据全过；日志实证学习真在发生
    （`过闸新增 2` / `升级 2` / `用 2 条（生效 1）`）。本轮改动**零影响** ——
    EML 读写都在 `MetaDGTF` 层，不读 `quant_readings`、不碰 `inp.pool` 暂存量。
  · **② dgtf_app —— 需要更新，已修**：`dgtf_app/selftest.py` 报 `PASS 366 / FAIL 1`，
    失败项「参数标签统一成『键（中文说明）』」。根因：上一轮引擎新增
    `actions.merge_expand`，**app 侧 `_KEY_CN` 没同步** ⇒ `label_for` 退化成裸键。
    ⇒ 又一次「引擎 `DEFAULT_CONFIG` 与 app `_KEY_CN` 各一份键清单」。
    修：补标签 + ★ 把该判据失败消息改成**报出缺标签的键名**（原来只报总数）。
    重跑 **PASS 367 / FAIL 0**。
  · **③ 日志显示同步 —— 逮到真断点，已修**：`quant_readings` 原来**只出到
    packed JSON**（产物 md 附录得翻），**正文与日志都没有** ⇒ 引擎算了 4 个读数
    但人类看不见（第 2 类失败的变体：有值但**没有可读出口**）。
    修：每层正文 `_render` 尾部加【各环节量化】段（`_patch_v12333_quantmd.py`）。
    ★ 三处取舍：**遍历全部键**（不维护渲染清单 ⇒ 新读数自动出现）/ 未知键
    **降级为键名** / **中文标签 + 英文键名都给**（可读 + 可 grep + 附录字段名
    覆盖统计不再失真）。
  · **④ 链路依赖 —— 无破坏**：`inp.pool._prev_cand_descs` **不进产物**
    （`Pool.to_dict()` 是手工白名单；实证产物 JSON 里搜不到）；`quant_readings`
    新键对下游无破坏（冒烟 / `--phase all` / AUDIT 全绿）；**三通道**
    （serial / B / C）落盘层与值**逐字相同**（无漂移）。
    ★ 确立下游依赖清单：`quant_readings` 的四个出口 = `to_dict()` / 产物正文（新）/
    产物附录 JSON / dgtf_app（经 md）—— 新增读数**四处都要能看到**。
  · 新判据 **㉟**（可读性：捕获 `_render` 正文，断言有段落 + 中文标签 + 英文键名；
    与 ㉞ **共用一次 mock run**）；新变异体 **M55**（关掉正文段 ⇒ 判红）。

【★ 时序缺陷：候选产出率读数**永不落盘**（真实入口探针逮到）】"""
OLD2 = u"""  **M53**（规则命中又偷调 LLM）/ **M54**（候选历史挂回每圈重建的 view）
  **均判红**（累计 **54**）；判据 **㉞**（真实入口产出）。"""
NEW2 = u"""  **M53**（规则命中又偷调 LLM）/ **M54**（候选历史挂回每圈重建的 view）/
  **M55**（量化读数不进产物正文）**均判红**（累计 **55**）；
  判据 **㉞**（真实入口产出）+ **㉟**（可读性：读数进正文）。
  dgtf_app 自检 **PASS 367 / FAIL 0**（补 `merge_expand` 中文标签后）。"""


def main():
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "CHANGELOG 应为 LF-only"
    s = raw.decode("utf-8")
    for old, new in ((OLD, NEW), (OLD2, NEW2)):
        assert s.count(old) == 1, "锚点命中 %d 次：%s" % (s.count(old), old[:30])
        s = s.replace(old, new, 1)
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK CHANGELOG 已补全局核查段，行数 %d" % s.count("\n"))


main()
