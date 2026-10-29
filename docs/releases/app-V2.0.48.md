# App 2.0.48 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.23（零行为差）。
> 主题：route 安全门——修复"融合后任务可能只调度 1 层"。

## 1. 变更

- daosheng_mode.build_plan 新增 route 安全门：
  - 预设/内置默认 `route_policy: union`：本地 route 预测与预设 route 取并集，
    预设为四层时**结果恒四层**（预测只作审计/补充，不砍层）；
  - `preset`：完全忽略预测；`predict`：旧行为（显式省层实验用）；
  - 非法值自动回落 union；
- plan 新增 route_policy / route_source / route_prediction 读数；被安全门拦下时写 warnings。
- configs/道生专属模式.yaml 增补 route_policy: union 与说明。

## 2. 修复效果

任务 20261029_113643_e25f29（「极端天气为什么越来越频繁」）此前因本地 route 预测
["1"] 只跑研究层；修复后同问题默认 route=0,1,both,all（四层），预测只留审计记录。

## 3. 判据

- fused_optimal 24 → 30 项（route 安全门 A9–A12，含真实本地预测复现）；
- fused_full_chain / daosheng_unified / auto_mode_local 继续跑。

## 4. 验收

一键验收 --with-service PASS 29 / SKIP 0 / FAIL 0；App selftest 455/0；
V2 71/71（1208 checks）；fast_gate 16/16；e2e 18/18；probe 81/81。
