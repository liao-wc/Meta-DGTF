# DSH 巡检报告 · 历史领域换题复跑

时间：2026-10-25T23:51:52+08:00
题目：中字形西汉大墓的墓主是谁？
状态：完整真跑完成，质量门通过

## 真跑

- tag: patrol-history-rerun-20261025
- exit=0，wall=1125.8s
- 账户窗口余额差=5.27 CNY（含并发运行，不可归因单跑）
- tokens=1013050，calls=99
- quality=0.9495，answer_quality=verified，answer_ready=true
- packed: outputs/20261025_235138_中字形西汉大墓的墓主是谁.packed.json

## 检查项

- App 2.0.24 / Engine 2.2.3
- DSH 守护 interval=5400，thread=true
- 余额与门禁见本轮最终回复

## 修复项

- 上一题“这座中字形汉墓藏着什么？”无明确指代，已加入自包含题目过滤器；
- 本题改为明确主体“中字形西汉大墓的墓主是谁？”。

## 背景

上一题“这座中字形汉墓藏着什么？”无明确指代，quality=0.218/unverified；
已加入自包含题目过滤器，本题为明确主体复跑。

## 验证

- 完整真跑 verified/ready
- 本轮无新阻塞问题

## 风险

- 成本为窗口差，含并发其他真跑
- 未 push；工作区有未提交变更

## 留存

- docs/reports/patrol_20261025_235138_history_rerun.md
- docs/patrol_runs.jsonl
- dgtf_memory/patrol_state.json
- dgtf_memory/patrol_history.jsonl
