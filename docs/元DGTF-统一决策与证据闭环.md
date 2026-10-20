# 元DGTF 统一决策与证据闭环

## 一、总原则

1. 层固定四层：0/1/both/all 全跑，auto 不砍层。
2. 圈可砍：事实短题每层最多 2 圈，四层仍全进入。
3. 检索是证据/先验，不是最终结论。
4. 检索结论与四层推理结论做一致性核对。
5. packed.decision_trace 是唯一事实源，md/app/审计共用。
6. V1 管执行，V2 管建议；V2 仲裁受四层硬约束与安全否决。
7. 记忆只存数值/结构，不存答案正文。

## 二、决策流水线

问题 -> 分类（fact/decision/boundary/research） -> 事实预检（可选） -> V1/V2 仲裁 -> 四层执行 -> 层内早停（只停圈） -> 四层后一致性 -> answer_summary。

## 三、四层与圈数

- route 恒为 ["0","1","both","all"]；显式 --route 仅用于单层验收。
- fact_flow.rounds_max=2：事实短题四层各 2 圈；0=按层默认。
- 决策/边界题使用按层默认圈数；实际停圈由原停止判据决定。

## 四、事实闭环

fact_flow 提供：
- classify_question / plan_fact_run / fixed_route
- FactCard 四态：unknown / no_record / conflict / answered
- evidence：官方源白名单、归一化、指纹、去重、预算、数值冲突、引用绑定
- consistency：match / partial / mismatch / not_comp
- 引擎在 _build_decision_trace 中把已有 web_results 归一成 EvidenceReport，生成 fact_card、evidence、consistency、answer_ready。

## 五、V1/V2 仲裁

decision_policy 支持 shadow/advisory/takeover/joint：
- H1 层集合不可改（四层）
- H2 顺序 0→1→both→all
- H3 圈数 1..cap
- H4 停止码白名单
- H5 无内容接管
- 安全否决：预算、契约、匿名/测试、连续否决回滚
- 回滚需显式重入门禁
- packed.v2_policy 记录裁决与事故

引擎接入点：scheduler.v2.mode 存在时调用 DecisionPolicy.decide；默认 shadow。

## 六、统一 EML

unified_memory 合并 V1 playbook 与 V2 v2_events：
- read_priors / record_outcome
- 跨源 (run_id, template) 去重
- 无答案正文；生产写保护；测试隔离
- 当前模块已落地并有 19 条离线判据；V2Shadow 已用统一先验只读路径，V1 EML 读 V2 事件仍待接。

## 七、输出契约

packed.decision_trace：
- question_type
- route/rounds
- layers（四层 entered/rounds/stop/product）
- retrieval（n/official/dates/urls）
- reasoning（answer/dates/layer）
- consistency（status/reasons）
- fact_card/evidence（事实题）
- answer_ready/stop_reason
- artifacts

md 顶部结论摘要：问题类型、检索结论、四层推理结论、一致性、四层产物表、停止判据。

## 八、停止规则

- 层内：本层 answer_ready 只停止加圈，不跳层。
- 四层后：all4 + 无 all_closure_unavailable/core_audit_gaps + consistency match/partial + fact_card answered 才 answer_ready。
- 冲突/未知不回退成单一答案。

## 九、DeepSeek 官方联网

- web_search.backend 支持 tavily / deepseek / snapshot。
- deepseek 走 POST https://api.deepseek.com/v1/tools/search
- 请求：query, count, need_content；Bearer API Key。
- 响应：title/url/snippet/summary/content/date/authority -> claim/tier。
- Key：web_search.api_key_env；缺省时 DeepSeek 后端回退 api.key。
- app 参数面板可选 backend。

## 十、免费验证

- 冒烟 266/0（无真实 API）
- 跨档验收 319/0
- app 自检 371/0（mock）
- 新模块：fact_flow 15、evidence 20、decision_policy 23、unified_memory 19
- 既有 tests 41、l0 16、core 9、all 9、one 10、both 10、zero 10

## 十一、未完成边界

- fact_flow 目前在打包后做证据/一致性回执，未在进入四层前真正发起预检检索；四层仍全跑。
- evidence gap 的逐 claim 触发/回填未接入主循环。
- unified_memory 未替换 V2Shadow 的 MemoryLake 读路径。
- F5 生成机制仍延期；guide/filter 不默认。
- DeepSeek Search 真网调用未在本轮执行（按要求不真跑），仅离线适配与静态检查。

## 逐 claim gap 循环与 V2 joint（最终补充）

- claim_gap.py：从 0/1/both/all 的产物抽 claim；只对无引用、含外部事实/日期 token 的 claim
  触发官方检索；每层最多 3 个，返回 resolved/unresolved/skipped 与 search 次数。
- 引擎在打包前执行，不改 reasoning 文本，只补 citations/缺口记录；产物 md 增「逐 claim 证据缺口」表。
- V2 默认 mode=joint：V1 auto 与 V2 proposal 经 DecisionPolicy 仲裁；四层硬约束、预算闸、回滚保留。
- claim_gap.enabled 生产默认 true；smoke/测试默认 false，避免无谓真实检索。
