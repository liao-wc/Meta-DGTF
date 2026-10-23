# dgtf_v2 · 三平面参考内核

**状态：V2 已发布（reference + production 契约层）。** 生产引擎是 元DGTF-V2.0.0.py；F2/F3/F4/F5 契约层默认开，L0-v2 archive 只读默认开；F5 生成机制已完成（V2.0.0）。2026-10-23 复测：dgtf_v2 下 32 个 tests_*.py 全部通过（运行需 PYTHONPATH=项目根）。

## 是什么

把元DGTF 的控制面拆成三个职责分离的平面：

- **知识面（EML v2）**：双时态事件溯源、AGM/TMS 修正、BM25+RRF+MMR 检索、巩固/遗忘、只给调度数值先验。
- **控制面（Scheduler v2）**：MAPE-K + EVOI + 有限视界 MPC + Pareto + 安全盾；只决定层/圈数/停止。
- **执行面（四层契约）**：0 修行 / 1 研究 / both 对撞 / all 元；每层有必须产出、禁止产出、退出判据。

详细设计见 ../docs/元DGTF-V2-三平面架构.md。

## 文件

    contracts.py     四层契约 + LayerState/Budget/LayerResult + validate_result
    memory.py        双时态 EML + BM25/RRF/MMR + AGM/TMS + 巩固/遗忘/先验
    scheduler.py     MAPE-K + EVOI + MPC + 安全盾 + credit
    orchestrator.py  确定性四层 mock + 端到端
    replay.py        真实 outputs/*.packed.json 回放
    layers_l0.py     Phase 5 · 0 层 MAP-Elites/novelty/Heaps/Thompson
    core_duty.py     四层核心职责审计 + actions 归位/证据回退修复
    layers_all.py    F2 · all 元层 ClosurePackage（六件套/动作四字段/origin）
    tests.py         41 项判据
    tests_l0.py      16 项 L0-v2 判据
    tests_core.py    9 项核心职责判据
    tests_all.py     9 项 F2 判据
    layers_one.py    F3 · 1 层 AnswerSetPackage
    tests_one.py     10 项 F3 判据
    layers_both.py   F4 · both 原生论证契约
    tests_both.py    10 项 F4 判据
    layers_zero.py   F5 · 0 层审计/生成契约
    tests_zero.py    11 项 F5 审计/生成判据

## 跑

    python dgtf_v2/tests.py
    python -m dgtf_v2.replay --limit 5

## 当前判据

- tests：41 / 41
- tests_l0：16 / 16
- tests_core：9 / 9
- tests_all：9 / 9；F2 all_v2 四层真跑 5/5（成本 5/5 在 600k），boundary profile 支持无 actions
- tests_one / tests_both / tests_zero：各 10 / 11；F3/F4 full-4 通过，F5 生成+审计通过
- 核心职责审计：20 份历史 packed 中 18 份 1 层 actions 错位，已改源头落盘；
  4 份 all 缺 decision/residual（未产出 all 的跑次，不伪造）
- L0 replay：10 份真实 0 层产物，467 候选 → 80 精英，novelty .92–.95，档案 4–8 格
- L0-v2 已接 V1 flag（actions.l0_v2_curate，默认 true / mode=archive 只读；guide/filter 不默认）
- 不调 LLM、不写 outputs；内核测试不改 V1 行为

## 接入路线

1. Phase 0：影子回放（本包）。
2. Phase 1：V1.24.0 已接 scheduler.v2 影子（只记录建议，不改执行）。
3. Phase 2：EML 双写，不迁移不删除。
4. Phase 3：契约闸先告警后拒绝。
5. Phase 4：接管层顺序/圈数，层内 prompt 不动。
6. Phase 5：F2/F3/F4/F5 契约层已接生产默认；L0 archive 只读；F5 生成机制已完成（V2.0.0）。

任何一步不达标，回滚 V1 auto_plan；生产引擎不因 V2 设计而改变。

## 统一决策/证据模块（离线）

    fact_flow.py         事实题分类/四层固定/圈数建议/FactCard
    evidence.py          官方源/归一/指纹/去重/预算/冲突/引用绑定
    consistency.py       检索 vs 推理：match/partial/mismatch/not_comp
    decision_policy.py   shadow/advisory/takeover/joint 仲裁 + 回滚
    unified_memory.py    V1 playbook + V2 events 统一先验/写保护

判据：tests_fact_flow 15、tests_evidence 20、tests_decision_policy 23、
tests_unified_memory 19。全部无 LLM/网络，使用注入 fake search 与 tmp 记忆。
