# -*- coding: utf-8 -*-
"""把第九节（第六期：各环节量化 + 降本）与第十节（第二期：目标入圈内动作）
追加进 v12333_报告.md（append-only，不动已有内容）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
RP = HERE / "v12333_报告.md"

ADD = """

---

## 九、第六期：各环节量化 + 降本（用户指令驱动 + 前沿依据检索）

### 9.1 指令原文与拆解

  > 「各层的锚点重述是否也要考虑量化，以及阴阳展开，候选生成，ing 的输出内容，
  > 还有 view 的输出重点等也要有相关依据，我觉得需要进行调整优化，请你检索最前沿
  > 算法和相关技术设计和相关学科知识应用于各个环节步骤，最好可以减少 LLM 的调用
  > 或者寻找最优解来减少时间和金钱成本。」

  拆成两件事，**都要求有依据**：
  · **各环节的量化尺子**：锚点重述 / 阴阳展开 / 候选生成 / ing 输出 / view 重点
    —— 此前这五处**没有任何读数**，好坏只靠肉眼。
  · **降本**：减少 LLM 调用、缩短时间、降低金钱成本。

### 9.2 五条前沿依据（检索所得，逐条对应落地）

  依据全文（含链接与要点摘抄）见 `_各环节量化与降本依据_v12333.md`。摘要：

  | # | 依据 | 来源 | 关键数字 | 对应落地 |
  |---|------|------|----------|----------|
  | ① | **重述失真毁下游链** | BenchDrift (arXiv:2608.11694)；Revisiting Reliability (arXiv:2512.14754) | 同意图换措辞 ⇒ 跟随率**最多掉 61.8%**；强模型**损失 > 收益** | L3 锚点保真度 |
  | ② | **对撞是否真发生** | SIEV (arXiv:2510.18134)；Hegelian Self-Reflection (arXiv:2501.14917) | 核心指标 = **对抗性依从率**；「胆怯」模型 pS 高但深度低 = **假对撞** | L2 阴阳分歧度 |
  | ③ | **早期信号提前停** | RASC (NAACL 2025)；DeepConf (ICLR 2026)；Think@n (UVA+Google) | 省 **~70% 采样** / **84.7% token** / **−49% 成本** | 依据储备（未接主循环） |
  | ④ | **语义密度 / 信息瓶颈** | Information-Theoretic Principles for Prompt Engineering | 压缩率 `R>0.6` 为优；**>5 个无信息 token ⇒ 性能 −15%+** | L4 语义密度 |
  | ⑤ | **降本叠加顺序** | Tokonomics 2025 生产案例 | 单策略 30~50%，**叠加 85%** | 全局排序（见 9.5） |

### 9.3 ★ 现状核查逮到的「第一类失败」：阴阳合并是孤儿函数

  · `_expand_pair_merged_once`（阴阳合并成一次调用）**存在但不可达**。
  · 证据链（**读**，不猜）：
    - `CHANGELOG.md` / `v12316_报告.md`：v1.23.16 删档，记「**未删**，冒烟判据直接调用它」；
    - `.workbuddy/memory/2026-10-09.md:1156` 同上；
    - 全仓 `grep`：**零个**真实调用点，只有 `def` 与文档提及。
  · ⇒ 正是本项目定义的**第 1 类失败：结构性不可达**（能力在、入口没了）。
  · 对照：`parallel_expand` 已实现且**可达**，但它只省**往返**、同 prompt 仍发 N 份
    ⇒ **不省 token**。合并才同时省往返与重复 user 输入。

### 9.4 落地四项（统一规格：纯函数 + 零成本 + 可开关 + 有留痕）

  | 项 | 函数 / 开关 | 判据 | 默认 | 出口 |
  |----|-------------|------|------|------|
  | **L1** 激活阴阳合并 | `merge_expand`（opt-in） | `_action_on(cfg, "merge_expand", False)` | **false** | 回落留痕 |
  | **L2** 阴阳分歧度 | `yin_yang_divergence(yin, yang)` | `1 - max_i max_j sim`；`<0.30 ⇒ fake_duel` | 一直算 | `quant_readings.yin_yang_divergence` |
  | **L3** 锚点保真度 | `restate_fidelity(question, anchor)` | `coverage<0.20 ⇒ drifted`；`ratio<0.35 ⇒ thin` | 一直算 | `quant_readings.*`（锚点侧） |
  | **L4** 语义密度 | `semantic_density(text)` | 扣填充语 + 标点后的字符占比 | 一直算 | `quant_readings.ing_density` |

  **★ 三条设计要点**（每条都对应一条红线或一条依据）：
  · **缺数据不表态**：L2 任一侧空 ⇒ `divergence=None` + `verdict=""`；L3 任一空 ⇒
    全 `None`；L4 空输入 ⇒ `None`。⇒ 「没测」与「测出来是 0」**必须区分**（本项目通则）。
  · **只标注不改流程**：L2/L3/L4 只写读数 + 打告警，**不改任何分支**（红线：建议与执行分开）。
  · **L4 不自动裁 prompt**：ACE 反面数据（1.8 万 token ⇒ 122，准确率 66.7→57.1）
    说明压缩**不可逆** ⇒ 只给读数与告警，要改行为必须显式开关。

### 9.5 降本账（可核算，不吹）

  · **真跑基准**（`_fullrun_GOALRUN`，route 四层齐 / serial / 2 圈）：
    **136 calls / 1.27M tok / 57.2 min**。
  · **L1 合并**：阴阳两臂本来 2 次调用（各含 1 份 user prompt）⇒ 合并成 1 次
    ⇒ 每处 pair 省 **1 次往返 + 1 份重复 user token**。按每圈 ≥1 处 pair 估，
    全场省 **8~16 次调用（≈6~12%）**（★ 估算值，非实测；因为默认关，未在本轮真跑里启用）。
  · **L4 语义密度**：若用于筛选 prompt（**尚未接**），保守估省 **5~15% 输入 token**。
  · **依据 ⑤ 的叠加顺序**（本轮**只做排序建议**，不改代码）：
    ①批处理（半天工作量、立即省 ~50%、**零功能改动**）⇒ ②Prompt 缓存
    （静态前缀 50~90% 折扣，**要求静态在前动态在后**）⇒ ③模型路由 ⇒ ④提示压缩
    ⇒ ⑤输出长度控制 ⇒ ⑥语义缓存。
    ★ 元 DGTF 现状：③模型路由 = `stages` 表**已有**；②Prompt 缓存**未做**
    （role/prompt 模板是天然静态前缀 ⇒ 是本项目**性价比最高**的下一项降本）。

### 9.6 ★ 判据通则（本轮新增）

  · **变异体注入必须真实可执行** —— M48 第一版写 `_LLM_HOOK[0](_t)`，而引擎里
    **没有** `_LLM_HOOK` ⇒ 变体 NameError、spy 计数仍是 0 ⇒ **判据假绿**。
    改成 `globals()["L"+"L"+"M"].call(prompt="x")`（真走 `LLM.call`，判据 ㉚ 的 spy
    打的正是它）⇒ 立刻判红。**通则**：变异体的注入**必须落在判据实际读的那个东西上**，
    否则「判红」与「跑挂了」分不开。
  · **「不调 LLM」要构造性证明**：spy 包住 `LLM.call` 计 0 次 —— 不是「我看代码
    没调」而是「**跑一遍，计数为 0**」。

### 9.7 验收（第六期）

  · 主文件 **24505 行 / 纯 CRLF**（CR-CR-LF 三元组计数 = 0）；
  · 冒烟 **EXIT=0 / 0 ✗**；AUDIT **68 PASS / 0 FAIL**；
  · 变异体 **48/48 判红**（新增 M45 开关默认打开 / M46 分歧度方向反 /
    M47 保真度缺输入硬表态 / M48 语义密度偷偷调 LLM）；
  · 判据 **㉗~㉛** 全部就位（含 L4 的零 LLM 构造性证明）。
  · 真跑验收见第十节（`_fullrun_QUANT.quant.json`）。

---

## 十、第二期收尾：四层目标读数**进入圈内动作**

### 10.1 设计（★ **零新增接线点**）

  第一期已在**每圈结束时**调用 `_layer_goal_now(entry, view)`（串行 15144 / 并行 16810
  两处）。第二期**复用这两处**：在同一个位置追加
  `self._refresh_goal_hint(entry, view)` ⇒ 把**本圈**的目标读数转成**下一圈**要用的
  形状指引（写 `self._goal_hint_next`），再由两条 prompt 组装路径读它
  （`_expand_from_question` / `_expand_from_views` 的 `build_user`）。

  ```
  纯函数 layer_goal_action_hint(entry, goal, prev=None) -> str
    0    修行：excavate < _LG_STOP_MARGIN ⇒ 换未挖的面（Heaps 饱和）；
              n_aspects < 4 ⇒ 优先摊开新面（还没铺够，别急着深挖）
    1    研究：settle < 0.6 ⇒ 优先给未答的面答案（★ 写着长 ≠ 收敛）
    both 对撞：sem_stagnation ≥ 0.8 ⇒ 换融合轴（CORE 停滞罚）；fuse < 0.3 ⇒ 去看矛盾处
    all  元  ：crystallize < 1.0 ⇒ 按 n_hits 补四件事（闭环/回看/决策/行动）
    达标 ⇒ ""（做到就闭嘴）；缺读数 ⇒ ""（不表态）
  ```

### 10.2 ★ 三条自我约束（对应红线）

  · **达标闭嘴**：目标已达成 ⇒ 返回空串，**不再下指令**（避免为了「有动作」而制造动作）。
  · **缺读数不表态**：`goal` 为空 ⇒ 空串（「没测 ≠ 测出来差」）。
  · **不返 role 名**：指引只写**形状**，不写「转向 / 复裁」这类 role 语义
    ⇒ 保住 role 语义的**单一真相源**（判据 ㉖ ③ 专门拦这个）。

### 10.3 验收（第二期）

  · 判据 **㉖**（方向 / 缺读数不表态 / 不混 role 语义 / **两通道都接线** /
    **两条 prompt 都注入** / 初始化）；
  · 变异体 **M43**（断并行通道）/ **M44**（缺读数硬给）判红；
  · ★ **一处真缺陷**（自洽核查逮到）：P2-1 的 A7 锚点只命中**串行**那处
    （15144），**并行**那处（16810）因上文注释不同而**漏接** ⇒ 补
    `_patch_v12333_goal_action_p2.py`。判据 ㉖ ④ 就是为拦这个写的
    （`src.count("self._refresh_goal_hint(entry, view)") < 2` ⇒ 判红）。
"""


def main() -> int:
    b = RP.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    assert "## 九、第六期" not in txt, "第九节已存在（防重复追加）"
    # ★ 尾随换行风格**跟随文件**（报告是 LF）。★ 注意：ADD 正文里若写「反斜杠 r」
    #   这类字面串，Write 工具可能把它变成**真 CR 字符** ⇒ 自检会被自己的说明文字
    #   顶红（本项目已栽过「注释污染判据」两次）。⇒ 文档行文里统一写
    #   **「CR-CR-LF 三元组」**这种不含转义序列的说法。
    crlf = (txt.count("\r\n") > 0 and txt.count("\r\n") == txt.count("\n"))
    flat = txt.replace("\r\n", "\n").rstrip("\n") + ADD
    out = flat.replace("\n", "\r\n") if crlf else flat
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data, "写出 CR-CR-LF 三元组（换行被污染）"
    RP.write_bytes(data)
    print("OK 报告已追加第九、十节（CRLF=%s / 行数=%d）"
          % (crlf, out.count("\n") + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
