# App 2.0.57 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.32（零行为差）。
> 主题：kind-aware 省层收益（reasoning 实测省 ~39%，fact ≈0）。

## 1. 变更

- 4 跑 reasoning A/B：route0 39,564/46,031 vs full 74,922/70,676 tokens（省约 39%，
  两臂均 unverified/ready=false）；
- 新增题型级 _ROUTE_SAVINGS_EVIDENCE（fact=0.0/n=6；reasoning=0.39/n=4）；
- route_pruning 改为题型实测优先：短程事实/fact 任意长度 keep_four_layers；
  reasoning subset_may_save（仍需质量证据才能自动砍层）；无证据退回模型估算；
- route_quality_risk 的 evidence/note 按题型指向对应证据文件。

## 2. 预算使用

本轮 4 跑 A/B 合计约 ¥0.46（每跑 max_tokens=150000）。

## 3. 判据与验收

- test_dynamic_opt 75 项（+2 净增）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认 route_policy=union（四层）不变；省层判定只记录/提示，不改变实际 route。
