# -*- coding: utf-8 -*-
"""追加今日记忆第十一节：降本真缺陷（规则命中省调用被抵消）+ and/or 陷阱。"""
import io, os, sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".workbuddy", "memory", "2026-10-14.md")
ADD = u"""
---

## 十一、★ 降本真缺陷：规则命中「省调用」被自己的补丁抵消

### 现象 / 根因
- `auto_plan(llm=...)` 的 **B1 规则命中**分支注释写「不花这次模式调用」，
  但为补 `orientation` 又调 `plan_orientation(q, cfg)` ——
  它**签名只有 `config`**、内部自己 `new LLM(cfg)`（没有 `llm=` 可注入）
  ⇒ **真花 1 次调用**。实测 spy：规则命中 `LLM.call` = **1**（应 0）。
- ⇒ 「规则优先省一次调用」被自己吃掉，净效果 ≈ 没做优化。
  用户点名诉求「减少 LLM 调用」的直接违背。

### 修（`_patch_v12333_orientrule.py`）
- 新增模块级纯函数 `orientation_rule(question)`（零成本）：
  **与 `_has_decision_context` 同源**（同一个 `_DECISION_CUES`）
  ⇒ 避免「打桩判 decision、渲染判 boundary」的双真相。
  命中决策语汇 ⇒ decision；否则 ⇒ boundary；空题面保守回 boundary。
- 规则命中时用它；**只有规则拿不准才回落 LLM 版**。
- 验收：规则命中 ⇒ `LLM.call` **0 次**（构造性证明）。
- 新判据 **㉝** + 变异体 **M52**（方向反）/ **M53**（又偷调 LLM）⇒ 均判红。

### ★★ 新形态：「有接线 ≠ 这跑走得到」的第三类
前两类是「结构性不可达」与「有值但零信息量」。这次是
**接线全在、行为也对，只是「成本账目」与「代码注释」不一致**。
⇒ 通则：**凡「为了省钱」写的分支，必须配一条「省钱真的发生了」的成本判据**
（构造性证明：spy 计数 == 0）。否则省钱的注释会随后续补丁**静默失效**。

### ★ `and/or` 三元陷阱（本轮真栽，排查绕了很久）
```python
_exp = _rule_hit and 0 or 1      # ✗ True and 0 = 0（假值）⇒ 0 or 1 = 1
_exp = 0 if _rule_hit else 1     # ✓
```
`x and A or B` 在 **A 是假值（0 / "" / []）** 时与 `A if x else B` **不等**。
症状：代码完全正确，判据**恒红**（期望 0 次调用被算成期望 1 次）。

### ★ 判据随实现更新的两种走向（要分清）
- **放宽**（错）：`== 3` → `>= 3` —— 判据从此没牙；
- **登记**（对）：`== 3` → `== 4`，数量仍是**硬等式**（新增调用点有人显式确认过）。
本轮 ㉛（3 → 4）用后者。

### ★ 同期修掉的三条历史欠账（`_v122_verify.py`）
- **6.6 AST 登记对账**：基线 v1.21.77 → 本版累计新增 **285** 符号，
  其中 **112 项从未登记**（本版自己 57 项 + 历史 55 项）⇒ 逐条补 reason，
  登记表 172 → **285**（= 新增总数，两向对齐）。
  ★ 教训练习：**别逐轮手抄**，`all_on` 的展开面要从权威来源
  `_ALL_ON_ITEMS` **导**（否则「修一次又冒出一批新的」）。
- **P5.2.c / P5.2.b**：判据假设「打桩必调 1 次」—— 但 B1 规则优先
  （v1.23.13）就是**有意不调** ⇒ 判据过时，改为「规则命中 ⇒ 0 次调用」。
- **V3 / V4 配置对账**：补登 `all_on` 展开面 11 键（`_V12329_33_AUTH_KEYS`）；
  V4 的 `all_on` 判断取错层（`_nt` 是 `api.thinking` 段，应按 `_new["all_on"]`）。

### 最终验收（v1.23.33）
- 主文件 **24611 行 / 纯 CRLF**（裸 LF 0 / CR-CR-LF 0）；
- 冒烟 **223 ✓ / 0 ✗**；AUDIT **68 PASS / 0 FAIL**；
- `--phase all` **PASS 319 / FAIL 0**；变异体 **53 / 53 判红**；
- 配置 **193 键 / 两向对账 0 差**；AST 登记 **285 / 285**。
"""


def main():
    if "## 十一、★ 降本真缺陷" in io.open(P, encoding="utf-8").read():
        print("已存在第十一节"); return
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "记忆应为 LF-only"
    s = raw.decode("utf-8").rstrip("\n") + "\n" + ADD
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK 第十一节已追加，行数 %d" % s.count("\n"))


main()
