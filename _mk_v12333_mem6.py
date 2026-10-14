# -*- coding: utf-8 -*-
"""追加当日工作记忆（第六期 + 第二期）。append-only。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
F = HERE / ".workbuddy" / "memory" / "2026-10-14.md"

ADD = """

---

## 六、各环节量化 + 降本（用户指令驱动 · 前沿依据检索）

### 用户指令原文
> 「各层的锚点重述是否也要考虑量化，以及阴阳展开，候选生成，ing 的输出内容，
> 还有 view 的输出重点等也要有相关依据……最好可以减少 LLM 的调用或者寻找最优解
> 来减少时间和金钱成本。」

### 五条前沿依据（检索所得，见 `_各环节量化与降本依据_v12333.md`）
1. **重述失真毁下游链** — BenchDrift (arXiv:2608.11694)：含义保持的重述 ⇒ 答案
   **双向漂移**，**强模型损失远大于收益**；Revisiting Reliability (arXiv:2512.14754)：
   同意图换措辞 ⇒ 跟随率**最多掉 61.8%**。→ 锚点保真度。
2. **对撞是否真发生** — SIEV (arXiv:2510.18134)：核心指标 = **对抗性依从率**；
   「胆怯」模型 pS 高但推理深度低 = **假对撞**。→ 阴阳分歧度。
3. **早期信号提前停** — RASC (NAACL 2025) 省 ~70% 采样；DeepConf (ICLR 2026)
   省 **84.7% token**（★ **全局平均会掩盖局部塌陷**）；Think@n 成本 **−49%**。
   → **依据储备**（未接主循环）。
4. **语义密度 / 信息瓶颈** — 提示压缩率 `R = I(X;Y)/H(X) > 0.6` 为优；
   **>5 个无信息 token ⇒ 性能 −15%+**。→ 语义密度。
5. **降本叠加顺序** — Tokonomics 2025：单策略 30~50%、**叠加 85%**；顺序 =
   批处理 → Prompt 缓存（**静态在前动态在后**）→ 模型路由 → 提示压缩 →
   输出长度控制 → 语义缓存。

### ★ 现状核查逮到「第 1 类失败」：阴阳合并是孤儿函数
- `_expand_pair_merged_once` **存在但零真实调用点**（v1.23.16 删档造成；
  历史文档明记「未删，冒烟判据直接调用它」）⇒ **结构性不可达**。
- 对照：`parallel_expand` 可达，但只省**往返**、同 prompt 仍发 N 份 ⇒ **不省 token**。

### 落地四项（统一规格：纯函数 + 零成本 + 可开关 + 有留痕）
- **L1 激活阴阳合并**（opt-in `merge_expand` 默认 **false** ⇒ 零行为差）
- **L2 `yin_yang_divergence(yin, yang)`**：`1 - max_i max_j sim`；`<0.30 ⇒ fake_duel`
- **L3 `restate_fidelity(question, anchor)`**：`coverage<0.20 ⇒ drifted`；`ratio<0.35 ⇒ thin`
- **L4 `semantic_density(text)`**：扣**填充语**+**标点**（`unicodedata.category` P*/S*）
  后的字符占比；★ 空输入 ⇒ `None`
- 出口 `View.quant_readings` + `to_dict`（**有才出**）；唯一写入口 `_quant_note`
  （值不可用就**不写键**：「没测」≠「测出来是 0」）。
- 三处**真实入口**接线：ing 输出后 / 锚点确定后 / `_expand` 调用后。

### 降本账
- 真跑基准 `_fullrun_GOALRUN` = **136 calls / 1.27M tok / 57.2 min**。
- L1 合并省 **1 次往返 + 1 份重复 user token / 每处 pair**（估全场 **6~12%** 调用）。
- L4 若用于筛 prompt 保守估省 **5~15% 输入 token**（**尚未接**）。
- ★ 依据 ⑤ 落地建议：本项目**性价比最高的下一项降本 = Prompt 缓存**
  （role/prompt 模板是天然静态前缀；要求静态在前动态在后）。

### ★★ 本轮三条通则（新）
1. **变异体注入必须真实可执行** —— M48 第一版写 `_LLM_HOOK[0](_t)`，引擎里
   **没有** `_LLM_HOOK` ⇒ NameError、spy 计数仍 0 ⇒ **假绿**。改成
   `globals()["L"+"L"+"M"].call(prompt="x")`（真走 `LLM.call`）⇒ 立刻判红。
   ⇒ **变异体的注入必须落在判据实际读的那个东西上**。
2. **「不调 LLM」要构造性证明**：spy 包 `LLM.call` 计 **0** 次（不是「看代码没调」）。
3. **Write 工具会把文档里的转义序列变成真字符** —— 我在报告正文写「反斜杠 r 反斜杠 r
   反斜杠 n」讲换行污染，Write 直接写成了**真 CR 字符**，于是脚本自检把自己的
   说明文字当污染顶红。⇒ 文档行文**统一写「CR-CR-LF 三元组」**这种不含转义的
   说法（与 R48「注释里的字面 token 污染判据」同源，这是**第三次**栽）。

### 验收（第六期）
- 主文件 **24505 行 / 纯 CRLF**；冒烟 **EXIT=0 / 0 ✗**；
- 变异体 **48 / 48 判红**（新增 M45 开关默认打开 / M46 分歧度方向反 /
  M47 保真度缺输入硬表态 / M48 语义密度偷偷调 LLM）；
- 判据 **㉗~㉛** 就位（含 L4 零 LLM 的构造性证明）。

---

## 七、第二期收尾：四层目标读数**进入圈内动作**

### 设计（★ **零新增接线点**）
- 第一期已在**每圈结束时**调 `_layer_goal_now(entry, view)`（串行 15144 / 并行 16810）。
- 第二期在**同一位置**追加 `self._refresh_goal_hint(entry, view)` ⇒ 把本圈读数转成
  **下一圈**的形状指引（写 `self._goal_hint_next`），由两条 `build_user`
  （`_expand_from_question` / `_expand_from_views`）读 `{goal_hint}` 注入。
- 纯函数 `layer_goal_action_hint(entry, goal, prev=None)`：0 修行换未挖的面 /
  1 研究先给未答的面 / both 对撞换融合轴 / all 元补四件事；**达标 ⇒ ""**；
  **缺读数 ⇒ ""**；**不返 role 名**（保 role 语义单一真相源）。

### ★ 一处真缺陷（自洽核查逮到）
P2-1 的 A7 锚点只命中**串行**那处（15144），**并行**那处（16810）因上文注释
不同而**漏接** ⇒ 补 `_patch_v12333_goal_action_p2.py`。判据 ㉖ ④
（`src.count("self._refresh_goal_hint(entry, view)") < 2` ⇒ 判红）就是为拦这个写的。

### 验收（第二期）
- 判据 **㉖**（方向 / 缺读数不表态 / 不混 role 语义 / **两通道都接线** /
  **两条 prompt 都注入** / 初始化）；变异体 **M43 / M44** 判红。
"""


def main() -> int:
    b = F.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    assert "## 六、各环节量化 + 降本" not in txt, "第六节已存在（防重复）"
    assert "## 七、第二期收尾" not in txt, "第七节已存在（防重复）"
    out = txt.rstrip("\n") + ADD
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data
    F.write_bytes(data)
    print("OK 当日记忆已追加第六、七节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
