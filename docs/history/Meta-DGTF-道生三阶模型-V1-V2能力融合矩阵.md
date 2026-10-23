# Meta-DGTF-道生三阶模型 · 历史谱系融合计划

- 目标版本：V2.1.0
- 历史版本：178 个
- 连续性 readiness：1.00
- continuity_ok：True
- 归档：元DGTF-V1历史归档-20261023.zip

## 时代

| 时代 | 起点 | 能力 |
|---|---|---|
| V1.0–V1.9 | V1.0 | 四层螺旋推理 / content/context/self 三通道 / 单文件引擎 / 产物落盘与审计 |
| V1.10–V1.20 | V1.10 | 外部锚点/证据链 / EML 雏形（episodes/playbook） / 质量读数与停止判据 / 串行/并行档位 |
| V1.21.x | V1.21 | 自动调度 auto_plan / 探针/悬置/延迟债务 / 输入健全性自查 / 分环节成本统计 |
| V1.22.x | V1.22 | 模块边界与依赖审计 / 快照/续跑/回滚 / 质量评分与回归门禁 / 安全与权限 |
| V1.23.x | V1.23 | e-process/保形预测/BOCPD/Dung / 质量-成本 Pareto / 事实门与答案门 / RAG/联网/外部输入 |
| V1.24–V1.25 | V1.24 | V2 影子调度 / EML v2 双写 / 四层契约 / L0-v2 archive |
| V1.26–V1.30 | V1.26 | 答案门/过程门分离 / 事实卡与一致性 / 真跑验收与质量重放 / 边界/长文/多轮/视觉 |
| V2.0 | V2.0.0 | EML v2 知识面 / Scheduler v2 控制面 / 四层契约 F2-F5 / F5 0 层生成 / App V2 本地工作台 |
| V2.1 | V2.1.0 | 历史谱系融合 / 能力连续性审计 / 运行 provenance / 来源/能力/演化文档 |

## 能力轴

| 能力 | V1 来源 | V2 实现 | 状态 | 判据 |
|---|---|---|---|---|
| 四层螺旋推理 | V1.0 | MetaDGTF.run / _run_serial / dgtf_v2.layers_* | native | dgtf_v2/tests.py + tests_core.py |
| content/context/self 三通道 | V1.0 | MemoryChannel / MetaDGTF.channels | native | tests_core.py + smoke_test.py |
| 证据链与外部锚点 | V1.21.x | dgtf_v2.evidence + external_anchor | native | tests_evidence.py + tests_fact_flow.py |
| 事实门 / 答案门 / 过程门 | V1.23.x-V1.30.x | fact_flow.py + fact_contract.py + evidence.py | native | tests_fact_flow.py + tests_fact_contract.py |
| 自动调度与 Pareto | V1.23.13-V1.23.65 | dgtf_v2.scheduler（MAPE-K/EVOI/MPC） | native | tests.py + tests_decision_policy.py |
| 前沿内核（e-process/保形/BOCPD/Dung） | V1.23.64-V1.23.66 | engine 内 F1-F4 + tests_evidence/consistency | native | tests_evidence.py + tests_decidability_audit.py |
| 质量-成本帕累托与信用分配 | V1.23.50-V1.23.66 | quality report + scheduler credit + bench | native | tests_structural_diversity.py + bench |
| EML 双时态知识面 | V1.24.0 | dgtf_v2.memory + unified_memory | native | tests_unified_memory.py + tests_evidence.py |
| 四层契约 F2-F5 | V1.24.0-V1.25.0 | layers_all/one/both/zero + contracts.py | native | tests_all.py + tests_one.py + tests_both.py + tests_zero.py |
| F5 0 层生成 | V2.0.0（V1 实验线） | dgtf_v2.layers_zero.generate_zero_layer | native | tests_zero.py |
| 本地 Web 工作台 | V1.4.x app | dgtf_app（HTTPS/鉴权/任务/产物/DSH） | native | dgtf_app/selftest.py 371 项 |
| 本地模型路由 / LoRA | V1.23.x app | scripts/local_model + app engine_runner | bridged | docs/llm_lora_finetune.md + pip check |
| RAG / 联网 / 出处 | V1.23.x | app RAG v2 + dgtf_v2.net_policy + web_search | native | tests_evidence.py + app selftest |
| 多轮 / 视觉 / 外部文件 | V1.30.x | multi_turn.py / vision_input.py / external_input.py | native | tests_multi_turn.py + tests_vision_input.py + tests_external_input.py |
| 安全边界（HTTPS/鉴权/网络策略） | V1.30.x app | server.py + dgtf_v2.net_policy | native | tests_api_policy.py + app selftest |
| 决策回执 / 过程账本 / 可回放 | V1.21.x-V1.23.x | process_ledger.py + replay.py + decision_trace | native | tests_facet_ledger.py + tests_decidability_audit.py |
| 历史谱系融合（V2.1 创新） | V1.0-V1.30.4（整个历史） | dgtf_v2.history_fusion + 运行时 provenance | native | tests_history_fusion.py |

## 生成说明

本计划由 dgtf_engine/dgtf_v2/history_fusion.py 从历史清单生成；
只做 provenance 与连续性审计，不改写答案。
