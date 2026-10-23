# -*- coding: utf-8 -*-
"""Step12b：CHANGELOG.md 加 v1.23.27 段（最新在最前）。

★ 收束摘要（`★ v1.23.27 收束摘要`）在定稿时补 —— 这里先写主体，
  摘要里的验收数字等真跑结束后回填（本脚本可重入：已存在则不重复插）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "CHANGELOG.md"

SEC = """v1.23.27 相对 v1.23.26

【要解决的问题】`_设计_五机制算法重构_v12326.md` §3.5/§3.4/§4.2 把
「接口层（E1/E2/E5/A1）」与「信念层（D1/D2/D3）」拆成两版。动手前核对
依赖发现**顺序倒置**：E1（引擎算 G）需要 `H_sem`（原 v1.23.28 的 D3）
与 `BeliefItem.status`（原 v1.23.28 的 D1）；E3 需要 AspectUnit.id（A1）
+ BeliefItem.id（D1）。**先把底座 A1 + D1/D2/D3 做出来，E 系列才拿得到
真实输入** ⇒ 本版把两版合并。共九项：

  ① A1 `AspectUnit` 结构化 + 双写。
     新增 `make_aspect_unit()`（**单一构造点**）+ `View.aspect_units` +
     `View.add_aspect_unit()`。★ `text == desc` 是保命设计 —— 旧读取点
     一个字都不用改。★ **幂等**是硬要求：编号 `A{n}` 由追加顺序决定，
     调用点在循环里，重复登记会污染 covers 的靶子集合。非法 ground
     归一化到 "anchor"（不抛错）。
  ② A2 覆盖对账**符号化**。
     `Pool.aspect_targets_v12327()` 收敛 amp#N/th#N/probe#N/A{N} 四种编号；
     `_und_self_touch_symbols()` 给「后来被谁按 id 引用」建凭据。
     ★ 旧口径靠**子串 / `_overlap_coef`** 猜引用关系 —— 尺子本身是被测物；
     符号对账用 **id 相等**，两者分离。
  ③ A3 **双读数分离**。
     `View.touch_rate`（能力读数：碰没碰过）与 `View.aspect_carry_rate`
     （延续读数：后来还追不追）。★ **永不合成一个分** —— 合起来会把
     「碰过一次但没延续」与「从没碰过」混成一类。
  ④ D1 `BeliefItem` 四态机。
     `_BELIEF_STATUS = SUSPENSION_STATUS`（**别名不是新枚举**）；
     `semantic_entropy` 默认 **`None` 不是 `0.0`**（0.0 会被读成「很稳定」，
     那是自欺）。`add_undecidable` 内与 `structural_amps` **双写**。
  ⑤ D2 迁移规则（纯函数）。
     优先级写死 **`resolved` > `revoked` > `stable` > 保持原状**：
     `active→stable` 需 k=2 圈 + ≥2 独立来源；`active→revoked` 需
     attack ≥ support；`stable→active` 因新 attack；任意→`resolved`
     由 decidable_channel。★ resolved 最高的理由（红线「停止与清算分开」）：
     一旦被可判定通道回答，「稳不稳 / 被不被质疑」都不再是这条主张的问题。
  ⑥ D3 语义熵 `H_sem`。
     `semantic_entropy_of()` 单链聚类到**簇代表**（保守：宁可高估发散，
     不高估稳定 —— 高估发散只是不判 stable，不改变任何主张的优劣）。
     ★ `n < 2` 返回 **`None`**：单样本谈「发散」无意义，而 0.0 会被读成
     「很稳定」（老坑「检测缺省要在补默认值之前判」）。
  ⑦ E1 EIG 可计算化。
     `G = (h_before - h_after) / h_before ∈ [0,1]`。★ 算不出来返回
     `(None, {"why":…})` **不是 `0.0`** —— 0.0 是「算出来零增益」，
     None 是「没有可谈的信息量」，两回事。
     ★★ 本项踩了**两个**让 G 恒为 0 的坑，都必须修：
        (a) **两臂要同一把尺子**：`_raw_entropy` 返回**原始**熵不归一化，
            分母恒为 `ln(n_before)`。各臂用自己的 `ln(n)` 会把「移除」的
            熵降**完全抵消**（ln3→ln2 的降幅被两个 ln 各自除掉）。
        (b) **命中一条要移除整簇**：未决 {B1,B2,B3}，B1~B2 同簇、B3 独立
            ⇒ h_before 用「2 簇」分歧度；若只移 B1，剩下 {B2,B3} **不再
            同簇** ⇒ 归一化后 `h_after > h_before` ⇒ G 被 `max(0.0,…)`
            夹成 0。语义上「命中一簇」= 这簇疑问被回答了，同簇是同一
            件事的另一种说法，**应一并消解**。
  ⑧ E2 子模批选。
     贪心 + 边际下限 `floor`（默认 0.0）。★ 「宁少勿滥」：`floor` 是
     「不许零增益补位」，**不是**「不许少」；G 的绝对值尺度依赖池大小，
     硬阈值会随池漂移。配置开关 `probe.submodular` 默认开；**算不出 G
     时自动退回**旧路径（所以打开它不会让「池子太小」的圈跑不动）。
     `expected_gain` 双写引擎 G + 模型自报，并标 `gain_source`。
  ⑨ E3 covers 双查 / E4 link 反查 / E5 双向判据 / E6 自适应停止。
     · E3：编号**对**只是必要条件，还要**语义对得上**（`_COVERS_SIM_MIN`
       = 0.30）。编号**不在集合里** ⇒ 新标志 `probe_covers_bad_ref`
       —— 这是「只查编号范围」永远抓不到的一类。
     · E4：`probe_link_dangling(N)` 查 link 是否引用池内实存 id。
       ★ **只留痕不拦**（红线「未对齐合法」）。
     · E5：空探针**双向**判 —— 有理由且与 untouched 对得上 ⇒
       `honest_empty`（不罚）；理由空洞/缺失 ⇒ `lazy_empty`（留痕不罚分）。
       ★ 旧行为与提示词「推不动就返回空数组」**方向正好相反**。
       ★ 接线缺口：E5 读的 `view.no_probe_reason` 原本**没人写** ⇒
         真跑里 `honest_empty` 永不触发。四处探针解析点补捕获。
     · E6：`e6_stop_verdict(seen, max_gain, min_gain, stop_floor)` 纯函数
       + `Pool.probe_stop_history`。`max_gain < stop_floor`（默认 0.02）
       ⇒ 停止信号（本轮只出不进，探针数 0 **合法**）。
       ★ `seen == 0` 是 `no_candidate` **不是停止** —— 「模型没给候选」≠
         「候选都推不动」，混为一谈会让「模型偷懒」读成「池已收敛」。
       ★ 与 `min_gain` 是**两把尺子**：一个管「值不值得做」，一个管
         「还能不能推得动」。边界取**严格小于**。

【改动的判据（判据随实现更新，不是放宽阈值）】
  · `check_v12326_sim3` 的 [D] covers 形态检查：原找 `if m:` / `else:`，
    E3 改成 `_cov_targets` 查表 + `_tgt is None`；改按**新结构**判（语义
    比较存在 + `bad_ref` 分支存在 + 语义比较在 id 命中**之后**）。
  · `check_probe_skip_no_false_flag`：原断言旧标志 `probe_return_empty`，
    E5 起它不再是终态；改成断言「**被注意到**」，并加正对照。
  · `check_v12320_quiet_output` / `check_v1238_render_guards` 的接线断言：
    原用 `except Exception` 把「取不到源码」与「源码里没这个串」**混成
    一个 bad 项** ⇒ 报出来像「死代码」。加共享 helper `_src_of(func)`
    （getsource 失败 ⇒ 退回读源文件 + ast 按 def 名切块），两类失败分开报。
    ★ 顺带查清：那条 order-dependent 假红**不是** `check_v1221_p2b` 造成
      （逐 check 实测前 74 个 / 只跑 p2b / p2b+后 8 个，getsource 都稳定）
      —— 「最后跑的是它」不等于「它弄坏的」（相关 ≠ 因果）。

【新增判据】
  `check_v12327_five_mechanisms()`（A1/A2/A3/D1/D2/D3/E1/E2/E6 九项，
  全部**驱动真实函数**判行为）；`_mut_v12327.py` 8 个变异体（M1~M8）。

【配置】
  `dgtf_config.yaml` 补 `sim.cluster=0.70` / `probe.submodular=true` /
  `probe.stop_floor=0.02`（值 = 引擎默认 ⇒ 出厂即默认）。

"""


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "CHANGELOG 不是纯 CRLF"
    assert "\r\r\n" not in txt, "含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    if "v1.23.27 相对 v1.23.26" in t:
        print("已存在 v1.23.27 段，跳过")
        return

    a = "v1.23.26 相对 v1.23.25\n"
    assert t.count(a) == 1, ("锚点命中 %d 次" % t.count(a))
    t = t.replace(a, SEC + a, 1)

    SRC.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    print("STEP12B CHANGELOG PATCH OK")


if __name__ == "__main__":
    main()
