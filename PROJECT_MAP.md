# Meta-DGTF-道生三阶模型 项目文件地图

## V2 生产层

| 类别 | 物理位置 | 说明 |
|---|---|---|
| V2 生产入口 | dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.44.py | 单文件生产引擎（V2.2.14 及更早只读保留），App 自动选用最高版本 |
| 引擎总目录 | dgtf_engine/ | 统一存放 dgtf_v1/ 与 dgtf_v2/ |
| V2 核心 | dgtf_engine/dgtf_v2/ | EML / Scheduler / 四层契约 / 证据与决策 |
| V2 发布说明 | V2.2.44-发布报告.md、V2.2.44-收束报告.md、docs/releases/V2.2.44.md（历史 V2.2.43 保留） | 发布、验证、边界 |
| 融合实现 | Meta-DGTF-V2.2.44.py 内联（history + behavior + self_check/dual_judge） | 单引擎文件：历史谱系、5 个 arm、auto 调度融合、outcome UCB |
| 历史清单 | dgtf_engine/dgtf_v2/history_manifest.json | 178 个历史快照数据；仅文档/审计参考 |
| 历史文档 | docs/history/ | 来源、定义、版本演化、能力矩阵 |
| V2 门户 | docs/index.html | GitHub Pages 静态入口 |

## V1 归档层

| 类别 | 物理位置 | 说明 |
|---|---|---|
| V1 引擎 | dgtf_engine/dgtf_v1/engine/元DGTF-V1.30.4.py | 回滚基线，不再作为默认生产入口 |
| V1 报告 | dgtf_engine/dgtf_v1/reports/ | V1 历史报告 |
| V1 脚本 | dgtf_engine/dgtf_v1/scripts/ | V1 历史验证/实验脚本 |
| V1 备份 | dgtf_engine/dgtf_v1/legacy/ | 旧配置和 smoke 备份 |

## App 与配置

| 类别 | 物理位置 | 说明 |
|---|---|---|
| App | dgtf_app/ | 本地 Web 工作台（2.0.37；local_chain.py 两段本地链路守护 + /api/health 动态读数） |
| 启动/运维 | scripts/、scripts/local_model/ | 启动、同步、部署、安全与本地模型脚本 |
| 本地链路 | dgtf_local_llm/、scripts/local_model/openai_shim.py、configs/本地模型-全链路.yaml | 8772 推理服务（fp32+CUDA graph）/ 8773 OpenAI 适配层 / App 本地档预设 |
| 全链路判据 | scripts/local_model/e2e_app_local.py、scripts/local_model/probe_layer_goals.py | App 真入口 e2e（18/18）/ 四层目标探针（81/81） |
| 帕累托基线 | scripts/pareto_flow.py | 全流程质量/成本非支配前沿（第一版） |
| 联动报告 | scripts/pareto_report.py | 三组件联动质量/成本/墙钟报告（MD/JSON） |
| 模式融合 | scripts/mode_fusion.py | 保留 B/serial/fast，M4 auto-fused 场景选档 |
| 闭环检查 | scripts/dsh_loop_check.py | 一键验收：队列来源闸、质量门预检、App live 视图、提案/high 队列、联网/工具调用遥测 |
| 默认配置 | dgtf_config.yaml | V2 生产配置 |
| 预设 | configs/ | 方案 A/B/C/F/G/H 等配置 |
| 自动化 | .github/ | CI、Pages、Release、分类、安全 |

## 文档与证据

| 类别 | 物理位置 | 说明 |
|---|---|---|
| 设计与发布 | docs/ | 架构、发布说明、依赖与安全 |
| 安全报告 | reports/ | 开源安全与迁移报告 |
| 审计 | audits/ | 历史审计证据 |
| 基准 | bench/ | 评测脚本与结果 |
| 历史归档 | archive/ | 本地忽略，不入公开 Git |

## 本地模型

| 类别 | 物理位置 | 说明 |
|---|---|---|
| 权重 | local_model/models/ | 本地权重，不进 Git |
| 环境 | local_model/envs/dgtf_llm_env/ | 训练/推理 venv，不进 Git |
| 微调 | llm_sft/、scripts/local_model/ | LoRA 配置、产物与训练/评估脚本 |

## 运行态（本地，不入库）

    dgtf_memory/  outputs/  runs/  cache/  dgtf_app/runs/

## 管理命令

    python scripts/dsh_repo_classify.py classify
    powershell -File scripts/dsh_repo_manage.ps1
