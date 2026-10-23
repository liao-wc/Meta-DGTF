# 项目文件分类

## 顶层结构

    app/            dgtf_app/        本地 Web 工作台
    engine/         v2/engine/元DGTF-V2.0.0.py  V2 单文件生产入口
    core/           v2/dgtf_v2/         V2 三平面核心
    v1/             V1 引擎/报告/脚本/备份
    v2/             V2 说明与发布索引
    docs/           设计与发布文档
    reports/        安全、迁移、验收报告
    audits/         审计证据
    bench/          评测与基准
    configs/        配置预设
    scripts/        启动、同步、部署、安全
    .github/        CI / Pages / Release / 安全
    site/           Pages 静态门户
    local_model/    权重、环境、模型说明
    llm_sft/        LoRA 微调
    archive/        本地归档（忽略）

## 版本边界

    V2 生产：v2/engine/元DGTF-V2.0.0.py + v2/dgtf_v2/
    V2 测试：v2/dgtf_v2/tests_*.py（32 个）
    V1 归档：v1/engine/元DGTF-V1.30.4.py
    V1 回滚：DGTF_APP_ENGINE=v1/engine/元DGTF-V1.30.4.py

## 不入库

    local_model/models/
    local_model/envs/
    dgtf_memory/
    outputs/
    runs/
    cache/
    archive/
    dgtf_app/runs/

## 状态

- V2 生产入口：v2/engine/元DGTF-V2.0.0.py
- App：2.0.0
- Engine：2.0.0
- V2 tests：32 / 32 PASS（F5 判据 11/11）
- F5：生成机制完成
- V2 命名：见 v2/NAMING.md
- fast_gate：12 / 12 PASS
- selftest：371 / 371 PASS
