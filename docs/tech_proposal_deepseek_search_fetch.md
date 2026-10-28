提案目标：评估 DeepSeek 官方 Search / Fetch API 是否可替代或补充现有检索链路。
证据：agent_knowledge.jsonl 有 4 条 actionable，主题均为官方 Search/Fetch；当前 DSH 巡检使用 web_search，引擎侧检索未接官方 API。
影响：若替代可改善证据格式/时延；若直接切换可能增加成本、改变证据门行为，甚至降低 verified 率。
步骤：
1. 只做离线兼容性对比：输入 10 条历史事实题，记录官方 Search/Fetch 的返回格式、引用、时延、费用；
2. 与现有 web_search/引擎证据格式做字段映射，不直接改线上链路；
3. 选取 1 条事实题做 opt-in 真跑，web-on，预算上限 5 CNY；
4. 比较 quality/verified/tokens/时延/官方源覆盖率；
5. 只有显著更优才接入，并先做 shadow 开关。
验证：python fast_gate.py；python dgtf_app/selftest.py；python scripts/run_v2_tests.py；python scripts/precheck_quality.py。
风险：API 配额/费用；官方源格式差异；证据门误判；不得读取或外发密钥。
需人工决策：是否提供官方 Search/Fetch 凭据、是否允许 1 次 opt-in 真跑及预算上限。