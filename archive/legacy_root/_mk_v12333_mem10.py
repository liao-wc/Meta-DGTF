# -*- coding: utf-8 -*-
"""追加今日记忆第十节：候选生成产出率量化 + 判据事故（3→4）。

★ 记忆是 LF-only；写文件走 read_bytes/write_bytes。
"""
import io, os, sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".workbuddy", "memory", "2026-10-14.md")
ADD = u"""
---

## 十、第六期第二批次：**候选生成产出率**（用户点名五处之第五处）

### 落地
- `candidate_yield(cands, prev_texts, thr=0.72)`（模块级纯函数，**零 LLM**）：
  逐条取与上圈全部候选描述的最大相似度（`_overlap_coef` / `_similar` 两把已有尺子），
  `new_ratio` = 相似度低于 `thr` 的条数占比；`collapsed = new_ratio < 0.34`。
  读数 `n / n_new / new_ratio / max_sim / collapsed / verdict`。
- ★ **缺输入 ⇒ 全 `None` + `verdict=""`（不表态）**：首次跑是「没得比」不是「没长」。
- 接线：`DGTF.run` 的 `_drop_banned` 之后、`_dual_judge` **之前**
  （`_dual_judge` 会改写候选集合 ⇒ 读在它之后 = 读加工过的）。
  历史走 `view._prev_cand_descs` 跨圈暂存。命中 `collapsed` 打一行 `vp` 留痕、**不拦截**。
- 补丁：`_patch_v12333_candyield.py`（2 锚点）。

### ★ 判据事故：㉛ 硬编码「调用点 == 3」⇒ 新增第四处后**干净基线判红**
- 现象：`_mut_v12332.py --only 50,51` 报 `X 干净基线不绿`（EXIT=2）；
  直接跑冒烟看到 `X [量化] _quant_note 真实调用点应为 3 处（实得 4）`。
- 修法**不是放宽阈值**，而是**把新调用点显式登记进判据**（3 → 4），
  数量约束仍为**硬等式** —— **判据随实现更新**。
- ★ 这条是「判据随实现更新」的**正向例子**：数量变了不是缺陷，但必须有人显式确认，
  所以计数仍写成 `!= 4` 而不是 `>= 3`。

### 新判据 ㉜（候选产出率）
- 方向两向：整批复述 ⇒ `collapsed`；全新生 ⇒ **不** collapsed。
- 缺输入不许回 `0`（`n_new` / `max_sim` 必须 `None`）。
- 接线位置：`_i_cy < _i_dj`（`_quant_note(view, "candidate_yield"` 必须早于
  `candidates = self._dual_judge(candidates`）。
- 真实入口：`candidate_yield([getattr(c, "desc", "")` 在源码里。

### 新变异体
- **M50** 产出率方向反（整批复述判 `ok`、全新生判 `collapsed`）⇒ 判红。
- **M51** 产出率缺输入硬给（首次跑也被判 `collapsed`）⇒ 判红。

### 验收（v1.23.33 终稿）
- 主文件 **24569 行 / 纯 CRLF**（裸 LF 0 / CR-CR-LF 0）/ AST OK；`_quant_note` 调用点 **4**；
- 冒烟 **223 ✓ / 0 ✗ / EXIT=0**；AUDIT **68 PASS / 0 FAIL**；
- 变异体 **51 / 51 判红**（+ M50 / M51）；配置 **193 键 / 两向对账 0 差**。

### 本轮新增通则（续 11.8）
- **「缺输入不表态」必须回 `None`，不能回 `0`** —— `0` 会被下游当成「测出来就是 0」，
  实际是「这次没得测」；首次跑 ⇒ 假 `collapsed` 告警（M51 打的就是它）。
- **零成本的证明是构造性的**（spy 包 `LLM.call` 计 0 次），不是「看代码没 `LLM` 字样」。
- ★ **写脚本的换行断言方向别写反**：报告是 LF-only ⇒ 判据是 `CRLF == 0`，
  不是「LF 数 == CRLF 数」（后者是**纯 CRLF** 的判据，本轮第一次跑栽在这）。
"""


def main():
    if "## 十、第六期第二批次" in io.open(P, encoding="utf-8").read():
        print("已存在第十节，跳过"); return
    raw = io.open(P, "rb").read()
    crlf = raw.count(b"\r\n")
    assert crlf == 0, "记忆应为 LF-only，实得 %d 处 CRLF" % crlf
    s = raw.decode("utf-8").rstrip("\n") + "\n" + ADD
    with io.open(P, "wb") as f:
        f.write(s.encode("utf-8"))
    print("OK 第十节已追加，行数 %d" % s.count("\n"))


main()
