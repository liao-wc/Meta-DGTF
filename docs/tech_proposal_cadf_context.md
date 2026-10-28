提案目标：评估 CAFÉ/Context-Aware Data Fabric 的动态上下文裁剪是否能降 token 且不降质量。
证据：agent_knowledge.jsonl 中 CADF 条目 triage=actionable；当前上下文注入有固定 max_chars/lessons/playbook 上限。
影响：裁剪可能降低 token 成本；过度裁剪可能丢关键证据，导致 needs_evidence 或答案质量下降。
步骤：
1. 离线统计当前 prompt 中 context 段占比与 token；
2. 设计 2 档裁剪（保守/激进），不直接替换线上；
3. 选 3 道同领域题做 A/B，固定同一配置，仅改 context 裁剪；
4. 比较 quality、verified、tokens、lost-evidence flags；
5. 只接受质量不降且 token 显著下降的档位，先 opt-in。
验证：fast_gate；selftest；run_v2_tests；precheck_quality；真实 A/B 记录。
风险：A/B 需要真跑预算；裁剪可能系统性丢证据；不得用改题型分类掩盖质量下降。
需人工决策：是否允许 6 次左右真跑 A/B、可接受预算与质量阈值。