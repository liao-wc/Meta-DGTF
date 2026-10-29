# App 2.0.72 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.47（零行为差）。
> 主题：project 质量证据扩到 0/4 + 语义预判结果跨进程落盘。

## 1. 变更

- project 加圈+上下文开关 A/B（真 API 约 ¥0.25）：两臂均 unverified（61.5k/62.6k tokens）；
  _QUALITY_EXPECTATION.project → 0/4，证据含 rounds2 JSON；
- 语义预判结果落盘 dgtf_memory/semantic_probe_index.json（120s/300 条），
  重启后 0 次 embedding 复用。

## 2. 预算使用

本轮 A/B 合计约 ¥0.25。

## 3. 判据与验收

- test_dynamic_opt 122 项（+1）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 仅缓存/证据变化；预判结果 120s 过期自动重算；索引缺失/损坏回退扫描。
