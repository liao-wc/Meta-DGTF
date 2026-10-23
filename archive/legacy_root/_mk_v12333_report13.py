# -*- coding: utf-8 -*-
"""追加报告第十三节：降本真缺陷（规则命中的省调用被抵消）。"""
import io, os, sys

P = "v12333_报告.md"
ADD = u"""
---

## 十三、★ 降本真缺陷：规则命中「省调用」被自己的补丁抵消

### 13.1 怎么发现的

  做 `--phase all` 收尾核查时，`_v122_verify.py` 的 **P5.2.c / P5.2.b** 判红。
  这两条断言的是「`auto_plan` 打桩一次调用带出取向」。顺着查下去，发现
  `auto_plan(llm=...)` 在 **B1 规则命中**时 **`LLM.call` 根本没被调用**
  （桩的 `calls` 是空的）—— 与判据的假设完全相反。

### 13.2 根因

  `auto_plan` 里规则命中分支的注释白纸黑字写：

  > 「命中即定案，**不花这次模式调用**」

  但它紧接着为了补 `orientation` 调了 `plan_orientation(q, cfg)` ——
  而 `plan_orientation` 的签名**只有 `config`**，内部自己 `new LLM(cfg)`
  （没有 `llm=` 参数可注入）⇒ **真花掉一次 LLM 调用**。

  实测（spy 包 `LLM.call`）：

  | 路径 | 修前 | 修后 |
  |---|---|---|
  | 规则命中（单一短问句） | **1 次** | **0 次** |
  | 规则命中 + 决策语汇 | 1 次 | 0 次 |
  | 规则拿不准 | 1 次 | 1 次（该花的） |

  ⇒ 「规则优先省一次调用」的设计意图**被自己的补丁吃掉**，
    净效果 = 与不做规则优化时一样贵。

### 13.3 为什么这是「有接线 ≠ 这跑走得到」的第三种形态

  前面记过两类：
  - **结构性不可达**（调用点被守卫挡死）；
  - **有值但零信息量**（读数恒定）。

  这次是第三类：**接线全在、行为也对，只是「成本账目」与「代码注释」不一致**。
  没有人把「规则命中 ⇒ 0 次调用」写成判据跑过 —— 所以注释里那句
  「不花这次调用」长期只是**一句愿望**。

  ⇒ 通则：**凡「为了省钱」写的分支，必须配一条「省钱真的发生了」的成本判据**
    （构造性证明：spy 计数 == 0）。否则省钱的注释会随着后续补丁**静默失效**。

### 13.4 修法

  新增模块级纯函数 `orientation_rule(question)`：

  ```python
  def orientation_rule(question: str) -> dict:
      \"\"\"[第六期 · 降本] 规则优先的**取向**判断（零成本纯函数，不调 LLM）。\"\"\"
      _q = str(question or "")
      if _has_decision_context(_q):
          return {"orientation": "decision", "reason": "规则：题面含决策语汇", ...}
      return {"orientation": "boundary", "reason": "规则：题面无决策语汇", ...}
  ```

  · **与 `_has_decision_context` 同源** —— 同一个 `_DECISION_CUES`。
    ★ 为什么必须同源：否则会出现「打桩判 decision、落地渲染判 boundary」
      的**双真相**（本项目栽过 N 次）。
  · 规则命中时用它；**只有规则拿不准（空题面）才回落 `plan_orientation`**。
  · 空题面 ⇒ 保守回 `boundary` —— 与 `_has_decision_context` 的既有约定
    同源：「题面取不到时宁可走边界模板，也不在不知道题面时套决策模板」。

### 13.5 判据与变异体

  · 新判据 **㉝**：取向规则方向两向（决策语汇 ⇒ decision / 无 ⇒ boundary）+
    空题面保守 + **构造性成本证明**（规则命中 ⇒ `LLM.call` **0 次**）。
  · 新变异体 **M52**（取向规则方向反）/ **M53**（规则命中又偷调 LLM）⇒ 均判红。

### 13.6 ★ 两条顺带记下的通则

  1. **`and/or` 三元陷阱（本轮真栽）**：
     ```python
     _exp = _rule_hit and 0 or 1      # ✗ True and 0 = 0（假值）⇒ 0 or 1 = 1
     _exp = 0 if _rule_hit else 1     # ✓
     ```
     `x and A or B` 在 **A 是假值（0 / "" / []）** 时与 `A if x else B` **不等**。
     这次的表现是：规则命中（期望 0 次调用）却算成期望 1 次 ⇒ **判据恒红**，
     而代码本身完全正确 —— 排查绕了很久。

  2. **「判据随实现更新」的两种走向要分清**：
     · **放宽**（错）：把 `== 3` 改成 `>= 3` —— 判据从此没有牙；
     · **登记**（对）：把 `== 3` 改成 `== 4`，数量仍是**硬等式** ——
       新增调用点这件事**有人显式确认过**。
     本轮 ㉛（3 → 4）用的是后者。
"""

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), P)
raw = io.open(p, "rb").read()
assert raw.count(b"\r\n") == 0, "报告应为 LF-only"
s = raw.decode("utf-8")
if "## 十三、★ 降本真缺陷" in s:
    print("已存在第十三节"); sys.exit(0)
s = s.rstrip("\n") + "\n" + ADD
io.open(p, "wb").write(s.encode("utf-8"))
print("OK 第十三节已追加，行数 %d" % s.count("\n"))
