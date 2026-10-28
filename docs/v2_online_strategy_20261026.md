# V2 在线自动策略（真正自动化）

时间：2026-10-26

## 目标

不再依赖人工 A/B 批次。正常 App 真实任务本身承担小比例探索，执行后自动写 outcome 并更新后验。

## 实现

模块：dgtf_app/v2_online.py

- 臂：
  - baseline_all2：四层 2 圈；
  - explore_all3：四层 3 圈；
  - explore_lean3：两层 3 圈；
- 前 6 个样本优先覆盖未探索臂；
- 之后 10% 概率探索最少样本臂；
- 其余按后验下界 exploit（n>=2，低成本惩罚）；
- assignment 写 dgtf_memory/v2_online.jsonl；
- 任务完成后 watcher 读取 packed，写 outcome；
- 不额外发起真跑，不需要人工 A/B 批次。

## 接入

server.py：

- 仅真实标准任务（mock / daosheng plan / retry / 显式 profile 跳过）；
- 任务启动前选臂并覆盖 route/rounds；
- 记录 _v2_online 元数据；
- 启动 watcher 等待任务完成后写 outcome；
- /api/schedule/v2/online 暴露统计。

UI：

- V2 面板新增“在线自动策略”：
  - assignments / outcomes / pending；
  - 探索率；
  - 各臂 n / quality / low / tokens。

配置：

dgtf_memory/v2_online_config.json：

    enabled=true
    exploration_rate=0.10
    min_exploit_n=2

## 与全局 V2 自动策略的区别

- 在线策略按任务选择臂，不写全局 schedule_policy；
- 全局模板 auto-apply 仍受校准闸保护；
- 在线策略可在真实任务中持续学习，无需人工 A/B。

## 测试

- v2_online 临时状态测试：12 次 assignment/outcome，summary 正常；
- /api/schedule/v2/online：ok=true，enabled=true；
- App 全方位检查：PASS；
- V2 tests / selftest 待复验。

## 风险

- 10% 探索可能增加少量 tokens；
- 当前臂集只含三个 route/rounds，不是所有模板；
- 任务失败/服务重启会留下 pending assignment；
- 真实效果需要继续积累 outcome。
