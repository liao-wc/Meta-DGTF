# V2 事件库开启与历史回填记录

时间：2026-10-26

## 问题

V2 面板长期没有新点：dgtf_memory/v2_events.jsonl 最后更新停留在 2026-10-25 16:02，
而 2026-10-26 的多条真跑均未写入 schedule_outcome。

## 原因

最近真跑使用 configs/道生专属模式.yaml，该配置缺少：

    scheduler:
      v2:
        shadow: true
        eml_path: dgtf_memory/v2_events.jsonl

而 configs/方案F-帕累托最优.yaml 已有该段，所以只有使用方案F/G 的跑次进入 V2 事件库。

## 处理

1. 在 configs/道生专属模式.yaml 末尾增加 scheduler.v2 shadow 配置；
   - 只观察，不改变执行；
2. 新增 scripts/backfill_v2_events.py；
   - 读取 outputs/*.packed.json；
   - 按 run_id 去重；
   - 只补 v2_events.jsonl 中不存在的 run_id；
   - 写前自动备份；
3. 回填结果：
   - 新增 run：118
   - 新增事件：868
   - v2_events 总行数：1788
   - unique_outcomes：886
   - 备份：dgtf_memory/v2_events.jsonl.bak_20261026_090955

## 验证

- /api/schedule/v2：ok=true，n=1788，unique=886
- /api/schedule/v2/pareto：30 个模板点，前沿 5 个
- V2 面板可见时每 10 秒刷新

## 注意

- 回填事件来自历史 packed 的 views/rounds，quality 为整跑质量、tokens 按层数均分，
  不是单层因果 A/B；
- 回填脚本按 run_id 去重，重复运行不会重复追加；
- 若后续真跑继续缺失事件，应检查实际使用的 config 是否带 scheduler.v2.shadow。
