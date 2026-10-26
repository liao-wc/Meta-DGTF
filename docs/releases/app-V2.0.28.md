# App V2.0.28 发布说明

发布日期：2026-10-26

上一版：App 2.0.27

## 主题

Agent 就绪灯与守护开关解耦。

## 主要改动

- Agent 灯是否绿色只取决于 DSH Agent 是否可用（dsh_headless）。
- DSH 守护关闭不再把 Agent 就绪灯变灰，只在数值中显示“守护关闭”。
- 排查发现守卫状态被显式关闭，Agent 灯变灰；已重新开启 120 分钟守卫。

## 验证

- Agent 灯 node --check PASS。
- 守护重新开启后 thread_running=true。
- App 全方位检查 PASS。
- App 版本一致性 PASS。
- App selftest 444/0。
- fast_gate 12/12。

## 静态缓存

`2.0.28-agentready`
