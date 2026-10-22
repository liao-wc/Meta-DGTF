# 元DGTF app 依赖链自洽审计

生成：2026-10-22 15:32:41

PASS 61 / FAIL 0

## FAIL
- 无

## PASS
- engine file exists
- engine version 1.30.0
- app version present 1.4.1
- README app version synced
- health ok
- consistency ok
- context trace check
- rag policy check
- rag index exists
- rag index nonempty
- rag index dim 512
- embedding service healthy
- context semantic
- context citations
- context layer contexts
- context trace history
- dsh chats list
- dsh sessions list
- dsh conversation cancel scoped
- dsh danger requires explicit confirmation
- dsh high-risk still manual
- dsh write prompt
- dsh privacy prompt
- security policy dsh
- embedding local only
- net policy blocks localhost
- net policy blocks metadata
- net policy allows public https
- net policy blocks file scheme
- dsh network policy api
- dsh network configurable hooks
- https support hooks
- agent action log hooks
- front task mapping keys
- front result mapping keys
- front knowledge mapping keys
- front chat status mapping keys
- front proposal mapping keys
- library action log hooks
- dsh current-session bridge hooks
- agent panel residual controls removed
- agent live info screen hooks
- engine layer payload contract
- output list contract
- clean output helper
- quality alternative api
- quality alt grade
- v2 auto apply
- v2 auto strategy applied
- v2 only gear select
- v2 auto status
- artifact llm_sft/adapter_qwen05b_v1/adapter_config.json
- artifact llm_sft/eval_base_vs_lora.json
- artifact llm_sft/adapter_qwen15b_v1/adapter_config.json
- artifact llm_sft/adapter_deepseek15b_v1/adapter_config.json
- artifact llm_sft/eval_deepseek_base.json
- llm adapter ready
- llm eval json
- dsh history ui
- dsh multi-turn one session
- input moved up