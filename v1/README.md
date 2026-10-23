# V1 归档

本目录保存元DGTF V1 历史内容：

    engine/    V1.30.4 生产引擎（V2 发布后作为回滚基线）
    reports/   V1 历史报告
    legacy/    旧配置备份、旧 smoke 备份

V2 发布后，生产入口是项目根目录的元DGTF-V2.0.0.py。

回滚：

    $env:DGTF_APP_ENGINE="v1/engine/元DGTF-V1.30.4.py"
