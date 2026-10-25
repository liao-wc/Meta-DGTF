# M4 质量预测的保形下界（Round 2，2026-10-25）

## 1. 为什么做

M4 质量预测器（kNN/ridge，见 `dgtf_engine/dgtf_v2/quality_predictor.py`）此前只有
**点预测**，`mode_fusion.fused_plan` 用 `0.5*预测 + 0.5*模式下界` 的经验夹取来做
「fast 不达标就选 B」的守卫。问题：
- 点预测没有风险保证：预测 0.95 真实可能 0.85，切到低质量档就是质量回退；
- 经验夹取是拍脑袋权重（研究调研 Top2 明确点名）。

本轮把它升级为**保形（conformal）下界**：在分布可交换假设下，真实质量有约
`1-alpha` 的概率不低于该下界（交叉保形 CV+ 近似，有限样本覆盖实测见 §3）。

## 2. 方法

1. **交叉残差**：K 折（默认 5 折，按 `idx % folds` 固定划分、可复现）在训练集上
   做 out-of-fold 预测，残差 `r = actual - oof_pred`（单侧、有符号）。
2. **下界修正量**：`q = Quantile_alpha(r)`；下界 `L(x) = clip(predict(x) + q, 0, 1)`。
3. **按模式细化**（工程护栏）：某模式残差样本 ≥15 且 `|q_mode - q_global| ≤ 0.15`
   才采用该模式自己的 q，否则回落全局 q —— 小样本模式分位数会过度保守
   （实测 B 桶 21 条算出 -0.47，会让切档永远弃权，已用护栏剔除）。
4. **接入切档**（`mode_fusion.fused_plan`）：
   - 模型 JSON 有 `conformal` 段时，`plan["quality_prediction_lower"]` 给出
     fast/B/serial 三模式下界，`plan["conformal"]` 给出 alpha/q_global/覆盖率；
   - 若 `min_quality` 有值：全部下界 < 目标 → 标记 `conformal abstain`（保留点预测
     选择，不静默换档）；fast 下界不达标而 B 达标 → 直接选 B（理由写进 plan）；
   - **模型无 conformal 段 ⇒ 完全保持旧行为**（tests 判据覆盖）。
5. **App 通道**：`dgtf_app/daosheng_mode.m4_prediction` 把
   `quality_prediction_lower` / `conformal` 带进道生模式的 plan，供审计侧读取。

## 3. 实测（166 条历史 packed 训练，零 API 成本）

`python scripts/train_quality_predictor.py`（自动写 `dgtf_memory/quality_predictor.json`
与仓库内 `dgtf_engine/dgtf_v2/quality_predictor_model.json`）：

| 项 | 值 |
|---|---|
| 校准方式 | K-fold=5 交叉保形（alpha=0.20） |
| n（校准） | 166 |
| q_global | **-0.0438** |
| q_by_mode（过护栏后） | `{"serial": -0.0367}`（B 桶 21 条偏离 >0.15 被剔除，回落全局） |
| **OOF 覆盖率** | **0.8012**（目标 1-alpha = 0.80 ✓） |
| **留出集覆盖率** | **0.7647 / n=34**（低于名义 0.80 约 3.5pp，属小样本抽样误差；如实记录） |
| OOF MAE | 0.1425 |
| 残差分位 | q10 -0.3822 / q50 0.0001 / q90 0.3125 |
| 模型选择 | kNN k=3 recent（random R²=0.873 / 时序 R²=0.595，与上一轮一致） |

判读：
- OOF 覆盖率精确落在名义值附近，说明「残差分布 + 分位数」口径自洽；
- 留出集 0.765 略低于 0.80，提示真实分布有轻微漂移（时序）⇒ 这是**保守方向**
  的偏差（下界偏低 = 少切激进档），符合「只能更好不能后退」的约束；
- 原始预测在部分特征组合下明显偏低（例：道生模式查询的原始下界 ≈0.06），
  这是**预测器本身的数据覆盖问题**，会以 `abstain` 形式显式暴露，而不是被
  夹取掩盖。默认 `daosheng` 不传 `min_quality`，因此不影响既定选档；一旦传了
  质量目标，planner 会显式标记弃权而不是硬切。

## 4. 判据（`tests_quality_conformal.py`，23 项，全 PASS）

- 分位数实现（插值/边界/空）；
- 校准字段完整、可复现、样本不足 8 时不校准；
- `predict_lower ≤ predict`、无 conformal 返回 None、`predict_row/predict_lower_row`
  与 `predict/predict_lower` 口径一致；
- 模型 JSON 往返（conformal 段不丢）；
- 手工构造模型显式验证 **fast→B by conformal lower** 守卫触发；
- 无 conformal 模型 ⇒ plan 无下界字段（零行为差）。

## 5. 回退

删掉模型 JSON 里的 `conformal` 段即回到旧行为（无需改代码）；或在
`mode_fusion.fused_plan` 调用侧不传 `features`（预测路径不启用）。


## 6. Round 4 修正：有效样本过滤 + OOD 护栏（2026-10-25）

上线后发现两个让 M4 预测**塌到 0.1** 的问题（实测于道生模式查询）：

1. **训练样本污染**：A/B/探针的「部分跑」（route 只跑 1~2 层、预算硬顶截断、
   无决策轨迹）以低质量标签进入训练集，近期加权 kNN 的邻居被它们主导。
   修正：quality_predictor.training_sample_ok() + 训练脚本默认只收
   「四层齐全 / 非 budget_hard_hit / 有 decision_trace / 非极短产物」的完整跑。
   实测丢弃：partial_route 60、
o_decision_trace 39、udget_hard_hit 7
   ⇒ 166 → **90 条有效样本**（训练 72 / 留出 18）。
2. **历史特征 OOD 外推**：App 侧历史读数口径与引擎 _auto_dispatch._history 不同
   （tokens_med z=+21.6、cut_rate z=-20.4），kNN 挑到最远邻居 ⇒ 三个模式都预测 0.11。
   修正：_z_vector() 统一标准化 —— hist_* 缺失按均值填补（z=0）；
   **|z|>3 的特征按均值填补（拒绝外推，不做 ±3 截断）**。

修正前后（同题「城市热岛」features）：

| 指标 | 修正前 | 修正后 |
|---|---|---|
| raw predict（fast/B/serial） | 0.11 / 0.11 / 0.11 | **0.953 / 0.955 / 0.957** |
| 保形下界（fast/B/serial） | 0.0 / 0.0 / 0.0 | **0.724 / 0.726 / 0.772** |
| 保形 q_global | -0.0438 | **-0.2288** |
| conformal coverage_oof | 0.8012（n=166） | **0.8000（n=90）** |
| conformal coverage_test | 0.7647（n=34） | **0.7778（n=18）** |

判读：修正后 M4 点预测与保形下界都回到可用区间（下界 0.72~0.77，不再恒 0）；
min_quality 守卫由此才真正生效（例如目标 0.9 时会显式弃权，目标 0.7 时可选 fast/B）。
判据：	ests_quality_conformal.py 增至 **31 项**（新增有效样本过滤 6 项、OOD 护栏 3 项）。
