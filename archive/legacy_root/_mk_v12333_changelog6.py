# -*- coding: utf-8 -*-
"""把第六期（各环节量化 + 降本）与第二期（目标入圈内动作）两段写进 CHANGELOG.md。

★ 用 Write 建脚本 + 执行（**不走 shell heredoc**：反引号会被当命令替换，
  \\n 会被吃成字面 /n —— 本项目已踩过两次）。
★ 锚点 = `★ v1.23.33 收束摘要` 那行（整行唯一），新段插在它**之前**。
"""
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"

ANCHOR = "★ v1.23.33 收束摘要"

NEW = """【第六期 · 各环节量化 + 降本（用户授权检索前沿依据后落地）】

  用户指令：「各层的锚点重述是否也要考虑量化，以及阴阳展开，候选生成，ing 的输出
  内容，还有 view 的输出重点等也要有相关依据……最好可以减少 LLM 的调用或者寻找
  最优解来减少时间和金钱成本。」⇒ 先检索，再落地，**每条落地都挂一条前沿依据**。
  依据全文见 `_各环节量化与降本依据_v12333.md`（五条硬依据 + 现状核查表 + 降本账）。

【五条前沿依据（逐条对应一处落地）】
  ① **重述失真毁下游链** → 锚点重述
     BenchDrift: The Wording Effect（Thakur et al., arXiv:2608.11694）：含义保持的
     重述使答案**双向漂移**，**强模型损失远大于收益** —— 脆弱性源于**重述本身**；
     Revisiting the Reliability of LM in Instruction-Following（arXiv:2512.14754）：
     同意图换措辞 ⇒ 指令跟随**最多掉 61.8%**。
  ② **对撞是否真发生** → 阴阳展开
     SIEV: A Dialectical View of LLM Reasoning（arXiv:2510.18134）：核心指标
     **对抗性依从率**（反题与正题实际不一致的比例）；「过于胆怯」的模型 pS 高但
     推理深度低 = **假对撞**。Hegelian Self-Reflection（arXiv:2501.14917）：辩证需
     明确缺陷类别（未定义构成要素 / 内容不完整 / 不兼容性 / 自我决定不完整）。
  ③ **早期信号提前停掉低价值样本** → 减少 LLM 调用
     RASC（Wan et al., NAACL 2025）：criteria-based early stopping ⇒ **省 ~70% 采样**；
     DeepConf（ICLR 2026）：局部置信窗口（最差片段）作早停触发 ⇒ 省 **84.7% token**
     且准确率还升 —— ★ **全局平均会掩盖局部塌陷**；Think@n（UVA + Google）：只解
     短前缀算 DTR ⇒ 只继续 Top-K ⇒ 成本 **−49%**。
  ④ **语义密度 / 信息瓶颈** → ing 输出与 view 重点
     Information-Theoretic Principles for Prompt Engineering：**提示压缩率**
     `R = I(X;Y)/H(X)`，优秀提示 `R > 0.6`；**语义密度**：**超过 5 个无信息 token
     ⇒ 性能降 15%+**。
  ⑤ **降本策略叠加顺序** → 全局最优
     Tokonomics 2025 生产案例：单策略 30~50%，**叠加达 85%**；顺序 =
     批处理 → Prompt 缓存（**静态在前动态在后**）→ 模型路由 → 提示压缩 →
     输出长度控制 → 语义缓存。

【★ 现状核查逮到的第一类失败（能力存在但不可达）】
  · **`_expand_pair_merged_once`（阴阳合并成一次调用）是孤儿函数** —— v1.23.16
    删档造成；历史文档（`.workbuddy/memory/2026-10-09.md`、`CHANGELOG.md`、
    `v12316_报告.md`）明确写「**未删**，冒烟判据直接调用它」 ⇒ 删档没删它、
    但**唯一的调用点没了**。⇒ 本项目第 1 类失败（结构性不可达）。
  · 并行展开（`parallel_expand`）早已实现，但它只省**往返**、不省 **token**
    （同 prompt 仍发 N 份）⇒ 合并才有 token 收益。

【落地四项（全部：纯函数 + 零成本 + 可开关 + 有留痕）】
  L1 **激活阴阳合并**（opt-in `merge_expand`，默认 **false** ⇒ 零行为差）：
     `_expand_pair` 内 `len(jobs)==2 and _action_on(..., "merge_expand", False)` ⇒
     走 `_expand_pair_merged_once`；不可用则**回落两臂独立调用**并打印留痕。
     ⇒ 省 1 次往返 + 1 份重复 user 输入 token。
  L2 **阴阳分歧度** `yin_yang_divergence(yin, yang) -> dict`（依据 ②）：
     `divergence = 1 - max_i max_j sim(yin_i, yang_j)`（`_overlap_coef` + `_similar`
     两把尺子取大）；`verdict = "fake_duel" if divergence < 0.30 else "ok"`；
     ★ 任一侧空 ⇒ `divergence=None` + `verdict=""`（不表态）。
  L3 **锚点保真度** `restate_fidelity(question, anchor) -> dict`（依据 ①）：
     `coverage`（问句关键词被锚点覆盖比例）/ `ratio`（长度比）/
     `verdict ∈ {ok, thin(ratio<0.35), drifted(coverage<0.20)}`；
     ★ 任一空 ⇒ 全 `None` + `""`。
  L4 **语义密度** `semantic_density(text) -> float|None`（依据 ④）：
     分子 = 扣掉**填充语**（`的/了/是/在/和/与/或/及…综上所述…`）与**标点**
     （`unicodedata.category` 的首字母 ∈ P/S）后的字符数；分母 = 全字符数。
     ★ 空输入 ⇒ `None`；**纯字符统计，零 LLM 调用**。

【接线（三处**真实入口**，不只纯函数）】
  · ing 输出后：`semantic_density(view.collision)` ⇒ `_quant_note(view, "ing_density", …)`，
    <0.6 打告警（依据 ④ 的 0.6 压缩率边界）。
  · 锚点确定后：`restate_fidelity(_q0, str(view.anchor))`，`drifted` 打告警。
  · `_expand` 调用点后：`_quant_note(view, "yin_yang_divergence", _yy)`，
    `fake_duel` 打告警。
  · `View.quant_readings: Dict[str, dict]` 新字段 + `to_dict` 出口
    （`d["quant_readings"]`，**有才出**）；唯一写入口 `_quant_note(view, key, val)`
    （值不可用就**不写键** —— 「没测」与「测出来是 0」必须区分开）。

【★ 本轮三条判据通则（都被实测踩到）】
  · **判据的负对照夹具必须抄真产物原文**（同第五期通则，本轮再次生效）。
  · **关键词优先级表的键会互相吞**（短键 ∈ 长键 ⇒ 先扫到的赢）。
  · **剥括号的函数要能自证**（喂「关键词在括号里」的合成串判落档当负对照）。
  · **变异体注入必须真实可执行** —— M48 第一版写 `_LLM_HOOK[0](_t)`，而引擎里
    **没有** `_LLM_HOOK` ⇒ 变体会 NameError、spy 计数仍是 0 ⇒ **假绿**。
    改成 `globals()["L"+"L"+"M"].call(prompt="x")`（真的走 `LLM.call`，
    判据 ㉚ 的 spy 打的就是它）⇒ 立刻判红。

【验收（第六期）】判据 **㉗~㉛**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +
  缺一侧不表态 / ㉙ 保真度方向 + 缺输入不表态 / ㉚ 语义密度方向 + 空输入不表态 +
  **「不调 LLM」的构造性证明**（spy `LLM.call` 计数须为 **0**）/ ㉛ 三处真实入口 + 出口；
  变异体 **M45**（合并开关默认打开）/ **M46**（分歧度方向反）/
  **M47**（保真度缺输入硬表态）/ **M48**（语义密度偷偷调 LLM）**均判红**（累计 **48**）。

"""


def main() -> int:
    b = CL.read_bytes()
    txt = b.decode("utf-8")
    # ★ CHANGELOG 是 Markdown 文档（**不守**主文件的纯 CRLF 铁律）⇒ 这里
    #   只做「不引入 \r\r\n」的自检，同时**保持文件原有的换行风格不变**。
    crlf = txt.count("\r\n")
    lf = txt.count("\n") - crlf
    assert b"\r\r\n" not in b, "CHANGELOG 里已有 \\r\\r\\n（换行被污染）"
    print("[newline] CRLF=%d / LF-only=%d ⇒ 按 LF 处理" % (crlf, lf))
    flat = txt.replace("\r\n", "\n")
    n = txt.count(ANCHOR)
    assert n == 1, "锚点命中 %d 次（应 1）" % n
    assert NEW not in flat, "新段已存在（防重复插入）"
    out = flat.replace(ANCHOR, NEW + ANCHOR, 1)
    assert out.count(ANCHOR) == 1
    assert out.count(NEW) == 1
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data, "写出 \\r\\r\\n（换行被污染）"
    CL.write_bytes(data)
    back = CL.read_bytes().decode("utf-8")
    assert NEW in back and back.count(ANCHOR) == 1
    print("OK CHANGELOG 已插入第六期段（%d 行）" % len(NEW.splitlines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
