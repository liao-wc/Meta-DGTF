# V1 归档

本目录保存元DGTF V1 历史内容：

    engine/    V1.30.4 生产引擎（V2 发布后作为回滚基线）
    reports/   V1 历史报告
    scripts/   V1 历史验证脚本与夹具
    legacy/    旧配置备份、旧 smoke 备份

V2 发布后，生产入口是项目根目录的元DGTF-V2.0.0.py。

回滚：

    $env:DGTF_APP_ENGINE="dgtf_engine/dgtf_v1/engine/元DGTF-V1.30.4.py"

## V1-only smoke 门禁

smoke_test.py 已明确改为 V1-only：V2 生产门禁不运行它。

    $env:DGTF_V1_SMOKE="1"
    python smoke_test.py

该门禁会临时把 V1 引擎/配置/报告装填到根路径，运行后清理。
历史语料检查 `check_v12314_history_corpus` 使用本地 outputs/ 与 V1 跑批语料。
