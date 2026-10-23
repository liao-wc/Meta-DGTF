# MetaDGTF-道生三阶模型 项目文件地图

## V2 生产层

| 类别 | 物理位置 | 说明 |
|---|---|---|
| V2 生产入口 | dgtf_engine/dgtf_v2/engine/MetaDGTF-道生三阶模型-V2.0.0.py | 单文件生产引擎，App 自动选用最高版本 |
| 引擎总目录 | dgtf_engine/ | 统一存放 dgtf_v1/ 与 dgtf_v2/ |
| V2 核心 | dgtf_engine/dgtf_v2/ | EML / Scheduler / 四层契约 / 证据与决策 |
| V2 发布说明 | V2.0.0-发布报告.md、docs/releases/V2.0.0.md | 发布、验证、边界 |
| V2 门户 | docs/index.html | GitHub Pages 静态入口 |

## V1 归档层

| 类别 | 物理位置 | 说明 |
|---|---|---|
| V1 引擎 | dgtf_engine/dgtf_v1/engine/MetaDGTF-V1.30.4.py | 回滚基线，不再作为默认生产入口 |
| V1 报告 | dgtf_engine/dgtf_v1/reports/ | V1 历史报告 |
| V1 脚本 | dgtf_engine/dgtf_v1/scripts/ | V1 历史验证/实验脚本 |
| V1 备份 | dgtf_engine/dgtf_v1/legacy/ | 旧配置和 smoke 备份 |

## App 与配置

| 类别 | 物理位置 | 说明 |
|---|---|---|
| App | dgtf_app/ | 本地 Web 工作台 |
| 启动/运维 | scripts/、scripts/local_model/ | 启动、同步、部署、安全与本地模型脚本 |
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
