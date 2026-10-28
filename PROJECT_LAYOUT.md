# Meta-DGTF-道生三阶模型 项目文件分类

## 顶层结构

    app/            dgtf_app/        本地 Web 工作台
    dgtf_engine/    V1/V2 引擎总目录
      dgtf_v1/      V1 引擎/报告/脚本/夹具/备份
      dgtf_v2/      V2 三平面核心
        engine/     V2 生产入口：Meta-DGTF-V2.2.15.py
    docs/           设计与发布文档（含 docs/index.html 静态门户）
    requirements.txt / requirements-local-model.txt  运行与本地模型依赖
    reports/        安全、迁移、验收报告
    audits/         审计证据
    bench/          评测与基准
    configs/        配置预设
    scripts/        启动、同步、部署、安全
    .github/        CI / Pages / Release / 安全
    local_model/    权重、环境、模型说明
    llm_sft/        LoRA 微调
    scripts/local_model/  本地模型训练/评估/合并
    archive/        本地归档（忽略）

## 版本边界

    V2 生产：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.15.py + dgtf_engine/dgtf_v2/
    V2 测试：dgtf_engine/dgtf_v2/tests_*.py（68 个，含单引擎内联融合 13 项 / 四层目标契约）
    V1 归档：dgtf_engine/dgtf_v1/engine/元DGTF-V1.30.4.py
    V1 回滚：DGTF_APP_ENGINE=dgtf_engine/dgtf_v1/engine/元DGTF-V1.30.4.py

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

- V2 生产入口：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.15.py
- App：2.0.37（本地链路两段守护 + /api/health local_chain 读数 + 本地档预设 + 道生专属模式 + 三体动态计划 + 预算守卫 + DSH 实时视图 + 读数缓存 + V2 帕累托图 + BGE 缓存）
- Engine：2.2.15（stage 登记闭环；本地链路提速 3.3x；四层目标读数契约）
- V2 tests：67 / 67 文件 PASS（1107 项检查；含 stage 登记 10 / 四层目标契约 58 / 题型判定 / 元层清算 / 判定审计 / 帕累托判据）
- F5：生成机制完成
- 历史融合：178 个版本 / 17 条能力轴 / readiness 1.00
- 行为融合：5 个 arm / auto 调度 / outcome UCB
- V2 命名：见 dgtf_engine/dgtf_v2/NAMING.md
- fast_gate：15 / 15 PASS（动态选最高版引擎）
- selftest：455 / 455 PASS（含本地链路 11 项）
