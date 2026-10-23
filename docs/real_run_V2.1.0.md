# V2.1.0 定向真跑记录（0 层）

日期：2026-10-23
引擎：Meta-DGTF-V2.1.0.py
App：2.1.0
问题：用一句话说明四层推理系统的最小可行闭环是什么？

## 参数

- route：0
- rounds：配置 1（实际 0 层 2 圈）
- parallel：serial
- web：off
- thinking：off
- run：20261023_211218

## 读数

- 退出码：0
- LLM calls：20
- LLM tokens：85,807
- history_fusion：178 个版本 / readiness=1.00 / continuity_ok=True / profile=contract-first / axes=17/17
- zero_contract：aspects=1, probes=3, suspensions=2, novelty_measured=true, gaps=[], ok=true
- L0-v2 archive：observed=22, novelty=0.8715, cells=11
- answer_ready=false：route 只跑 0 层，不产生 all 闭合，预期如此，不冒充全层答案。

## 全四层长跑

route 0,1,both,all / rounds 1 在 26 calls / 121,965 tokens 后遇到 DeepSeek API 长尾，
无返回、无 packed，本轮终止；不作为通过证据，待供应商恢复后用同一命令重跑。

## 产物

- outputs/20261023_211218_用一句话说明四层推理系统的最小可行闭环是.packed.json
- outputs/20261023_211218_用一句话说明四层推理系统的最小可行闭环是.md
