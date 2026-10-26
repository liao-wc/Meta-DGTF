# App V2.0.35（2026-10-26，收束版）

## 主题
Round 125–127 收束：本地 judge 快失败、App 缓存显式绕过、probe 覆盖 R7 兜底、
合并后引擎真实 local 验证、新域真题、外汇冲突时间锚定、v9b self_check 槽位回滚。

## 改动
- dgtf_local_llm/service.py：dual_judge 忙时 503 BUSY 快失败（/metrics dual_judge_fastfail）；
  **self_check 槽位回 v8b**（v9b local A/B 两题 0.9525/0.9417 均低于 v8b 0.99/0.9509），
  self_check_min 保留 v9b。
- dgtf_app/server.py：no_cache/force_rerun 别名显式绕过产物缓存与运行中去重；
  pp_fast_e2e.py 支持 DGTF_E2E_NO_CACHE=1。
- 引擎：_probe_covers_target（严尺子 + 词面近义 AND 兜底）；_anchor_resolve_answer
  （题面年份+年末/12月 时间锚定，消解同一年不同时点数值冲突；A86）。
- 验收：inal_acceptance.py --with-service 13/13。

## 验证（Round 125–127）
- fast_gate 12/12；V2 51/51（836 checks）；矩阵事实 60 行；App 12 行；
- 合并后引擎 --dual-judge-mode local 真跑：0.9857 / verified（本地 judge 8 次回退，吞吐仍限）；
- 新域：嫦娥六号 0.9639、成人睡眠 0.9409；外汇题离线锚定修复后 answered / display=32024亿美元；
- v9b local self_check A/B：出生人口 0.9525、光速 0.9417（→ self_check 槽位回 v8b）。
