# 元 DGTF · 变更记录（CHANGELOG）

> 本文件是单文件引擎 `元DGTF-V1.23.x.py` 的**变更记录**。
> 2026-10-09（v1.23.7）把它从模块 docstring 里搬出来 —— 代码文件从此只剩代码。
> **v1.23.6 及更早的段落是原样搬迁，一字未改**（搬移只动位置，不动内容）。
>
> **约定**：每版一段，**最新在最前**；每段 = 【主题】+ 改动说明 + （定稿时）
> `★ vX.Y.Z 收束摘要`（交付物 / 改了哪几处 / 验收数字 / 未做）。
> **判据**（`smoke_test.py`）：段序按版本号**严格递减**、收束摘要标题**不重复**
> （`check_v72_changelog_hygiene`）；代码文件里**不得**再出现版本段
> （`check_v1237_changelog_outside_code`）。

---

v1.30.2 相对 v1.30.1

【主题】答案门/过程门分离与质量重放。

【改动】
· decision_trace 增加 raw_answer_ready/process_ready/answer_quality；过程未达标时对外 answer_ready=False。
· 事实卡 uncovered/冲突/同题 token 缺失 → needs_evidence。
· 新增 scripts/replay_quality.py 离线重放 packed。
· app /api/quality 增加 answer/process/evidence_gaps/tri/depth。

【验证】
· fast_gate 12/0；audit70 通过；质量重放 127 packed。

v1.30.1 相对 v1.30.0

【主题】P0 质量门与结构化决策输出修复。

【改动】
· 事实卡闭环：uncovered/冲突/同题 token 缺失不再算 answered；事实预检只在 FactCard.ok 时注入。
· process_ledger：layer-1 citations 改读 pools["1"].sub_questions；decidability_audit 空读数不再误判标准失败。
· 决策产物：md 落地层优先读 packed 顶层 actions/not_do。
· bench：新增 packed 入口，输出 decision_structured 结构化 rubric。

【验证】
· py_compile 通过；事实门/ledger/bench 结构化用例通过；后续接 6 份 packed 重放。

v1.25.0 相对 v1.24.0

【主题】V2 收口正式发版：四层契约默认开 + L0 archive 恢复 + 版本号升到 1.25.0。

【改动】
· 新增 元DGTF-V1.25.0.py；V1.24.0.py 保留作回滚版，代码内容除版本头/__version__ 外不改。
· 生产默认：l0_v2_curate=true/archive；all_v2/one_v2/both_v2/zero_v2=true。
· F2 all 闭合：四层真跑 5/5，成本 5/5 在 600k；boundary profile 支持无 actions/not_do。
· F3/F4：分层 5/5、6/6；四层 full-4 204700/204724 通过；契约只写 packed，不改 views。
· F5：0 层只读审计/novelty 真跑通过；生成机制仍延期，不接 L0-v2。
· L0-v2：archive 只读默认恢复，移出生成路径；guide/filter 仍实验。
· 配置/测试/文档版本引用同步为 V1.25.0；smoke/变异体/审计入口指向新文件。

【验证】
· 冒烟 266 / 0；跨档验收 PASS 319 / FAIL 0；前端自检 371 / 0；
  L0-v2 16/16；F3/F4/F5 各 10/10；F2 9/9；核心职责 9/9；V2 判据 41/41。

【未做】
· F5 生成机制延期；guide/filter 不默认。
· eng001 664k 超软预算 10.6%，未计入 F2 成本合格 5 题。
· hypothetical 是 mock 参考，不是真实输出质量。

---

v1.24.0 相对 v1.23.66

【主题】Phase 1–4：V2 影子调度 + EML 双写 + 契约体检 + 初始串行接管（opt-in）。

【改动】
· 新增 scheduler.v2 配置（enabled 默认 false，本机 yaml true；shadow=true）。
· MetaDGTF.run 在 mode/route/rounds 决定后挂 V2Shadow：起点建议、终点建议、
  同预算 mock 参考轨迹；写 packed.v2_shadow 与 md 一行。
· 失败只留痕（v2_shadow.error / logger），不阻断 V1；层序/圈数/停止/prompt 不变。
· dgtf_v2/ 参考内核：41 项判据；20 份真实 packed 回放。
· 产物 md 增加“V2 影子调度”一行；参数面板增加 scheduler.v2 标签。
· Phase 2：V2MemoryBridge 双写 dgtf_memory/v2_events.jsonl（结构计数 + outcome，
  不含答案正文；allow_anon=false 防测试污染）。
· Phase 3：packed 映射 LayerResult → validate_result，contract_gate=off/warn/raise；
  本机 warn；首次体检抓到 1 层 decidable 无 citations、all 层 actions 为空。
· Phase 4（opt-in）：takeover=true 且 serial 时用 V2 提案覆盖初始 order/rounds；
  层内仍调 V1 _run_layer；提案不覆盖全部 route 则回退。
· A/B pilot（5 对/10 跑，600k）：V2 5/5 闭合，V1 0/5；calls −24.0%、tokens −16.0%，
  覆盖均值 90% vs 86%，三态 .633 vs .447；preset 见 configs/方案G-V2接管.yaml。
· 2M 追加（Q1）：V2 89 calls/528k 闭合；V1 128 calls/882k 仍 both（手动停止）。
· Phase 5 收口：L0-v2 恢复为 archive 只读（默认 l0_v2_curate=true）；
  guide/filter 仍实验，不默认。
· F2 all 元层：layers_all.py ClosurePackage（六件套/动作四字段/origin/完整度/风险透明度），
  actions.all_v2 **默认 true**；四层真跑 5/5（成本 5/5 在 600k），boundary profile 支持无 actions。
· F3/F4/F5 契约层：layers_one/both/zero + tests 各 10/10；
  actions.one_v2/both_v2/zero_v2 **默认 true**；
  F3/F4 四层 full-4 通过（204700/204724），F5 只开只读审计/novelty，生成机制延期。
· 质量口径修正：raw tri 是原始一致率，不是三态质量；tri 只作标签定义/诊断。
· V2 reference 收口：F2 5/5（成本全在 600k 内，boundary profile 支持）、
  F3 5/5、F4 6/6、F5 审计/novelty 1/1；L0-v2 archive 只读默认恢复；
  coverage_parts 失败不再静默（确定性回退）；门禁 266/319/371。
· tri_ratio 口径修正：raw agreement（agree/total）不是三态质量；quality 新增
  tri_agreement/tri_alpha/tri_kappa/tri_alpha_units/tri_alpha_verdict/tri_reliable/
  tri_distribution；md 增“机会校正一致（ordinal）”行；bench 解析 alpha；
  tri 只作标签定义/诊断，不作质量门。
· 四层职责修复：_pack_result 不再把 actions/not_do 写进 views.1，改落 all/顶层；
  core_duty 审计 20 份历史 packed（18 份 1 层越权、4 份 all 缺项）；
  bridge 按 decidable_product(evidence) 映射 1 层证据，动作字段对齐 owner/deadline/rollback。
· 新跑 114408 端到端通过：views.1 无 actions、all decision/residual/provenance 原生齐、
  core_ok=true、core_duty repairs=[]；core_gate 默认 warn 已接。

【验证】
· 冒烟 266 / 0；跨档验收 PASS 319 / FAIL 0；工程审计 70 / 0
· 前端自检 371 / 0；变异体 3 / 3；内核 24 / 0；V2 判据 41 / 41；L0-v2 16 / 16；核心职责 9 / 9

【未做】
· F5 L0-v2 生成机制延期（只开只读审计/novelty）；guide/filter 不默认。
· eng001 额外样本 664k 超软预算 10.6%，未计入 F2 成本合格 5 题。
· hypothetical 是 mock 参考，不是真实输出质量。

---

v1.23.66 相对 v1.23.65

【主题】先修判据反向，再补失败自修复、分环节成本与质量闭环；不靠再加模块。

【问题】
· anytime 停止判据写反：用「多数圈仍在长」当停止条件，注释却写「跌破 0.5」；
  越在产出的层越容易被提前停掉（质量风险），且两处调用点（串行 / B）同错。
· json_mode 解析失败只记 bad_json，调用点走兜底 ⇒ 内容直接丢。
· 只有总 calls/tokens；钱花在哪一环、哪项质量指标达标，读者答不出。
· spiral.shape_limit 只裁 view，_pool_text 硬编码 8 ⇒ 配置调低时池没降。
· F4 论证裁决默认关，冲突条目仍会被当有效经验召回。

【修法】
· 新增 anytime_stagnant_decided：生长序列取反后判「多数不再长」；串行/B 两处替换；
  判停理由改为「不再长」下界 > 0.5。12 圈全停滞=停；全在长/样本不足=不停。
· 新增 LLM._repair_json：解析失败时一次低温修复（只修格式、不改语义），
  计入 ops；配置 api.json_repair（默认 false，本机 true）。
· 新增 LLM.stage_stats()：按 stage 汇总 calls/tokens/ms；packed 落
  llm_by_stage + llm_json_repaired/failed；md 落分环节 Top4。
· 新增 _quality_report：覆盖率（分子/分母）、三态、决策动作数、not_do、
  各层质量线索/停止/发散态；packed 落 quality，md 落质量闭环。
· _pool_text 遵守 spiral.shape_limit（默认 0 时仍 8 条，零行为差）。
· dgtf_config.yaml：playbook.argumentation.enabled=true；api.json_repair=true。

【验证】
· 冒烟 266 / 0；跨档验收 PASS 319 / FAIL 0；工程审计 70 / 0
· 变异体子集 3 / 3 判红；前端自检 371 / 0（补 api.json_repair 标签后重跑）；机制判据 14 / 14

【未做】
· 没做真跑 A/B；anytime 修正后的真实圈数/成本变化需真跑；
· JSON 自修复只修格式，不修语义；
· ms 含重试等待，只看相对量级。

---

v1.23.65 相对 v1.23.64

【主题】把“质量/成本”调到帕累托前沿：先修质量尺子，再按 10 个完成跑次改配置，
并用总 token 软预算封住成本尾部。

【问题（都有实测，见 v12365_报告.md）】

| 问题 | 证据 | 影响 |
|---|---|---|
| 质量尺子失效 | bench_score 只认 v1.22 单行 verb=… 六字段；v1.23 是缩进四字段 | 真实 3/3 被算成 1/3，“优化”会优化错对象 |
| 成本尾部被支配 | 199 calls / 2.94M tokens 只有 83.3% 覆盖 / 50% 一致；129 calls / 1.16M 有 100% / 60% | 多花的钱没有换来质量 |
| 元层多跑 2 圈 | spiral.all_extra_rounds=2 + all 上限 6 ⇒ 8 圈 | 2.94M 跑次的直接来源 |
| 上下文未裁剪 | spiral.shape_limit=0 | 已证 A/B −8.8% tokens 的键没开 |
| high 思考无证据 | probe 四档打平；high 只是更贵 | 成本高、延迟高 |
| 三环节思考无收益 | assess_decidability Δ0.0；from_pool Δ−0.167；re_evaluate_pool Δ0.0 | 白付思考 token/延迟 |
| 无 token 预算 | 只有 max_calls / max_minutes | 调用次数挡不住单次上下文暴涨 |

【修法 · 质量尺子】bench/bench_score.py 双格式：
· 行动块解析（A\d+ 起，收缩进行）；新四字段（负责人/时限/验收/回退）与旧六字段都认；
· 覆盖率 5/6（66%）与 73.2% 都解析；修行/研究 objective 双格式。
⇒ 10 个完成跑次真实为：修行/研究 10/10、decision 8/8 个 3/3、boundary 2/2、覆盖率中位 100%。

【修法 · 配置（每条都有实测或 probe 依据）】
· spiral.shape_limit 0 → 8（A/B −8.8% tokens，无过裁）
· spiral.all_extra_rounds 2 → 1（砍 8 圈尾部）
· duty.span_tolerant false → true（度量对称化）
· api.thinking.effort high → low（high 无质量证据）
· assess_decidability / from_pool / re_evaluate_pool：enabled → disabled（实测无收益）
· decompose_normal：disabled → enabled（probe Δ+1.0，n=3）
· max_tokens：新增 2,000,000（0=不设限）
· all_on: true → false；原由 all_on 展开的 8 项**逐项显式写入 yaml**
  （playbook.mode / anytime_alpha / belief.merge_semantic / sem_entropy_thr /
   web_search.enabled / external_anchor.as_evidence / thinking.default /
   actions.merge_expand）⇒ 12 项生效值逐项核对与改前相同。
· **清空 dgtf_config.user.yaml**：原文件把 api.default_model 写成 '777'
  （服务端 400），并把全部 thinking.stages 置 enabled、effort=high ——
  它是真正覆盖主配置的文件，也是 400 与成本失控的直接来源。
  清空同时移除了若干实验性覆盖（actions.* / external_anchor.retriever,triage /
  web_search 额外 stage,tier_proposal / output.dump_rounds / memory.shape* /
  spiral.both_quota.min_items），原文件备份在
  _archive/v12365_user_cfg_before.yaml，可单键恢复。

【修法 · all_on】
· effort high → low；bandit 退出 all_on（A/B 已把它当混淆因素；改显式 opt-in）；
· 新增 shape_limit=8。all_on 仍保留 web/EML/anytime/merge_expand 的**一键全开**语义，
  但本机改 all_on:false，用显式 yaml 作为单一事实源。

【修法 · 前端 dgtf_app】
· 自检 368 → **371**（+2 下拉护栏 +1 外链 scheme 护栏），全绿；补 4 个缺中文标签的键
  （max_tokens / playbook.argumentation.enabled / .semantics / stop.anytime_mode）；
· 模型下拉移除已停服 deepseek-chat / deepseek-reasoner（选中即 400），
  改 deepseek-flash / deepseek-v4-pro；runtime.effort 移除引擎不认的 medium，
  补 api.thinking.effort = low/high/max；
· 路径/安全核查：静态目录 resolve 校验、产物/归档/资料库文件名归一、
  资料库 .env 拒绝 + 扩展名白名单、默认只绑 127.0.0.1 —— 未发现穿越。

【修法 · 机制】总 token 软预算
· _token_budget_over()：llm.total_tokens + _ck_base.tokens >= max_tokens；
· 串行层/ C / D~H 圈首、B 波循环、串行层间守卫都查；
· 到点走层/圈边界优雅停（paused + pending_layers + 快照），可 resume_ckpt；
· 默认 0 ⇒ 出厂/冒烟零行为差。

【验证】
· 冒烟 266 ✓ / 0 ✗（+1 = 成本控制判据）
· 跨档验收 PASS 319 / FAIL 0
· 工程审计 PASS 70 / FAIL 0
· 优化判据 OPT PASS 27 / FAIL 0（_chk_v12365_opt.py）
· 内核判据 KERNEL PASS 24 / FAIL 0
· 变异体子集 3/3 判红（全套未重跑）
· 前端自检 371 ✓ / 0 ✗（dgtf_app/selftest.py）

★ v1.23.65 收束摘要

交付物：元DGTF-V1.23.65.py（27486 行 / 纯 CRLF / +~50 行）；
质量尺子双格式；配置调到 129 calls / 1.16M 的帕累托膝点；总 token 软预算；
all_on 去掉 high 思考与 bandit 漂移。

改了哪几处：主文件 10 个替换块；bench/bench_score.py 两处解析；
dgtf_config.yaml 9 个键 + all_on 显式化 8 项；dgtf_config.user.yaml 清空；
smoke CONFIG_TUNED / 新判据；_mut SRC；_v122_ast_registry.json（+1 符号）；
CHANGELOG / 本报告 / README。

未做：新配置的真跑 A/B（≈¥4 / 70min）；effort low / 三环节关思考的净省未实测；
decompose_normal 只有 n=3 的 probe；全套 113 变异体未重跑。

---

v1.23.64 相对 v1.23.63

【主题】任意停时统计 / 保形预测 / 贝叶斯变点 / 抽象论证四条前沿内核进主文件；
EML 原子落盘与锁的正确性；重试的错误分类与抖动；Windows GBK 编码面收口。

【问题（本轮全项目审计，证据见 v12364_报告.md）】

| 问题 | 证据 | 影响 |
|---|---|---|
| 门禁在 GBK 下必崩 | _run_gate.py 打印 EXIT 时 UnicodeEncodeError；bench_calibrate.py 打 ✓ 崩 | 本机默认环境下五道门不可跑，且**退出码 1 会冒充失败** |
| EML 整表重写非原子 | _eml_finish 新增行时裸 open("w") | 崩溃/断电会截断记忆库；坏行又被静默跳过 ⇒ 静默丢证据 |
| 锁失败仍裸奔写库 | _eml_finish 不看 eml_lock 的 yield 值 | 并发真跑时可能无锁读-改-写 |
| 陈旧锁只看 mtime | 长跑持锁 > stale 会被第二个进程抢走 | 互斥失效（理论可复现，测试用活 pid 负对照钉住） |
| 4xx 也重试 | LLM.call 对所有异常一视同仁 | 参数错/鉴权错重试 3 次，白烧钱与时间 |
| 无抖动 | backoff ** attempt | 并行分层同拍重试（thundering herd） |
| anytime 只有一条统计口径 | stitched Hoeffding | 小样本下停得更晚（实测中位 54 圈 vs 37 圈） |

【修法 · 前沿内核 F（纯函数，无新依赖）】

· F1 e-process（Ramdas et al. 2023）：对任意停时 I 类错误 ≤ α；
  与 stitched Hoeffding 同签名分派，默认仍是 hoeffding（零行为差）。
  判据：800 次 140 步仿真的**边跑边看**假阳率 0.031 ≤ 0.05；
  功效中位 37 圈 vs Hoeffding 54 圈。
· F2 保形预测（Vovk et al. 2005）：有限样本修正分位数、p 值、预测集；
  覆盖率判据 0.940 ≥ 0.9；空校准集返回 +inf（保守全弃权）。
· F3 BOCPD（Adams & MacKay 2007）：NIG 共轭 + run-length 后验；
  5σ 漂移在 0..7 步内检出，平稳序列误报 0（合成负对照）。
· F4 Dung 论证（Dung 1995）+ 负担排序：playbook 同 (kind,cond) 动作冲突
  只标 arg_status / defeated_by，不删行、不改 status；精确并列保持 undecided
  （红线「未对齐是合法状态」）。默认关。

【修法 · 工程】

· eml_rewrite_jsonl 改 tmp + os.replace，且新增 allow_grow（只增不删）；
  _eml_finish 的新增/不变两条路都走它，删除裸 open("w") 分支。
· eml_lock：monotonic 计时、pid:token、回收前问活进程、释放只删自己的锁。
· eml_read_jsonl：坏行计数 + logger.warning（不再静默当空库）。
· LLM.call：4xx（除 408/409/429）不重试；抖动 [0.5,1.0]×backoff；
  尊重 Retry-After（上限 60s）。
· _force_utf8_streams 同时给子进程设 PYTHONUTF8/PYTHONIOENCODING（setdefault）。

【新配置键（默认保守）】
· stop.anytime_mode = hoeffding
· playbook.argumentation.enabled = false / semantics = grounded

【验证】
· 冒烟 265 ✓ / 0 ✗（+1 为本轮新判据）
· 跨档验收 PASS 319 / FAIL 0
· 工程审计 PASS 70 / FAIL 0
· 开发期判据 DEV PASS 33 / FAIL 0（_chk_v12364_dev.py）
· 内核判据 KERNEL PASS 24 / FAIL 0（_chk_v12364_kernel.py）

★ v1.23.64 收束摘要

交付物：元DGTF-V1.23.64.py（27433 行 / 纯 CRLF / +626 −50）；
四条前沿内核进单文件；两项工程加固（原子落盘 / 锁正确性）；
两项重试优化（错误分类 / 抖动）；GBK 编码面修复。

改了哪几处：主文件 12 个替换块 + 1 个插入块；smoke_test.py SRC；
_mut_v12332.py SRC；_v122_ast_registry.json（+22 符号）；dgtf_config.yaml 头；
CHANGELOG.md 本段；v12364_报告.md 新建。

验收数字：见上。

未做：保形/BOCPD 尚未接进停止判据（只有只读诊断脚本）；AGM 信念修正
未做；e-process 只做了 Bernoulli 型（多分类要新做 Dirichlet 型）。

---

v1.23.63 相对 v1.23.62

【主题】非结构化输出要留痕；`max_retries=0` 不该等于"一次都不试"。

【问题（故障注入 v2，打的是底层 `client.chat.completions.create`）】

| 故障 | 改前表现 |
|---|---|
| 抛异常 / 空内容 | 重试 → 抛 → 调用点记 `errors`（**留痕** ✓） |
| **非 JSON 文本 / "null"** | 内容非空、解析失败 ⇒ **当空处理、零留痕** ✗ |
| 类型不对 | 调用点报错（留痕 ✓） |

「答了但答不成结构」这一类**静默丢失** —— 产物看起来只是"内容少"，
读的人分不清「模型不配合」与「题本身没什么可写」⇒ 违反红线「失败留痕」。

【修法 · 留痕】`LLM` 增 `bad_json` 计数；`call()` 在 `json_mode=True` 且解析不出时
+1 并 `logger.warning`（带内容片段）；产物顶层增 `llm_bad_json`；
产物 md 在 >0 时加一行「模型返回了非结构化内容 N 次」。
**不改控制流**：解析失败仍走原兜底路径，只是这件事现在**有记录**。

【修法 · 脚枪】重试循环原是 `range(1, self.max_retries + 1)` ⇒ `max_retries=0`
是**空循环** ⇒ 所有调用必然失败，且报错是 `LLM 连续 0 次失败: None`（看不出根因）。
改成 `_tries = max(1, int(self.max_retries or 0))`：
· 默认 3 ⇒ 3 次尝试，**与改前完全一样**；
· 0 ⇒ 1 次尝试（修好脚枪）。
同文件的 `WebSearchGate` 本来就写 `range(max_retries + 1)`，两处语义现在一致了。

---

★ v1.23.63 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.63.py`（26857 行 / 纯 CRLF）+ 冒烟新判据
`check_v12363_bad_json_visible` + 变异体 M114/M115 + 本段。

**改了什么**：`LLM` 增 `bad_json` 计数与 warning；产物增 `llm_bad_json` 与 md 提示；
重试循环至少 1 次。8 个改动块 / 删 4 行 / 增 33 行；无新符号（325 / 589）；无新配置键。

**验收**：冒烟 264 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 113/113（M114、M115 均判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据五臂：`json_mode+散文` 计数且**返回原文**（控制流不变）· `null` 同样计数 ·
`json_mode=False` **不误记** · 合法 JSON 不计数 · `max_retries=0` **仍能调通**。

**两次测试设计自查**：
1. 故障注入 v1 直接替换 `LLM.call` ⇒ 把它自己的重试包装一起换掉了，
   测到的只是"调用点对空串的反应"。改打底层 `create` 才测到生产路径。
2. 判据第一次在 smoke 里红：因为 smoke 已把 `LLM.call` 换成桩 ⇒ 必须调
   `LLM._real_call`。**同一个坑一天踩两次：整体替换外层包装 = 把被测对象换掉。**

**未做**：`shape_limit` 取值扫描（≈¥12）；圈内恢复（需先做确定性改造）。

v1.23.62 相对 v1.23.61

【主题】`contra`（反向证据）接活 —— 一条从没被喂过数据的闸。

【问题（死代码审计）】`contra` **唯一的写入点**是 `eml_note_contra()`，
而它**全项目没人调用**（AST 审计：名字全文只出现 1 次）。于是：

· `contra` 恒为 0；
· `eml_promote()` 里 `if int(e.get("contra", 0)) >= int(promote_n): continue`
  **永远不触发** —— 判据写着"反向证据够了不许升级"，可反向证据从不累积；
· `_eml_note_use()` 的负面分支只降 `weight`，不记 `contra`。

判据在、输入没人产出 —— **与「读数无出口」是同一类死法**（第 ④ 次遇到）。

【修法】只补一行（不新增机制）：负面分支除了降 weight，再记一次 `contra`：

    eml_note_contra([_e], [_e], why="used_but_duty_low")

★ 行为变化要说清：`playbook.mode` 默认 `shadow`/`off` ⇒ **默认路径零影响**；
  打开 EML 时，一个被反复证明"用了没用"的条目，会在 3 次负面后**不再被升级**。
  这正是 `eml_promote` 文档里写的语义（"反向证据够 ⇒ 降级"）。

---

★ v1.23.62 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.62.py`（26828 行 / 纯 CRLF）+ 冒烟新判据
`check_v12362_contra_live` + 变异体 M113 + 本段。

**改了什么**：`_eml_note_use` 负面分支补记 `contra`（9 行）；版本号两处。
3 个改动块 / 增 9 行；无新符号（325 / 589）；无新配置键。

**验收**：冒烟 263 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 111/111（M113 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据四臂（`contra`）：累积（3 次 → 3，留 `contra_last` 原因）·
`contra=3` **拦住**升级 · `contra=0` **放行**（两向对照，证明闸不是见谁都拦）·
`_eml_note_use` 里确实有调用点（AST 取体）。

**顺带**：本版同时把**从未接线**的 `check_p0_156_units(src)` 接进 `main()`
（157/157 全接），并提供审计脚本 `_audit_unwired_checks.py` 防复发。

**未做**：`shape_limit` 取值扫描（≈¥12）；圈内恢复（需先做确定性改造）。

v1.23.61 相对 v1.23.60

【主题】`run()` 空题守卫 —— 拒绝运行，不凭空产出、不花钱。

【问题（健壮性探针扫出来的）】退化输入 9 例（空 / 纯空白 / 单字 / 纯标点 /
只有问号 / 引号反斜杠 / 换行 / emoji / 5500 字长题）**没有一个把引擎打挂** ——
这部分是好的。但 **`run("")` 照样跑了，产出 2 个候选**：

· 空题没有任何可研究的东西，跑下去只会产出**凭空编造的候选**
  （违背「没有读数就不假装 / 未对齐如实说」这条红线）；
· 而且**白花一次调用**。

app 那边有挡（`server.py`：`if not question: 400`），但**引擎是库** ——
任何脚本（包括我自己的探针）都能直接传空串。

【修法】`run()` 在**任何 LLM 调用之前**检查 `str(question).strip()`：
为空 ⇒ 立刻返回结构化拒绝：

    refused = {"reason": "empty_question", "why": "…"}
    views = {}   llm_calls = 0   llm_tokens = 0

★ 不抛异常（会打断调用方）；也不用 `paused`（那是"没跑完"，这是"不该跑"）。

---

★ v1.23.61 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.61.py`（26819 行 / 纯 CRLF）+ 冒烟新判据
`check_v12361_empty_guard` + 变异体 M112 + 本段。

**改了什么**：`run()` 加空题守卫（13 行）；版本号两处。3 个改动块 / 删 2 行 / 增 15 行；
无新符号（325 / 589）；无新配置键。

**验收**：冒烟 261 ✓ / 0 ✗（含补线的 `check_p0_156_units`）；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 110/110（M112 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据四臂：空题被拒 + **零 LLM 调用**（拒绝必须免费）+ 纯空白同样拒 +
单字题不被误拒（守卫不能变成"见谁都拒"）。

**一处判据自查**：第一版断言写成 `int(r.get("llm_calls") or -1) == 0`，
而值就是 `0` ⇒ `0 or -1` 得 `-1` ⇒ 假红。改成直接比较（`== 0`）。
**`or` 在值为 0 时会被吞 —— 这条坑我自己记过，还是踩了。**

**未做**：`shape_limit` 取值扫描（≈¥12）；圈内恢复（需先做确定性改造）。

v1.23.60 相对 v1.23.59

【主题】快照记**层内进度** —— 被杀之后能看见"死在第几圈"。

【问题】检查点原来只在**层完成**时才有该层状态。一层跑到第 5 圈被杀，
快照里只知道"这层没完成"，`rounds_run` 只有已完成层的；**死在第几圈查不到**。
估预算也只能按层算，不能按圈算（实测一层 4~7 圈，时长差 2 倍）。

【修法（只记录，不恢复）】
  · `_layer_goal_now` —— 三个执行器（serial / 并行 / 分层阶段）**每圈都会走到这一处**
    ⇒ 在这一处记 `_layer_progress[entry]`：
    `rounds_done` / `candidates` / `amps` / `threads` / 本圈目标读数；
  · `_ckpt_snapshot` 把它与 `goal_hist`（跨圈目标读数历史）一起写进快照；
  · `run()` 起跑清空 `_layer_progress`（同一实例可能被复用）。
  ★ **续跑一个字没改**：`load_resume_snapshot` 不读这两个字段，截断层照旧"整层重跑"。

【为什么不做圈内恢复】`seeds` / `carry` 由**上一圈 View** 派生、**不是纯函数** ⇒
中途恢复会得到"另一条轨迹"，却挂着同一个 `run_id` 和正常完成标记 ——
这比"整层重跑"更危险（整层重跑至少是一次干净、自洽的跑次）。
详见 `docs/圈内检查点-设计.md` §三（含两步走方案与第 2 步的前置条件）。

---

★ v1.23.60 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.60.py`（26806 行 / 纯 CRLF）+ 冒烟新判据
`check_v12360_layer_progress` + 变异体 M111 + 本段。

**改了什么**：每圈记层内进度；快照多两个字段（`layer_progress` / `goal_hist`）；
起跑清空。5 个改动块 / 删 2 行 / 增 26 行；无新符号（325 / 589）；无新配置键。

**验收**：冒烟 259 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 109/109（M111 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
判据四臂：快照里 `rounds_done == rounds_run` · `goal_hist` 条数 == 圈数 ·
**续跑侧返回键集合没变且函数体里没有这两个字段**（AST 取体，不用字符串切）·
已完成的快照仍拒绝续跑。

**一处判据自查**：第一版判据说"续跑侧没读"用了 `split("\ndef ")` 切函数体，
结果把后面 **7700 行**（类方法缩进 4 格）全吞进来 ⇒ 判据测的是整份文件、永远判红。
改用 **AST** 精确取（76 行）后通过。**抠函数体一律走 AST。**

**未做**：圈内**恢复**（要先把 `seeds`/`carry` 改成只依赖 pool 的纯函数，再证等价性）；
`shape_limit` 取值扫描。

v1.23.59 相对 v1.23.58

【主题】修行层增益**换信号**：Heaps 边际（稀疏）→ 相对新增率（总在）。

【问题（实测，¥0.4 的探针）】`stop.gain_floor` 的输入是 `refinement_gain`，
修行层取 `excavate`（Heaps 边际 ΔV/Δn）。那个读数有两道门：
`_lg_aspect_margin` 要 `len(hist) >= 3` 才开算，退化增长还**返回 None**。
探针实测 4 圈里 **3 圈是 None**：

    圈  excavate  n_aspects
    1   None      16
    2   None      16
    3   0.0       14
    4   None      20

⇒ 增益恒 None ⇒ **早停判据永远不触发**。不是阈值问题，是**信号太稀疏**。

【换法】修行层增益 = **相对新增率** = `max(0, Δn_aspects) / 上圈 n_aspects`
  · 只要有两圈、上圈 n>0 就有值 ⇒ 不再稀疏；
  · 语义仍是「新增趋零」（新增长不动 ⇒ 增益→0 ⇒ 迭代饱和）；
  · 0..1 有界，与 `gain_floor` 同量纲。

【保留不动】
  · `excavate` 读数本身（四层目标的公开读数 —— 目标定义是红线，不改）；
  · 其余三层方向（settle / fuse / crystallize 仍是「本圈 − 上圈」）；
  · **老产物没有 `n_aspects` ⇒ 退回 Heaps 算路**（逐字不变）。
  ★ 无新配置键；`gain_floor` 默认 0 ⇒ 判据直接返回 ⇒ 出厂零行为差。

---

★ v1.23.59 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.59.py`（26782 行 / 纯 CRLF）+ 冒烟新判据
`check_v12359_gain_signal` + 变异体 M110 + 本段。

**改了什么**：`refinement_gain` 修行层分支优先用相对新增率，老产物退回 Heaps。
5 个改动块 / 删 3 行 / 增 17 行；无新符号（325 / 589）。

**验收**：冒烟 258 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 108/108（M110 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据的夹具是**实测真实读数**（16, 16, 14, 20）：同一组数据旧信号全 None，
新信号算出 `[0.0, 0.0, 0.4286]` 并在连续两圈 0 后触发；另三臂：层面在长不许停 ·
老产物退回 Heaps · 其余三层方向未变。

**未做**：更细粒度检查点（圈内），见下一版。

v1.23.58 相对 v1.23.57

【主题】晋升门槛 `_eff_n` 与每个 shadow 的**拦截原因**进产物。

【问题（可达性审计留下的洞）】`eml_promote` 里自适应后的实际门槛 `_eff_n` 只活在
函数内部，产物里查不到。于是「库 11 < 冷启阈值 20 ⇒ 门槛从 3 降到 1，但 3 个 shadow
仍被质量闸挡下」这句话**只能是推断**。
**「我推断它降到了 1」与「产物里写着 1」是两件事。**

【修法】`eml_promote(..., trace: dict = None)`：
  · 传了就填 `eff_n` / `promote_n` / `adaptive` / `n_lib` / `cold_lib` /
    `shadow`（逐条 verdict）/ `shadow_verdicts`（分类计数）；
  · 调用方挂成 `_blk["promote_trace"]`；
  · 产物 md 正文加一行：
    `↳ 晋升门槛 ≥1（名义 3；自适应：库 11 < 冷启 20 ⇒ 降到 1）｜shadow 拦截：n_short×3`
  ★ 五类 verdict：`n_short` / `contra` / `quality_down` / `cost_only` / `promoted`
    —— 否则「0 升级」分不清是「没东西可升」还是「有但被挡住」。
  ★ 无新配置键；不传 `trace` ⇒ 行为**逐字不变**。

---

★ v1.23.58 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.58.py`（26768 行 / 纯 CRLF）+ 冒烟新判据
`check_v12358_promote_trace` + 变异体 M109 + 本段。

**改了什么**：`eml_promote` 增加可选 `trace` 参数并逐条记录拦截原因；调用方挂进产物；
产物 md 加一行晋升门槛。14 个改动块 / 删 4 行 / 增 54 行；无新符号（325 / 589）。

**验收**：冒烟 257 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 107/107（M109 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
开发期 15 项全过，含**旧版对照**（不传 `trace` 时返回值与条目状态含 weight **逐字相同**）。

**未做**：`gain_floor` 去留（A 承认不可用 / B 换信号改语义）；`shape_limit` 取值扫描；
更细粒度检查点。

v1.23.57 相对 v1.23.56

【主题】把 `goal_trace` **跨圈接上** —— `stop.gain_floor` 从此才走得到。

【问题（A/B 追查发现的结构性缺陷）】引擎**每圈新建 view**（`view = dg.run(inp)`，
旁边注释原话「每圈新建 view、只 return 最后」），而 `_layer_goal_now` 把当圈读数
只 append 到**当圈那个 view** 上 ⇒ 下一圈换对象，历史就丢。产物实测：

    层 0  跑 4 圈 → goal_trace 1 条
    层 1  跑 7 圈 → goal_trace 1 条
    both  跑 7 圈 → goal_trace 1 条
    all   跑 2 圈 → goal_trace 1 条

而 `layer_gain_stop_signal` 的第一道门是 `len(prev) >= _LG_STOP_FLAT_N + 1`（=3）
⇒ 门**恒关** ⇒ **`stop.gain_floor` 在任何取值下都不会触发**。
这是「结构性不可达」：调用点在、逻辑对，被数据流挡死 —— 不是阈值太严。
（原计划的 `gain_floor` 取值扫描 6/8/12 **因此作废**：只会扫出三个"零触发"。）

【修法】只搬数据、不动判据：
  · 每层历史挂在**引擎**上（`self._goal_hist[entry]`），`_layer_goal_now` 追加到它；
  · 每圈把**完整历史**挂回当前 view（`view.goal_trace = list(_h)`）；
  · `run()` 起跑清空（同一实例可能被复用跑多次，不清会污染本跑的早停判据）。
  ★ `gain_floor` 默认 0（关）⇒ 出厂行为**逐字不变**（那条历史根本没人看）。

---

★ v1.23.57 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.57.py`（26718 行 / 纯 CRLF）+ 冒烟新判据
`check_v12357_goal_trace_carry` + 变异体 M108 + 本段。

**改了什么**：目标读数历史挂引擎 + 每圈挂回 view + 起跑清空。4 个改动块 / 删 3 行 / 增 20 行；
无新符号（325 / 589）。

**验收**：冒烟 256 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 106/106（M108 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据拆两段：真入口证「`goal_trace` 条数 == `rounds_run`」，纯函数证「3 条低增益
历史**必须触发**」—— 因为 mock 产物是固定文本，修行层第 2 圈就被"复述/空转"自然停了，
走不到第 3 圈，"触发"这一支只能靠纯函数证。开发期另有**旧版对照**（v1.23.56 同条件
仍恒 1 条）。

**未做**：`gain_floor` 取值扫描（**通道刚修好，可以做了**，但那要真跑 ≈¥12）；
`shape_limit` 扫描；更细粒度检查点。

v1.23.56 相对 v1.23.55

【主题】快照记账改成**跨窗口累计**（`llm_calls` / `llm_tokens` 不再被续跑抹掉）。

【问题（A/B 真跑暴露）】快照里的计数取自 `self.llm.total_calls` —— 那是**按实例**
  的计数器。续跑新建实例就归零 ⇒ 第二个窗口的快照只记本窗口。实测：A 臂那条
  `V1255A` 实际花了 **230 calls**，快照里写的是 **97**。
  按这个数结算成本，**前面那个窗口的钱查不到** —— 直接打穿 v1.23.50 立命的
  「被杀跑次也能结算成本」。我这次只能另建外部账本兜底。

【修法】
  · `load_resume_snapshot` 把快照里的 `llm_calls` / `llm_tokens` 一起返回；
  · `run()` 拿到续跑快照时记进 `self._ck_base`（跨窗口基线），并把基线打进日志；
  · `_ckpt_snapshot` 落盘写 **累计 = 基线 + 本实例**，同时**另存**
    `window_calls` / `window_tokens` 保留本窗口读数。
    ⇒ **结算看累计，分析看窗口**，两个口径都能读。
  · **无新配置键**；不传 `resume_ckpt` ⇒ 基线为 0 ⇒ 数值与旧版**逐字相同**。

【判据更新】`check_v12350_resume` 里那条**静态字面量**断言
  `"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),` 随实现失配 ⇒
  改成新字面量（登记式）。该 check 本来就有行为级断言（快照 `llm_calls > 0`），
  静态那条只是顺带指纹，留着继续挡"记账字段被删"。

---

★ v1.23.56 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.56.py`（26701 行 / 纯 CRLF）+ 冒烟新判据
`check_v12356_ckpt_cumulative` + 变异体 M107 + 本段。

**改了什么**：快照记账累计 + `window_*` 两口径；`load_resume_snapshot` 带回计数；
`run()` 设基线。7 个改动块 / 删 5 行 / 增 29 行；无新符号（325 / 589）。

**验收**：冒烟 255 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 105/105（M107 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据两窗口真入口：第二窗口 `llm_calls` **恰好等于** 基线 + 本窗口，
且 `window_calls` 严格小于它（两口径分得开）；开发期另有**旧版对照**
（同链路跑 v1.23.55 ⇒ 第二窗口归零、没有 `window_calls` 字段）。

**未做**：`shape_limit` 取值扫描（6/8/12，各一跑 ≈¥12）；给
`gain_floor` / `eml_adaptive` / `eml_semantic_merge` 造可触发场景；更细粒度检查点。

v1.23.55 相对 v1.23.54

【主题】`paused` 时的缺层从「❌ 缺陷」改成「⏸ 待续」。

【问题（A/B 真跑时亲眼看到）】墙钟预算暂停的跑次会打：

    ❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的
    · 元：未记录原因（这是缺陷）

可暂停时缺层是**设计**（续跑会接着跑）。这条提示会让人去查一个不存在的 bug；
更糟的是它把 `layer_gap` 写进产物 ⇒ **下游任何「缺层 = 缺陷」的判据都跟着误判**。

【修法】`_layer_guard` 把缺层拆两拨：
  · 在 `pending_layers` 里且 `packed["paused"]` ⇒ 记 `paused_gap`，说"待续"
    （提示 `resume_ckpt`），**不写** `layer_gap`；
  · 其余 ⇒ 仍是真缺陷，`layer_gap` 原样大声报。
  ★ 真缺陷**不许**被暂停豁免：暂停时某层既没产出、也不在 pending 里，照样报红。
  ★ 无新配置键；**非暂停路径逐字不变**。

---

★ v1.23.55 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.55.py`（26677 行 / 纯 CRLF）+ 冒烟新判据
`check_v12355_paused_gap` + 变异体 M106 + 本段。

**改了什么**：`_layer_guard` 拆分「待续 / 真缺」两条分支；docstring 补说明；
版本号两处。4 个改动块 / 删 14 行 / 增 39 行；无新符号（325 条 / 589）。

**验收**：冒烟 254 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 104/104（M106 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据三臂：暂停+pending ⇒ 只记 `paused_gap`；暂停+非 pending ⇒ 仍报 `layer_gap`；
非暂停 ⇒ 旧行为逐字不变（旧判据 `check_layer_guard` 同时仍绿）。

**未做**：元层单层对照（`route=["all"]`）**实测不成立** —— 层守卫直接拒绝
（「需要至少 2 个上游 view，当前只有 0 个」），只花了 1 次调用。要定性元层那个
分歧只能再跑一次全跑（≈¥7.8）。

v1.23.54 相对 v1.23.53

【主题】并行跑次也能被**墙钟预算**截住、也能**续跑**。

【问题】`max_minutes` 原来只挂在 `_run_serial` 的**层间**守卫上 ⇒ 并行模式
  （A/B/C + D~H）设了预算也照跑到天亮，宿主一回收就**全丢**；而续跑入口又
  **硬拒非 serial** ⇒ 强杀之后连"续"都续不了。**预算保护对并行是空的** ——
  而真跑最常见的死法恰恰是"跑太久被宿主回收"。

【修法】
  · `_wall_clock_over()` 收成**唯一**判据（原来 serial 里内联了一份）。
  · **三个**单层执行器的圈边界都判（漏一个，那些模式就还是裸跑）：
    `_run_layer`（serial + A/B）／C 模式自己的圈循环／`_run_layer_stage`（D~H）。
    到点 ⇒ 该层进 `_paused_rest`，`stop_reason` 带「墙钟预算」标记 ⇒ 整跑 `paused`。
  · serial 层间守卫从「重绑」改「**并集**」：截断层有 view 但仍未跑完，
    重绑会把它丢掉（续跑于是当它已完成 —— 分片跑永远跑不完整）。
  · `load_resume_snapshot`：不再拒绝并行快照，改记源模式；并把带标记的层从
    views/pools **摘掉**（截断层不算完成，续跑重跑它）。
  · `run()` 派发：并行续跑**一律按 serial 跑剩余层**，产物记 `resumed_serial`
    —— 降级留痕，不静默。
  · **无新配置键**；`max_minutes` 默认 0 / 不传 `resume_ckpt` ⇒ 逐字零行为差。

【一个必须知道的细节】`stop_reason` 是**逐圈在循环体末尾**拼的，圈首 break 会跳过
  那一步 ⇒ 标记必须**直接盖到 view 上**。第一版只写了 `_budget_stop_note`，
  判据当场逮到「续跑什么都不重跑」——**假修**。

【判据更新】`check_v12350_resume` 里「mode 非 serial ⇒ 必须拒绝」那条负对照，
  编码的是旧语义 ⇒ 改成「`mode=B` ⇒ 允许 + 必须记下 `src_mode`」。
  这不是放宽，是把断言对准新语义（「题面不同 ⇒ 拒绝」不变）。

---

★ v1.23.54 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.54.py`（26652 行 / 纯 CRLF）+ 冒烟新判据
`check_v12354_parallel_wall_clock` + 变异体 M105 + 本段。

**改了什么**：`_wall_clock_over()` 唯一判据；三个单层执行器圈边界判墙钟 + 标记
直接盖到 view；serial 层间守卫改并集；续跑放开并行 + 摘截断层；派发降级记
`resumed_serial`。12 个改动块 / 删 25 行 / 增 110 行；AST 登记 +1 符号（589）。

**验收**：冒烟 253 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 103/103（M105 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
开发期 16 项全过：真入口证明「A 模式到点 ⇒ paused + 标记 + EML 零写入」，
续跑证明「完成的层不重跑、截断层重跑、层 0 产物逐字复用」。

**未做**：下一轮 A/B（须冻结 bandit + 同口径比 S，**要花钱，等你点头**）；
并行模式的「层内更细粒度」检查点（现在是圈边界，一个圈跑不完仍会超时）。

v1.23.53 相对 v1.23.52

【主题】记忆库目录**一处解析**：`bandit` 不再偷偷写回仓库。

【问题（挂账「目录两处解析未收敛」）】记忆库的落点在**两个地方**解析：
  · episode / playbook → `playbook.dir`（空则 `eml_dir()`）
  · bandit → `auto.bandit.dir`（空则 `eml_dir()`，**恒指仓库**）
  ⇒ 任何设了 `playbook.dir` 的调用方（冒烟、A/B 脚本、想隔离库的人）都会让
  **bandit 偷偷写进生产 `dgtf_memory/`**。冒烟隔离因此要三个旋钮
  （`output.save_dir` + `playbook.dir` + `auto.bandit.dir`）—— **漏一个就污染**，
  这类「漏一格」的事故本项目已经栽过（一次冒烟的跑次把真实条目的证据数抬高）。

【修法】
  · 新增唯一解析 `eml_store_dir(cfg)`，三处都走它：
    `auto.bandit.dir`（显式，**仍优先**） ＞ `playbook.dir` ＞ 仓库根 `dgtf_memory/`。
  · 为什么是**模块级函数**而不是实例方法：bandit 的**载入**发生在实例属性
    `_eml_cfg` 赋值**之前**，用实例状态会静默回落到 `eml_dir()` —— 那正是要修的
    bug 本身。读 `self.config` 没有这个顺序问题。
  · `_load_bandit` / `_save_bandit` 各加一个 `fallback` 形参（默认 None ⇒ 旧行为）。
  · **无新配置键**；生产默认（`playbook.dir` 空）解析结果与旧版**逐字相同**。

---

★ v1.23.53 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.53.py`（26567 行 / 纯 CRLF）+ 冒烟新判据
`check_v12353_eml_dir_single` + 变异体 M104 + 本段。

**改了什么**：新增 `eml_store_dir()`（唯一解析）；`_load_bandit` / `_save_bandit`
加 `fallback`；三处调用点统一；版本号两处。10 个改动块 / 删 9 行 / 增 30 行；
AST 登记 +1 个符号（588）。

**验收**：冒烟 252 ✓ / 0 ✗（含新判据）；`--phase all` PASS 319 / FAIL 0；
AUDIT 69/0；变异体 102/102（M104 判红 = 判据有牙）；app 自检 368/0；
两版 `load_config` 逐字相同。**不跑真跑**：默认路径解析结果不变，能力由
「真入口：`playbook.dir` 里种的 bandit 能被读到、写也只写那儿」证明；
另有**旧版对照**（同 cfg 跑 v1.23.52 ⇒ 仍写 `eml_dir()`）。

**未做**：并行模式续跑（★ 查清了：`max_minutes` 只挂在 `_run_serial` 上 ⇒
并行模式**根本不会暂停**，所以并行续跑只服务「被强杀」；要做得重做并行调度器的
半程状态，风险最高、收益最低，等真有并行跑次再说）；下一轮 A/B（须冻结 bandit
+ 同口径比 S）。

v1.23.52 相对 v1.23.51

【主题】`paused` 跑次**不写 EML 库**：半程样本不是证据。

【问题】上一版只保证「不重复调用就不多写」。可墙钟预算暂停的跑次**仍会写一条
  半程样本**；续跑跑完后同一个 `run_id` 又写一条完整样本（读数不同 ⇒ 幂等守卫
  **按设计**放行）⇒ 一个跑次还是**两条证据**：`used_outcomes` 记两笔、`weight`
  罚两遍。清账脚本 `_fix_eml_dup_20261016.py` 收拾的正是这一类 —— 上一版只堵了
  「重复调用」这一个口子，没堵「同一跑次分两次收尾」这个口子。

【修法】
  · `_eml_finish` 在 `off` 判完之后**先判暂停**：产物带 `paused` 或
    `pending_layers` ⇒ 直接返回（`skipped_paused`）—— **连库目录都不建、也不抢锁**。
  · 判据取自**产物本身**（`run()` 在调 `_eml_finish` 之前就写好了这两个键），
    所以不依赖调用方传参，任何入口口径一致。
  · **成本不会丢**：`llm_calls` / `llm_tokens` 仍在产物与快照里 ⇒ 暂停/被杀的
    跑次照样能结算。
  · **无新配置键**；`max_minutes` 默认 0 ⇒ 守卫条件恒假 ⇒ 默认行为逐字不变。

---

★ v1.23.52 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.52.py`（26546 行 / 纯 CRLF）+ 冒烟新判据
`check_v12352_paused_no_eml` + 变异体 M103 + 本段。

**改了什么**：`_eml_finish` 加「暂停不写库」守卫（off 之后、取锁之前）；版本号两处；
docstring 补一句。4 个改动块 / 删 2 行 / 增 18 行。

**验收**：冒烟 251 ✓ / 0 ✗（含新判据）；`--phase all` PASS 319 / FAIL 0；
AUDIT 69/0；变异体 101/101（M103 判红 = 判据有牙）；app 自检 368/0；
两版 `load_config` 逐字相同。**不跑真跑**：默认 `max_minutes=0` ⇒ 守卫恒不触发，
真跑行为与 v1.23.51 逐字相同；能力由「真入口 `run(max_minutes=极小)` ⇒ 零写入」
的构造性判据证明，另有**旧版对照**（v1.23.51 同场景写 1 条）。

**未做**：并行模式续跑；记忆库目录解析归一（bandit 走 `eml_dir()`、不吃
`playbook.dir`）；下一轮 A/B（须冻结 bandit + 同口径比 S）。

v1.23.51 相对 v1.23.50

【主题】`_eml_finish` 幂等：**一个跑次只学一条 episode**。

【问题】A/B 真跑把 `_eml_finish` 调了两次（`run()` 内部已经调过一次）——于是每个
  跑次写出**两条完全相同**的 `episode`、`used_outcomes` 与 `weight` 被罚两遍
  （实测 7 个条目 weight 多扣 0.05/次，事后要靠清账脚本收拾）。
  为什么上一版没暴露：**「`run_id` 必须在 `_eml_finish` 之前盖章」是 v1.23.50 才修的**
  —— 在那之前内部那次拿到空 id，被「匿名跑次一律不写库」的闸挡掉，于是调用方那次
  看起来"正常"。**修好一个锁，会让原本被它挡住的 bug 显形。**

【修法】
  · `_eml_finish` 在**拿到跨进程锁之后、写 episode 之前**加守卫：已有**同 `run_id`
    且除 `t` 外逐字相同**的 `episode` ⇒ 直接返回（`dup_skipped`），不写库、不再罚 weight。
  · 判据用「读数逐字相同」而不是只看 `run_id`：墙钟预算 `paused` 的跑次也会写一条
    **半程样本**，续跑完成时读数不同 ⇒ **必须能写**，否则完整样本永远进不了库。
  · `_fullrun_V1250AB.py` 的双调用改成**条件补调**（只有真的没有 `playbook` 块、
    或那块是异常兜底时才补）。引擎守卫不能替代这一处：守卫返回的是 `dup_skipped`
    留痕，拿它覆盖产物会把学习块降级成空壳。
  · **无新配置键**；单次调用行为逐字不变。

【数据清账（独立提交）】`_fix_eml_dup_20261016.py` 把已脏的记忆库摘干净：
  `episodes` 99→97 行、`nogoods` 21→19 行、7 个条目 `weight` 按逆运算补回
  （L0001 `.30` / L0003 `.35` / L0004 `.50` / L0006 `.75` / L0007 `.75` /
  L0008 `.40` / L0009 `.75`）；`MEMORY.md` 不动（`t_used` 按 `run_id` 去重，
  证据数本来就是对的）。

---

★ v1.23.51 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.51.py`（26530 行 / 纯 CRLF）+ 冒烟新判据
`check_v12351_eml_once_per_run` + 变异体 M102 + 清账脚本 + 本段。

**改了什么**：`_eml_finish` 幂等守卫（锁内、写前，按「同 `run_id` + 读数指纹」判重）；
A/B 脚本改条件补调；记忆库清账。4 个改动块 / 删 2 行 / 增 34 行。

**验收**：冒烟 250 ✓ / 0 ✗（上版 249 ✓，+1 = 新判据）；`--phase all` PASS 319 / FAIL 0；
AUDIT 69/0；变异体 100/100（M102 判红 = 判据有牙）；app 自检 368/0；
两版 `load_config` 逐字相同（无新键）。**不跑真跑** —— 判据是「哪条通道会经过这行代码」，
答案是**只有重复调用才经过**，而重复调用正是要消灭的行为。

**未做**：并行模式续跑；`paused` 不写 EML；记忆库目录解析归一；下一轮 A/B
（须冻结 bandit + 同口径比 S）。

v1.23.50 相对 v1.23.49

【主题】断点续跑（复用已完成层）+ 快照记账 + `route` 死捕获 + 墙钟预算。

【问题】真实事故：今天 A/B 真跑被宿主回收**两次**（18.2 min / 12.7 min），烧掉约 ¥2
  而 **v1.23.49 的快照只能「留痕」不能「接着跑」** ⇒ 钱不可回收；连「这跑烧了多少」
  都查不出来（快照没记账）；快照里的 `route` 是**死捕获**（引擎从不设 `_route`）⇒ 恒 `[]`。

【修法】
  · `run(..., resume_ckpt=<快照路径>)`：复用快照里**已完成层**（不重跑、不再花那部分钱），
    并**还原其池**（下游层读上游池，池不还原则续跑结果与一次跑完不同）。
    层完成判据 = `_results[e]` 有值（该字段**只在层跑完后赋值**）。
    三道硬校验：状态可续（running/interrupted/paused）、题面逐字相同、**只支持 serial**
    （并行模式的 `_results` 由并发填）——不过就**按原样全跑并说明理由**，绝不静默混跑。
  · 快照加记账：`llm_calls` / `llm_tokens` / 各层 `rounds_run`。
  · 快照带 `mode`；`run()` 补 `self._route = list(route)`（记**生效** route）。
  · `run(..., max_minutes=N)`（默认 0 = 关）：层间墙钟预算 ⇒ 优雅停（快照 `paused`、
    产物交代 `pending_layers`）⇒ 切片跑完，避开宿主回收窗口。
  ★ **无新配置键** ⇒ 不传参时与 v1.23.49 **逐字相同**。

【验收】冒烟 248/0（+`check_v12350_resume`：构造性证明 + 两条负对照 + 预算优雅停）·
  verify 319/0 · AUDIT 69/0 · 变异体 99/99（+M101 续跑不跳过已完成层）。

★ v1.23.50 收束摘要：交付「断点续跑 + 快照记账 + route 修复 + 墙钟预算」；主文件 26498 行 /
  纯 CRLF / AST OK / 新增符号 2（`View.from_dict` / `load_resume_snapshot`）已登记 / 零新键。
  未做：并行模式（A/B/C/stage）的续跑（本版只支持 serial）。

v1.23.49 相对 v1.23.48

【主题】跑中快照（心跳落盘 + 孤儿回收）—— 修「`run()` 只在返回后写盘 ⇒ 宿主回收就全丢」。

【问题】实测：12:37 的 A/B 真跑（`_fullrun_V1248AB.py`）被宿主回收，**~24 分钟 / ~¥2 全丢**。
  `run()` 是 60 分钟级长跑，packed 只在 `return` 前组装、调用方只在返回后才写盘。

【修法】`run()` 起 **daemon** 心跳线程，每 `ckpt_interval`（默认 30s）把各层
  `View.to_dict()` **原子**落盘（`tmp` + `os.replace` ⇒ 强杀不留半份）；
  `recover_orphan_runs()` 把过期 `running` 回填 `interrupted` + `interrupted_why`（幂等）；
  新键 `runtime.live_checkpoint` / `runtime.ckpt_interval`（引擎 + yaml + app 三处同步）。
  ★★ **默认 true 是本项目「新键默认关 ⇒ 零行为差」惯例的唯一例外** —— 用户拍板：
    它是纯安全网（daemon 心跳 + 原子落盘），不碰任何引擎输出/结论，只决定「崩了能否找回」；
    12:37 已用 24 分钟 / ~¥2 证明「默认关」的代价是**全丢**。要回零行为差设 `false` 即可。
  ★ 自曝双 bug（本轮单独复现抓出）：`_ckpt_snapshot` 的 `dict(None)`（层中途无 View，
    **长跑中途是常态**）+ 未定义 `ENGINE_VERSION` —— 皆被 `except: pass` 吞
    ⇒ 安全网**从未落盘**。已修（None 守卫 + `__version__`）。

【验收】冒烟 **246/0**（+`check_v12349_run_ckpt`：回环 / 原子 / 过期回填 / **负对照** /
  **幂等** / 不起线程×2 / 起停闭环 / **出厂配置端到端真落盘**）· verify **319/0** ·
  AUDIT **69/0** · 变异体 **98 判红 / 98**（+M100 孤儿回收不判过期）。
  ★ 附带治理：冒烟「写生产记忆库」**三条泄漏全修**（LLM 桩未还原 / CLI+E2E 的
    playbook+save_dir / bandit 不吃 `playbook.dir`），工作树回退 + 证据归档
    （`_archive/v1.23.49/dgtf_memory_smoke_pollution_20261016/说明.md`）；
    CHANGELOG 补登 v1.23.44~48；app 标签「默认关」→「默认开」；陈旧判据**登记式**修复
    （`check_v1234_runtime` ×2 / `_probe_v1234_runtime.py` T12/T12b / AST 登记 `_beat`）。

★ v1.23.49 收束摘要：交付「跑中快照 + 孤儿回收（**默认开 = 惯例唯一例外**）」；主文件 26296 行 /
  纯 CRLF / AST OK / 新增 AST 符号 8（含内层 `_beat`）已登记 / 新键 2。
  未做（挂账）：记忆库目录两处解析未收敛 / 历史 ~72 条冒烟 episode 未清 /
  `_smoke_*.log` 入库口径矛盾；③ A/B 真跑另行重跑（`_fullrun_V1249AB.py`）。

> ★ **补登说明**（v1.23.49 轮发现）：v1.23.44 ~ v1.23.48 这五轮**只落了 `vNN_报告.md`，
>   漏了本文件的「每版一段」**。本版按各版**报告**补登（内容以报告为准，未新增判断）。

v1.23.48 相对 v1.23.47（补登）

【主题】P-3b EML commit 前**语义近重合并**（防冗余堆积）。

【问题】`eml_merge_candidate` 只按**精确** `(kind, cond, action)` 去重 ⇒ 同一条经验
  值差一点（`delta=1` vs `2`、`rate=0.30` vs `0.31`）就**另开一条** ⇒ 库只增不减。

【修法】`eml_merge_candidate(..., semantic_merge=False)`：精确键仍**优先**；为真时
  精确键不中再按**粗键**（`kind + cond.issue + action.key`）并入（证据累加）。
  新键 `memory.eml_semantic_merge: false`（引擎 + yaml + app 三处同步）。
  ★ 只影响「要不要新开一条」，不改学到的内容；`action.key` 不同**绝不并**（负对照）。

【验收】冒烟 245/0（+`check_v12348_eml_semantic`）· verify 319/0 · AUDIT 69/0 · 变异体 97/97（+M99）。

★ v1.23.48 收束摘要：交付「EML 语义近重合并（P-3b）」；主文件 26137 行 / 纯 CRLF / AST OK /
  零新符号 / 新键 1（`memory.eml_semantic_merge` 默认 false ⇒ 逐字零行为差）。

v1.23.47 相对 v1.23.46（补登）

【主题】P-2b 早停阈值 α 由 **AutoTune 跨跑建议**（backlog 遗留项）。

【依据】SOTA 点名 `static thresholds` 是学习回路失败模式（ReasoningBank, arXiv:2509.25140）。

【修法】**只建议不执行**：新纯函数 `autotune_suggest_gain_floor(episodes, base, step, min_n,
  quality_floor)` —— 有截断且中位质量不差 ⇒ 建议 α 抬 `step`；质量差 ⇒ 保持；证据不足 ⇒ 不建议。
  挂进 `autotune_phase_learn`（`suggested_gain_floor` / `gain_floor_why`）。红线守：
  **不写配置**（判据显式断言），采纳仍走既有 `autotune_apply_to_cfg`。**零新配置键**。

【验收】冒烟 244/0（+`check_v12347_gain_suggest`）· verify 319/0 · AUDIT 69/0 · 变异体 96/96（+M98）。
  本轮踩坑：**不能用「文件后面才定义」的模块常量当默认参数**（def 时求值 ⇒ NameError）。

★ v1.23.47 收束摘要：交付「早停阈值跨跑建议（P-2b）」；主文件 26115 行 / 纯 CRLF / AST OK /
  新增 AST 符号 1（已登记）/ 零新键。

v1.23.46 相对 v1.23.45（补登）

【主题】P-5 职责 S 口径**对称化**（先诊断后修）。

【诊断】真产物 `{S:0.0, C:0.25, R:0.0}` ⇒ S=0 是 **R=0** 拖的。根因：C 判**全文**、R 判
  **单句**，而 `_hit` 的覆盖率**按问项长度归一** ⇒ 问项跨句时 C 记、R 不记。
  ★ 「同一个 `_hit` 函数」≠「同一口径」—— 项目自留的注释成了假安心。

【修法】`duty_of_layer` / `duty_components` 加 `span_tolerant`；为真时 R 用**跨句窗口**。
  新键 `duty.span_tolerant: false`（三处同步）⇒ 默认逐字零行为差。

【验收】冒烟 243/0（+`check_v12346_duty_span`，**构造性复现** off `C=1/R=0/S=0` → on `R=0.5/S=0.67`）·
  verify 319/0 · AUDIT 69/0 · 变异体 95/95（+M97）。

★ v1.23.46 收束摘要：交付「职责 S 跨句口径（P-5）」；主文件 26061 行 / 纯 CRLF / AST OK /
  零新符号 / 新键 1（`duty.span_tolerant` 默认 false）。

v1.23.45 相对 v1.23.44（补登）

【主题】P-4 **输出内**逐字复读率读数（补结构盲区）。

【依据】Reflective Budget Governor（Zenodo 22844856）：集合式 n-gram/trigram 信号对
  「同一输出内部」的逐字复读**结构盲**（两次灾难性退化都没被发现）；原有
  `drop_rehashes` / `sem_stagnation` 都是**与上游比**。

【修法】新纯函数 `output_repetition(text, n=3)`：输出内重复 n-gram 占比（太短/空 ⇒ None）。
  接进 `ing` 环节零成本读数，**两个出口**（`_READING_LABELS` + `_QUANT_LABELS`），
  `verdict = repeat`（>= 常量 `_OUTREP_ALERT 0.3`）/`ok`。**零新配置键** ⇒ 出厂逐字不变。

【验收】冒烟 242/0（+`check_v12345_output_rep`）· verify 319/0 · AUDIT 69/0 · 变异体 94/94（+M96）。

★ v1.23.45 收束摘要：交付「输出内复读率读数（P-4）」；主文件 26041 行 / 纯 CRLF / AST OK /
  新增 AST 符号 1（已登记）/ 零新键。

v1.23.44 相对 v1.23.43（补登）

【主题】P-3 学习闭环：EML 阈值**冷启自适应**。

【问题】查真库（11 条）：3 条 `shadow` 卡在 `n_evidence=1 < _EML_PROMOTE_N(3)` ⇒ **升级 0**；
  遗忘侧 `recency < 0.05` 需 age > 60 天 ⇒ **遗忘 0**。两者都是 SOTA 点名的
  cold start + static thresholds（ReasoningBank, arXiv:2509.25140）。

【修法】`eml_promote(..., adaptive=False)` / `eml_sweep_forget(..., adaptive=False)`：
  adaptive 且库 < `_EML_COLD_LIB(20)` ⇒ 晋升门槛降到 1；退休门槛随库规模放大。
  接线读 `memory.eml_adaptive`；新键 `memory.eml_adaptive: false`（三处同步）⇒ 默认逐字零行为差。
  ★ 红线守：只改「**何时**升/忘」，不改「学什么」。

【验收】冒烟 241/0（+`check_v12344_eml_adaptive`）· verify 319/0 · AUDIT 69/0 · 变异体 93/93（+M95）。

★ v1.23.44 收束摘要：交付「EML 冷启自适应（P-3）」；主文件 26004 行 / 纯 CRLF / AST OK /
  零新符号 / 新键 1（`memory.eml_adaptive` 默认 false）。

v1.23.43 相对 v1.23.42

【主题】P-2 **早停**（backlog 第 2 项）：单标量增益 + 配置式阈值。

【问题】停因分布：层 both **5 圈走满**才「体力耗尽」（未触发任何判据）；饱和信号散落在
  多个判据里（`excavate` 边际率 / `settle`·`fuse` 连续不涨 / `sem_stagnation` / 复述 streak），
  且触发晚。

【修法（SOTA 最优停止）】依据 **arXiv:2608.10729**：自反式迭代的最优停止是**单一、阶段无关
  阈值 α⋆**（把策略搜索降到一个标量），实测优于固定轮数与 UCB。
  · 新纯函数 `refinement_gain(entry, goal, prev)`：各层用**自己**的目标读数，增量方向**统一**
    成「越大越有进展」（修行 `excavate` 取「上一圈−本圈」，其余取「本圈−上一圈」）；
    没读数 / 没上一圈 ⇒ **None**。
  · 新纯函数 `layer_gain_stop_signal`：增益 < 阈值**连续 N 圈** ⇒ 停。
  · 接线 `_goal_stop_signal`：先逐层判据，未命中再看单标量早停。
  · 新配置键 `stop.gain_floor: 0.0`（引擎 + yaml + app 三处同步）。
  ★ **默认 0 = 关 ⇒ 逐字零行为差**。

【验收】
  · 冒烟 **240 ✓ / 0 ✗**（+`check_v12343_gain_stop`：方向统一 / None / 默认关 / 饱和命中 /
    **负对照**有进展不误停）；verify **PASS 319 / FAIL 0**；AUDIT **PASS 69 / FAIL 0**；
    变异体 **92 判红 / 92**（+M94 单标量早停失效）。
  · 全 mock，零 API。

★ v1.23.43 收束摘要：交付「早停单标量 + 配置阈值（P-2）」；主文件 25973 行 / 纯 CRLF / AST OK /
  新增 AST 符号 2（已登记）/ 新配置键 1（`stop.gain_floor` 默认 0）⇒ 默认逐字不变。
  未做：α 由 AutoTune 跨跑学习（列为 P-2b）。

v1.23.42 相对 v1.23.41

【主题】P-1 **上下文裁剪**（backlog 第 1 项，成本最大杠杆）。

【问题】真跑 `_fullrun_V1236FULL` 143 calls / 1.15M tok / 57min，单次均值 8059、最大 32297，
  **最贵 20% 调用占 46.5% token 且集中后段圈**。根因：`View.shape_of` **无窗口**渲染整个
  view（候选/&/线头/探针/悬置/裁决…全量），而 `_expand_from_views` 每圈把它当 `views_text`
  重灌 ⇒ 后段圈单次 prompt 随圈数上涨。（对照：`_pool_text` 已 `[-8:]` 窗口化，`shape_of` 漏了。）

【修法（SOTA observation masking：保留最近 N、更老换结构化占位，成本↓52%）】
  · `View.shape_of(v, limit=0)`：`limit>0` ⇒ 每类只列最近 N 条 + 表头标总数；`limit=0` **逐字不变**；
  · `_expand_from_views` 读 `spiral.shape_limit`（默认 0）传入；
  · 新增配置键 `spiral.shape_limit: 0`（引擎 + yaml + app 三处同步）。
  ★ 默认 0 = 不限 ⇒ **零行为差**；开启才裁剪。

【验收】
  · **零行为差**：`shape_of(v)` 与 v1.23.41 **逐字相同**（2308 字符）。
  · **纯函数压缩**：`limit=8` 2308 → 1016（**↓56%**，48 候选/15 & 的真实规模）。
  · **接线可达**：造大 upstream view 调 `_expand_from_views` ⇒ user prompt 5106 → 2534（**↓50%**）。
  · 冒烟 **239 ✓ / 0 ✗**（+`check_v12342_ctx_shape`）；verify **PASS 319 / FAIL 0**；
    AUDIT **PASS 69 / FAIL 0**；变异体 **91 判红 / 91**（+M93 窗口不生效）。
  · 全程 **mock，零 API**。

★ v1.23.42 收束摘要：交付「shape_of 窗口化（P-1）」；主文件 25908 行 / 纯 CRLF / AST OK /
  零新 AST 符号（`shape_of` 加形参）/ 新配置键 1 个（`spiral.shape_limit` 默认 0）；
  默认零行为差，开启后 views_text ↓56%、expand user prompt ↓50%。未做：未跑真跑对表
  （成本下降由构造性判据 + 接线单元探针钉住）。

v1.23.41 相对 v1.23.40

【主题】运行质量问题修复 + 缺漏机制优化（P1~P4）。来源：对 8 个真实产物 × 21 个层实例
  的诊断（`_诊断_v12341_运行质量问题.md`）。

【P1 · crystallize 恒 0.500 —— 时序颠倒（修）】8 个产物里元层无一例外
  `crystallize=0.500`。根因：`crystallize = 命中四件事/4`，「结晶+回看」两件事来自
  `view.meta_closure`，而它在**收尾**才赋；但计数点 `_layer_goal_now` 在**圈循环内**
  每圈末调 ⇒ 层停止那刻恒只数到「决策+行动」= 2/4。**真值反证**：读最终 view 的
  原始来源 = 4/4 = 1.000。修法（零新 AST 符号）：抽 `_LG_LABELS` 唯一真相源 +
  删前段内联渲染 + `_finalize_layer_common` **收尾重算并刷新** `goal_now`/`goal_verdict`。
  ★ 不动 `goal_trace`（逐圈历史）与停止判据（须用当圈值实时决定）。

【P2 · excavate 方向口径矛盾（修，不改值）】模块声明「每条读数越大越接近目标」+
  docstring「读数 = 1 − 边际新增」说「大=好」；实现（margin）+ 判据⑫ 说「小=好」。
  修：声明/docstring 标 `excavate` 为**距离型**（越小越接近），`goal_verdict` 加
  「（边际新增率·趋零即挖尽）」提示。★ 只动注释/文档/显示，取值与判据一字不动。

【P3/P4 · 深查后判「按设计」+ 归因补全】P3「体力耗尽…未触发任何停止判据」：各判据
  需 ≥2 圈方生效（`excavate` 更需 hist≥3），短跑本就该截断；P4「自省连续…未消化」：
  走 `carry_streak>=2` + 推迟逻辑，产物已渲染 `carry_check.notes`。⇒ 非 bug。
  优化：截断消息附**末圈近阈读数**；自省未消化停因附**未消化点名**。★ 只加文本，
  不改停止决策。

【验收】
  · 冒烟 **238 ✓ / 0 ✗**（新增 3 条：`check_v12341_goal_fresh` / `_excavate_dir` /
    `_attribution`；P1 判据对**改前 v1.23.40 天然判红** ⇒ 有判别力）。
  · verify `--phase all` **PASS 319 / FAIL 0**；AUDIT **PASS 69 / FAIL 0**。
  · 变异体 **90 判红 / 90**（新增 M89 收尾不刷新 / M90 显示丢提示 / M91 截断不附近阈 /
    M92 未消化不附点名）。
  · **全链路检测**：静态 0 断链 · 动态四层全产出 · **元层 `crystallize` 由恒 0.500
    → 1.000**（时序修好，真实度量不再恒值）。

★ v1.23.41 收束摘要：交付「P1 读数时序修复 + P2 口径统一 + P3/P4 归因补全」；主文件
  25882 行 / 纯 CRLF / AST OK / 零新 AST 符号 / 零新配置键；验收全绿（冒烟 238·verify 319·
  AUDIT 69·变异体 90 全红）；全链路元层 crystallize 0.500→1.000 证明时序修好。未做：
  未跑新真跑（P1~P4 全为默认行为/显示侧，效果由构造性判据 + 全链路 mock 覆盖）。

v1.23.40 相对 v1.23.39

【主题】两件事：① 回喂 **stage 兜底**（声明入库带真实环节名）；② 放宽表 **8→12** + 加「强制放宽」开关。

【问题①（真跑缺口）】v1.23.38 的池复用式回喂要求 `record["stage"] == _st` 才命中；
  但按需声明**全部**发生在 `LLM.call(stage=None)`（展开主路径不传 stage）⇒ 入库
  record 的 `stage` 为空 ⇒ **回喂在真实调用图上从未生效**（v1.23.39 R1：4 次声明
  全 `stage=None`、`[WEB-BACKFEED]` 0 次）。探针之所以绿，是**显式传了 stage**。

【修法①】两处，不新增 AST 符号：
  · `_infer_stage_from_stack` 跳过元组加 `_web_need_report` —— 否则会把自己当环节名；
  · `LLM._web_need_report` 在 stage 为空时**兜底**取真实环节名再入库；
    兜底只在真有声明时算（不声明零开销），取不到仍用空串（宁可匹配不上，不许猜错）。

【问题②（遗留改判）】v1.23.39 遗留「放宽表可扩 `decompose_*`」。实测（R1/R2）原本
  指向不扩（拆解触发仅 1~2 次）；但用户口径反转：**「扩也无妨，先强制它使用」** ⇒ 本轮扩。

【修法②】不新增 AST 符号：
  · `_TICK_WEB_RELAX` **8→12**：加 `decompose_normal/hybrid/koan/from_pool` 四兄弟；
  · 圈级心跳取 `web_search.relax_force`：`true` 时**每圈**无条件走全表放宽（不再
    要求「上一圈零增量」），`why` 标 `[强制放宽]`；
  · 新增配置键 `web_search.relax_force: false`（引擎 `DEFAULT_CONFIG` + `dgtf_config.yaml`
    + `dgtf_app/params.py` 三处同步）。
  ★ 默认 `false` ⇒ 与改前逐字等价（零行为差）；拆解项只在放宽时开，成本受控；
    没动任何成本闸门（仍只走 `ControlSurface`）。

【验收】
  · 冒烟 **235 ✓ / 0 ✗**（新增 `check_v12340_backfeed_stage` 四臂 + `check_v12340_relax_force`
    四臂；负对照指向 v1.23.39 判红 2 条）。
  · verify `--phase all` **PASS 319 / FAIL 0**；AUDIT **PASS 69 / FAIL 0**。
  · 变异体 **86 判红 / 86**（新增 M85 去兜底 / M86 漏本函数 / M87 强制开关被忽略 /
    M88 扩项被回退；均锚点命中 1 + 变异后 AST OK + 单跑判红）。
  · **真跑靶点验证（关键）**：修行层 2 圈，同 v1.23.39 R1 题面 ——
    `[WEB-NEED] stage=expand_pair_merged_once 声明 3 条 ⇒ 采纳 6 条`（stage 是真实名，
    不再是 `None`）+ `[WEB-BACKFEED] stage=expand_pair_merged_once 复用 6 条 ⇒ 注入`
    **2 次** ⇒ 回喂在真实调用图上闭环（v1.23.39 为 0）。

★ v1.23.40 收束摘要：交付「回喂闭环修复 + 放宽表扩展 12 + 强制放宽开关」；主文件
  25832 行 / 纯 CRLF / AST OK / 零新 AST 符号；验收全绿（冒烟 235·verify 319·AUDIT 69·变异体
  86 全判红）；真跑靶点 `[WEB-BACKFEED]` 由 0→2 次证明回喂真生效。未做：R3 仅 2 圈靶点，
  未做多题型 `relax_force=true` 对照（留待按需真跑）。

v1.23.39 相对 v1.23.38

【主题】按需联网**四层一致**（环节自己声明了就真查）。

【问题】v1.23.36 起「所有层都能联网」说的是**代码路径**（修行层硬豁免已取消），
  但 `WebSearchGate.allow` 仍要求 `web_search.stages.<环节>` 静态授权，
  而 37 个环节开关**默认只开 5 个**（研究/对撞/元层），**修行层一个都没开**
  ⇒ 修行层环节即使写了 `===WEB-NEED===` 声明，也会被 `stage 未授权` 挡掉
  ⇒ **声明了却查不到 = 四层行为不一致**（用户口径：四个层都应该一致，按需联网检索）。

【修法】两处，都在既有函数体内，**不新增 AST 符号**：
  · `WebSearchGate.allow(..., on_demand=False)`：`on_demand=True` 时**跳过
    `stages` 静态授权**（那份开关只管「引擎主动注入」）；
  · `MetaDGTF._web_search`：`used_as == "record"`（按需声明路径）⇒ 传
    `on_demand=True`。
  ★ **成本闸门一条不减**：总闸 / 连续失败降级 / 三层配额全部照旧。
  ★ 引擎主动注入路径（`evidence`）语义**不变**；不声明仍**零调用**。

【验收】
  · 冒烟 **233 ✓ / 0 ✗**（新增 `check_v12339_ondemand`：正/负一/负二/负三/
    负四/端到端/静态七项）；负对照（指向 v1.23.38）**判红 6 条** ⇒ 判据有判别力。
  · verify `--phase all` **PASS 319 / FAIL 0**；AUDIT **PASS 69 / FAIL 0**。
  · 变异体 **82 判红 / 82**（新增 M83 去按需豁免 / M84 短路总闸）。
  · **真跑（靶点跑，直接 v1.23.39，不跑 v1.23.38 对照臂）**：
    - R1 修行层（`route=["0"]`，5 圈）：48 calls / 256,583 tokens /
      **收 24 条 W#**；**4 次 `[WEB-NEED] stage=None 声明 ⇒ 每次采纳 6 条**；
      读数 候选 60 · & 10 · 线头 15 · 悬置 3 · 保真 ok · 密度 ok · 候选率 ok。
    - R2 回归（`route=["0","1"]`，4+4 圈）：84 calls / 484,638 tokens /
      **收 36 条 W#**；4 次声明；**「未授权」计数 0**；研究层 `& 16`。
    - 成本 ≈ ¥2 / 33min（原三跑方案 ¥13-15 / 3.5h ⇒ 省 ~80%）。
    ⇒ **核心靶命中**：修行层按需联网在真题上真跑通。

【★ 真跑逮到的第二个缺口（探针/判据看不见）】
  回喂按 `record["stage"] == 当前环节名` 匹配，而**按需声明全部发生在
  `LLM.call(stage=None)`**（展开主路径不传 stage；日志实证 4 次全 `stage=None`）
  ⇒ record 的 stage 为空 ⇒ **回喂永远匹配不上** ⇒ v1.23.38 的回喂在真实调用图上
  **从未生效过**（探针能触发是因为探针**显式传了 stage**）。
  候选修法（下一版）：`_web_need_report` 在 stage 为空时用
  `_infer_stage_from_stack()` 兜底取真实环节名再入库。
  ★ 又一实例「探针全绿 ≠ 真跑可达」。

v1.23.38 相对 v1.23.37

【主题】**联网按需「回喂」**（池复用式）+ 圈级心跳**放宽目标表扩展**（4 → 8）。
—— 把 v1.23.37 只做了一半的按需协议补完：声明 ⇒ 检索 ⇒ **后续环节真的用上**。

【① 联网按需「回喂」（池复用式）】
v1.23.37 做到「声明 ⇒ 检索 ⇒ 进池 + 留痕」，但结果**只躺在池里**，
下一环节经 `_web_augment` 时**又查一遍**、且拿不到池里那份。
本版让 `_web_augment` 在检索**之前**先扫池：
· 命中（`used_as == "record"` 且 `stage` 匹配）⇒ **直接复用**，不再调 `_searcher`
  ⇒ 回喂路径下 `_searcher` 调用次数 = **0**（成本判据：省钱真发生）。
· 复用**安全**：这些条目当年进池时**已过 Gate**（授权 + 三层配额 + 失败降级），
  这里只是取出来用，**不产生任何新的外部调用**。
· **留痕**：`logger.info("[WEB-BACKFEED] stage=… 复用池内按需结果 N 条 ⇒ 注入")`。

改动**只两处、都在既有函数体内、不新增任何 AST 符号**：
① 注入侧（`MetaDGTF.run` 的 `_llm_ctx_set`）多注入一个线程上下文键
   `backfeed_pool=self.pools.get("1")` ⇒ `LLM` 侧能读到池。
② 消费侧（`LLM._web_augment`）检索前先扫池，命中就复用 + 留痕。

**零行为差**：不带池（老调用方）/ 池里没有 record / `stage` 不匹配 / 无注入器
⇒ **全部原路不变**（四条负对照各有判据）。

【② 圈级心跳放宽目标表扩展（4 → 8）】
`MetaDGTF._TICK_WEB_RELAX` 原表 `("ing", "probe_research", "probe_duel",
"probe_meta")` —— 只挑「最需要外部刺激」的那一类。本版按**同族补漏**：
· `he` —— 「和」环节，与表内 `ing`（推理）**对偶**（缺它不对称）
· `phase_probe` —— 阶段探针，与表内三类 `probe_*` **同族**
· `expand_pair` / `expand_pair_merged_once` —— 展开对撞对：
  停滞（池零增量）= 没有新对 ⇒ 正是该问外面的时刻。
★ 只在「上一圈零增量 + 联网总闸已开」时经 `ControlSurface` 放宽 ⇒ 默认零行为差。
★ **两向对账**：每个成员必须在 `web_search.stages` 里存在，否则「放宽」是
  **死配置**（放宽一个引擎不认的 stage，永远不生效且**不报错**）
  ⇒ 新判据 `check_v12338_relax_targets` 钉住（8/8 全在 30 个环节里）。

【验收】
· 主文件 `元DGTF-V1.23.38.py`：25772 行 / 纯 CRLF（`\r\r\n` = 0）/ AST OK。
· 冒烟 `smoke_test.py`：**232 ✓ / 0 ✗**（比上版 +2 = 两条新判据）。
· 变异体 `_mut_v12332.py`：**80 条**（新增 M80/M81/M82），全量判红见 `_mut_v12338full.log`。
· 前置探针 `_probe_v12338_backfeed.py`（改前/改后同支对表）：
  | 场景 | v1.23.37 | v1.23.38 |
  | A 池里有本 stage 的 record | `_searcher` 调 1 次 / 用新检索结果 | 调 **0** 次 / 用**池内原文** |
  | B 池里没有（负对照） | 调 1 次 | 调 **1** 次 |
  | C 无注入器 | None | None |
· **无新增配置键**（回喂与放宽表都是行为侧改动）⇒ `load_config` 逐字差异 **0 项**。

【判据纪律】
· 新判据 `check_v12338_backfeed` 走**真实入口产出**：真驱动 `_web_augment` 看它
  到底注入了什么（正 = 复用且 `_searcher` 零调用；负 = 池空仍检索 / `stage`
  不匹配不复用 / 无注入器 `None` / 不带池退回原行为）。
· 新判据 `check_v12338_relax_targets` 定位/解析**一律用纯字符串操作**
  （`find` / `endswith` / `split`）**不用正则** —— 本项目在「脚本 → 落盘 → 解析」
  三层里数错反斜杠已踩多次（本轮 `r"...\\(..."` 写成双反斜杠 ⇒ 正则匹配字面
  反斜杠 ⇒ 判据恒报「找不到定义」，且**不报错**）。
· 版次批注**不许进代码注释**（要落本文件）—— 本轮实测踩到：把 `[v1.23.38]`
  写进 `_TICK_WEB_RELAX` 的注释 ⇒ 冒烟 `[v1236] 正文注释里仍有版次批注` 判红。


★ v1.23.38 收束摘要

**交付物**：主文件 `元DGTF-V1.23.38.py`（25772 行 / 纯 CRLF / AST OK）。
**改了哪几处**：
1. 联网按需「回喂」（池复用式）—— 两处、都在既有函数体内、**不新增 AST 符号**：
   · `MetaDGTF.run` 的 `_llm_ctx_set` 多注入 `backfeed_pool=self.pools.get("1")`；
   · `LLM._web_augment` 检索**前**先扫池，命中（`used_as=="record"` 且 `stage`
     匹配）⇒ **直接复用** + `[WEB-BACKFEED]` 留痕。
2. 放宽目标表 `MetaDGTF._TICK_WEB_RELAX` **4 → 8**（补 `he` / `phase_probe` /
   `expand_pair` / `expand_pair_merged_once`），并与 `web_search.stages` 两向对账。
3. `dgtf_config.yaml` 头部升版 + 升级段；**无新增配置键** ⇒ `load_config`
   逐字差异 **0 项**。

**验收数字**（全部实测）：
| 项 | 结果 |
|---|---|
| 冒烟 `smoke_test.py` | **232 ✓ / 0 ✗**（EXIT=0；比上版 +2 = 两条新判据） |
| verify `--phase all` | **PASS 319 / FAIL 0**（26 阶段） |
| AUDIT `_probe_v1232_audit.py` | **PASS 69 / FAIL 0** |
| 变异体 `_mut_v12332.py` | **80 判红 / 80 总数**（0 假绿、0 锚失效；新增 M80/M81/M82） |
| app 自检 `dgtf_app/selftest.py` | **PASS 368 / FAIL 0**（mock，零花费） |
| 前置探针（改前/改后对表） | 回喂场景 `_searcher` 调用 **1 → 0** 次；负对照不变 |

**未做 / 下一步**：
· 本版**未跑真跑**（行为侧改动 + 全套判据已覆盖；联网回喂的成本判据已由探针
  的「`_searcher` 调用 = 0」直接证明）。若要更强证据，可在全开真跑里看
  `[WEB-BACKFEED]` 留痕条数。
· 放宽表已扩到 8 个，**未纳入**的候选：`decompose_*` 四兄弟（拆解类，高频，
  停滞时联网调用会明显增多）—— 需实测后再定，不先扩。
· 挂账 #2（等待型）/ #3（留痕不删）：**无需行动**。

---

v1.23.37 相对 v1.23.36


【主题】**联网按需协议**（环节自己说要不要）+ **圈级心跳**（运行中逐圈调整）。
—— 补齐「联网全面化」与「运行中动态调整」的最后两环。

【① 联网按需协议】
  · 前一批做的是「**统一增强层**」（引擎在调用**前**主动挂参考，按环节开关）；
    那是「引擎猜需不需要」。**「按需」的"需"只有环节自己知道** ⇒ 本版补上：
      环节产出末尾可写 `===WEB-NEED===` + `{"queries": [...]}`
      ⇒ 引擎解析 ⇒ **逐条过同一个 Gate**（授权/三层配额/失败降级）⇒
        检索 ⇒ 进池（W#）+ `logger` 留痕（`[WEB-NEED]` 行）。
  · **可选协议**：不写就**零变化**；★ 本版**不"回喂"**（那要在同一环节再调一次，
    成本翻倍）—— 先把「**声明被听见并真的去查了**」做实。
  · 容错：`parse_web_need` 对畸形输入**一律不抛错**（只当没声明），
    并对一次声明**截量**（默认 3 条，防一个环节吃光配额）。

【② 圈级心跳】
  · 层级心跳只在**层收尾**能拿到 view；圈级要读「上一圈」，而 `view` 每圈新建。
    若去两个圈循环调用点各存一次 view，就落进本项目反复踩的
    「**同一条逻辑两处各写一份**」⇒ 迟早分叉。
  · **⇒ 改用「池增量」**：`_before_round` **每圈都调**，在它里记「本圈开始的
    池规模」；下一圈的增量 = **上一圈的产出**（新增 & 与线头）⇒ **只改一处**。
  · 触发：上一圈**零增量**（复述/停滞）⇒ 放宽本圈对撞/探针类环节联网
    （经 `ControlSurface`，可追溯 + 可控）。
  · **零行为差**：第一圈无基线 ⇒ 不动；增量为正 ⇒ 不动。

【③ 并入 v1.23.36】
  联网全接（30 环节）· 所有层注入 · 读数全量显示（日志+产物同源）·
  三层 trace · 显式控制面 · 心跳级调度 · EML 五分支「学了要做」·
  所有可配置行为纳入学习（`_action_on` 运行时覆盖 + `thinking_hint`/`action_hint`）·
  ★ 真跑逮到的 `yin_yang_divergence` 静默缺失（`merge_expand` 合并路径提前 return）。

【验收】（见 `v12337_报告.md`）
  · 主文件 **25730 行 / 纯 CRLF / AST OK**；版本号两处一致（docstring + `__version__`）。
  · 冒烟 **230 ✓ / 0 ✗**（EXIT=0）；新增 `check_v12336_webneed`（按需协议）与
    `check_v12337_roundtick`（圈级心跳），**都是构造性判据**（真驱动消费方）。
  · `_v122_verify.py --phase all` ⇒ **PASS 319 / FAIL 0**（26 阶段）。
  · `_probe_v1232_audit.py` ⇒ **AUDIT PASS 69 / FAIL 0**。
  · 变异体 **77 判红 / 77 总数**（无假绿）；含 M72 复现真跑逮到的 yin_yang 缺陷。
  · ★ **真跑实测**（`V1236FULL`）：3437s = 57.3min / **143 calls** / 1,152,428 tokens；
    四层读数总表 **12 条**全显示。★ EML **实际应用 3 条** `rounds_delta`
    （both 4→5、all 5→6、0 4→5）⇒ **不是「学了不做」**。

★ v1.23.37 收束摘要

  · **交付物**：`元DGTF-V1.23.37.py`（25730 行，纯 CRLF）+
    `smoke_test.py`（+2 判据）· `_mut_v12332.py`（77 条）· `v12337_报告.md` ·
    `dgtf_config.yaml`（头部 + 升级段，**无新增键**）· `_v122_ast_registry.json`（308 条）。
  · **改了哪几处**：① `LLM.call` 加按需协议挂钩（1 处）；② 新增模块级
    `parse_web_need` + `LLM._web_need_report`；③ `MetaDGTF._before_round` 加圈级
    心跳（**只改 1 处**）；④ `_finalize_layer_common` 存 `_last_view`。
  · **验收数字**：冒烟 230/0 · verify 319/0 · AUDIT 69/0 · 变异体 77/77 判红 ·
    真跑 143 calls / 12 条读数 / EML 应用 3 条。
  · **未做**：按需协议的**回喂**（声明 ⇒ 检索 ⇒ 让环节看到结果）；本版只做
    「听见 + 去查 + 留痕」。挂账 #2（等待型）/ #3（留痕不删）无需行动。
  · **存档**：`c7d0bd0`（main）；并行分支 `feat/v12337` 已推送 GitHub。

---

v1.23.36 相对 v1.23.34

【主题】**联网全接 + 读数全量显示 + 决策可追溯 + 显式控制面**
—— 「自由调度 × 自我学习一体」的三件地基（用户口径见下）。

  用户指令（本版）：
  ① 「联网全接**配置可控开关**」；
  ② 「**所有层都注入**」；
  ③ 「运行中和结束时所有读数都**完整显示在日志中**，同时**结构化显示在产物文档中**」；
  ④ 「自由调度和自我学习是**一体**的，渗透到整个元DGTF的运行中，所有行为逻辑都有
     **追溯和可控性**；先检索最前沿技术和算法和学科知识进行融合创新并应用于元DGTF」。

【五条前沿依据（逐条对应一处落地）】
  ① ★★ **E³-Agent**（arXiv 2605.27428, 2026）—— **快慢双路径 + 显式控制面**：
     毫秒级调度（fast-path）与事件驱动的 LLM 元控制器（slow-path）分开，两者经
     **一个小的、显式的控制面**连接；**从执行反馈在线学习**。
     ⇒ 落地 `ControlSurface`（所有运行时调度调整的唯一收口）。
  ② ★ **Heartbeat-Driven Activity Scheduling**（arXiv 2604.14178, 2026）——
     用**周期性心跳主动**编排（不是等失败才反思），策略由**历史日志元学习**改进。
     ⇒ 落地方向：`_before_round`（已是两条通道共用的「圈前统一动作」）作心跳位。
  ③ ★ **MetaClaw**（arXiv 2603.17187, 2026）—— **双时间尺度学习**：快适应
     （单次失败⇒合成技能⇒零停机注入）与慢适应（策略优化）**互相强化**。
     ⇒ 与既有 EML（`shadow→on` 为慢、`_eml_note_contra` 为快）对齐。
  ④ ★★ **可追溯三层**（agent observability, 2026）—— **L1 决策（why，含
     「考虑过的选项」）/ L2 动作（what）/ L3 归因（did it matter）**；
     OpenTelemetry 的 **`decision.chain` span kind** 与 **Decision Log Format**
     都要求**记录被否的选项**（审计要看得见「没走的路」）。
     ⇒ 落地 `_trace_note` / `trace_decide` / `trace_outcome` + `view.trace_log`。
  ⑤ ★ **Observing ≠ Auditability**（specswriter）—— 观测平台会**采样/截断**，
     **审计级不许采样**；另记「不到 5% 的部署 agent 记录了 temperature/top-k/seed」
     ⇒ 参数要变成**可追溯属性**。⇒ 落地：trace **全量不截断**。

【落地一：联网全接（一处改覆盖 30 个环节）】
  · **30 个环节**（AST 实测：含 LLM 调用的函数，扣 `_call_long`）——
    原先只有 **7 个**能联网，**差 23 个**；
  · 实现放在 **`LLM.call`**（所有环节的必经之路）：新增 `_web_augment`，
    按需给该环节的 prompt 挂「外部参考」段 ⇒ **一处改、全部生效**
    （逐处改 30 个 prompt 既慢又散、且必然漏）；
  · **依赖注入**：`LLM` 是模块级类、拿不到 `_web_search`（它在 `MetaDGTF` 上）
    ⇒ 用 **thread-local 上下文**注入 `web_searcher` / `question` / `entry` / `round`
    （thread-local 是因为并行模式下多层同进程多线程，全局变量会串台）；
  · **stage 推断**：多数调用点没显式传 `stage=` ⇒ 从**调用栈**推断环节名
    （`_infer_stage_from_stack`，去前导下划线）⇒ 30 个环节**各自一个开关**；
  · **配置**：`web_search.stages` 从 7 键 → **37 键**（新增 30 个环节开关，默认
    **全 false**）；配置叶子键 **193 → 223**。
  · ★ **零行为差**：总闸 `web_search.enabled` 出厂 false ∧ 逐环节默认 false
    ⇒ 不打开就与今天逐字相同。

【落地二：★ 红线调整（用户指令）—— 「所有层都注入」】
  · 原实现按 yaml 注释（「修行层联网会污染『输入是形状不是数据』」）设了
    **修行层硬豁免**（entry == "0" 永不注入）；
  · 用户指令「**所有层都注入**」⇒ **硬豁免取消**；
  · ★ 保护**没有消失，而是从硬编码改成配置式**：30 个环节开关出厂全 false
    ⇒ 不打开就不注入（默认行为逐字不变）；要注入须**显式打开**（谁开谁负责）。
  · ★ `practice_term_calibration`（修行层术语校准）**仍只留痕、不注入** ——
    它与本条是两条独立路径，本次不动它。

【落地三：读数全量显示（日志 + 产物同一份）】
  · 新增 `_readings_bundle`（**单一真相源**：把一层的全部读数收成一个 dict）→
    `_readings_line`（运行中一行）/ `_readings_table`（结束总表 + Markdown 版）；
  · 三处显示：**运行中**每层一行（`logger.info`，★ **不受 verbose 控制** ——
    走 `vp` 会被 `verbose=False` 静默吞掉，第一版正是这么错的）；
    **结束**时跨层总表；**产物** md 的「## 读数总表（四层）」表格；
  · ★ 日志版与产物版**渲染自同一份 bundle**，且产物那张表是**日志那次渲染的
    同一个字符串**（`packed["readings_table"]`）⇒ **不可能漂移**。

【落地四：可追溯地基（三层 trace）】
  · `View.trace_log` 字段 + `_trace_note`（**模块级**写入口：调用点分布在
    `DGTF`/`MetaDGTF` 两类无继承关系的类上，做成方法会解析不到）；
  · `trace_decide`（**必须带「考虑过的全部选项」**，没有备选就不算决策）+
    `trace_outcome`（动作前后的读数对比 = EML 唯一能依赖的学习信号）；
  · ★ **空值不写**（缺读数 ≠ 读数是空）；★ **不采样、不截断**（审计级）。

【落地五：显式控制面 `ControlSurface`】
  · 白名单 + 边界 + **必留痕**（缺 `why`/`trace_ref` ⇒ 拒；越界 ⇒ 拒，**不夹取**）；
  · **接线**到 EML 的 `_eml_apply`（`rounds_delta` / `duty_floor` 两处写入改经它）
    —— ★ 是**接线**不是**登记豁免**：审计判据「A2 死类已登记」抓到它「定义后零引用」，
      正确修法是让它真的被用（这正是「可控性本体」）；
  · **绝不写配置**（红线：建议与执行分开）——只改内存态，快照可进产物对账。

【★ 两个插错位置的事故（都已修，值得记）】
  ① 30 个开关**插进了 `api.thinking.stages`**（不是 `web_search.stages`）——
     `s.find('"web_search"')` 命中的是别处。★ 危害不只是"位置丑"：那些 `False`
     会让环节的思考档**优先返回 False** ⇒ **全开时被强制关思考**（行为退化）。
     修法：撤销 + 用「先找段起点、再在段内找键」的**两段定位**，并加**段内校验**。
  ② `practice_term_calibration` / `stop_criteria` 的判据断言「默认关时走到 Gate」
     —— 但那两个方法**开头就判 `enabled`**（与既有 `_research_web_prep` 同惯例）
     ⇒ 根本不调 `_web_search`。判据改为断言**结果**（零检索 + 没走到 Gate）。

【验收】判据 `check_v12336_allweb`（源码级 + **构造性**：未接线不增强 /
  总闸关不增强 / 开+授权即增强 / **四层全可注入** / 未授权被 Gate 拒且有拒因）
  + `check_v12336_readings`（**三处显示 + 同源核对**：日志表与产物表的圈数必须一致）。
  变异体见 `_mut_v12332.py`（M60 起）。

【v1.23.36 续：心跳级调度 `_schedule_tick` + EML 两向对账】（同版第二次提交）

  用户口径：「自由调度与自我学习**一体**」要**真的参与运行中的动态调整**，
  不能只停在「候选生成了、库也存了、召回也召回了」。

  · **心跳级调度**（依据 ② Heartbeat-Driven Activity Scheduling：**周期性心跳主动**
    编排，不是等失败才反思）—— 落点 `_finalize_layer_common` 末尾（两条跑圈通道
    **共用**的收尾；此刻 `view` 在手 = **读数可取**，下一层还没跑 = **调整来得及**）。
    首批三条规则，**只读已有读数、不新增计算**：`candidate_yield` 判 `collapsed`
    ⇒ 放宽**下一层**对撞/探针类环节的联网；语义停滞 ⇒ 同样允许探针环节联网；
    职责 S < floor ⇒ 记一条 `carve_first`。**全部经 `ControlSurface`**（可追溯 +
    可控）+ **默认零行为差**（读数取不到 ⇒ 不动；同值 ⇒ `write` 判 noop 不落）。
  · **放宽如何真的生效**：给 `WebSearchGate` 加**运行时放宽集** `_relaxed`
    （**只改内存态、不碰配置**）：`_web_search` 把控制面放开的环节同步进去，
    `allow()` 的授权判定多认这一条 —— 但**配额 / 连续失败降级 / 各 stage 上限照旧**
    ⇒ 放开的只是「授权」这一道，**可控性不降**。
  · ★★ **EML 两向对账（修「学而不做」）**：实测 `eml_candidates_from_result`
    生成 **4 种** `action.key`，而 `_eml_apply` 只有 **2 个**分支 ⇒ `carve_first` /
    `tri_advisory_only` / `note_cost_no_gain` **生成 → 过闸 → 存库 → 召回，
    但永不生效**，且**没有任何判据看得见**（召回日志只说「用了几条」，不说
    「其中几条真生效」）。
    修法：新增 `_EML_RECORD_ONLY` **豁免表**，把「只记录、不应用」**写明并写清原因**
    （「不在 `_eml_apply` 里」从「像是忘了」变成**显式的决定**）；配判据
    `check_v12336_eml`：**两向对账**（生成侧 ↔ 应用侧 ∪ 豁免表）+ **过期登记**检查
    + **构造性**（真造 episode 看能不能真生成）。实测：生成 4 ↔ 应用 2 ↔ 豁免 3，
    **无学而不做、无过期登记**。
    ★ `carve_first` **不硬接**的理由（写进豁免表）：它要的是「**下一跑**这些层优先
    雕」，而本引擎**没有跨跑调度接口**（跨跑建议走 AutoTune 的建议文件，红线：
    **建议与执行分离**）⇒ 硬接会变成「一次跑中途改另一件事的优先级」，语义不对。
  · 新增判据 `check_v12336_tick`（心跳：主动触发 / 幂等 / **默认零行为差** /
    **不写配置**——查**前后差异**）+ `check_v12336_readings` / `check_v12336_allweb`；
    变异体 **M60~M68**（9 条）判红，`_mut_v12332.py` 共 **68** 条。
    ★ `--only N` 用**索引**，本轮**两次**因「插入位置 ≠ 编号」跑错靶子 ⇒ 输出已改为
    **带索引**（`OK [65] M65 …`），跑错当场可见。

【收尾时踩的坑（都已修，值得记）】
  ① **索引与编号错位**（两次）：新条目插在中间 ⇒ `--only` 跑错靶子。修：移到末尾 +
     输出带索引。
  ② **判据自己喂错参数**：`eml_candidates_from_result(result, ep)` 第一参数是**产物**、
     第二才是 episode；把 ep 塞进第一位 ⇒ 生成空 ⇒ 判据误报「闸门过严」。且 `duty`
     的值应是 **float** 不是 dict。
  ③ **判据误报**：心跳「不写配置」第一版查「配置里有没有 True」—— 而 `build_cfg` 的
     stages **本来就有** True ⇒ 误报。改成查**前后差异**。
  ④ **`grep` 匹配 emoji 不可靠**：`grep -c '📊'` 返回 0，而 Python 读同一文件是 6
     ⇒ **假阴性**。检查含 emoji 的日志一律用 Python 读。

★ v1.23.36 收束摘要

  · **交付物**：`元DGTF-V1.23.36.py`（**25390 行 / 纯 CRLF**，CR-CR-LF 0）/
    `CHANGELOG.md` / `dgtf_config.yaml`（叶子键 **223**）/ `smoke_test.py`（本轮
    **+4 判据**）/ `_mut_v12332.py`（**68** 条）/ `dgtf_app/`（自检 **368 / 0**）/
    `_v122_ast_registry.json`（**306**）。
  · **改了哪几处**：① `LLM.call` 加 `_web_augment` + thread-local 注入 ⇒ 联网
    **一处改覆盖 30 个环节**；② 修行层「不注入」**硬豁免 → 30 开关配置式保护**；
    ③ `_readings_bundle` / `_readings_line` / `_readings_table` **三处同源显示**；
    ④ `View.trace_log` + `_trace_note` / `trace_decide` / `trace_outcome` 三层 trace；
    ⑤ `ControlSurface` 显式控制面（接线 EML 两处写入，**绝不写配置**）；
    ⑥ `_schedule_tick` 心跳级调度（`_finalize_layer_common` 末尾）+
    `WebSearchGate._relaxed` 运行时放宽集；⑦ `_EML_RECORD_ONLY` 豁免表 +
    `check_v12336_eml` 两向对账。
  · **验收数字**：主文件 25390 行 / 纯 CRLF / AST OK；冒烟 **228 ✓ / 0 ✗ / EXIT=0**；
    `--phase all` **EXIT=0**（42/0 · 34/0 · 30/0 · **AUDIT 69/0** · 16/0 · 26/0）；
    变异体 **68 条**；配置叶子键 **223**（`web_search.stages` **37** 键，其中**新增
    30 键默认 false**、原有 7 键保持原值）/ `DEFAULT_CONFIG` ↔ 出厂 yaml **两向 0 差**；
    AST 登记 **306 / 306**；dgtf_app 自检 **368 / 0**。
  · **未做**：全开四层真跑 `_fullrun_V1236FULL` **于第 3 层中途被中断**（日志 2661 行 /
    126 calls；读数行已实测正常打出 ×6，但**无收尾段、无 `.json` 伴生**）⇒
    **未取得完整四层读数对照**；是否重跑待定。

---

v1.23.34 相对 v1.23.33

【主题】**提示词优化**：有据 · 智者语气 · 输出结构（**改措辞，不改机制**）。

  用户诉求：阴阳视角 / 展开 / ing / 对撞 / view 等阶段要能**引用证据**（自己的
  产物 / 联网 / 导入资料）进行论述；全文有深度且看得懂；语气像「见过很多、
  也愿意把话讲明白的人」；字数按需；有理有据；并在「**不改变原有语义和行为**」
  的前提下优化提示词、优化 ing 与 view 的输出结构。依据全文见 `v12334_报告.md`。

【五条前沿依据（逐条对应一处落地）】
  ① ★★ **第四面墙问题**（josephwp.com, *The Fourth Wall Problem*）——
     LLM 区分不了「用户给的 / 系统注入的 / 自己知道的」；又因 RLHF 奖励来源标注，
     它会**主动交代来源**、把系统管道讲给读者听（"从你的 recall snippet 看…"）。
     解法的关键一件是**显式禁止短语** —— **光有正面要求不够**。
     ⇒ 落地：**内容级引用允许、管道级暴露禁止**（`EVIDENCE` 的禁止清单）。
  ② **换语气不改数据**（shshell.com, RAG Prompt 设计）—— 多角色 RAG 用同一份
     Context、换模板即换语气 ⇒ 语气与机制**可解耦** ⇒ 落地：语气单独抽成 `VOICE`。
  ③ **人设影响准确性**（TrendFlash 2025）—— 指派角色能让输出**更保守准确**
     ⇒ 智者人设服务于「有据」，不做装饰（否则与 `ANTI_PRETTY` 冲突）。
  ④ **证据要求要具体**（byaiteam.com）—— 把「有据」写成**可执行清单**。
  ⑤ **标签分隔指令与数据** ⇒ 沿用本项目既有 `【】` 惯例，**不引入新记号**
     （避免与既有解析冲突）。

【落地三期（改措辞，零机制改动）】
  · 第一期 · 共通表达规范 + 抽重复：
    - 新增 `VOICE`：怎么说话（讲人话 / 有分寸 / 短而准；**和蔼不是讨好**）；
    - 新增 `EVIDENCE`：有据（三类可引来源 + **管道级禁止清单** + 无据不编）；
    - 新增 `EXPLORE_FORMAT`：六处视角提示词原本各有一份**逐字相同**的 5 行
      格式契约 ⇒ **抽成一处**（以后一处改、六处生效）。**数值契约不变**
      （8 条上限 / 20-80 字），只把「按需」讲清楚。
    - 接线：`VOICE` / `EVIDENCE` 各接 7 处（六视角 + ing）；`EXPLORE_FORMAT` 接 6 处。
  · 第二期 · `ing`（对撞）：六步正文改成**各起一行、先结论后依据**；接上
    `VOICE` + `EVIDENCE`；明确「篇幅按需」。
  · 第三期 · `view`（显形）输出结构：`_render` 正文最前面加一行**本层速览**
    （跑了 N 圈 · 候选 X · & Y · 线头 Z），让读者先抓全局 —— **只增一行**。

【不改动清单（红线自检，逐项有判据）】
  输出格式契约 `- [kind] 描述` ／ `===ING-STRUCT===` 与 `ing_structured` 出口 ／
  任何判定条件 · 通道 · 四态 · 停止判据 ／ 配置键（只同步 yaml 头部版本 +
  升级段，键值一律不动）／ `ANTI_PRETTY` 与「不煽情、不客服」（**追加**而非
  替换）／ 「阴视角 · 阳视角 · 结构化尾块」字样（★ 冒烟 mock 靠它们分流）。

【验收】判据 `check_v12334_prompt`（**两向**：新规范接上了 + 老红线一条没少）；
  变异体 **M56**（阴视角漏接 `VOICE`）/ **M57**（`EVIDENCE` 丢禁止清单）/
  **M58**（`EXPLORE_FORMAT` 改格式契约）/ **M59**（`_render` 去掉本层速览）
  ⇒ 均判红。全套读数见 `v12334_报告.md` 第六节。

---

v1.23.33 相对 v1.23.32

【主题】**机制级吸收**：把「随时看随时停」变成有保证的事。承接
`_学科与前沿映射_v12332.md` 的合并吸收清单，把**剩余 11 项**一次做完。
【机制级三项（都是「可开关 + 有读数 + 有留痕」，**默认全关**）】
  ① **anytime-valid 停止判据**（`stop.anytime_alpha`，默认 **0 = 关**）：
     本项目每圈边跑边判 = **optional stopping**，原先**没有任何有效性保证**。
     新增 **stitched Hoeffding 置信序列**（Howard et al. 2021）：「结构仍在长」的
     0/1 序列，其均值下界**对任意停时都成立**（`E[φ_τ] ≤ α`）；下界跌破 0.5 ⇒
     追加一条停止理由。实测：12 个 1 ⇒ 下界 **0.5606 > 0.5** ⇒ 可停；
     3 个 1 ⇒ **不判**（样本不足不表态）。
  ② **发散检测 + 回滚指针**（只出读数与指针，**不改停止行为**）：三态
     收敛/平稳/停滞/**发散**（方差前后半 + lag-1 自相关，与 CSD 同源）+
     「历史最佳圈」**指针**。★ 依据 LoopGain，但**只给指针**：被回滚的圈**不删**
     （红线「失败留痕」）。
  ③ **预算 bandit**（`auto.bandit.enabled`，默认 **false**）：UCB1-with-cost
     （吸收 AAAI'26 Budget-Aware LinUCB 的思想，不引依赖、不上上下文特征）；
     臂 = 圈数上限三档（3/4/6），奖励 = **职责度中位 − cost_w×（tokens/1000）**，
     状态落 `dgtf_memory/bandit.json`。★ **探索会故意选较差档** ⇒ 必须显式打开，
     且**每次探索选择都在产物留痕**。

【读数/结构八项】
  ④ **compact 内部面预算**（率失真）：只出**读数与政策**，**不自动压缩** ——
     ACE 反面数据：1.8 万 token 压到 122 ⇒ 准确率 66.7→57.1。
  ⑤ **锚点离线解析验证**（refchecker「按可审计表面判」）：URL 形态/协议/域名完整性，
     零网络请求；挂到 `pool.anchors` 每条锚点。
  ⑥ **锚点内部批判**（史学 Quellenkritik）：外部批判已有 `tier`，**内部批判此前缺失**
     ⇒ 按域名类型给「立场/利益倾向**提示**」（gov/edu/org/com/媒体…），**不是判词**。
  ⑦ **分级证明标准 + 谁主张谁举证**（法学）：causal → beyond_reasonable_doubt、
     numerical/predictive → clear_and_convincing、其余 preponderance；**不改 gate**。
  ⑧ **裁决维度拆分**（逻辑/事实/边界/后果）：对撞层 `adjudications` 增 `aspect` ——
     依据多评委框架 + 红线「自省是另一个视角，不可合并」。
  ⑨ **信念陈旧度读数**（ABES + ftl-beliefs 的 STALE）：age ≥ 3 圈未再确认 ⇒ 提示；
     ★ **不改四态**（加第五态会让历史 packed 的判据全部失准）。
  ⑩ 产物三行新读数：内部面预算 / 信念陈旧度 / 预算 bandit（仅启用时）。
  ⑪ 两个 opt-in 键 + 出厂 yaml 同步（头部 + 升级段 + `stop:` + `auto.bandit`）。

【★ 本轮两条判据通则（都被实测踩到）】
  · **变异体要打在「行为出口」上**：M21 拆掉锚点离线检查的协议守卫后，
    域名守卫**仍然拦住**同一条输入 ⇒ 行为没变 ⇒ 假绿。改成破坏最终判定才判红。
  · **能变成纯函数判据的，不要写成「驱动大函数看副作用」**（承 v1.23.32 收尾）：
    后者一旦「没跑到」，表现与「通过」完全一样。

【★★ 本版两个**沉默失效**（真跑逐项核对时抓出，都已修）】
  · **P7 把 `View` 当 `dict` 用**：`_pack_result` 三段写了
    `(results.get(e) or {}).get("...")`，而 `results` 的值是 **View 对象** ⇒
    `AttributeError` ⇒ 被 `except Exception` 静默吞掉 ⇒ `compact` /
    `belief_staleness` / `bandit` 三键从未写进 packed（**产物里整行读数消失、
    且不报错**）。修：加鸭子类型 helper `_rv(obj,key,default)` 并改用它；
    两处 `except` 从静默改成「异常名写进产物」。
  · **P8 读数算在序列赋值之前**：`_layer_csd_now` 排在
    `view.round_log = list(state["round_log"])` **之前** ⇒ CSD / 发散三态 /
    anytime 下界**永远算不出**（同样不报错）。修：调用点后移。
  ⇒ 通则：**`except: pass` + 类型假设错误 = 沉默失效**；
    **读逐圈序列的计算必须排在序列赋值之后**。两条都只能靠
    「核对产物里到底有没有那行」发现 —— 这正是本版加「层读数进产物」
    **行为判据**的价值。

【★ 本轮工程坑（写进过程文档）】
  · **heredoc 吃转义**（第 3 次）：`newline="
"` 在 heredoc 里成真换行 ⇒ 目标文件语法错。
    ⇒ 通则：**凡内容含反斜杠/三层引号，一律走脚本文件 + `@@NL@@` 占位替换**。
  · **模块缺 `import math`**：新纯函数用 math，主文件原本只在函数内 import ⇒ NameError。
  · **变异体列表缺逗号**：追加条目时上一条无逗号 ⇒ 元组被当函数调用。

【验收】
  · 主文件 **22914 行 / 纯 CRLF**（v1.23.32: 22282）。
  · 真实入口探针 `_probe_v12332.py` **52 ✓ / 0 ✗**（新增 T15~T23）。
  · 变异体 `_mut_v12332.py` **23 / 23 判红**（新增 M16~M23）。
  · 冒烟 **223 ✓ / 0 ✗**（EXIT=0）；`--phase all` 与真跑见下。
  · 配置两向对账：`stop.anytime_alpha` / `auto.bandit` **两侧都有** ⇒ 0 差。

【真跑驱动的第二轮：全开键的沉默炸点 + AutoTune】
  · **P9 真跑脚本自带第二份「全开清单」**（矩阵跑批 4 题全灭的真因）：
    `_run_full_v12333.py` 手写 `_set("api.thinking", True)`，而引擎
    `_ALL_ON_ITEMS` 用的是 `api.thinking.default` ⇒ **同一语义两处定义必漂移** ⇒
    把 mapping 写成 **bool** ⇒ 首圈 `AttributeError: 'bool' object has no attribute 'get'`。
    修（**两道**）：① 真跑脚本**删掉自带清单**，改为**只读引擎 `_ALL_ON_ITEMS`**
    并回读生效值（单一真相源），实测 10/10 逐项 ✓；② 引擎 `LLM.__init__` 加
    **形状守卫**（非 mapping ⇒ 降级 `{}` **并告警** —— 按「失败留痕」纪律，绝不
    静默当空）。★ 守卫必须**紧贴取值之后、首个 `.get` 之前**，放晚了第一处 `.get`
    照样先炸（第一版就踩了这个坑）。
  · **P10 `run()` 从不盖 run_id ⇒ EML 从不学习真实跑**（自学习闭环对真路径整体失效）：
    全引擎**唯一**设置 `packed["id"]` 的地方原本**不存在**（id 直到 `save_result`
    才以文件名形式出现）⇒ `episode_from_result` 永远拿到空串 ⇒ 撞上
    「无 run_id 一律不写库」闸（该闸本意是**拦测试**，却把 CLI 与 app 真跑一并拦了）。
    真跑产物里 `playbook.anon_skipped: true` 即此因。**后果：用户在跑的「自学习」
    其实一直是空的**（库内 5 条 episode 全是测试/种子写的，真跑零贡献）。修（**三处**）：
      ① `run(..., run_id="")` **显式收 id**，且只在 `_eml_finish` **之前**盖进产物
         （晚盖 = 这一跑又被当匿名丢）；
      ② CLI `main()` 与 ③ 交互 `_interactive_run()` 都显式传
         `run_id=datetime.now().strftime(...)`；
      不给 id 仍走匿名跳过 ⇒ **测试隔离不破**。
  · **P11 出厂 yaml `all_on: true` 撞「配置两向对账」**：登记进 `CONFIG_TUNED`
    （189 项 / 29 手调**全部已登记**）。
  · **P12 正文注释残留版次批注**（`[v1.23.33 形状守卫]`）撞 `check_v1236_*`：去掉版次前缀。
  · **AutoTune 跨跑调优器**（新增机制，`dgtf_autotune.json` 只出**建议**）：
    从 `episodes.jsonl` 推「模式 / 层集 / 各层圈数上限」。依据
    **Successive Halving / Hyperband**（预算受限粗筛）+ **帕累托前沿**
    （质量↑/成本↓，**不做加权标量化** —— 给成本拍假币汇率 = 凭空打分，与
    「悬置不打分」同一红线）。取舍判据 = **帕累托膝盖**（同质量 τ 内取成本最低
    ⇒「该去的层去掉」的量化）；圈数 = 未截断中位 + 截断层 +1。
    ★ **只建议不改行为**（「建议与执行分开」）；缺读数 ⇒ `ok=False` **不瞎猜**
    （**没测 ≠ 测出来差**）。新增 `autotune` 配置段（min_n / quality_tau / out）。
  · **记忆库并发锁 `eml_lock`**（新增机制；用户要求「可以 3 并发跑」）：
    `playbook.jsonl` 的**升级 / 遗忘 / macro 是整表重写**（读-改-写），**不是原子
    append** —— 两进程同时改会互相覆盖（丢条目 / 写坏半行）。新增
    `O_CREAT|O_EXCL` **跨进程自旋锁**（无需 fcntl/msvcrt），带**陈旧锁回收**
    （持锁进程崩了不永久死锁）。用于 `_eml_finish` 的写库段与 `_save_bandit`。
    ★ 这是**并发正确性前提**，不是性能优化；单跑时零副作用。真跑 sweep 已按
    **3 并发**执行（`_autotune_v12333.py sweep --conc 3`，并支持**幂等跳过**已完成项）。
  · **首轮真跑 sweep 的两个真 bug（AutoTune 自身）**：
    ① **分母不一致**：`autotune_rank` 原把**无 duty 的历史跑次**也算进成本中位 ⇒
       两层组成本中位被拉到 305,076（真值 378,837）⇒ **帕累托膝盖判错**。
       修：质量、成本中位**只在两者都齐的子集**上算（`n_paired` 落盘 + 证据强度标注）。
    ② **`autotune.min_n` 是死键**：`autotune_recommend` 从没接它（「参数没有出口」）。
       修：`autotune_run → autotune_recommend(min_n=…)`；并 1 → **2**。
  · **首轮真跑 sweep 结论**（P1 两层 / P2 四层 / P3 三层 × 2 题，全开，3 并发 88.5min）：
    四层比两层贵 **2.9~3.0×**（1,137k vs 379k tok）而 duty **无改善**（同题配对方向还不一致）；
    对撞层 `both` 恒 0.0。圈数建议 `{0:5,1:4,both:5,all:5}` 与 `_AUTO_ROUNDS_BASE`
    基本一致 ⇒ **圈数默认不改**；证据薄弱（n=2）⇒ **层集默认不改**；
    本轮唯一据数据收紧：`autotune.min_n` **1→2**。详见 `_autotune_v12333_结论.md`。
  · **验收（第二轮）**：冒烟 **EXIT=0 / 0 ✗**（新增 `check_v12333_autotune`）；
    探针 **52 ✓ / 0 ✗**；变异体 **33 / 33 判红**（M25 形状守卫 / M26~M30 AutoTune /
    M31 run_id 记账 / M32 锁不互斥 / M33 成本换分母）；
    出厂 yaml `all_on: true` 在 `CONFIG_TUNED` **销账**（189 项 / 29 手调全登记）。

【第三轮 · 四层目标语义 + AutoTune 三阶段自主决策】

  用户战略指令：AutoTune 后期目标是**自主执行决策**（前期配置选择 / 中期动态调整 /
  后期学习纠正与输出结论）。四层定义：修行层（最少圈数挖尽各层面 ⇒ 无穷收敛）·
  研究层（最少圈数给确定答案 ⇒ 有限收敛）· 对撞层（融合发散与确定 ⇒ 生成新层面）·
  元层（对三层所有产物做记忆结晶/决策/行动 + 回看）；整个元DGTF 是「活着的自洽体」。

  · **设计红线：不发明新分数，只把已有产物出口变成方向明确的目标读数。**
    四层目标 = 每层**已有产物**的一条读数（原料全在现有出口）：
    修行 `excavate`（`aspect_units`+`aspect_hist`+`divergence`，**越低越挖尽**）·
    研究 `settle`（`covered_answer`，**越高越确定**）·
    对撞 `fuse`（`duel_suspensions`+`upstream_*`，**越高越真融合**）·
    元 `crystallize`（`meta_closure`+`engagements`+`suspensions`，**越高越完整**）。
    ★ 主读数**分开成轴、不合成总分**（红线：自省是另一个视角，不可合并）；
    缺读数回 `None` 不是 `0`（没测 ≠ 测出是 0）。

  · **四条前沿依据**（用户授权检索；每条对应一处硬约束）：
    ① **Heaps' law / type-token 饱和**（Herdan 1960；SSR `m̃=αN^μ`，arXiv 1806.09419）
       ⇒ 修行层用**边际新增率**（末段新增/上段新增），**不是**「层面数/圈数」；
    ② **content entropy 收敛 + 伪收敛警告**（*Towards a Science of Collective AI* 2025）
       ⇒ 研究层必须配 `pseudo_convergence` 守卫（收敛但 answered=0 ⇒ True）；
    ③ **CORE**（Pandey et al., NeurIPS 2025）= mode entropy × repetition penalty ×
       **semantic stagnation penalty** ⇒ 对撞 `fuse = 产出率 × (1−停滞率)`，**罚复读上游**；
    ④ **Darwin Gödel Machine**（Zhang et al. 2025, arXiv:2505.22954；ICLR 2026）
       = archive + 开放探索；消融「贪心只从最优分支」39.7% vs 带 archive **50.0%**
       ⇒ 后期学习**禁贪心**、每臂保留非零概率。

  · **★ 依据修正了第一版设计的三处方向性错误**（都属「方向错的断言比没断言更危险」）：
    ① 修行层第一版写 `1 − n_aspects/rounds_run` ⇒ **挖得多反而读数低**（会把好配置判劣）
       ⇒ 改依据①的边际新增率，自测「还在挖 1.0 > 已挖尽 0.5」✓；
    ② 研究层只报 `settle` 会把「一个都没答上却声称收敛」读成完美收敛 ⇒ 补伪收敛守卫；
    ③ 对撞层只看产出量会把「复读上游、一分不发」读成满分融合 ⇒ 补语义停滞罚。

  · **三阶段自主决策**（严格守「建议与执行分开」红线，三段都**不改配置**）：
    前期 `autotune_phase_select`（同题型走 `same_type`，否则退回全体并**显式标注**
    `global`；依据 Successive Halving 只出「跑哪些臂」不出圈数）·
    中期 `autotune_phase_adjust`（按 `t` 排序取首尾：上升→继续 / 下降→回滚 / 平→收敛；
    样本不足 `min_n` ⇒ **不出现该 key** 不瞎猜）·
    后期 `autotune_phase_learn`（纠正 + 结论，报 archive 多样性与证据强度）；
    总入口 `autotune_decide`；`autotune_run` 产出决策书 `rec["decide"]`。
    `autotune_archive`（依据④）：`p ∝ 质量秩 × 1/(1+探索次数)`，夹 `floor=0.05`
    并归一化 ⇒ **全部臂保留非零概率**（含质量 `None` 的臂）。

  · **新增原料出口**（补「读数缺原料」）：`Pool.aspect_hist`（每圈 append **累计层面数**，
    含同值 —— 平稳本身就是读数）· `View.aspect_hist`/`upstream_layers`/`upstream_texts`/
    `sem_stagnation`（四出口进 `to_dict` 白名单）· `episode_from_result` 增 `goal_readings` ·
    `autotune_score` 增 `goal_med` 质量口径（优先级 `goal_med` > `duty_med` > `tri_rate` >
    `unknown`）+ 出口 `t`。对撞层 `sem_stagnation` **复用引擎已算的 `rephrase_ratio`**
    （★ 两把尺子会漂 ⇒ 不许另算一套）。

  · **验收（第三轮）**：冒烟 **223 ✓ / 0 ✗**（判据扩至 ⑫~⑳）；
    变异体 **36 / 36 判红**（新增 M34 修行方向 / M35 archive 贪心 / M36 对撞不罚复读）；
    真实入口可达性核验（打点探针 + 轻量链路核验 `_chk_v12333_goal_chain.py` 全过）：
    `Pool.merge` 每圈 append ⇒ 逐圈序列成立；回填点（主循环 `14711`）在
    `_apply_view_to_pool`（含 merge）**之后**、`re_evaluate_pool`**之前**；
    三处 `entry` 分支均**无 `continue`** ⇒ 对四层全部可达。
    真跑验收：`_run_full_v12333.py` 增落 `_fullrun_<tag>.goals.json`（见报告七节）。

【第四期 · 四层目标**进入每层每圈运行**（用户战略追加）】

  用户指令：「四层的目标要落实到设计中每层每圈的运行中，而不只是读数」。

  · **只读核查逮到缺口**：`layer_goal_readings` 原**只在** `episode_from_result`
    （事后出口）被调用，**主循环零引用** ⇒ 四层目标确实只是事后读数。
  · **第一期落地（本轮）**：目标读数 → **停止判据**（与 `duty_streak`/`anytime_ok`
    同构：调用方算 → 传 `_stop_reasons` → 加一条理由）：
    修行 `excavate < 0.1`（Heaps 饱和 = 挖尽）· 研究 `settle` 连续 2 圈不涨 ·
    对撞 `sem_stagnation ≥ 0.8`（CORE 罚触顶）或 `fuse` 不涨 · 元 `crystallize == 1.0`。
    ★ 没读数 ⇒ **不表态**（回 `(False,"")`，「没测 ≠ 测出来差」）；
    只加理由、不改象限、不设 stopped（停止与清算分开）；逐圈存 `view.goal_trace`。
  · **Q2 授权改 duty 语义**：目标读数**并列**进层末判定 `view.goal_verdict`
    （与 `duty_verdict` 分开报，**duty 判定一个字不改** ⇒ 历史读数可比）。
  · **真跑逮到 1 个真缺陷**：研究层原读**臆造键** `covered_answer`（view 里
    根本没这字段）⇒ `settle` 恒 null；而判据夹具**自带该键** ⇒ **判据假绿**。
    真实原料 = `settlement.answered/total`（与 `coverage_of` 同源）⇒ 改读它 +
    `covered/uncovered_aspects` 兜底；夹具同步改真实字段。
  · **接线自洽核查**：4 条跑圈函数只见 2 处接线 —— 实为 `_run_layer_C` /
    `_run_layer_stage` 复用 `_run_one_round_B`（后者调 `_b_check_stop`）
    ⇒ 2 处**覆盖全部 7 条路径**（与 duty 同构，**不是漏**）。
  · **验收（第四期）**：判据 **㉑~㉔**（纯函数方向 / 缺读数不表态 / 样本不足不表态 /
    真实入口接线）；变异体 **M37**（臆造键）/ **M38**（断运行接线）/
    **M39**（缺读数当达标）**均判红**（累计 39）。

【第五期：真跑验收 + 目标停因**优先级错位**（一个真缺陷 + 一个隐藏形态）】
  · **真跑 `_fullrun_GOALRUN`（route=`0,1,both,all` · serial · 2 圈，实测 57.2min /
    136 calls / 1.27M tok）**：日志出现
    `⏹ 螺旋停止（第 3 圈）：修行目标已达成（层面边际新增率 0.000 < 0.10，
    Heaps 饱和 ⇒ 挖到不能再挖）` ⇒ **四层目标真的进了运行驱动**（不只是读数）。
    产物 `_fullrun_GOALRUN.goals.json` 四层读数**全部有值**：
    `0: excavate 0.0 / n_aspects 11 / rounds 3`；`1: settle 1.0 / pseudo false`；
    `both: fuse 0.5 / sem_stagnation 0.5 / n_new 11`；`all: crystallize 1.0 / n_hits 4`。
  · **D1 目标停因未登记优先级**（自洽核查逮到）：`stop_priority` 按关键词映射，
    目标停因文案**一个都不命中** `_STOP_CASCADE` ⇒ 全落**最低档 3**（与「体力耗尽」
    同级）—— 语义**刚好相反**（达成 ≠ 力竭）。修：把 `"目标已达成" / "目标受阻"`
    登记进档 0（与「职责增益收敛」同类）。
  · **D2 走满型停因把「被推迟的判据名」嵌进括号**（判据逮到的**隐藏形态**）：
    真实文案是
    `体力耗尽（4 圈走满；1 次停止判据被「未深入方向」推迟（悬置决定稳定，
    自然安住），是被截断不是自然停止）` —— 括号里的两个名字（「悬置决定稳定」
    「自然安住」）**正是档 0 的键** ⇒ 全文子串匹配把「走满被截断」误判成
    「自然停（档 0）」，**语义相反**。修：`stop_priority` **先剥括号再加匹配**
    （剥空则回退原文，不静默变档）。
  · **D3 键区间重叠：裸键「耗尽」吞掉「体力耗尽」**（D2 修好后**立刻**浮现）：
    档 2 有裸键 `"耗尽"`，档 3 有 `"体力耗尽"` ⇒ 档 2 先扫到 ⇒ 截断被报成
    「无信息增益」。修：删档 2 的 `"耗尽"`（`"材料耗尽"` 已覆盖其本意）。
  · **★ 三条通则（跨轮复用）**：
    ① **判据的「负对照」夹具必须抄真产物的原文** —— 我第一版夹具写成
       `"体力耗尽（4 圈走满）"`（简写），恰好**避开**了括号转述 ⇒ 判据假绿；
       换成真日志原文后**立刻**抓到 D2。
    ② **关键词优先级表的键会互相吞** —— 短键 ∈ 长键 ⇒ 先扫到的赢；
       登记新键时必须**回扫全部旧键**，看有没有子串包含。
    ③ **剥括号的函数要能自证** —— 我把「关键词写在括号里」的合成串喂进去
       判「落档 3」当**负对照**，证明剥括号真的生效（不是恒返回原串）。
  · **验收（第五期）**：判据 **㉕**（目标停因落档 0 + 两条真文案负对照 +
    档 2 真文案落档）；变异体 **M40**（未登记）/ **M41**（不剥括号）/
    **M42**（档 2 塞回裸键）**均判红**（累计 **42**）。
    冒烟 **EXIT=0 / 0 ✗**；AUDIT **68 PASS / 0 FAIL**；
    配置 **192 vs 192 键 / 0 差**（手调 29 项**全部已登记**，非漂移）。

【第六期 · 各环节量化 + 降本（用户授权检索前沿依据后落地）】

  用户指令：「各层的锚点重述是否也要考虑量化，以及阴阳展开，候选生成，ing 的输出
  内容，还有 view 的输出重点等也要有相关依据……最好可以减少 LLM 的调用或者寻找
  最优解来减少时间和金钱成本。」⇒ 先检索，再落地，**每条落地都挂一条前沿依据**。
  依据全文见 `_各环节量化与降本依据_v12333.md`（五条硬依据 + 现状核查表 + 降本账）。

【五条前沿依据（逐条对应一处落地）】
  ① **重述失真毁下游链** → 锚点重述
     BenchDrift: The Wording Effect（Thakur et al., arXiv:2608.11694）：含义保持的
     重述使答案**双向漂移**，**强模型损失远大于收益** —— 脆弱性源于**重述本身**；
     Revisiting the Reliability of LM in Instruction-Following（arXiv:2512.14754）：
     同意图换措辞 ⇒ 指令跟随**最多掉 61.8%**。
  ② **对撞是否真发生** → 阴阳展开
     SIEV: A Dialectical View of LLM Reasoning（arXiv:2510.18134）：核心指标
     **对抗性依从率**（反题与正题实际不一致的比例）；「过于胆怯」的模型 pS 高但
     推理深度低 = **假对撞**。Hegelian Self-Reflection（arXiv:2501.14917）：辩证需
     明确缺陷类别（未定义构成要素 / 内容不完整 / 不兼容性 / 自我决定不完整）。
  ③ **早期信号提前停掉低价值样本** → 减少 LLM 调用
     RASC（Wan et al., NAACL 2025）：criteria-based early stopping ⇒ **省 ~70% 采样**；
     DeepConf（ICLR 2026）：局部置信窗口（最差片段）作早停触发 ⇒ 省 **84.7% token**
     且准确率还升 —— ★ **全局平均会掩盖局部塌陷**；Think@n（UVA + Google）：只解
     短前缀算 DTR ⇒ 只继续 Top-K ⇒ 成本 **−49%**。
  ④ **语义密度 / 信息瓶颈** → ing 输出与 view 重点
     Information-Theoretic Principles for Prompt Engineering：**提示压缩率**
     `R = I(X;Y)/H(X)`，优秀提示 `R > 0.6`；**语义密度**：**超过 5 个无信息 token
     ⇒ 性能降 15%+**。
  ⑤ **降本策略叠加顺序** → 全局最优
     Tokonomics 2025 生产案例：单策略 30~50%，**叠加达 85%**；顺序 =
     批处理 → Prompt 缓存（**静态在前动态在后**）→ 模型路由 → 提示压缩 →
     输出长度控制 → 语义缓存。

【★ 现状核查逮到的第一类失败（能力存在但不可达）】
  · **`_expand_pair_merged_once`（阴阳合并成一次调用）是孤儿函数** —— v1.23.16
    删档造成；历史文档（`.workbuddy/memory/2026-10-09.md`、`CHANGELOG.md`、
    `v12316_报告.md`）明确写「**未删**，冒烟判据直接调用它」 ⇒ 删档没删它、
    但**唯一的调用点没了**。⇒ 本项目第 1 类失败（结构性不可达）。
  · 并行展开（`parallel_expand`）早已实现，但它只省**往返**、不省 **token**
    （同 prompt 仍发 N 份）⇒ 合并才有 token 收益。

【落地四项（全部：纯函数 + 零成本 + 可开关 + 有留痕）】
  L1 **激活阴阳合并**（opt-in `merge_expand`，默认 **false** ⇒ 零行为差）：
     `_expand_pair` 内 `len(jobs)==2 and _action_on(..., "merge_expand", False)` ⇒
     走 `_expand_pair_merged_once`；不可用则**回落两臂独立调用**并打印留痕。
     ⇒ 省 1 次往返 + 1 份重复 user 输入 token。
  L2 **阴阳分歧度** `yin_yang_divergence(yin, yang) -> dict`（依据 ②）：
     `divergence = 1 - max_i max_j sim(yin_i, yang_j)`（`_overlap_coef` + `_similar`
     两把尺子取大）；`verdict = "fake_duel" if divergence < 0.30 else "ok"`；
     ★ 任一侧空 ⇒ `divergence=None` + `verdict=""`（不表态）。
  L3 **锚点保真度** `restate_fidelity(question, anchor) -> dict`（依据 ①）：
     `coverage`（问句关键词被锚点覆盖比例）/ `ratio`（长度比）/
     `verdict ∈ {ok, thin(ratio<0.35), drifted(coverage<0.20)}`；
     ★ 任一空 ⇒ 全 `None` + `""`。
  L4 **语义密度** `semantic_density(text) -> float|None`（依据 ④）：
     分子 = 扣掉**填充语**（`的/了/是/在/和/与/或/及…综上所述…`）与**标点**
     （`unicodedata.category` 的首字母 ∈ P/S）后的字符数；分母 = 全字符数。
     ★ 空输入 ⇒ `None`；**纯字符统计，零 LLM 调用**。

【接线（三处**真实入口**，不只纯函数）】
  · ing 输出后：`semantic_density(view.collision)` ⇒ `_quant_note(view, "ing_density", …)`，
    <0.6 打告警（依据 ④ 的 0.6 压缩率边界）。
  · 锚点确定后：`restate_fidelity(_q0, str(view.anchor))`，`drifted` 打告警。
  · `_expand` 调用点后：`_quant_note(view, "yin_yang_divergence", _yy)`，
    `fake_duel` 打告警。
  · `View.quant_readings: Dict[str, dict]` 新字段 + `to_dict` 出口
    （`d["quant_readings"]`，**有才出**）；唯一写入口 `_quant_note(view, key, val)`
    （值不可用就**不写键** —— 「没测」与「测出来是 0」必须区分开）。

【★ 本轮三条判据通则（都被实测踩到）】
  · **判据的负对照夹具必须抄真产物原文**（同第五期通则，本轮再次生效）。
  · **关键词优先级表的键会互相吞**（短键 ∈ 长键 ⇒ 先扫到的赢）。
  · **剥括号的函数要能自证**（喂「关键词在括号里」的合成串判落档当负对照）。
  · **变异体注入必须真实可执行** —— M48 第一版写 `_LLM_HOOK[0](_t)`，而引擎里
    **没有** `_LLM_HOOK` ⇒ 变体会 NameError、spy 计数仍是 0 ⇒ **假绿**。
    改成 `globals()["L"+"L"+"M"].call(prompt="x")`（真的走 `LLM.call`，
    判据 ㉚ 的 spy 打的就是它）⇒ 立刻判红。

【★★ 真跑逮到的真缺陷：`_quant_note` 结构性不可达（已修）】
  · **现象**：真跑 `_fullrun_QUANT`（四层齐 / 2 圈 / 136 calls / 133 万 tok / 59.3 min）
    落盘 `_fullrun_QUANT.quant.json` —— **四层 `quant_readings` 全空**，
    而四层目标读数 `_fullrun_QUANT.goals.json` **全部有值**
    （`0 excavate 0.0 / n_aspects 12`；`1 settle 1.0`；`both fuse 0.8519`；
    `all crystallize 1.0 / n_hits 4`）。
  · **打点探针**（`_probe_v12333_quant.py`，猴补丁包一层、**不改主文件**）四问定位：
    Q1 `_quant_note` 调用 **0 次**；Q2 三个纯函数**都跑了**
    （`restate_fidelity` → `verdict=drifted`／`coverage 0.1875`；
    `semantic_density` → **0.8004**；`yin_yang_divergence` → `divergence 0.3636`／`ok`）；
    Q4 `views` 的值是 `View` 对象（不是 dict）。
  · **根因**：`_quant_note(self, view, key, val)` **只定义在 `MetaDGTF`**，
    而三处调用点在 **`DGTF.run`**（L8776 / L8812 / L8874）——
    `MetaDGTF` **不继承** `DGTF`（每跑一层**新建 `DGTF` 实例**）
    ⇒ `DGTF` 实例解析不到该属性 ⇒ **AttributeError**；
    而三处调用都包在 `try: … except Exception: pass` 里 ⇒ **静默吞掉**。
  · ★ 这是本项目错型「**有接线 ≠ 这跑走得到**」+「**静默失败**」的合体。
    判据 ㉛ 第一版只查「`self._quant_note(view,` 出现 ≥2 次」（**存在性**）
    ⇒ 接线看似在、实则不可达 ⇒ **判据假绿**。
  · **修法**（`_patch_v12333_quantnote_fix.py`）：把 `_quant_note` **降为模块级函数**
    （它本就是纯写入口、**不依赖 self**），三处调用改裸名，
    并删掉 `MetaDGTF` 的方法版（**避免两个真相源**）。
  · **判据升级**（㉛）：从「数出现次数」改为**可达性证明** ——
    ① 模块级 `_quant_note` 必须 `callable`；② **拿真 `View` 写一条，必须落进去**；
    ③ 不许再有 `self._quant_note(`；④ 真实调用点 == 3 处；⑤ 定义份数 == 1。
  · **变异体 M49**（`_quant_note` 退回「孤儿函数」名 ⇒ 调用点解析不到）**判红**。
  · ★★ **本轮最重要的一条通则**：
    **「有接线」≠「这跑走得到」，而「查字面存在」的判据查不出可达性。**
    凡新能力，必须配「**真实入口产出**」判据（跑一次真实入口、**断言产出**），
    不能只查调用点是否存在 —— 与 v1.23.27 的 D1/D2 同族，这是它的第二次显形。

【★ 收尾补漏：`merge_expand` 有读点、没登记】
  · `_action_on(config, "merge_expand", False)` 是**读取端**：`actions` 段有该键就用它，
    没有就落**调用点给的默认 false** ⇒ 行为上「默认关」是对的。
  · 但它**没登记进 `DEFAULT_CONFIG["actions"]`** ⇒
    ① 用户在 yaml 里**打不开**（有开关但没登记 = 配置写了也没用）；
    ② 与审计 J 类（「每个键都要有读点」）**互为反面** —— 这次是「有读点、没键」。
  · 修（`_patch_v12333_merge_key_reg.py`）：`DEFAULT_CONFIG["actions"]` 与出厂 yaml
    各登记一行（**默认 false ⇒ 零行为差**）。配置键 **192 → 193**，两向对账仍 **0 差**。
  · ★ 通则：**新增任何开关，必须同时登记「读取端默认值」与「配置声明」** ——
    只做前者，开关是隐形的；只做后者，是「写了没生效」。

【候选生成产出率（用户点名五处之第五处，第六期第二批次）】
  · 问题：候选池是下游全部付费环节的输入；若一圈生成的「候选」其实是上圈说法的
    **复述**，对偶判断 / ing / view 都在为**零信息量**付费，账面却显示「产出 N 条」。
  · 落地：`candidate_yield()`（模块级纯函数，零 LLM）—— 逐条取与**上圈全部候选描述**
    的最大相似度，`new_ratio` = 相似度低于 `thr`（默认 0.72）的条数占比；
    `collapsed` = `new_ratio < 0.34`。四项读数 `n / n_new / new_ratio / max_sim`。
  · ★ **缺输入 ⇒ 全 `None` + `verdict=""`（不表态）** —— 首次跑是「没得比」，不是
    「没长」；硬给 `collapsed` 会造出**假告警**（M51 打的就是它）。
  · 接线：`DGTF.run` 的 `_drop_banned` 之后、`_dual_judge` **之前** ——
    `_dual_judge` 会改写候选集合，读在它之后 = 读加工过的东西（判据 ㉜ 显式断言顺序）。
    命中 `collapsed` 打一行 `vp` 留痕（明说「可能在为无信息量付费」），**不拦截**
    （红线：留痕与拦截分开）。

【全局链路核查（用户要求以全局视角过一遍四条链路）】
  · **① 自我学习迭代（EML）**：判据全过；日志实证学习真在发生
    （`过闸新增 2` / `升级 2` / `用 2 条（生效 1）`）。本轮改动**零影响** ——
    EML 读写都在 `MetaDGTF` 层，不读 `quant_readings`、不碰 `inp.pool` 暂存量。
  · **② dgtf_app —— 需要更新，已修**：`dgtf_app/selftest.py` 报 `PASS 366 / FAIL 1`，
    失败项「参数标签统一成『键（中文说明）』」。根因：上一轮引擎新增
    `actions.merge_expand`，**app 侧 `_KEY_CN` 没同步** ⇒ `label_for` 退化成裸键。
    ⇒ 又一次「引擎 `DEFAULT_CONFIG` 与 app `_KEY_CN` 各一份键清单」。
    修：补标签 + ★ 把该判据失败消息改成**报出缺标签的键名**（原来只报总数）。
    重跑 **PASS 367 / FAIL 0**；再加一条「mock 的量化格式与真引擎对齐
    （两向对账 · 防漂移）」后 → **PASS 368 / FAIL 0**。
  · **③ 日志显示同步 —— 逮到真断点，已修**：`quant_readings` 原来**只出到
    packed JSON**（产物 md 附录得翻），**正文与日志都没有** ⇒ 引擎算了 4 个读数
    但人类看不见（第 2 类失败的变体：有值但**没有可读出口**）。
    修：每层正文 `_render` 尾部加【各环节量化】段（`_patch_v12333_quantmd.py`）。
    ★ 三处取舍：**遍历全部键**（不维护渲染清单 ⇒ 新读数自动出现）/ 未知键
    **降级为键名** / **中文标签 + 英文键名都给**（可读 + 可 grep + 附录字段名
    覆盖统计不再失真）。
  · **④ 链路依赖 —— 无破坏**：`inp.pool._prev_cand_descs` **不进产物**
    （`Pool.to_dict()` 是手工白名单；实证产物 JSON 里搜不到）；`quant_readings`
    新键对下游无破坏（冒烟 / `--phase all` / AUDIT 全绿）；**三通道**
    （serial / B / C）落盘层与值**逐字相同**（无漂移）。
    ★ 确立下游依赖清单：`quant_readings` 的四个出口 = `to_dict()` / 产物正文（新）/
    产物附录 JSON / dgtf_app（经 md）—— 新增读数**四处都要能看到**。
  · 新判据 **㉟**（可读性：捕获 `_render` 正文，断言有段落 + 中文标签 + 英文键名；
    与 ㉞ **共用一次 mock run**）；新变异体 **M55**（关掉正文段 ⇒ 判红）。

【★ 时序缺陷：候选产出率读数**永不落盘**（真实入口探针逮到）】
  · 现象：收尾按铁律补「真实入口产出」验证（`_probe_v12333_candyield.py`，
    复用冒烟 mock ⇒ **零花费**、走真实 `MetaDGTF.run`）。四问结果：
    `candidate_yield` 被调 **2 次**（接线在），但两次 `verdict` 都是 `''`、
    `quant_readings` 里**没有这个键** ⇒ **读数永不落盘**。
  · 根因（本项目第 3 类失败：**时序颠倒**）：`MetaDGTF` 圈循环里每圈
    `dg = DGTF(entry, ...)` + `view = dg.run(inp)` ⇒ **DGTF 实例与 view 都每圈新建**；
    我把「上一圈候选」写在 `view._prev_cand_descs` 上 ⇒ **下一圈必然读不到**
    ⇒ 恒 `None` ⇒ 永久走「缺输入不表态」分支。
  · 修（`_patch_v12333_candyield_ts.py`，不动任何签名）：`inp.pool`
    （= `self.pools[entry]`）**每层一个、跨圈复用** ⇒ 历史改挂 `inp.pool`。
  · 验收：修后第 1 圈 `verdict=''`（无历史，正确）/ 第 2 圈
    `n_new=0 new_ratio=0.0 max_sim=1.0 verdict='collapsed'`（mock 两圈相同，正确）；
    **serial / B / C 三通道**落盘层都是 `['0','1']` 且值逐字相同（**无漂移**）。
  · 新判据 **㉞**（真实入口产出：断言 `quant_readings` 里真有键 + 形态含 verdict
    + mock 下必须判 collapsed + 源码守卫「`view._prev_cand_descs` 不许出现」）；
    新变异体 **M54**（历史挂回 view ⇒ 判红）。
  · ★ 同期修 ㉜ 的**锚过脆**：原判据钉了整行字面，参数一折行即失配（干净基线判红）
    ⇒ 改成**压掉全部空白后查语义**。通则：**锚不能钉在会变的东西上**。

【★ 降本真缺陷：规则命中「省调用」被自己抵消（本轮真跑逮到）】
  · 现象：`auto_plan(llm=...)` 的 B1 规则命中分支，注释写「命中即定案，
    **不花这次模式调用**」—— 但紧接着为补 `orientation` 又调了
    `plan_orientation(q, cfg)`，而它的签名**只有 `config`**、内部自己
    `new LLM(cfg)` ⇒ **真花掉一次调用**。实测规则命中路径 `LLM.call` = **1**
    （本应 0）。
  · ⇒ 「省调用」的设计意图被自己的补丁吃掉，正是用户点名诉求
    「减少 LLM 调用」的直接违背。★ 形态同「有接线 ≠ 这跑走得到」：
    **成本账目与代码注释不一致，因为没人把「规则命中 ⇒ 0 次调用」当判据跑过**。
  · 修（`_patch_v12333_orientrule.py`）：新增模块级纯函数 `orientation_rule()`
    （零成本，与 `_has_decision_context` **同源** —— 避免「打桩判 decision、
    渲染判 boundary」的双真相）；规则命中时用它，**只有规则拿不准才回落 LLM 版**。
  · 验收：规则命中 ⇒ `LLM.call` **0 次**（构造性证明，spy 计数）；
    取向由本地规则给（决策语汇 ⇒ decision / 否则 boundary）；
    新判据 **㉝** + 变异体 **M52**（方向反）/ **M53**（又偷调 LLM）均判红。

【验收（第六期）】判据 **㉗~㉝**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +
  缺一侧不表态 / ㉙ 保真度方向 + 缺输入不表态 / ㉚ 语义密度方向 + 空输入不表态 +
  **「不调 LLM」的构造性证明**（spy `LLM.call` 计数须为 **0**）/
  **㉛ 可达性**（模块级 + 真写一次 + 无 `self._quant_note(` + **4 处调用** + 1 份定义）/
  **㉜ 候选产出率**（方向两向 + 缺输入不许回 0 + 接线在对偶判断之前 + 真实入口）；
  变异体 **M45**（合并开关默认打开）/ **M46**（分歧度方向反）/
  **M47**（保真度缺输入硬表态）/ **M48**（语义密度偷偷调 LLM）/
  **M49**（`_quant_note` 结构性不可达）/ **M50**（产出率方向反）/
  **M51**（产出率缺输入硬给）/ **M52**（取向规则方向反）/
  **M53**（规则命中又偷调 LLM）/ **M54**（候选历史挂回每圈重建的 view）/
  **M55**（量化读数不进产物正文）**均判红**（累计 **55**）；
  判据 **㉞**（真实入口产出）+ **㉟**（可读性：读数进正文）。
  dgtf_app 自检 **PASS 368 / FAIL 0**（补 `merge_expand` 中文标签 +
  mock 量化格式对账判据后）。
  · **⑤ [顺带] `mock_engine.py` 同步**：它的注释承诺「格式**照抄真引擎**」，
    但真引擎新增量化段/告警行时 mock 没跟 ⇒ **承诺失效**（同一份格式两处定义
    必漂移）。已同步，并新增「mock ↔ 真引擎两向对账」判据把承诺**判据化**。
  · **⑥ [顺带] 新建 app 侧变异体 `_mut_app_v12333.py`**：本项目红线是
    「审计必须自带变异体」，但 **app 侧此前一直没有** ⇒ 新增的 app 判据没人
    背书。现覆盖 M-A1（mock 段落改名）/ M-A2（`merge_expand` 标签清掉），
    跑完**逐项核对源码已还原**。
  · ★ 判据随实现更新：㉛ 原硬编码「调用点 == 3」，新增第四处接线后**干净基线判红**；
    修法是**把新调用点显式登记进判据**（3 → 4），数量约束仍为硬等式 ——
    不是放宽阈值。

★ v1.23.33 收束摘要
  交付物：`元DGTF-V1.23.33.py` + `dgtf_config.yaml`（两键 + 升级段）+
  `v12333_报告.md` + 探针/变异体（沿用 `_probe_v12332.py` / `_mut_v12332.py`，已扩容）。
  改了哪几处：anytime 停止（opt-in）/ 发散+指针 / 预算 bandit（opt-in）/
  compact 读数 / 锚点离线+内部批判 / 分级证明标准 / 裁决维度 / 陈旧度 / 三行读数 / 两键 /
  **四层目标读数（layer_goals）+ AutoTune 三阶段决策 + archive 开放探索 +
  目标读数进入每层每圈运行（停止判据 + 层末并列判定）+ 停因级联两处修正
  （剥括号匹配 / 档 2 去重叠键）** +
  **目标读数进圈内动作（第二期：`layer_goal_action_hint` → `_goal_hint_next` →
  两条 prompt 的 `{goal_hint}` 注入；★ **零新增接线点**，复用第一期两处
  `_layer_goal_now`）** +
  **各环节量化 + 降本（第六期：激活阴阳合并 / 阴阳分歧度 / 锚点保真度 /
  语义密度，四项纯函数 + 零成本 + 可开关 + 有留痕 + 三处真实入口接线）**。
  未做（有意）：anytime 只用于「结构增长」这一维（一致率每跑只采一次，无逐圈序列）；
  bandit 只做圈数上限（动作空间越大、探索代价越高）；
  锚点联网可达性验证留给联网通道（不把可选成本塞进主路径）；
  三阶段决策**只出建议不落地配置**（红线：建议与执行分开）；
  archive 只在后期学习段使用，不介入前期选择；
  阴阳合并是 **opt-in**（`merge_expand` 默认 false ⇒ 零行为差）；
  语义密度只做**读数与告警**、不自动裁剪 prompt（压缩是不可逆的信息损失，
  要改行为必须显式开关）；分歧度/保真度只**标注不改流程**（红线：建议与执行分开）；
  RASC/DeepConf/Think@n 三类早停**只做了依据储备**，未接进主循环
  （它们要求「判据可提前评估」，本轮先补齐**判据的尺子**，早停留给下一期）。

---

v1.23.32 相对 v1.23.31

【主题】学科吸收：把「读数不是分数」做成**可执行的尺子**。来源是本轮检索产出的
两份映射（`_开源映射_v12332_候选.md` / `_学科与前沿映射_v12332.md`）。

【★ 最重要的一条：三态一致率的尺子一直是错的】
  · 学科事实：**原始一致率不计机会一致** —— 偏斜标签下「随便判」也会高一致。
    实证对照（Amazon 团队 2025）：原始一致率 **79% ↔ Cohen's κ 仅 0.34~0.44**。
    而三态（decidable/partial/undecidable）**天然定序** ⇒ 应用 **ordinal** 距离函数。
    Krippendorff 口径：**α≥0.800 可靠 / 0.667~0.800 仅支持暂定 / <0.667 不可靠**。
  · ★ **用真跑数据实算**（上一版产物，6 条子问题 × 3 票）：
    旧读数 `tri_state` = **3/6 = 0.500**；而复算得
    **ordinal α = −0.333**、加权 κ = **0.000**、判词「不可靠」。
    ⇒ 原始 50% 看着「中等偏低」，机会校正后是 **0 到负** —— 那次标签基本**无信号**。
    这与此前「一致率=标签可定义性边界」的定性不冲突，但**更狠**：
    不是边界附近的噪声，而是在机会校正尺度上**无信息**。
  · 落地：原始一致率行**改标题并加注**「不计机会一致，须与下行一起读」；
    新增「**机会校正一致（ordinal）**：α / 加权 κ（n_unit）｜判词」；
    新增「**少数类一致（undecidable）**」—— 偏斜时多数类共识廉价，少数类一致才有信息。
    样本不足 ⇒ **印「未测（样本不足）」而不印 0**。

【其余五项（全是口径/留痕，不改机制语义）】
  ② **读数尺度登记**（Stevens 测量论四重）：`tri_state_agreement`/`tier`/`csd_warning`
     = ordinal；`duty.S` = interval；`semantic_entropy`/`touch_rate` = ratio。
     配 `scale_word_violations()`：**定序读数不许出现「均值/两倍/百分比提升/标准差」**
     —— 定序尺度的差值无定义，在其上做算术是测量学错误。未登记 ⇒ `unknown`（不许默认当 interval）。
  ③ **停因级联**（SHP）：停因按优先级排序（判定/收敛 > 熵收敛 > 无信息增益 > 硬上限），
     产物另报「【主因（最高优先级）】」。★ **不变量：主因必须出现在全部触发里**
     —— 报告的原因不能是没触发的那个；未匹配文案落最低档，**不静默丢弃**。
  ④ **成本两分**（SHP）：`LLM` 新增 `ops_*` / `eval_*`，按 `cost_bucket(stage)` 分类；
     **未登记 stage 一律计 ops**（把任务成本说小才是失真）。产物新增「成本两分行」。
     不变量：`ops_calls + eval_calls == total_calls`。
  ⑤ **CSD 早期预警**（复杂系统/生态学）：逐圈序列的**方差 + lag-1 自相关**，
     层尾出读数。★ 口径写死在文案里：「**概率性评估，非预测**」（学科自己的反面证据：
     六种 regime shift 机制里多数没有 CSD 前兆）。★ **不参与任何停止判定**（零行为改动）。
  ⑥ 阈值沿用学科口径（Krippendorff 的 0.800/0.667 是**定义**，不是本项目自定）
     ⇒ **本版不新增任何配置键**。

【第二批（同样全是读数/结构，不改行为）】
  ⑥ **截断两向记账**（AgentExit）：截断时**同时**报「省下的圈」与「丢掉的 core 问项」——
     只报一面必然误导。
  ⑦ **输入自检加规则类**（llm-guard）：不可见字符（零宽/软连字符）+ 指令注入形态
     + 预设式（「为什么X」预设 X 成立）。**只取规则类**（其 ML 扫描器会拉
     transformers，违「单文件零依赖」）；**不计入 LLM 调用**。
  ⑧ **言语行为标注**（Austin/Searle）：行动按**承诺/断言/请求**分类；全是「请求」
     无「承诺」⇒ 出「公文体风险」告警（不是方案，是祈使句堆砌）。
  ⑨ **FMEA 可检测性**（安全工程）：RPN 的第三维 —— **不可检测的失败最危险**；
     产物**无条件输出**本节（「没输出」会被读成「没有失败」）。
  ⑩ **多样性预算**（Ashby 必要多样性定律）：本跑动用的「层×通道」组合数；
     踩到上限时「跑得不好」是**控制论上不可能**，不是工程缺陷（读数，非分数）。
  ⑪ **nogoods 矛盾档案**（ftl-beliefs）：`nogoods.jsonl` **append-only**，
     闸拒与「用了但未达标」都留档 —— 矛盾只累积、不覆盖。

【★ 本轮抓出并修掉的一个判据缺陷（M9 假绿）】
  「成本两分」最初把分类逻辑**内联在 `LLM.call` 里** ⇒ 判据只能看源码，
  变异体（分类恒返回 ops）**假绿**。修法：抽成纯函数 `cost_bucket(stage)` 并改测它。
  ⇒ 通则：**判据要能驱动到的逻辑，才有资格被当判据**。
  ★ 同一条通则在本轮被**第二次**踩到（M15）：nogoods 的写入内联在 `_eml_finish` 里，
    判据只能断言「源码里有这个常量」⇒ 变异体「抹空记录内容」**假绿**。
    修法：抽 `nogood_record()` 纯函数 + 判据加**纯函数直测**（不依赖引擎构造）。

【验收】
  · 主文件 **22282 行 / 纯 CRLF**（v1.23.31: 21551）。
  · 真实入口探针 `_probe_v12332.py` **38 ✓ / 0 ✗**
    （关键数字：偏斜夹具 **原始 0.900 vs α 0.294**；
    v1.23.29 真跑 **0.500 vs α −0.333**；v1.23.32 真跑 **0.667 vs α 0.065**）。
  · 变异体 `_mut_v12332.py` **15 / 15 判红**（干净基线先绿）。
  · 冒烟 **223 ✓ / 0 ✗**；`--phase all` 全绿；AUDIT **67/0**；复审 **16/0**。
  · 配置：**未新增任何键**（只同步头部版本 + 升级段）。

★ v1.23.32 收束摘要
  交付物：`元DGTF-V1.23.32.py` + `dgtf_config.yaml`（头部/升级段）+
  `v12332_报告.md` + `_probe_v12332.py` / `_mut_v12332.py` +
  两份映射文档（`_开源映射_v12332_候选.md` / `_学科与前沿映射_v12332.md`）。
  改了哪几处：一致率口径 / 尺度登记 / 停因级联 / 成本两分 / CSD 读数。
  验收数字：探针 28✓0✗；变异体 9/9 判红；冒烟 0 ✗；配置键新增 0 个。
  未做（有意）：CSD **不参与**停止判定（学科反面证据不支持当预测器，先当读数观察）；
  anytime-valid（e-process）停止留待下一版（属机制级改动，本版先修口径与读数）；
  `tri_state` 字段形状不动（新指标走新键 `tri_alpha`，加性改动）。

---

v1.23.31 相对 v1.23.30

【主题】EML · 经验记忆回路 —— 让元DGTF **跨跑储存记忆**，并在**每次运行中
自我学习与迭代**（读 → 用 → 写 + 一道质量闸 + 五条学坏防线）。

【缺口诊断】原来只有「版本记忆」（CHANGELOG）与「统计记忆」（auto 读历史读数），
没有**经验层**（哪类做法有效）与**闭环**（跑完写回 → 下次生效 → 再验证）：
`auto` 只读**数**不读**内容**；`.workbuddy/memory/` 是人写的、机器不回写；
v1.23.30 的 `duty` 读数只留痕、不参与下次怎么跑。

【前沿依据（2025，皆已读原文要点）】
  · **ACE**（arXiv 2510.04618）：三角色 Generator/Reflector/Curator；★ **不重写
    知识** —— 实测把 1.8 万 token 策略压缩成 122 token，准确率 66.7→57.1。
  · **Memory-R1 / Mem0**：写入决策 ADD/MERGE/UPDATE/**矛盾单独建档**。
  · **WebCoach**：经验作**建议**注入（成功率 47%→61%，**步数不增**）⇒ 强制双边记账。
  · **MRRL**：**质量闸四问** + micro/meso/macro 三级反思 + 遗忘清扫。
  · **NAACL'25 子问题覆盖** / **SAGE** 遗忘曲线。
  · 开源对照（本轮检索所得）：`kvyb/llmace`（ACE 的 Python 实现）、
    `ulandz/evermind`（**RRIF 四维**）、`hanishkeloth/agentmemory`
    （procedural execution-tracking）、`aravindvaddi/MemoryMCP`（访问加强）。

【改动】
  ① 存储 `dgtf_memory/`：`episodes.jsonl`（每次跑的标准化 episode）·
     `playbook.jsonl`（增量经验条目，**append-only**）· MEMORY.md（自动生成索引）。
  ② **读** `_eml_prepare` / `eml_recall`：RRIF 四维打分
     `recency^0.5 × evidence × weight × freq`（第四维 Frequency 吸收自 evermind）；
     只取 `active`，`shadow` 一律不生效。
  ③ **用** `_eml_apply`：生效面**只有两处** —— 截断过的层 `rounds+1`、
     `duty.floor`。★ **绝不注入答案内容**（红线「输入是形状不是数据」）。
  ④ **写** `_eml_finish`：micro 抽候选（截断/职责未尽/三态不稳/只贵不好）→
     质量闸四问（evidence / contradiction / verifiable / redline）→
     只增合并（同键**累证据**不新增行）→ meso 升级 → macro 父条目（**只索引**）→
     遗忘清扫（只改状态位）→ 访问加强（`used_outcomes`，**达标才加强**）。
  ⑤ 新增 `playbook` 配置段，**出厂默认 `mode="shadow"`** ⇒ 零行为差。
  ⑥ 产物头部新增「本次记忆（EML 经验回路）」块：用了几条 / 生效几条 /
     过闸新增几条 / 被闸拒原因分类 / 库内总数。

【★★ 本轮最该记的一条：测试污染了生产数据】
  一次冒烟上百次 `run()`，这些**无 run_id** 的跑次把真实条目的**证据计数**
  从 2 灌到 4 ⇒ 直接触发 `promote` —— **测试替生产刷票**（promote 正是按
  证据数判的）。两道修：① 冒烟 `build_cfg` 把 `playbook.dir` 指到临时目录；
  ② 引擎级闸：**无 run_id 的跑次一律不写库**（`learn_from_anon` 显式才收）。
  ★ 通则：**凡是「按次数/证据累计」才生效的机制，先回答「谁在计数」**。

【★ 本轮抓出并修掉的 5 个真 bug（全部写进通则）】
  1. **同键候选被判「重复」拒掉** ⇒ 证据永远累不到 3 ⇒ **学不会**（探针 T9 抓出）。
     改为「同键 = 累证据 +1」（这本就是 meso 的输入）。
  2. `n_evidence` 从 0 起：写下它的那次跑本身就是证据 ⇒ 从 1 起（口径错）。
  3. MEMORY.md 落到默认目录而非配置目录（`dirpath` 未透传）。
  4. **YAML 注释里混进裸 `\r`** 把行劈断 ⇒ 解析失败。★ 写进配置/代码的字符串
     要扫裸 CR（`count(\r) != count(\r\n)`）。
  5. **阈值判据缺负向用例**：meso 门槛只测「够则升」⇒ 门槛写恒真的错实现照样
     过关（变异体 M4 假绿）⇒ 补「证据 1/3 ⇒ 不许升」。★ **阈值类判据必须两向测**。

【验收】
  · 冒烟 **223 ✓ / 0 ✗**（新增 `check_v12331_memory_loop`）。
  · 真实入口探针 `_probe_v12331.py` **35 ✓ / 0 ✗**（含 T9 构造性证明、T10 三态）。
  · 变异体 `_mut_v12331.py` **10 / 10 判红**（干净基线先绿）。
  · AUDIT **PASS 67 / FAIL 0**；复审探针 **PASS 16 / FAIL 0**。
  · 配置两向对账：`DEFAULT_CONFIG.playbook` ↔ 出厂 yaml **逐字 0 差**。
  · **记忆库首建**：把最近 **5 次真跑**补录成 episode
    （`_demo_v12331_seed_memory.py`）⇒ 5 条经验、**1 条升 active**
    （修行层被截断 3 次 ⇒ 同向证据到 3 ⇒ `rounds_delta: layer 0 +1`）；
    证据字段全是真跑 id，**无匿名条目**。

【★ 构造性证明「会学」（实测序列）】
```
第 1 跑：过闸新增 2 · 库 2 条（shadow）
第 2 跑：过闸新增 2 · 升级 2      ← 同向证据累到 promote_n ⇒ shadow→active
第 5 跑：读到 2 条 → 真生效 1 条 → applied=[{L0001, rounds_delta, layer=1, 3→4}]
         访问加强 {strengthened: 1, negative: 0, duty_med: 0.5}
```
裁决的是「读到 + 生效 + 留痕」，**不是「分数更高」**（红线：只升不降的指标是自欺）。

★ v1.23.31 收束摘要
  交付物：`元DGTF-V1.23.31.py`（21551 行 / 纯 CRLF）+ 出厂 `dgtf_config.yaml`
  （playbook 段）+ `_设计_经验记忆回路_v12331.md` + `v12331_报告.md` +
  `_probe_v12331.py` / `_mut_v12331.py` / `_demo_v12331_seed_memory.py` +
  **真实记忆库 `dgtf_memory/`（9 条，2 条 active）**。
  改了哪几处：存储三段 / 质量闸四问 / 三级反思 / 遗忘 / 访问加强 / 配置段 / 产物块。
  验收数字：冒烟 223✓0✗；探针 35✓0✗；变异体 10/10 判红；AUDIT 67/0；复审 16/0；
  配置差异 0 项。
  未做（有意）：不自动切 `on`（出厂 shadow，先观察）；不注入答案/结论；
  不把学习效果做成分数；检索用规则（无向量库/embedding 依赖）。

---

v1.23.30 相对 v1.23.29

【主题】层职责守卫（LDG）—— 在**停止/收敛处**回答一句：这一层到底替原始问题
干了什么。起因是最近一次真跑的机器读数（不是观感）。

【诊断（`_ana_v12330_quality.py`，全部实算）】
  · **缺省冒充读数**：`distance_to_question` 缺省 1.0（模型没报就顶格）且只在
    `<1.0` 时渲染 ⇒ 该跑 3/4 层「没有这个读数」在产物里完全不可见；
    全量 **22/37 层-次（59%）** 为缺省顶格。
  · **对齐空转**：研究层「独立度 1.00」配「对齐覆盖率 0.00」⇒ 生成的结构
    **完全不落在问题上**（15 份产物中 4 份对齐覆盖率为 0）。
  · **截断冒充停止**：一层停在「体力耗尽（未触发任何停止判据）」；
    全量 **10/15 份（67%）** 至少一层被截断。
  · **交付面被内部面淹没**：交付正文 71 行 / 1922 字 = 全文 **3.5%**；
    内部明细 86.5%；交付正文问项词只命中 2/11。
  · **回溯实测（守卫跑到上一版产物上）**：四层职责度 S = 0.04 / 0.00 / 0.03 /
    0.00（门槛 0.35），四层对原问题的「直接断言」合计 **2 条**
    （1/47、0/58、1/52、0/95）。这就是「回答不了原问题、输出无质量内容」
    的量化形态。

【设计依据（2025 前沿，原创落地）】
  · LiveRAG / SIGIR 2025：Coverage（加权）+ Relatedness（惩罚无用断言）取
    **调和平均** —— 本版保留其结构，但用**规则判定**替代其 NLI 判定（把开销
    从「每条断言一次 LLM」压到 0），并把它从「评测指标」改成**层内停止判据
    + 署名纪律**（原论文不做控制）。
  · NAACL 2025 子问题覆盖（core/background/follow-up）：本版把「附加目标」
    单列 followup（权重 0.1），**防一句并列把「主问没答」洗成高覆盖**。
  · EMNLP 2025 自纠收敛（每轮只削固定比例 ⇒ 边际递减）：落成新停止理由
    「职责增益收敛」。

【改动】
  ① 三读数（规则、零新增调用）：`question_aspects` 抽问项并分
     core/background/followup；C 按权重加权命中；R = |Direct|/(|Direct|+|Useless|)；
     S = 2CR/(C+R)。
  ② 守卫动作（停止/收敛处）：S < `duty.floor`(0.35) ⇒ 写**独立判定行**
     `职责未尽：…` 并点名缺失 core，**渲染时紧跟停止理由**（看到「自然安住」
     的同一屏必看到它）；缺失 core 并入后续层 carry（定向提醒，不重跑本层）。
  ③ 新停止判据「职责增益收敛」：连续 `patience`(2) 圈 ΔS < `tau`(0.02)
     ⇒ 层可**因推不动而停**（直治 67% 的截断）。
  ④ 新增 `duty` 配置段（floor/tau/patience/remedy_rounds），默认 = 引擎常量
     ⇒ **出厂零行为差**。
  ⑤ 修真：`distance_to_question` 缺省 `1.0` → `None`，渲染改「有值才印」
     （三处：manifest / lines / `save_result`）。

【★★ 本轮最该记的一条：测试污染了生产数据】
  一次冒烟上百次 `run()`，这些**无 run_id** 的跑次把真实条目的**证据计数**
  从 2 灌到 4 ⇒ 直接触发 `promote` —— **测试替生产刷票**（promote 正是按
  证据数判的）。两道修：① 冒烟 `build_cfg` 把 `playbook.dir` 指到临时目录；
  ② 引擎级闸：**无 run_id 的跑次一律不写库**（`learn_from_anon` 显式才收）。
  ★ 通则：**凡是「按次数/证据累计」才生效的机制，先回答「谁在计数」**。

【★ 本轮抓出并修掉的 5 个真 bug（全部写进通则）】
  1. 新分支插在它读的变量赋值**之前** ⇒ `UnboundLocalError`。
  2. **署名块时序**：职责判定先写 `stop_reason` ⇒ 把「体力耗尽」文案顶掉。
     ★ 读数可以早算，**署名必须晚写**。
  3. 把职责判定塞进 `stop_reason` 撞红线「**停止与清算分开**」⇒ 改独立判定行。
  4. 跨通道计数器挂在调用方 `state` ⇒ 串行通道没有该变量，四层全崩。
     ★ **挂对象（view），不挂调用方局部**。
  5. `view.quality_flags` 被收尾清洗**整表覆盖** ⇒ `duty_short` 静默丢失。
  ★ 变异体替判据补强三处（M3/M5/M9 起初假绿）⇒ **「不许越界」类判据必须
    钉等式/公式，不能只钉不等式**；以及「只查字段缺省查不到入口缺省」。

【验收】
  · 冒烟 **223 ✓ / 0 ✗**（v1.23.29: 222 ✓）。
  · 真实入口探针 `_probe_v12330.py` **21 ✓ / 0 ✗**。
  · 变异体 `_mut_v12330.py` **9 / 9 判红**（干净基线先绿）。
  · AUDIT **PASS 67 / FAIL 0**；复审探针 **PASS 16 / FAIL 0**。
  · 配置两向对账：`DEFAULT_CONFIG.duty` ↔ 出厂 yaml **逐字 0 差**。

★ v1.23.30 收束摘要
  交付物：`元DGTF-V1.23.30.py` + 出厂 `dgtf_config.yaml`（duty 段）+
  `_设计_层职责守卫_v12330.md`（设计+依据）+ `v12330_报告.md` +
  `_ana_v12330_quality.py` / `_demo_v12330_ldg_on_realrun.py`（回溯演示，
  落在 `outputs/_ldg_v12330_回溯_20261013_205109.md`）+ 探针 + 变异体。
  改了哪几处：三读数 / 守卫动作 / 新停止判据 / duty 配置段 / distance 缺省修真。
  验收数字：冒烟 223✓0✗；探针 21✓0✗；变异体 9/9 判红；AUDIT 67/0；
  复审 16/0；配置差异 0 项。
  未做（有意）：不做自动重跑本层补救（只做下游定向注入）；不把职责度做成
  分数/排序（红线）；问项抽取用规则而非 LLM（守卫不能变成新开销源）。

---

v1.23.29 相对 v1.23.28

【主题】收束版：清欠 + 冗余收敛 + 读数修真。上一版挂账**全部处理**，不新增
机制面，把审计抓到的冗余、假读数、口径错位一次清完。

【审计结论（`_审计_v12329_全维度.md`）】
  · A1 产物冗余：`## 这一次我是谁` 是 `## 附：逐层明细` 的**截断复制**
    （`"[<层>] " + view.manifest[:900]`），且 `self.self_text` 无消费方。
  · B1 模式冗余：9 模式近 80 跑 serial 71 / B 6 / C 1 / 其余六个 0；
    auto 分派**先花一次 LLM 调用**再说「退回 serial」。
  · C1 口径错位（真 bug）：`touch_rate` 在 `round_log` 无
    `anchor_touched_n` 键时误入逐圈分支 ⇒ 非空 `anchor_touched` 也恒 0.0；
    `aspect_carry_rate` 同款（把「未接线」印成「延续了 0 条」）。
  · C2 `DEFAULT_CONFIG` 两行缩进断裂（4 空格 vs 兄弟行 16 空格）。
  · D1/D2/D4/D6 = v1.23.28 §7.1 挂账四项。

【改动】
  ① A1：`## 这一次我是谁（索引）` 只留层标签 + 字数 + 指向（去整段复制）。
  ② B1 **规则优先分派**：新增模块级唯一实现 `mode_rule(q)`（并列→B /
     递进→C / 短问句→serial，命中即定案 confidence 0.9 source=rule），
     **三处接线**（`_decide_parallel_mode` / `plan_resources` /
     `auto_plan(llm=...)`）统一先走规则 ⇒ 省掉那次「退回保守」的调用。
     自动路径收敛到 `_AUTO_REACHABLE_MODES = ("serial","B","C")`；
     D~H 六个 stage 模式保留为**显式传参**选项。
  ③ C1：`touch_rate` 加 `_has_per_round` 前提（键确实出现过才走逐圈，
     否则退回一次性观测 1.0/0.0 —— 0.0 在该口径是**真实答案**，不是冒充）；
     `aspect_carry_rate` 无延续读数时返回 `None`（渲染层印「—」）。
  ④ C2：缩进修复（16 空格）。
  ⑤ D1 **相对分位阈值**：`sem_thr_relative()` 取本批两两 sim3 的 p60 再
     夹取 [0.20, 0.55]；`belief.sem_entropy_thr: rel` 启用（写数字 = 旧
     绝对口径，**默认零行为差**）。
  ⑥ D2 **语义归并（保守）**：`_BELIEF_MERGE_SIM = 0.85`（刻意高门槛：
     不同主张实测 0.00~0.79 够不到），默认**关**；命中 ⇒ 把「换说法重提」
     记为**已存在条目的一次复现**（occurrences+1，text 保留首说法），
     `merge_log` 留痕出口（from/into/sim/source）；配置
     `belief.merge_semantic` / `belief.merge_sim` 显式下发到每个池。
  ⑦ D6：`honest_about_empty` 历史触发率实测 **14/101 ≈ 13.9%**（能力
     真实可达、非常发）—— v1.23.27 挂账收口。
  ⑧ D4：Pool 侧前向守卫（`__dataclass_fields__` 逐字段查出口）+ View 侧
     `asdict` + property 显式补口，双口径各自有守卫 ⇒ **不改代码**，
     以守卫背书（收束版不做无收益重构）。

【★ 本轮踩到的两个坑（写下来防复用）】
  · **规则层插在 `_route_default` 赋值之前 ⇒ UnboundLocalError**（冒烟
    [P2-8] 抓出）。「给多出口函数加统一后处理要套外层、不插中间」的
    同类变体：**新分支要放在它读的变量已就绪之后**。
  · **判据的题面会被新分派改变语义**：v1235 [1d]/[1e]、v71 F8、v1.22.1 P5
    原来都靠「桩调 LLM 返回任意 mode」来测钳制/兜底；规则命中后 LLM 根本
    不被调 ⇒ 必须把题面换成**规则拿不准**的那类（`_SMOKE_RULE_MISS_Q`），
    并**新增 [1f] 判据**钉住「规则命中 ⇒ 三处同案且零调用」。
    这是「判据随实现更新」，不是放宽阈值。

【验收】
  · 冒烟 **222 ✓ / 0 ✗**（v1.23.28: 221 ✓）。
  · `--phase all` 全绿，AUDIT **PASS 67 / FAIL 0**。
  · 真实入口探针 `_probe_v12329.py` **20 ✓ / 0 ✗**。
  · 变异体 `_mut_v12329.py` **8/8 判红**（干净基线先绿）：A1 标题、
    B1 模式集放水、C1 守卫恒真、D1 rel 关死、D2 阈值放水 / 开关旁路 /
    出口删除 / 下发断线。
  · 复审探针 `_probe_v12328_review.py` 指向本版 **PASS 16 / FAIL 0**。
  · 配置两向对账：`DEFAULT_CONFIG` ↔ 出厂 yaml **逐字差异 0 项**。
  · 主文件 **20385 行 / 纯 CRLF**（v1.23.28: 20146）。

★ v1.23.29 收束摘要
  交付物：`元DGTF-V1.23.29.py`（20385 行 / 纯 CRLF）+ 出厂 `dgtf_config.yaml`
  （头部版本 + 升级段 + 2 个新键）+ `v12329_报告.md` + `_审计_v12329_全维度.md`
  + 探针/变异体脚本各一。
  改了哪几处：A1 索引化 / B1 规则优先三分派 / C1 两读数口径 / C2 缩进 /
  D1 相对阈值 / D2 保守语义归并 / D6 统计收口 / D4 守卫背书。
  验收数字：冒烟 222✓0✗；--phase all 全绿 AUDIT 67/0；探针 20✓0✗；
  变异体 8/8 判红；复审 16/0；配置差异 0 项。
  未做（有意）：D~H 六个 stage 模式**不合并**（手动选项保留）；
  `_v1230_w6_runs.json` 陈旧基线维持「已登记的授权陈旧 + 显式警告」；
  历史挂账 #2（等待型，仅配判据）/#3（留痕不删，布尔兼容）维持。

---

v1.23.28 相对 v1.23.27

【要解决的问题】v1.23.27 交付后做了一次**收尾核查**：把九项新机制**逐个走
真实入口**（不是调纯函数），量「能力是否真的落地」。结论是**三项不合格** ——
纯函数判据全绿，真实入口却拿不到产出。本版围绕「接线」而非「算法」修，
外加全仓库复审抓到的三类问题。

【★ 核心教训】**纯函数判据全绿 ≠ 该能力在引擎里可达**。
  v1.23.27 的 D1/D2 判据全是 `mod.belief_transition(...)` 直接喂构造入参 ——
  完美通过；而真实入口下 `upsert_belief` 被嵌在「结构名是**新的**」守卫里
  ⇒ 复现被 `_DUP_SIM` 挡掉 ⇒ `support` 恒 1 元素 ⇒ `stable` 永不成立。
  新能力从此必须配一条「**真实入口产出**」判据（`check_v12328_real_entry`）。

【三项「效果不如原版」的重新设计】
  ① A3 双读数**死字段** → 补出口。
     `touch_rate` / `aspect_carry_rate` 是 `View` 级 property，而
     `View.to_dict = asdict(self)` **不收集 property** ⇒ 值算出来了、
     产物里读不到。改：`View.to_dict` 显式补两个键（`asdict` 之外）。
  ② D1/D2 **三条迁移不可达** → 登记与去重解耦。
     · `upsert_belief` 移出「新条目」守卫 ⇒ 每圈都登记（复现是 D2 前提）；
     · `sources` 用**层名**（0/1/both/all）而非圈号 —— 同一主张被不同层
       独立提炼才算「独立复现」，用圈号会让「同一层反复说」冒充独立；
     · `attack` / `resolved_by` 元数据在注入点统一补（`_belief_attack` /
       `_belief_resolved`）⇒ 两条驱动从 0 处传参变为真的传。
  ③ D3 可观测字段**未接线** → `add_undecidable` 出口前刷新一次
     （唯一调用点）⇒ 产物 `semantic_entropy` 从恒 `null` 变为有值。

【D2 `revoked` 规则**重新设计**（对称化）】
  改前：`if _atk and len(_atk) >= len(_sup): return "revoked"`。
  ★ 真实入口下 `_sup` 每圈恒 +1（每层一个来源）、`_atk` 每圈至多 +1
    ⇒ 该条件**只在「每圈都攻击」时成立** —— 「攻击面 ≥ 支持面」实际
    退化成「攻击从未缺席」。v1.23.27 因登记被守卫吞掉（条目恒 0 个）
    从未暴露；修好登记后立刻变成「只要一直被骂就推翻」。
  改后：**与 `stable` 用同一把尺子** —— 攻击也要跨 ≥2 个**不同来源**、
    跨 ≥2 圈独立复现才判 `revoked`（`_BELIEF_REVOKE_SOURCES = 2`）。
    新增 `attack_sources` 字段（与 `support` 对称），缺省回落 `sources`。
  ★ 为什么更符合整体机制：DGTF 的核心是「对撞」——对撞的判据从来不是
    「谁说得次数多」，而是「谁经得起独立复现」。支持方如此，反对方亦然。

【全仓库复审抓到的三类问题】
  ① **E1 增益透传真 bug**（`_gains` 键取错字段）。
     `{str(x.get("text","")): x.get("g") for x in trace if x.get("picked")}`
     —— trace 条目的键是 **`"picked"`**（值是文本），**没有 `"text"` 键**
     ⇒ 键恒为 `""` ⇒ 后续查找**恒 miss** ⇒ `expected_gain_engine` 恒
     `None`、`gain_source` 恒 `"model"`。E1 算出来的 G **从未到达输出**。
     改：`x.get("picked")`。这也**收口了 v1.23.27 的已知待办**
     （「探针 gain_source 标记未落盘」）。
  ② **`_GAIN_MARGINAL_FLOOR = 0.0` 让守卫恒假**。
     `G ∈ [0,1]` + `if _best_g < _fl:` ⇒ **永不成立** ⇒ `below_floor`
     结构性不可达（「宁少勿滥」的核心分支从没跑过）。改：`0.02`。
  ③ **A1 `A{n}` 两套编号不同物 + `untouched` 从不带 id**。
     `aspect_units['A1']` = 锚点触及第 1 条 vs `aspect_targets['A1']` =
     `covered_unders` 第 1 条 —— 两套表同号不同物；且 `untouched` 写入
     只有 `{"desc":...}` ⇒ 渲染前缀**永远印不出**。改：`untouched` /
     `anchor_touched` 写入带 `id`，`aspect_targets_v12327` 按
     `aspect_units` 的实际 id 对齐。

【新增/更新判据（`smoke_test.py`）】
  · `check_v12328_real_entry()`：走 `Pool.add_undecidable`（引擎唯一写
    入口）数圈，断言 `belief_transitions` 真的含 `stable` / `revoked` /
    `resolved` 三种迁移 + **同层负对照必须为 0**（stable 与 revoked 各一条）。
  · A1 补「`untouched` 带 id 且 ∈ `aspect_units`」；A3 补「`to_dict` 出口」；
    E2 补「`floor > 0` 且 G=0 候选被 `below_floor` 挡下」。
  · D2 纯函数判据**随实现更新**：`attack>support` → 「跨 ≥2 来源 + 同
    来源负对照」。
  · `Pool.to_dict` 出口 `belief_status_counts` / `aspect_units`
    （两个 A1/D1 池级镜像）。

【配置】`dgtf_config.yaml` 头部版本 → v1.23.28，升版段追加；`DEFAULT_CONFIG`
  新增 `belief.revoke_sources=2`（值 = 引擎默认 ⇒ 出厂即默认）。

【★ 真跑核对产物后的第二轮修复：D3 语义熵三次迭代 + 一个死字段】
  交付前把真跑产物（`outputs/20261013_144044_*.packed.json`）**逐字段
  核对**新落盘项，抓到的**都不是**「字段缺失」，而是「**字段有值但读数
  无信息量**」—— 比缺字段更隐蔽。

  ① **D3 `semantic_entropy` 出厂版实测 6/6 恒 `h_norm = 1.0`**。
     读数**零信息量**。三轮定位与重设计：
     · 第 1 轮（出厂）：`_txt = [本条目text] + 全池 structural_amps`
       —— 任何条目都摊上一批**其他主张**的文本 ⇒ 簇必然全异
       ⇒ 恒为上界。**推倒**。
     · 第 2 轮：改为按条目自身 `occurrences`（逐字重复才累加）——
       直测发现 `upsert_belief` 按**精确文本**认领 ⇒ 换说法 = 新条目
       ⇒ **无论怎么走都得到 `None`**。仍无信息量（换了个方向）。
     · 第 3 轮（定稿）：熵度量的是「**同一条主张**的历次说法有多发散」
       ⇒ 分组必须用 `_sim3` 聚类，**只取包住本条目的那个簇**；
       候选集 = 本条 `occurrences` + 池内其他条目 `text`（它们可能是
       同一主张的另一种说法）。簇内出现数 < 2 ⇒ `None`（诚实缺省）、
       ≥2 且全同簇 ⇒ `0.0`（说法收敛）、分裂 ⇒ `> 0`（说法发散）。
      新增 `occurrence_n` / `occurrences` 两个可观测出口。
  ② **根因：`_sim3` 是字符二元组 Jaccard，0.70 只有近乎逐字才够得着。**
     实测「同主张 0.41~0.79 / 不同主张 0.00」两组**完全可分**，而阈值
     沿用了 `sim.cluster = 0.70`（那是 **E2 探针批选**的口径，不是
     同一件事）⇒ 簇恒单元素 ⇒ 熵恒 `None`。
     新增配置键 **`belief.sem_entropy_thr`（默认 0.30）**，与
     `sim.cluster` **解耦**；`Pool.sem_entropy_thr` 字段 + 出口
     （键名 == 字段名，前向守卫要求）；`MetaDGTF.__init__` 下发。
  ③ **`View.belief_items`：声明了、也出口了、但从不被赋值** 的死字段
     （`View.to_dict = asdict(self)` ⇒ 该键恒 `[]`）。与 v1.23.27 的
     `touch_rate` / `belief_transitions` 同型。改：在
     `_apply_view_to_pool_locked` 里回填本轮相关条目（按 text 精确命中，
     命中不到保持 `[]` —— 不猜、不兜底）。
     ★ **第二遍真跑又抓到：回填位置错了（时序颠倒）。** 首次修法把回填
       放在 `pool.merge(...)` 之后，而信念条目是在**更靠后的
       `pool.add_undecidable(...)`** 里才 upsert 进池的 ⇒ 回填读到的池
       还是空的 ⇒ `view.belief_items` **恒 `[]`**（产物实证：`pools.1` 有
       6 条、`views.1.amps[0].desc` 与 `belief_items[0].text` 逐字相同，
       而 `views.1.belief_items` 仍是 0 条 —— 不是键对不上，是**读在写前**）。
       修：回填块**整块搬移**到 `add_undecidable` 之后（只改执行时点）。
       ★ 验证三件套：构造性证明（真实入口 `view n=0 → n=2`）+ 负对照
       （text 对不上仍 `[]`）+ **变异体 M11**（搬回原位必须判红）。
       ★ M11 走 `_run_case_via_import(变异文本)`，**不碰主文件**。
  ④ **已核实「不是缺陷」的一项（避免误修）**：`Pool.to_dict` 的
     `belief_transitions` 出口**存在**；真跑产物里键缺席是因为该次 6 条
     全 `active`、无迁移，被 `if self.belief_transitions:` **正确**抑制 ——
     这是设计行为。

【判据随实现更新（不是放宽阈值）】
  · `check_v12328_real_entry` 的 D3 判据**换形态**：原判据「真实入口后
    `semantic_entropy` 非 None」隐含 R1 版语义（两条**不同**主张 ⇒ 有值），
    R3 重设计后两条无关主张各只有一种说法 ⇒ 正确读数就是 `None` ⇒
    旧判据**过时**（不是真回归）。改为构造性证明 + 两条负对照：
      · 正例：同一主张的**两种近义说法** ⇒ 必须聚成一簇 ⇒ 熵 `0.0`；
      · 负对照 1：单条主张 ⇒ 必须 `None`（不许印 0.0 冒充「很稳」）；
      · 负对照 2：把池的 `sem_entropy_thr` 拨回 **0.70** ⇒ 同一组近义
        说法必须退化成 `None`（证阈值**真接线**，不是摆设）。
  · `_mut_v12328.py` 增至 **11 个变异体**：新增 M9（分组退化成全池混合）、
    M10（阈值常量拨回 0.70）、M11（F3 回填时序退回），一律打在判据读的
    那个东西上。
  · **`_v122_verify.py` 两条过时判据**（`--phase all` FAIL 2 → 0）：
    · **V3** 的基线是 `_bak_dgtf_config.pre_v1232`，白名单只登了
      v1.23.16/17 两批；而 **v1.23.18**（`external_anchor.enabled`
      false→true）与 **v1.23.20**（`output.show_ing` / `show_manifest`
      true→false）的有意改动**从未登记** ⇒ 一直误报。新增具名常量
      `_V12318_20_AUTH_KEYS` 并入 `_allow`（**登记**，不是删判据），
      并补 **V3.a**（白名单内必须放行，防空过）/ **V3.b**（4 个清单外
      合成样本必须判红，证有牙）。
    · **`L1.src`** 的锚**曾经是会变的东西**：断言 `_v1230_w6_runs.json`
      的 `src == 本版`，而那个 10 跑回归批已决定**不重跑**（跨版本差异 ≈
      同文件重跑差异，重跑只买采样噪声）⇒ 每升一版必红一次。
      改：新增 `_V1230_W6_AUTH_STALE_SRC = {"元DGTF-V1.23.4.py"}`
      —— 出自本版 ⇒ 通过；出自**已登记的授权陈旧基线** ⇒ 通过但
      **显式打印 `⚠️ 陈旧（已授权）`**（★ 不许静默变绿）；未登记版本 ⇒
      照旧判红。补 **L1.src.a/b** 两条判别力自检。

【配置（第二轮）】`dgtf_config.yaml` 新增 `belief.sem_entropy_thr: 0.30`；
  升版段追加「五、」小节记录三轮迭代；头部「新增键」计数 1 → 2。

★ v1.23.28 收束摘要

- **交付物**：`元DGTF-V1.23.28.py`（**20146 行** / 975598 bytes / 纯 CRLF，
  `bareLF=0` / `CRCRLF=0`）
- **本版共两轮**：第一轮静态审查 + 接线修复；第二轮**真跑产物核对**
  （推翻并重做 D3、抓到 `View.belief_items` 时序颠倒、修正两条过时判据）
- **★ 最重要的收获 —— 「走得到」有三种失败形态**（前两种 v1.23.27 已记）：
  ① 调用点存在但**结构性不可达**；
  ② 字段有值但**读数零信息量**（本轮新增：D3 恒 1.0 骗过所有纯函数判据）；
  ③ **时序颠倒** —— 代码全对、接线全在，只是**读在了写之前**（本轮 F3）。
  ⇒ 通则：新能力必须配「**真实入口产出**」判据；且判据要能区分
  「**没触发**」与「**坏了**」（否则会把正确行为当缺陷反复"修"）。
- **改了哪几处**：第一轮 17 + 9 + 1 + 4 项；第二轮 5 项 D3 重设计 +
  1 项 F3 时序修正（共 6 个补丁脚本）
- **D3 `semantic_entropy` 三轮迭代**（真跑实测）：
  R1 恒 **1.0**（上界）→ R2 恒 **None** → R3 **近义 0.0 / 无关 None** ✅
  · 根因：`_sim3` 是**字符二元组 Jaccard**，`0.70` 只有近乎逐字才够得着
    ⇒ 新增 `belief.sem_entropy_thr`（默认 **0.30**），与 `sim.cluster` 解耦。
- **F3 `View.belief_items` 时序修正**：回填块从 `pool.merge(...)` 之后搬到
  **`pool.add_undecidable(...)` 之后**（条目在那才进池）。
- **配置同步**：`dgtf_config.yaml` 头部版本 + 升版段「五、六、」两小节 +
  `belief.sem_entropy_thr: 0.30`（`DEFAULT_CONFIG` 对齐）
- **验收数字**：
  · 冒烟 **exit 0 / 0 ✗**
  · 变异体 **11 通过 / 0 失败**（新增 M9 全池混合 / M10 阈值回退 / M11 时序退回）
  · `--phase all` **PASS 319 / FAIL 0**（修好 V3、`L1.src` 两条过时判据：
    313 → 319，含 4 条新判别力自检）
  · 审计探针 **AUDIT PASS 67 / FAIL 0**；运行期探针 **PASS 26 / FAIL 0**
  · 配置两向对账 **172 vs 172，`missing=[]` / `extra=[]`**
  · 真跑（route 0,1）：`revoke_sources=2` / `sem_entropy_thr=0.3` 四池一致；
    `belief_items` 6 条，`occurrence_n` **4 种取值**（4/1/3/4/4/2）、
    `semantic_entropy` **有区分**（`0.0` / `None`）—— 对照第一轮的 `6/6 恒 1.0`；
    `views.1.belief_items` = **4**（真跑探针 `pool_after=5 / view_after=5`）
- **未做**：三态一致率天花板（标签可定义性边界，不动）；挂账三项维持现状；
  三条下版候选见报告 §7.1（`_sim3` 阈值相对分位 / `upsert_belief` 语义归并 /
  `to_dict` 两种语义统一）

v1.23.27 相对 v1.23.26

【要解决的问题】`_设计_五机制算法重构_v12326.md` §3.5/§3.4/§4.2 把
「接口层（E1/E2/E5/A1）」与「信念层（D1/D2/D3）」拆成两版。动手前核对
依赖发现**顺序倒置**：E1（引擎算 G）需要 `H_sem`（原 v1.23.28 的 D3）
与 `BeliefItem.status`（原 v1.23.28 的 D1）；E3 需要 AspectUnit.id（A1）
+ BeliefItem.id（D1）。**先把底座 A1 + D1/D2/D3 做出来，E 系列才拿得到
真实输入** ⇒ 本版把两版合并。共九项：

  ① A1 `AspectUnit` 结构化 + 双写。
     新增 `make_aspect_unit()`（**单一构造点**）+ `View.aspect_units` +
     `View.add_aspect_unit()`。★ `text == desc` 是保命设计 —— 旧读取点
     一个字都不用改。★ **幂等**是硬要求：编号 `A{n}` 由追加顺序决定，
     调用点在循环里，重复登记会污染 covers 的靶子集合。非法 ground
     归一化到 "anchor"（不抛错）。
  ② A2 覆盖对账**符号化**。
     `Pool.aspect_targets_v12327()` 收敛 amp#N/th#N/probe#N/A{N} 四种编号；
     `_und_self_touch_symbols()` 给「后来被谁按 id 引用」建凭据。
     ★ 旧口径靠**子串 / `_overlap_coef`** 猜引用关系 —— 尺子本身是被测物；
     符号对账用 **id 相等**，两者分离。
  ③ A3 **双读数分离**。
     `View.touch_rate`（能力读数：碰没碰过）与 `View.aspect_carry_rate`
     （延续读数：后来还追不追）。★ **永不合成一个分** —— 合起来会把
     「碰过一次但没延续」与「从没碰过」混成一类。
  ④ D1 `BeliefItem` 四态机。
     `_BELIEF_STATUS = SUSPENSION_STATUS`（**别名不是新枚举**）；
     `semantic_entropy` 默认 **`None` 不是 `0.0`**（0.0 会被读成「很稳定」，
     那是自欺）。`add_undecidable` 内与 `structural_amps` **双写**。
  ⑤ D2 迁移规则（纯函数）。
     优先级写死 **`resolved` > `revoked` > `stable` > 保持原状**：
     `active→stable` 需 k=2 圈 + ≥2 独立来源；`active→revoked` 需
     attack ≥ support；`stable→active` 因新 attack；任意→`resolved`
     由 decidable_channel。★ resolved 最高的理由（红线「停止与清算分开」）：
     一旦被可判定通道回答，「稳不稳 / 被不被质疑」都不再是这条主张的问题。
  ⑥ D3 语义熵 `H_sem`。
     `semantic_entropy_of()` 单链聚类到**簇代表**（保守：宁可高估发散，
     不高估稳定 —— 高估发散只是不判 stable，不改变任何主张的优劣）。
     ★ `n < 2` 返回 **`None`**：单样本谈「发散」无意义，而 0.0 会被读成
     「很稳定」（老坑「检测缺省要在补默认值之前判」）。
  ⑦ E1 EIG 可计算化。
     `G = (h_before - h_after) / h_before ∈ [0,1]`。★ 算不出来返回
     `(None, {"why":…})` **不是 `0.0`** —— 0.0 是「算出来零增益」，
     None 是「没有可谈的信息量」，两回事。
     ★★ 本项踩了**两个**让 G 恒为 0 的坑，都必须修：
        (a) **两臂要同一把尺子**：`_raw_entropy` 返回**原始**熵不归一化，
            分母恒为 `ln(n_before)`。各臂用自己的 `ln(n)` 会把「移除」的
            熵降**完全抵消**（ln3→ln2 的降幅被两个 ln 各自除掉）。
        (b) **命中一条要移除整簇**：未决 {B1,B2,B3}，B1~B2 同簇、B3 独立
            ⇒ h_before 用「2 簇」分歧度；若只移 B1，剩下 {B2,B3} **不再
            同簇** ⇒ 归一化后 `h_after > h_before` ⇒ G 被 `max(0.0,…)`
            夹成 0。语义上「命中一簇」= 这簇疑问被回答了，同簇是同一
            件事的另一种说法，**应一并消解**。
  ⑧ E2 子模批选。
     贪心 + 边际下限 `floor`（默认 0.0）。★ 「宁少勿滥」：`floor` 是
     「不许零增益补位」，**不是**「不许少」；G 的绝对值尺度依赖池大小，
     硬阈值会随池漂移。配置开关 `probe.submodular` 默认开；**算不出 G
     时自动退回**旧路径（所以打开它不会让「池子太小」的圈跑不动）。
     `expected_gain` 双写引擎 G + 模型自报，并标 `gain_source`。
  ⑨ E3 covers 双查 / E4 link 反查 / E5 双向判据 / E6 自适应停止。
     · E3：编号**对**只是必要条件，还要**语义对得上**（`_COVERS_SIM_MIN`
       = 0.30）。编号**不在集合里** ⇒ 新标志 `probe_covers_bad_ref`
       —— 这是「只查编号范围」永远抓不到的一类。
     · E4：`probe_link_dangling(N)` 查 link 是否引用池内实存 id。
       ★ **只留痕不拦**（红线「未对齐合法」）。
     · E5：空探针**双向**判 —— 有理由且与 untouched 对得上 ⇒
       `honest_empty`（不罚）；理由空洞/缺失 ⇒ `lazy_empty`（留痕不罚分）。
       ★ 旧行为与提示词「推不动就返回空数组」**方向正好相反**。
       ★ 接线缺口：E5 读的 `view.no_probe_reason` 原本**没人写** ⇒
         真跑里 `honest_empty` 永不触发。四处探针解析点补捕获。
     · E6：`e6_stop_verdict(seen, max_gain, min_gain, stop_floor)` 纯函数
       + `Pool.probe_stop_history`。`max_gain < stop_floor`（默认 0.02）
       ⇒ 停止信号（本轮只出不进，探针数 0 **合法**）。
       ★ `seen == 0` 是 `no_candidate` **不是停止** —— 「模型没给候选」≠
         「候选都推不动」，混为一谈会让「模型偷懒」读成「池已收敛」。
       ★ 与 `min_gain` 是**两把尺子**：一个管「值不值得做」，一个管
         「还能不能推得动」。边界取**严格小于**。

【改动的判据（判据随实现更新，不是放宽阈值）】
  · `check_v12326_sim3` 的 [D] covers 形态检查：原找 `if m:` / `else:`，
    E3 改成 `_cov_targets` 查表 + `_tgt is None`；改按**新结构**判（语义
    比较存在 + `bad_ref` 分支存在 + 语义比较在 id 命中**之后**）。
  · `check_probe_skip_no_false_flag`：原断言旧标志 `probe_return_empty`，
    E5 起它不再是终态；改成断言「**被注意到**」，并加正对照。
  · `check_v12320_quiet_output` / `check_v1238_render_guards` 的接线断言：
    原用 `except Exception` 把「取不到源码」与「源码里没这个串」**混成
    一个 bad 项** ⇒ 报出来像「死代码」。加共享 helper `_src_of(func)`
    （getsource 失败 ⇒ 退回读源文件 + ast 按 def 名切块），两类失败分开报。
    ★ 顺带查清：那条 order-dependent 假红**不是** `check_v1221_p2b` 造成
      （逐 check 实测前 74 个 / 只跑 p2b / p2b+后 8 个，getsource 都稳定）
      —— 「最后跑的是它」不等于「它弄坏的」（相关 ≠ 因果）。
  · `check_v12315`（**本轮修的事实性缺陷**）：它读的「历史语料」是
    `outputs/`，而它**自己**也往 `outputs/` 写夹具目录（`_v12315_up*`）
    ⇒ **被测对象与读数来源共用一个活目录**；并行进程（`dgtf_app/selftest.py`）
    又在同时增删该目录（日志有 `WinError 2` 直接证据）⇒ 两次读数之间
    世界已变，报「上限放大后样本数没增加（62 → 33）」的**假红**。
    修法：三处读数改**冻结快照**（`mkdtemp` + `copy2` 保 mtime）+ 尾部清理。
    ★ **阈值一字未改** —— 修的是读数来源，不是判据松紧。
    ★ 隔离验证 `_diag_v12315_race.py`：活目录读到 n=425/tri_n=295（不稳），
      冻结快照稳定 n=303/tri_n=195（连跑两次逐位相同）。
    ★ 判别力背书 `_mut_v12315_snapshot.py`：`_lim` ×999 变异体 ⇒
      fact 20→164 / nonfact 20→228 ⇒ **判红 1/1**（不是「把红改成绿」）。

【新增判据】
  `check_v12327_five_mechanisms()`（A1/A2/A3/D1/D2/D3/E1/E2/E6 九项，
  全部**驱动真实函数**判行为）；`_mut_v12327.py` **9 个变异体（M1~M9）**。
  ★ M9 是真跑暴露边界后补的：E6 的四个记录点**必须留在 `if not out:` 里**
    —— 真跑四层每层都产出了探针，从不进该分支 ⇒ `probe_stop_history`
    真跑里 **0 条**（设计正确，但是覆盖边界）。若不固定这条语义，
    将来挪成无条件调用会让「每轮一条」，「池收敛」与「模型偷懒」
    再也分不出来，而**原判据全绿也发现不了**。

【配置】
  `dgtf_config.yaml` 补 `sim.cluster=0.70` / `probe.submodular=true` /
  `probe.stop_floor=0.02`（值 = 引擎默认 ⇒ 出厂即默认）。

★ v1.23.27 收束摘要
  验收：冒烟 **EXIT=0 / 0 ✗ / 220 ✓**；变异体 `_mut_v12327.py` **9/9 判红**
  （M9 为真跑暴露边界后补）+ `_mut_v12315_snapshot.py` **1/1**；
  配置同步 `load_config` 逐字差异 **0 项**；主文件纯 CRLF。
  真跑（`--phase all`，199 calls / 2938969 tokens / **1h 07m 55s**，EXIT=0）：
    · **E1** 85 条探针的引擎增益 **0.50~0.75**（中位 ≈0.60）⇒ 有区分度
    · **E4** link 反查 **32 次**（四层稳定，只留痕不拦）⇒ 验证「未对齐合法」
    · **E3** `probe_no_target_covered` **3 次**；研究层覆盖率段 0.66
    · **E5 / E6** 各 0 次（本轮未进各自分支，属覆盖边界非 bug）
  产物：`view[*].aspect_units` **18/14/10/9 条**（`A1`~`A18` 编号可见）、
    `belief_items` 17 条（全 active）、`covered_unders` / `aspect_targets` 均在。
  真跑纠正的两处**先前错判**：
    ① `View.to_dict` = **`asdict(self)`**（自动全量），与 `Pool.to_dict`
       的**手工白名单**是两种语义 ⇒ 「搜键名字面量」查不出 `asdict` 那条路，
       A1 的 `A{n}` **本来就落盘**（先前误判为「无出口」）。
    ② 日志 `^  A[0-9]\.` = 0 **不是**未接线 —— `--show-view` 默认 off，
       `shape_of` 三个调用点全是**喂 LLM 的提示词**。
  判据侧修掉两个**假红**（都是「判据读的不是我以为的那个东西」）：
    · `check_v12315` 读活 `outputs/` 与本判据自己的夹具目录**同一个活目录**
      + 并行进程在增删 ⇒ 改**冻结快照**（阈值一字未改）；配变异体 1/1 背书。
    · E6 源码判据锚点笔误 `__e6_note_stop`（双下划线）⇒ 四条全报「缺调用」。
  已知待办（不改，下版候选）：探针的 `gain_source` 标记只落在「喂下一轮的
    副本」，**未落盘**（`expected_gain` 数值本身已落盘）。

v1.23.26 相对 v1.23.25

【要解决的问题】上一轮对 14 圈真实产物做了「锚点重述 / 探针设计」的量化诊断
（`_分析_锚点重述与探针设计_v12325.md`），结论是：**机制骨架都对，坏的是尺子和接口**。
本版只做「尺子」那一半（**不动 LLM 接口** ⇒ 可零成本独立验证），共四处：

  ① `_overlap_coef` 对短句**系统性高估** —— 根因级。
     `_overlap_coef(a,b) = |A∩B| / min(|A|,|B|)`。min 分母是**有意**引入的
     （为了让「短句被长句整段包住」接近 1，那正是复述的形状），但它同时让
     **两条 3 词短语共享 1 个名词就得 0.5**。实测：
     `_overlap_coef("模型 部署", "模型 训练")` = **0.500**；
     而 `_similar(同对)` = **0**（因 `min(len)<=8` 走子串包含）。
     两把尺子在同一对上结论**完全相反**，而 `_overlap_coef` 被 **19 处**调用、
     跨禁词 / 未追踪 / 线头 / 复述四种语义场景 —— **一把尺子量五件事**。
  ② 池内去重阈值是**硬编码字面量**（`Pool.merge` 三处 0.9 + 一处 0.85），
     「参数按层可覆盖」这条红线在池内形同虚设 —— **一处都改不了**。
  ③ `probe_no_target_covered` 的**数字编号分支只查编号在范围内**，不校验语义：
     covers 乱指 `T1`（编号合法、语义完全无关）**实测不报红**（见本版负对照）。
  ④ BM25 缺失：`_kw` 是**平权词袋**（「模型」与「是」权重相同），无 IDF。

【改了哪几处】
  1. **新增 `_sim3` 三级尺子**（`_bm25_corpus` / `_bm25_best` / `_jaccard` / `_sim3`
     / `_sim3_pair`，模块级，接在 `_overlap_coef` 之后）。
     · L1 字面层 = **对称 Jaccard**（分母 = **并集**，不是 min ⇒ 消除短句虚高）；
     · L2 稀疏层 = **BM25**（纯 Python，`_BM25_K1=1.5` / `_BM25_B=0.75`），
       语料 = **本圈池内条目**，归一化 `raw/(raw+k1)` 压回 [0,1)；
     · L4 结构层 = 两侧都是 `T3` 式编号且相等 ⇒ 直接 `1.0`（符号必然命中，
       不受相似度尺子影响）；
     · **语料 < 4 篇自动关闭 BM25 通道**（小语料 IDF 不可靠）⇒ 退回纯 Jaccard，
       降级路径与主路径是**同一个函数**，读数可比；
     · **对称性**：`sim3(a,b) == sim3(b,a)`（冒烟逐位验证）。
     · 同一对实测 `_sim3("模型 部署","模型 训练")` = **0.333**（旧 0.500）。
  2. **复述检测切到 `_sim3`**：`_sent_is_rephrase(s, u, corpus=None)` 主判据换成
     `_sim3 >= _REPHRASE_SIM3`（新常量 0.62）。`_detect_ing_rephrase` 内部
     **只编一次语料**并传给每句判定 —— 否则 IDF 随调用次序变，
     同一对句子会给出不同的分（同一圈内必须同一把尺子）。
     ★ `_overlap_coef >= _REPHRASE_OVERLAP` 那一条**保留**：它管的是
     「s 的关键词几乎全在 u 里」这个**特定几何**，是 sim3 抓不到的一类；
     两条判据各管各的形状（docstring 已写明）。
  3. **池内去重阈值可配**：`Pool.merge` 加 `thr=` / `susp_thr=` 参数，
     默认取新常量 `_DEDUP_SIM=0.90` / `_DEDUP_SUSP_SIM=0.85`
     （= **原字面量逐位相同**）；调用点从 `self.config["sim"]` 读；
     `DEFAULT_CONFIG` 新增 `"sim"` 段。**不配置就与 v1.23.25 行为一致**。
  4. **covers 数字编号分支补语义校验**：编号在范围内**还要**
     `_similar(探针问题, 该未触及项, 0.70) or _overlap_coef(...) >= _COV_OVERLAP_MIN(0.50)`。
     比较对象是**探针的 question vs 该项**（不是两个 untouched 项互比 —— 那是
     清单内部一致性，不是覆盖）。非数字分支原本就有 `_similar`，未动。
  5. **★ 修正 `_sim3` 的 BM25 通道方向（变异体 M1 挖出的真 bug）**。
     第一版实现是 `bm = (_bm25_best(a, corpus) + _bm25_best(b, corpus)) / 2`，
     而 `_bm25_best(q, corpus)` 算的是「**q 对语料每篇**取最大」——
     它测的是 **q 与语料的相关性**，**不是 a 与 b 的相似度**。后果：
     两条**各自与语料相关、但彼此毫不相干**的句子会被抬到虚高分。
     实测（改前）：`a = "量子纠缠实验需要极低温"`、
     `b = "人工智能模型部署管线优化"`，二者字面重叠 = **0.000**，
     而 `sim3(a, b, 带语料)` = **0.467**（因 `_bm25_best(a)=0.771`、
     `_bm25_best(b)=0.786`）。⇒ 新增 `_bm25_pair(query, doc, corpus)`：
     **doc 当唯一文档、IDF 取整份语料**，只累加**双方共有**的词 ⇒
     无关必为 0（实测 0.467 → **0.000**），相关对保持（0.746 → 0.717）。
     `_sim3` 内的 `bm` 改用 pair 后**双向平均**（对称化）。
  6. **`_sent_is_rephrase` 判据顺序：`_sim3` 提到首判**。
     原顺序是 `_similar` → `_sim3` → `_overlap_coef`，但 `_similar` 与
     `_overlap_coef` 是**宽尺子**（后者 min 分母还在、前者短串走子串包含），
     实测几乎**总在 sim3 之前命中** ⇒ sim3 那条线在**行为上不可观测**
     （变异体 M1 最初打这个位置，判绿 —— 这条「判绿」直接挖出了上面第 5 点）。
     调序后结构层（T 编号）短路**优先**生效。
     ★ **行为等价性已实测**：8000 组随机对 **零差异**（sim3 的分是
     `0.4·jaccard + 0.6·bm`，其中 `jaccard ≤ overlap_coef` 恒成立 ⇒
     sim3 先判不会多抓）。调序只为可观测，**不改语义**。
  7. **清掉补丁自引入的版次批注**（2 处）：本轮补丁在正文注释里写了
     「等价于 v1.23.25 里 …」，触发了 v1.23.6 起的「正文不留版次批注」判据。
     改成语义表述（「上一版」），信息不丢、判据不误报。
  8. `dgtf_config.yaml`：头部版本 + 新增升级段 + 新增 `sim` 段（2 键）。

【不在本版范围（下一版）】`expected_gain` 取消自报改引擎算 EIG、子模批选、
`link` 反查、「空探针」判据双向化、`AspectUnit` 结构化、`BeliefItem` 四态机 ——
这些都要动 LLM 接口，需真跑验证，见设计报告 §4.2 的 v1.23.27 / v1.23.28。

【验收】
  · 冒烟 `smoke_test.py`：✓=219 / ✗=0（exit 0）；新增 `check_v12326_sim3`
  · 变异体 `_mut_v12326.py`：**8 / 8 判红 + 正对照判绿**
  · 负对照 `_nv_v12326_covers.py`：改前 A 案例（covers 乱指 T1）**不报红**，
    改后**报红**，B/C/D/E 全部正确 ⇒ 修的是语义校验，不是把判据改成一味报红
  · 配置同步：**本轮新增键 0 差异** —— `sim.dedup` / `sim.dedup_susp`
    在 `DEFAULT_CONFIG` 与出厂 yaml 两侧相等。
    ★ 口径说明：出厂 yaml 与 `DEFAULT_CONFIG` 存在**历史遗留**差异
      （`spiral.*` / `memory.*` / `actions.*`，与相似度无关）；
      v1.23.25 下该差异 = **30 项**，本版 = **28 项**（`sim` 两键由
      「yaml 有、DEFAULT 无」变为「两侧相等」）⇒ 本版是**修掉** 2 项，
      不是引入差异。「0 项」只对本轮新增键成立，不能笼统说成全量 0。
  · 主文件 CRLF 自检：`CRLF=18827 / 裸 LF=0 / lone CR=0 / \r\r\n=0`

★ v1.23.26 收束摘要
  交付物：`元DGTF-V1.23.26.py`（18827 行 / 906886 bytes / 纯 CRLF；
  上一版 18593 行 / 896053 bytes）。
  改了哪几处：14 处编辑（版本号 ×2 / `_sim3` 族 **6 个**新函数 —— 含
  `_bm25_pair` / `_REPHRASE_SIM3` 新常量 / `_sent_is_rephrase` 签名·判据·顺序 /
  `_detect_ing_rephrase` 编语料 / `_DEDUP_SIM`+`_DEDUP_SUSP_SIM` 新常量 /
  `Pool.merge` 签名与体内 4 处 / merge 调用点读配置 / `_COV_OVERLAP_MIN` 新常量 /
  covers 数字分支语义校验 / `DEFAULT_CONFIG.sim` 段 / 清 2 处版次批注）
  + smoke 3 处同步 + 配置 2 处同步。
  ★ 其中「`_sim3` 的 BM25 通道方向修正」**不在原计划里** ——
    是变异体 M1 判绿挖出来的（见【验收】）。
  验收数字：冒烟 219✓/0✗；变异体 8/8；负对照 5/5；
  配置 0 差异；CRLF 自检全 0。
  未做：**真跑（full run）** —— 本版改的是内部尺子与阈值来源，**喂进模型的内容
  一字未增**（`_sim3` 只在引擎侧算相似度，不进 prompt），故以零成本判据 + 变异体
  + 负对照替代真跑；如需真跑证据，留待下次 `--phase all` 时顺带看复述率读数变化。

v1.23.25 相对 v1.23.24

【要解决的问题】上一版把「结构覆盖率」**换了口径并改名成「独立度」**（结构视角：有多**新**）。
改名是对的（旧口径确实跟提示词反着来），但**原名位置就此空着** —— 这说明还有一路
视角没被承载：结构除了「新不新」，还该看「**活不活**」。

  那一路该按什么算？三个「不可判定通道」读数原本视角混乱、读者易混：
  清晰度（模型自评）、独立度（结构与方面重不重合）、对齐覆盖率（方面被对上几成）。
  缺的那一路，问的应是「结构**自己**会不会再被呼回来」。

【改了哪几处】
  1. **结构覆盖率**按本义重设计并加回 ——
     结构覆盖率 = **被研究出自己触及的概率**
     = 后续圈**自己的产物**（线头 / 探针 / 自报触及）里再次呼应到的
       `structural_amps` 条数 ÷ `structural_amps` 总条数。
     · 分子凭据 = `_und_self_touch_texts()`：`threads[].desc` / `threads[].polarity_why`
       / `probes[].question` / `covered_unders[]`。
       ★ **刻意不取** `und_aspects`（会和独立度互为函数 ⇒ 破坏正交）、
         也不取 `evidence[].cite` 的 `A#`（实测引用 **0 次**）。
     · 分母 = 结构条数（**与独立度同分母**，故两者可横向比、可验正交）。
     · 空池记 `None`（不可计算）—— **不印 0.00** 冒充读数。
     · 新增键 `last_sc_ratio` / `last_sc_pool` / `last_sc_touched` / `sc_history`
       / `sc_touched_amps`（`Pool.add_undecidable`）。
     · `Pool._und_self_touch_texts()` 新增方法；`Pool.covered_unders` 新增字段
       （并入 `Pool.to_dict` 白名单 —— 冒烟前向守卫当场抓出漏挂）。
     · `add_undecidable` 加 `covered_aspects: Optional[List[str]] = None`（默认 None ⇒ 旧调用不受影响）。
     · 调用点 `_apply_view_to_pool` 传 `view.covered_aspects`。
  2. **第七节三个读数并列印出**：清晰度 ｜ 独立度 ｜ 对齐覆盖率 ｜ 结构覆盖率，
     每段都写口径来源与「量的是什么」（结构覆盖率那行标注「量的是『结构有多活』，
     不是方面被覆盖几成」）。渲染点：产物 `_und_channel_line`、终端 `_update_trackers`。
  3. 旧键 `last_struct_coverage` / `struct_coverage_history` / `last_struct_hit`
     / `struct_trace` **一字未动**。
  4. **提示词没动** —— 本版只加读数与产物描述，不改任何判定逻辑。

【一轮诊断：六个候选凭据全部实测排除】
  ① `structural_amps` 撞 `und_aspects`：4/5 份 max overlap ≤ 0.17（= 上一版要换掉的那条）
  ② `aligned_amps` 撞方面：已被「对齐覆盖率」占用
  ③ `covered_aspects` 撞方面：实测 `aligned ⊇ covered` ⇒ 是 ② 的子集
  ④ `struct_trace.newly`：**全空**（引用体系已改）
  ⑤ `amp.polarity`：**100% 填充** ⇒ 零判别力
  ⑥ 引用表 `A#`：真产物里 **0 次** ⇒ 分母非零分子恒 0
  ⇒ 由用户给出定义「**是被研究出自己触及的概率**」破局。

【验收】
  · 冒烟 `smoke_test.py`：✓=151 / ✗=0（exit 0）
  · 变异体 `_mut_v12325.py`：**8 / 8 判红 + 正对照判绿**
  · 真产物对照 `_cmp_v12325_structcov.py`：新旧不同 **7/7**；新值范围 **[0.143, 1.000]**
    （有跨度）；独立度范围 [0.800, 1.000]；两者 **Pearson r ≈ 0.13（正交）**
  · 配置同步：164 键 / **0 差异**（本版无新增配置键）
  · 主文件 CRLF 自检：`CRLF=18593 / 裸 LF=0 / lone CR=0 / \r\r\n=0`

★ v1.23.25 收束摘要
  交付物：`元DGTF-V1.23.25.py`（18593 行 / 896053 bytes / 纯 CRLF；上一版 18491 行）。
  改了哪几处：11 处编辑（版本号 ×2 / 新键初始化 / 自触及计算 / `_und_self_touch_texts`
  新方法 / `covered_unders` 累积 / `add_undecidable` 签名 / 产物渲染 / 终端渲染 /
  调用点传参 / `Pool` 字段 / `to_dict` 白名单）+ smoke 4 处同步 + 配置 2 处同步。
  验收数字：冒烟 151✓/0✗；变异体 8/8；真产物 7/7 新旧不同、r ≈ 0.13；配置 0 差异。
  未做：**真跑（full run）** —— 本版改的是读数与描述（喂进模型的是多一行自述式读数），
  真产物对照已在 7 份真实历史上验证新旧口径，故以零成本对照替代单次真跑；
  如需真跑证据，留待下次 `--phase all` 时顺带比对第七节三读数并列的实际输出。

v1.23.24 相对 v1.23.23

【要解决的问题】两个「读数 / 文案」在说假话，而且都活了很久：

  一、不可判定通道的**结构覆盖率**：7 份近期产物里 **6 份恒 0.00**（另 1 份 0.60）。
     根因不是质量差，是**两侧口径反着来** —— 喂模型的提示词要求 `structural_amps`
     「独立提炼、**不得直接复述** und_aspects 的原话」，而这个读数用
     「跟 und_aspects 一致的比例」打分。一个要求「别跟它一致」，一个奖励「跟它一致」
     ⇒ 只要模型照办，读数必然是 0。而 0.00 是个**合法值**，所以它静静活了很久，
     读者还会以为这条通道不及格。

  二、修行层停因里有两个借来的东西：
     ① 印成 `ing 连续 N 圈复述` ——「ing」是**对撞层**的输入名，修行 / 研究 / 元层
        根本没有这个输入；
     ② sat 判「无新维度」时会把 `idle_stall` **顶到门槛上**，而那一刻 `stall_why`
        是空串 ⇒ 停因印成 `连续 1 轮有新增但无推进（）`（真跑产物
        `outputs/20261013_050650_普通人应该做些什么来迎接AI时代的到来.md` 就这么印的）。

【改了哪几处】
  1. **独立度**取代结构覆盖率（换口径，不只是改名）：
     独立度 = 不与任何 `und_aspects` 重合（`_overlap_coef < 0.3`）的
     `structural_amps` 条数 ÷ `structural_amps` 总条数。分母换成**结构条数**，
     于是「越高越合规」。空池记 `None`（不可计算），**不印 0.00** 冒充读数。
     · 新增键 `last_indep_ratio` / `last_indep_pool` / `last_indep_free` /
       `indep_history`（`Pool.add_undecidable`）。
     · 旧键 `last_struct_coverage` / `struct_coverage_history` / `last_struct_hit`
       **一字未动** —— 历史 packed 与命中轨迹照旧解析。
     · 渲染点跟着改：产物 `_und_channel_line`、终端 `_update_trackers`、
       喂模型的 `_pool_shape`、视图 dump 与 md 附录的「计入覆盖率」字样。
     · 渲染到**只有旧键**的 dict（历史 packed 重渲染）时走旧口径分支并显式标
       「旧口径」—— 不丢信息、也不误导。
     · 「对齐覆盖率」**保留原名**：`aligned_amps` 的定义就是「正好对应」，
       用覆盖率是自洽的；只有「独立」这一路名字错了。
     · **提示词没动** —— 保留「独立提炼 / 不得复述」，它现在与新读数同向。
  2. 修行层停因文案去借词：条件 1 改成 `{层名}层连续 N 圈复述`。
     ★ 条件 1 **仍对四层生效**（v1.23.17 的设计不变）。
  3. 修空括号：`_stop_reasons` 新增关键字参数 `stall_is_sat: bool = False`
     （带默认值 ⇒ 旧调用点与旧夹具不受影响），两条跑圈通道各算一次
     `_stall_is_sat = bool(sat_verdict is False and not stalled)`；这一支印
     `连续 N 轮无新结构维度（结构饱和度判定，不是新增停滞）`。
     ★ 不是给空串兜默认词 —— 那样 `stall_why` 会变成万金油，下次真 stall 时分不清。
  4. 修行层**任何**停止都补「本轮显形 + 未生质量」（原来只在「体力耗尽」截断时补），
     让「停得合理」可核。
  5. 红线表述：「修行层不追求收敛」→「修行层**本来就能停**，要的是**停得合理**」；
     并在 `_stop_reasons` docstring 写一张**修行层适用停止条件显式清单**
     （逐条标适用 / 不适用及理由），改条件前先看表。

【影响面】
  · ★ **运行期可见变化**：`_pool_shape` 那一行由「不可判定结构覆盖 X」改成
    「不可判定独立度 X」。旧口径下值为 0.00 时该行**本来就不出现**
    （`if value:` 是真值门）⇒ 这是**新增一条提示**，不是把旧提示换掉。
  · 产物的第七节、修行层停因文案会变；`packed.json` 新增 4 个键（加性）。
  · 出厂配置**无新增键、无默认值改动** —— `load_config` 改前 / 改后逐字差异 0 项。
  · 判据：`smoke_test.py` 的 `SRC` 指本版；新增 `check_v12324_indep_therapy`
    （带负对照，判别力由 8 个变异体证明）；`check_v69_abcde` 的 B 段落点跟着改；
    v1.22 阶段1 与 `_v122_verify.py` 的红线锚点由旧句换成新句。

【怎么退回旧行为】没有配置开关（改的是口径与文案）；退回 = 用 v1.23.23 的主文件。

【未做】P2 停圈相位（属调参，需先在看真跑数据）；P3 清单后补（引擎只标记不处置）；
  两条通道对 sat 推计数的**持久化口径不一致**（串行留到下一圈、并行只影响本圈）——
  属实现细节待定，本版只保证两边都修到空括号；提示词里的「ing」不动（属另一主题）。

★ v1.23.24 收束摘要
  ────────────────────────────────────────────────────────────
  **交付物**：元DGTF-V1.23.24.py（18491 行 CRLF）+ 本段 changelog + 升级段
    （dgtf_config.yaml）+ 判据 `check_v12324_indep_therapy` + 变异体 `_mut_v12324.py`。
  **改了什么**：主文件 37 个改动块（删 33 行 / 增 139 行）；结构覆盖率 → 独立度
    换口径 + 旧键不变式；修行层停因去「ing」、修 sat 空括号、任何停止都附体检、
    红线表述与适用条件清单。
  **验收**：探针 before/after 对表（旧键逐数不变 / 空池 None / legacy 回退 /
    shape 已换）；8 变异体全判红 + 正对照判绿；真实产物离线复算（旧口径 5/6 行
    = 0.000 → 独立度 5/6 行 = 1.000）；出厂配置逐字差异 0 项；全套冒烟
    exit 0 / 0 ✗ / ✓ 见 `_smoke_v12324.log`；真跑同题同参对照见 `v12324_报告.md`。
  **未做**：P2 停圈相位、P3 清单后补、两条通道 sat 持久化的口径分歧、
    提示词里的「ing」。

v1.23.23 相对 v1.23.22

【要解决的问题】工作台的日志窗口里，**阴阳视角那一块的最后一行被砍在半句上**
  （实测 `- [concept] 纠缠熵面积律不能单`）。查下来**不是前端裁的** ——
  `outputs/<tid>.run.log` 里就是这行：引擎有**六处**日志回显写死了字符上限，
  而模型返回的是**多行正文**，字符数一到就停在某一行中间；完整正文又不在这一层
  的日志里（`view 全文` 折叠块只覆盖 view 条那一段）⇒ 读者看到的就是半截话。

【改了哪几处】
  1. 新增模块级纯函数 `_vp_preview(text, limit=4000)`：**按整行截断** —— 切点取
     `limit` 之前最后一个换行；真被截断时补一行 `…（预览到此，另有 N 字未显示）`，
     **不静默丢内容**（与 `dump_round`「不挑字段、不截断」同一条纪律）。
     `limit` 默认 4000 对视图正文（4~8 行 / 200~600 字）等于不截断。
  2. **六处**回显统一走它，原来各写一个上限：
     · `_expand_view_once`          `raw[:200]`        （阴阳视角正文，用户实测的那处）
     · `_expand_pair_merged_once`   `(raw or '')[:160]`（阴阳合并版）
     · 候选清单                      `c.desc[:50]`
     · 未判子问题清单                `s['question'][:50]`
     · 回流硬执行拦下的重现候选       `d[:40]`
     · 子问题推进的目标              `e['target'][:40]`

【影响面】只改**日志文本**：产物 md / packed.json / 检索行为 / 判定行为**逐字未变**；
  日志会变长，多出的正是原先被砍掉的那部分。无新增配置键。
【怎么退回旧行为】把六处 `_vp_preview(x)` 换回原来的切片即可（没有配置开关）。
【未做】`[{i}] {c.desc}` 这类**清单**仍然是「一条一行」的格式，不做换行折行 ——
  那是渲染格式，不是截断。

★ v1.23.23 收束摘要
  ────────────────────────────────────────────────────────────
  **交付物**：元DGTF-V1.23.23.py（18385 行 CRLF）+ 本段 changelog + 冒烟判据
    `check_v12323_view_echo_full`。
  **改了什么**：新增 `_vp_preview`（按整行截断 + 可见痕），六处日志回显的上限
    （`raw[:200]` / `[:160]` / `c.desc[:50]` / `s['question'][:50]` / `d[:40]` /
    `e['target'][:40]`）全部取消 —— 「阴阳视角内容没显示完全」的**根因在引擎**，
    不在前端。
  **验收**：探针 `_probe_v12323_echo.py` 改前 0/3、改后 18/18（含真实日志样例）；
    变异体 8/8 被判红；全套冒烟 exit 0 / 0 ✗ / ✓ 见 `_smoke_v12323.log`。
  **未做**：清单类（候选项逐条）不做折行；`show_dual` 的条数上限不动。

v1.23.22 相对 v1.23.21

【要解决的问题】工作台的「联网检索库」要装**条目内容和链接**，但两条检索通道
  （`AnchorRetriever._tavily` / `WebSearchClient._http`）返回的条目虽然**本来就带
  `claim` + `url`**，却只在**失败**时留痕（成功时什么也不落）—— 应用层拿不到
  「检索到了什么、来自哪」。

【改了哪几处】
  1. 新增模块级 `_record_web_hits(query, items)`：把命中**追加**到
     `outputs/_web_hits.jsonl`（`ts` / `query` / `claim` / `url` / `tier` / `kind`）。
     路径可用环境变量 `DGTF_OUTPUT_DIR` 覆盖；任何写失败都**静默**（不拖累检索）。
  2. `AnchorRetriever._tavily` 与 `WebSearchClient._http` 的成功返回前各调一次。

【影响面】纯**新增落盘**：检索行为、产物 md / packed.json 都不变；
  0 条命中时不写文件（不留空行噪声）。

v1.23.21 相对 v1.23.20

【要解决的问题】工作台要「运行时实时显示消耗 token」，而引擎只在**结束**时打一次
  `完成 | N 次 LLM | M tokens`（`:18081`）—— 运行中拿不到读数。

【改了哪几处】
  1. LLM 调用点（`total_calls` 累加处）补一行
     `logger.info("[tok] calls=%d tokens=%d", …)`：每次调用后打**累计**。
     走 logging 不走 `vp` —— `vp` 受 `output.verbose` 控制，而这是「运行状态」
     不是「调试细节」，关 verbose（v1.23.20 的默认姿态）也必须看得到。

【影响面】纯**新增输出**：产物 md / packed.json 一字不变；旧行为不受影响
  （多出来的只是 stderr 上的 INFO 行，应用层解析后从卡片日志里滤掉）。

v1.23.20 相对 v1.23.19

【要解决的问题】终端跑起来被两类大块刷屏，混得看不清进度：
  ①`【ing 全文】` / `【view 全文】`（对撞/显形的全文框）—— 与产物略读重复；
  ②`圈全量留痕` / `收尾留痕`（每层每圈把 view 的全部字段逐条打出来）。
  结果是「想看进度就得忍受满屏留痕」。

【改了哪几处】
  1. 留痕（`dump_round` / `dump_final`）从 `verbose` 里拆出**独立开关**
     `output.dump_rounds`，**默认 false**。`verbose` 仍管进度，
     于是「有进度、无留痕」第一次能同时成立。
  2. `DEFAULT_CONFIG.output` 新增键 `"dump_rounds": False`。
  3. 出厂 `dgtf_config.yaml` 把 `output.show_ing` / `output.show_manifest`
     改回 `false`（这两键注释里写的就是「【建议】默认：false」，
     实际值在某轮调试里留成了 true）。

【影响面】纯输出层：产物 md / packed.json 一字不变。要看留痕时把
  `output.dump_rounds` 改 true 即恢复；留痕内容在产物 md 的
  「全量字段」附录里本来就有副本。
★ v1.23.20 收束摘要

- **交付物**：`元DGTF-V1.23.20.py`（18321 行 / 纯 CRLF）
- **改了哪几处（6）**：docstring 标题 · `__version__` · `DGTF.__init__` 新增
  `self.dump_rounds` · `dump_round` 守卫 · `dump_final` 守卫 ·
  `DEFAULT_CONFIG.output` 新增 `"dump_rounds": False`
- **配置同步**：`dgtf_config.yaml` 的 `show_ing` / `show_manifest` 回 `false`、
  新增 `dump_rounds: false`、头部版本 → v1.23.20
- **验收数字**：冒烟 exit 0 / 0 ✗ / **PASS 213**；离线 E2E 全绿；
  真跑 route 0（126s / 11 calls / 30445 tokens / 无异常）——
  `圈全量留痕` **0** 次、`收尾留痕` **0** 次、`【ing 全文】`/`【view 全文】` **0** 次，
  而 `━━━` 进度 **62** 次
- **未做**：无遗留

v1.23.19 相对 v1.23.18

【要解决的问题】回答「锚点对照为什么没做」时查出一条**真缺陷**：
  `external_anchor` 自称有「真检索」后端（`retriever: tavily`），
  但 `_retrieve_anchors` 全篇**只有一处调用**，而它在 `_anchor_round` 的
  `not self._anchors` 早退**之后** —— 而 `self._anchors` 非空的唯一来源是
  **快照文件** ⇒ **没挂文件时真检索一次都不会被调用**；连「后端未实现」该有的
  抛错留痕也发生不了（承诺了「非 snapshot 抛错留痕」，实际够不到）。
  同时它的 docstring 还写着「引擎现在没有联网能力」—— 这句**早已不成立**。

【改了什么】（引擎 8 处编辑；★ 默认路径逐字不变，`load_config` 差异 ∅）
- `_anchor_round`：早退里**摘掉「已有锚点」**，把它放到**模式分流之后**
  （snapshot 模式仍要求已读入锚点；真检索模式由它自己填 `self._anchors`）⇒
  真检索可独立启动。实测：tavily + 空锚点 → 检索调用 **0 → 1** 次、
  `_anchors` **0 → 2** 条、按 `per_round` 投池；未实现后端**真抛错留痕**
  （改前留痕为空：`False → True`）。
- `_anchor_round` 的 docstring 重写：写清**两条来源**、**为什么早退条件要挪**、
  以及**与 `web_search` 的边界**（拿本次喂进层里的东西回头量层结论 = 自证）。
- `_load_anchors`：`unconfigured` **只对 snapshot 模式**置位 —— 真检索模式不读
  `path`，它是**已配置**（改前 tavily 模式也被误标「未挂文件」，`True → False`）。
- `_anchor_crosscheck` 的 base dict 加 `retriever_mode`；渲染两处（头部通道行 /
  产物明细「未做」）把**两条接入路**写全（`path` 指快照 JSON / `retriever: tavily`
  按圈真检索），真检索模式在头部标注后端。

【为什么**不**把 `web_search` 收到的结果直接当锚点】
  那批进的是 `pool.web_results`，是**喂给各层的证据**（带 `used_as`）；
  拿它回头量各层的结论是**自证**，不是校验。锚点对照要的是**独立**的尺子
  （运行前落盘的快照，或另一路按池内问题发起的检索）。两者互相独立是**故意**的。

【验收】
- 探针 9 项读数变化 + 3 条负对照（含**不桩**的那条：未实现后端的抛错留痕
  `False → True`）；默认路径 `B_snapshot_*` **前后一致**（0 调用 / 0 条）。
- 变异体 **4/4 判红**（早退复活 / `unconfigured` 对所有模式 / 渲染只提一条路 /
  检索结果不并池），control 判绿。
- ★ **真联网**（这条代码**有史以来第一次执行**）：未知后端抛错；snapshot 返回 `[]`；
  **tavily 真检索返回 6 条**（`id/claim/url/tier` 齐备、内容相关）；
  同 queries 第二次 **0.01 s** 命中 `cache/anchors/`。
- 冒烟 `exit 0 / ✗ 0 / ✓ 212`；整体审计 **PASS 67 / FAIL 0**；
  配置三向：`load_config` 差异 **∅**（本版不改任何生效值，出厂 `retriever` 仍 `snapshot`）。
- 主文件 18287 → **18316** 行 / 纯 CRLF；AST 符号新增/消失 **0 / 0**。
- **真跑同题 × `retriever: "tavily"`**（2199 s / rc=0）：**那条修好的路走通了** ——
  头部「**开** —— 已接入 72 条（真检索后端 `tavily`）」；日志 10 次「`⚓ 锚点入池 +2`」；
  **收尾对照做了**：「结论 12 条 —— 印证 4 / 冲突 0 / 无对应 8（用到锚点 3/72）」；
  `### 外部锚点 · 逐条对照` 在；packed `enabled=True / unconfigured=False /
  anchors=72 / retriever_mode='tavily' / pooled=20 / error=''`。
  ★ 成本 calls 184→203、tokens +16% —— 来自「锚点注入池判 prompt + 一次对照调用 +
  停圈不同」，是「要真尺子」的自觉代价；**默认不开**（出厂仍 `snapshot`）。

【未做 / 遗留（如实记账）】
- **没有**把 `web_search` 的结果接进锚点对照（理由见上）；出厂 `retriever` 仍
  是 `snapshot`（真检索要显式打开 —— 每圈最多 2 次网络调用，「默认零调用」是硬约束）。
- `_tavily` 的 `id` 每轮从 `t1` 重新编号 ⇒ 跨圈同 id 会被 `already` 去重（少投几条）；
  既有实现，本版未改。
- 默认路径（snapshot）**未重复真跑**：本版对它逐字不变（探针前后一致），
  所以只跑了真检索那一态。
- 锚点仍不是 auto 调度项（v1.23.13 的排除决定不变）。

v1.23.18 相对 v1.23.17

【要解决的问题】把「外部锚点」默认打开。但只翻一个默认值不行 ——
  `enabled=true` + 没配 `path` 在改前是**一条错误路径**（`_load_anchors` 记
  `"enabled=True 但没有给 path"`）：只翻默认值 ⇒ **每一次默认运行都在产物头部
  写「已接入 0 条；⚠️ 接入失败」、正文写「锚点异常」**。一把开关换来每跑一个假故障。

【改了什么】
- `external_anchor.enabled` 出厂默认 **false → true**（`DEFAULT_CONFIG` + 出厂 yaml
  两处一致）。
- **造出「未挂文件」这个独立干净态**：`_load_anchors` 在 `path` 为空时置
  `self._anchor_unconfigured = True` 并 **不记 error**（改前正是记 error）；
  `_anchor_crosscheck` 的 base dict 新增 `unconfigured` 键，且无锚点时**不再**塞
  「没有可用锚点（未开启或加载失败）」兜底文案。
  ★ **负对照**：`path` 非空但文件不存在 ⇒ **仍然记 error**（失败不许被吞成「未挂文件」）。
- **文本通道渲染两态 → 四态**：缺失⇒`**关**` / 未挂⇒`**开（未挂锚点文件）**` /
  已接入⇒`**开** —— 已接入 N 条` / 失败⇒`**开** —— ⚠️ 接入失败`。
  ★ 缺席态文案由「无」改成「**关**」，与联网通道对称。
- **产物「锚点明细」未挂文件时不再写五行零**（原先写「结论 0 条 / 印证 0 / 冲突 0 /
  无对应 0 / 入池 0」—— 读起来像「对照做过、结果全是 0」）；改成一行
  「**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**」。
- **事实题「未接入外部校验」留痕改成按两条通道的实际状态发言**（改前写
  「两条通道都关：锚点文件无、联网检索关」—— 锚点默认开着之后这句就不成立了）。

【判据】
- **改**两处旧判据（判据随实现更新，不是放宽）：`[A]` 关闭态夹具原来**靠默认关**
  才成立 ⇒ 改成**显式关**；`[A]` 与 `check_v12312_anchor_lanes` case A 的文案断言
  「…：无」→「…：关」（后者还改成**只取文本通道那一行**再查，比原来更准）。
- **新增** `check_v12318_anchor_default_on`：出厂值（DEFAULT + yaml 都 true、
  不预置 path）/ 干净态行为 + **负对照**（path 不存在仍记 error）/ 渲染四态互不冒充 /
  产物不写五行零且不写「锚点异常」。
- 变异体 **4/4 判红**（默认开回退 / 干净态记 error / 渲染缺未挂态 / 明细仍写零行）。

【验收】
- 探针 12 项读数变化：`A_def_enabled` False→**True**；`B_err`
  `'enabled=True 但没有给 path'`→**`''`**；`B_unconfigured` 无→**True**；
  四态渲染各说各的（改前「未挂文件」与「失败」都渲染成「已接入 0 条」）；
  五行零明细 → **false×4**；留痕话术两版对照（含**新增的 `E2` 真跑形态**：
  「锚点通道：**开着但未挂文件**」）。
- 冒烟 `exit 0 / ✗ 0 / ✓ 211`（比 v1.23.17 的 210 多 1 = 新增判据）。
- 整体审计 **PASS 67 / FAIL 0**；配置三向：`load_config` 差异**恰为**
  `{external_anchor.enabled: False → True}`；yaml 列全 `DEFAULT_CONFIG` 全部键；
  登记表无过期条目（yaml 值改后仍 == 默认 ⇒ 无需登记）。
- 主文件 18258 → **18287** 行 / 纯 CRLF；AST 符号新增/消失 **0**。
- **真跑同题**（同题 / 同调用方式 / **不带锚点文件**，2124 s / rc=0）：头部文本通道 =「**开（未挂锚点文件）**」；
  **不出现**「锚点异常」、**不出现**五行零明细；出现一行「**锚点对照**：未做」；
  packed 的 `external_anchor` = `enabled=True / unconfigured=True / anchors=0 / error=''`（v1.23.17 那份**根本没有该键**）。
  ★ **锚点通道零额外调用**：packed 里 **`anchor_calls = 0`**（无锚点时 `_anchor_crosscheck` 直接早退）。
  ★ 整体 `calls`/`tokens` 168→184、2,039,789→2,236,350 属**同题不同跑**的波动（各层停圈合计 16→17；本版只改「配置默认值 + 渲染」，不可能改变循环行为）；
  自然停 4/4→2/4 同理 —— 同一题两次真跑的差异 ≥ 跨版本差异。

【未做 / 遗留（如实记账）】
- **没有 `--anchor on/off` 命令行开关**（锚点只有配置文件一个入口）；本版不加。
- `external_anchor` **仍不是 auto 调度项**（v1.23.13 明确排除），保持原分工。
- 出厂 yaml **不预置 `path`**（锚点快照是题相关的；`anchors/` 下有 6 份真实快照，
  要用就把 `path` 指过去）。
- 真跑只跑了**不带锚点文件**这一态；「已接入 N 条」「接入失败」两态由冒烟的
  `[B]`/`[C]` 用**整次 mock run** 覆盖，没有再花一次真跑。
- 未挂文件时走 `logger.info`（不是 warning）—— 日志里会多一行 INFO。

v1.23.17 相对 v1.23.16

【要解决的问题】v1.23.16 的同题真跑里四层只剩研究层被截断。逐条核它六条停止通路：
  条件 1 不对它开放；条件 2/3/4/5 都要 `idle >= 2`（它每圈都在产新 & ⇒ 恒 0）；
  条件 6 要 ≥2 条 `stable` 悬置（它悬置 0 条）⇒ **唯一现实的出口是 sat 判定**，
  而 sat 的检查点（`layer_no % sat_every_n == 0`，间隔 3）在它上限 4 时**只在第 3 圈
  查过**，第 4 圈没有检查点。三处出厂值随之下调。

【改了什么】
- `spiral.structure_saturation_every_n` **3 → 2**（含两条通道的各一处 `.get` 缺省）：
  检查点落在第 2/4/6…圈，上限 4 的层最后一圈也被查到。
- `spiral.soft_max` **3 → 2**（含四处缺省）：条件 6「自然安住」与条件 1 的
  `layer_no >= soft_max` 推迟都从第 2 圈起生效。
- **停止判据条件 1（复述 / 自省点名未消化）四层通用**，两处：
  ① `_stop_reasons` 去掉 `if entry in ("all", "both")` 门槛（`layer_no < soft_max`
     的推迟保留）；
  ② `_apply_view_to_pool_locked` 的 else 分支把 0/1 层的连续复述圈数写进
     `view._meta_idle_streak` —— 否则 `_compute_rephrase_streak` 对 0/1 恒返回 0，
     **门槛去掉了行为也不变**。不改 `view.idle` 的既有语义。
- 出厂 yaml 顺带**统一**：`structure_saturation_every_n` 原为 **1**（引擎默认 3，
  两者本就不一致 ⇒ 同一版本「裸跑」与「带 yaml 跑」行为不同），本版两处统一为 2。
- 修 **v1.23.16 引入的两个真缺陷**：
  · `check_cost_profile` 被「整条重写」时，与成本档**无关**的判据（覆盖率双口径 /
    不可判定命中轨迹）被留在 `return True` 之后 ⇒ 约 90 行 / 33 条语句**从没跑过**。
    恢复为 `check_v12317_und_coverage_trace` 并接线（✓ 数 207 → 210 即为佐证）。
  · 两处夹具把「停止」当常量（P1-6 晚写者 3/3、#13 预算 barrier 4/4）⇒ 本版让 0/1
    层更容易停之后当场失效；改成**固定该变量**（抬 `soft_max` / 抬 idle 阈值 / 关
    sat），不是改小期望值。

【验收】
- 探针 12 项读数变化 + 1 项负对照不变：改前 0/1 层无理由 → 改后「复述 + 自省点名」
  两半理由都有；`view._meta_idle_streak` `None`→`2`、`_compute_rephrase_streak`
  `0`→`2`；**负对照** `soft_max=3 & layer_no=2` 仍被推迟（没被一起改坏）。
- 冒烟 `exit 0 / 0 ✗ / 210 ✓`；新增判据与**恢复的判据**都真跑到。
- 变异体 **5/5 判红**（条件 1 重关门 / `soft_max` 回 3 / sat 回 3 / 复述载体不写 /
  去推迟），control 判绿。
- 整体审计 **PASS 67 / FAIL 0**；`load_config` 差异**恰为**有意改的两项
  （`spiral.soft_max` 3→2、`spiral.structure_saturation_every_n` 1→2）；
  `CONFIG_TUNED` 无过期条目；主文件 18249 → **18258** 行 / 纯 CRLF。
- **真跑同题对照**（同题 / 同调用方式，用时 2108 s）：自然停 **3/4 → 4/4** 层
  （**四层全部自然停**）；**研究层从「4 圈截断」变成「第 2 圈自然停」**
  （停因含「结构饱和度判定连续无新维度」）；对撞 3→4 圈、元 7→6 圈；
  `calls`/`tokens` 174 / 2,080,311 → **168 / 2,039,789**（早停省钱）；
  sat 判定 5 → **8** 次。★ v1.21.48 老风险实测：研究层**确实第 2 圈停**，
  但**可判定覆盖率没有塌到 33%**（42% → **55%**）；代价落在不可判定
  对齐覆盖率（60% → 20%）。两版是同题不同跑，该格对比**有混杂**。

【未做 / 风险】
- ⚠️ 出厂 yaml 里留着的 v1.21.48 / v1.21.49 实测记录：间隔 **2** 曾让研究层
  **第 2 圈就停**、可判定覆盖率仅 **33%**（v1.21.49 才把它放宽到 3）。本版回到 2 是
  **有意**的（间隔 3 漏检查点）；但**本版未单独测可判定覆盖率**，如实记。
  要回退：把该项与 `soft_max` 各自改回 3（两项独立）。
- 修行层（0）的复述理由文案仍是「ing」（元 / 对撞层的用词）—— 文案债未清。
- 条件 1 的两条 streak 载体（`rephrased_streak` / `meta_idle_streak`）**未合并** ——
  本版只把 0/1 的圈数镜像进后者，属结构债。

v1.23.16 相对 v1.23.15

【要解决的问题】v1.23.15 同题真跑（两组 8 个层圈）暴露：自然停 **1** 次、
  被截断 **7** 次；12 个层圈里 **11 个** `idle_new_amp = 0`。诊断出四条根因：
  ① 主判据量的是「字面新增」不是「语义新增」——实测研究层 16 条 & 两两词集
     重叠**峰值 0.45**、达标（≥0.55）**0 对**，于是每圈都被算成「全新 &」；
  ② 唯一能识破「换措辞」的 sat 判定（LLM 判「有没有引入新结构维度」），结论
     **只对研究层生效**，元层判出来只打一行日志 ⇒ 元层结构上不可能自然停；
  ③ sat 判定的检查间隔被成本档惰性化（3 → 4）⇒ 层上限低于 4 的层永远跑不到它；
  ④ 跨圈比对只覆盖**近 2 圈**，跨 3 圈以上的重复抓不到。

【治本三条 · 停止判据】
- 新增模块级纯函数 `_sat_override(entry, sat_verdict, idle_new_amp, idle_stall,
  r_idle_limit, r_stall_limit)` —— serial 与并行 B **共用唯一实现**。四层同等生效：
  判「无新维度」⇒ `idle_new_amp = max(_, r_idle_limit)`；0 层没有「无新 &」这条
  通路（条件 2 排除 "0"）⇒ 它的落点是 `idle_stall = max(_, r_stall_limit)`。
  未判定（None）/ 判「有新维度」（True）⇒ 一律不动计数。
- `_lazy_every_n` 去掉惰性化（恒等返回 n）—— 停止判据的检查频率不该由省钱档位决定。
- 参照集从「近 `round_window`(2) 圈的 new_amps」改成「**池内全部 &**」（`list(snap_amps)`
  / `list(snap_threads)`，serial + 并行 B 两处）；`win_amps` / `win_threads` /
  `r_window` / `spiral.round_window` 键一并删除。sat 判定的 prompt 文案同步改述
  （「近几圈已有 &」→「池内已有 &」）。

【删除成本档维度 · 本版唯一改变默认行为的改动】
- 只保留一种行为（原 `quality`：不裁剪）。删除 `_COST_PROFILES` / `_profile_plan`
  / `_PROBE_SKIP_ROLES`，以及它带走的**五类省法**：① 阴阳展开合并成一次调用
  ② 探针按「收束/复裁」角色跳过 ③ 候选截断（`_build_inp_duel` 与 `_self_check`
  两处）④ `shape_chars` / `shape_items` 缩放 ⑤ 低频项惰性化。
- 配置键 `cost_profile`、CLI `--profile`（含 `auto` 分支 `_auto_profile`）**一并删除**；
  auto 项 **12 → 11**（去掉「成本档」），产物头部「自动调度」表随之少一行；
  `_assemble_plan` schema、`_auto_pick_cost_profile`、`_AUTO_PROFILES_ORDER`（死常量）、
  产物三处渲染行（`save_result` 的「成本档位」/ 显化行 / 落地层「💰 成本档」）全部删除。
- 历史兼容侧**保留**：`_hist_from_packed` / `_hist_from_md` / `_hist_add` 里对旧产物
  `profile` 字段的读取（`.get` 容错，用于读旧产物）。
- ★ 代价如实说明：删档 = 恢复「不裁剪」，真跑 token 会高于上一版的 balanced 档。
  去惰性化还让**池重估**从每 2 圈变成每圈（`re_eval_every_n` 也走 `_lazy_every_n`）。

【验收】
- 探针 40 项读数（改前 / 改后对表）：`_COST_PROFILES` / `_profile_plan` /
  `_auto_pick_cost_profile` / `_auto_profile` 全 False、`DEFAULT_CONFIG` 无键、
  auto **12 → 11**、`_lazy_every_n(3)` **4 → 3**、窗口串 **2 → 0**、
  sat 入口的 `entry in ("1","all")` 限制消失。
- 冒烟 exit 0 / **0 ✗ / 207 ✓**；新判据 `check_v12316_stop_therapy` 五组
  （档位维度四处不存在 / 惰性化归零 / `_sat_override` 六条含三组负对照 /
  停止可达：元层拿到 sat 结论必须给出理由 / 参照集是池内全量且跨圈重复在引擎
  判重口径下成立）。
- 变异体 **7 个全部判红**（sat 不推计数 / 惰性化复活 / 参照集换空表 /
  sat 只对研究层 / 档位常量复活 / auto 项退回 12 / stall 分支不推）。
- 审计脚本 `_probe_v1232_audit.py` 在本版上 PASS 65 / FAIL 0。
- 真跑同题对照（同题 / 同调用方式，用时 2093 s）：自然停 **1/4 → 3/4** 层、截断 3/4 → **1/4**、实际停圈 4/4/5/7 → **3/4/3/7**、sat 判定触发 2 → **5** 次；`calls`/`tokens` 174 / 2,080,311（比基线的 193 / 2,420,429 **更省** —— 自然停生效后早停了）。★ 直接证据：**对撞层**的停止理由出现「结构饱和度判定连续无新维度」（旧版该结论只对研究层生效）。★ **[定稿后逐层核对 · 归因更正]** 上面的
  「1/4 → 3/4」是**净数**：有直接证据的只有**修行 / 对撞两层**（第 3 圈
  `idle_amp` 由 0 跳到 2，源自 sat 去惰性化后在第 3 圈判「无新维度」）；
  **元层的自然停来自条件 6「悬置决定稳定」**（两版元层悬置实测 stable
  0 → 6 条，内容驱动），**与本改动无关**；**研究层反而从自然停退成截断**。
  两版为同题不同跑（LLM 随机、内容不同）⇒ 非受控对照，疗效结论只对
  修行 / 对撞两层成立。

【本轮修掉自己九处错】(1) ★★ AST 删语句取「最小」⇒ 留下孤立 `if`（IndentationError）、
  取「最外层」⇒ 上溯到包装它的大 If（把刚注入的新判据本身都删了）；正解是**只看
  语句首行**。(2) ★★ 重叠区间必须先合并再按下标删，否则按旧行号删内层/外层会错位。
  (3) 特征串不加括号才能覆盖 `if/else` 整块。(4) ★★ yaml 里写 `@@REALRUN@@` 占位符
  裸行 ⇒ `ScannerError`（冒烟只报「出厂 yaml 解析失败」，看不出是占位符）。
  (5) 拿「已注入版」的行号去改「原始版」⇒ 锚点命中 0 次。(6) `_is_dup` 是
  `_run_layer` 内的**局部函数**，模块级取不到 ⇒ 判据改用它的两个组成函数复现口径。
  (7) ★★ **有 FAIL 时后面判据根本不跑** —— 前 151 ✓ 里不含新判据（它在 main 尾部，
  被审计那条 FAIL 提前 return）⇒「✓ 数够多」不等于「新判据跑过」。
  (8) 变异体锚点缩进写成 8 空格（实际 4）。(9) ★ 删维度要 grep「消费点」不是
  「定义点」——`cand_limit` 有两处消费（`_build_inp_duel` 与 `_self_check`）。

────────────────────────────────────────────────────────────
★ v1.23.16 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.16.py`（18408 → 18249 行，纯 CRLF）+ 本段 + `v12316_报告.md`。

**改了什么**：自然停治本三条（sat 四层同等 / 去惰性化 / 参照集池内全量）；
删除成本档维度（五类省法下线、键与 CLI 参数删除、auto 项 12 → 11）。

**验收**：冒烟 0 ✗ / 207 ✓；变异体 7/7 判红；审计 PASS 65 / FAIL 0；
探针改前改后逐项对表；真跑同题对照：自然停 1/4 → 3/4 层。

**未做**：`_expand_pair_merged_once` 成孤儿函数但未删（冒烟判据直接调用它）；
mock 驱动 sat 通路未跑通（sat 的行为判据由纯函数承担，真跑做最终裁决）；
联网侧两条规则仍零触发；上限扫描（up6/up10）仍未补。

v1.23.15 相对 v1.23.14

【主题】把 v1.23.14 报告 §八 的「未做 / 边界」四条做完：
  分层抽样 + 时间衰减、抽取器补齐、三条规则按实测定、真跑对照实验。

【为什么 / 三条「零样本」的真相】
  · 「三态一致率只有 n=1」**是抽取器的错**：产物里 **254/368** 份都写了
    `**三态判决一致率**：A/B` 这一行，而上一版只从 packed 抽 ⇒ 读数几乎为空。
  · 实测分布（n=255）：p10 = **0.167**、中位 = **0.333**、p75 = 0.6。
  · ★★ 由此推翻一个拍脑袋的阈值：上一版规则是「一致率 < 0.5 ⇒ 不降档
    （质量优先保护）」—— 而**中位数就是 0.333** ⇒ 会拦掉 **54%** 的情况，
    这条「保护」实际等于把降档功能**废掉**。本项目早有定论：一致率天花板在
    17~67%，是「标签可定义性边界」，当中位数附近的「质量线」从一开始就站不住。
  · 「截断率」只有 6 层样本（头部「停止」行 v1.23.8 才引入）；
    「联网失败/空结果」0 次 ⇒ 这两条**确实**缺数据，改成加**样本量门槛** +
    靠真跑产出（见下）。

【做什么】
  · `auto.history_limit` 语义从「总样本数」改成 **「每题型上限」**：两桶各自
    最多取 limit 条，扫描上限 4×limit，两桶都满即提前停。
    原语义下窗口一缩，事实型会被整体挤掉，「按题型比同类」退化成「比全语料」。
  · 读数改**时间衰减加权分位**：权重 `0.5 ** (age_days / 半衰期)`；
    新键 `auto.history_halflife_days`（出厂 **14 天**，0 = 不衰减）。
    语料跨十几天，旧样本是旧配置下的读数，等权平均会把结论拉向旧行为。
  · 抽取器补齐：新增抽「**三态判决一致率**」与「**外部锚点 · 联网**」两行；
    ★ **抽不到的字段不写键**（`web_fail = 0` 与「没有这一行」是两件事）。
  · 三条规则按实测定：
    · 一致率异常线 0.5 → **实测 p10 = 0.167**，并要求 ≥30 份样本才启用；
    · 截断率要 ≥24 **层**样本才表态（`_AUTO_STOP_MIN_N`）；
    · 圈数三级回退保留（实际停圈需 ≥3 份样本）。
  · 真跑对照实验（同题 × 全四层 × 不同圈数上限 + 一次 auto 默认），见报告 §三/§四。

【验收】
  · 探针 32 项读数（分层 / 衰减数值与两向 / 抽取补齐 / 三条规则两向）。
  · 冒烟 exit 0 / 0 ✗ / 210 ✓（守卫 102→103）。
  · 变异体 7 个全部判红，control 判绿。
  · ★ 本轮变异体抓到 **3 处假绿**：① M1（不分层）的夹具在「3 事实 + 1 决策、
    上限 2」下两种实现结果相同，改成「2 事实在前 + 2 决策在后」才分岔；
    ② M5（缺字段写 0）把 `setdefault` 放在 `if _mw:` 块内 ⇒ 「没有联网行」
    的样例走不到它，移到函数出口才判红；③ 判据里 `import time as _t` 与
    夹具循环变量 `_t` 撞名 ⇒ `'str' object has no attribute 'time'`。
    ⇒ **变异体的样例要选在两种实现会分歧的地方**；判据里的导入别名要加前缀。
  · ★ 首版把「取样口径」两行插在 `_hl` 赋值**之前** ⇒ `UnboundLocalError`，
    `_auto_dispatch_lines` 一调用就炸、**产物渲染整个失效**；
    是**上一版留存的判据**（v12314「产物渲染异常」）抓出来的。
    ⇒ 插入点必须晚于它用到的所有变量；老判据继续跑有价值。
  · ★ 配置同步脚本的**升级段原本没有幂等**，我跑了两次 ⇒ yaml 里同一段出现
    两次（手工去重，并加了显式判重 + 重复计数断言）。
    ⇒ 这条我自己写进技能第 25 条，然后又踩了一次。
  · `load_config` 差异 ∅；yaml 覆盖出厂全键并写出 6 个 `auto` 键；
    AST 登记 added 142→145；主文件 18286 → 18407 行 / 纯 CRLF。
  · `--phase all` PASS 310 / FAIL 5，红名单全部落在基线
    红名单之内 ⇒ 无新增红。

【真跑结论】同题（老城区内涝权衡题）× 全四层 × 只改圈数上限，两点对照：
  · **up2**（显式锁 7 项，上限 2/2/2/2，元层被 `all_extra_rounds` 抬到 3）：
    实际停圈 2/2/2/3、**自然 0 / 截断 4**、79 calls / 739,219 tokens、约 38 分钟。
  · **auto**（不传任何参数）：auto 从历史取上限 4/4/5/7，实际停圈 4/4/5/7、
    **自然 1 / 截断 3**、193 calls / 2,420,429 tokens、模式 B、**联网收 24 条
    （4 个环节、失败 0）**。
  ★★ **实际停圈 == 圈数上限**（6 组数字全部相等）⇒ **停止判据在这类题上几乎
    不触发**：「给足上限让它自然停」这条路走不通，上限就是成本。
    ⇒ 最优不是「上限最小」（79 calls 那份是**被截断**的产物、质量没交代），
    而是**按历史给够用的上限** —— 这正是 `_AUTO_ROUNDS_BASE` 取实测 p50
    （4/4/5/6）而不是给满 `hard_max = 12` 的依据。
  ★ 三处新渲染行在真跑里全部兑现：「自动调度」表（up2 显示「auto 接管 **5** 项」
    / auto 显示「12 项」，即「显式 ＞ auto」在真跑里可见）、「实际停圈」行、
    「外部锚点 · 联网」行（**该读数第一次有真数据**）。
  ★ 真跑**立刻**改善历史读数：层样本 6 → **22**、联网入池 96 → **144**、
    三态一致率 n 255 → **259**；截断率从 0.333 变成 **0.727** ——
    印证「6 层样本不足以下结论」，也说明 `_AUTO_STOP_MIN_N = 24` 的门槛没白设。
  ★ 成本口径（供下次估算）：单次调用 ≈ 25 秒；四层×2 圈 ≈ 38 分钟 / 79 calls /
    74 万 tokens；四层×4/4/5/7 圈 + 联网 ≈ 45 分钟 / 193 calls / 242 万 tokens。
    据此**砍掉 up6/up10**（预计 1.5 小时以上、边际价值低），并用看门狗在两组
    落盘后立即停掉 runner。

【未做 / 新的边界】（同上，逐条列）
  1. up6/up10 未跑（成本决策）—— 「上限 → 自然停」的完整曲线仍未画出；
  2. 联网侧仍只有 1 个样本，两条联网规则依然零触发；
  3. 截断率层样本 14（真跑后 22）仍低于门槛 24 ⇒ 该规则仍不表态；
  4. 窗口效应只是缓解（分层 + 衰减），未做时间桶抽样；
  5. 未做 ≥3 个上限点的完整扫描。

  ────────────────────────────────────────────────────────────
★ v1.23.15 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.15.py`（18407 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + `auto.history_halflife_days` + 升级段）。

**改了什么**：历史取样改「每题型上限」分层 + 时间衰减加权分位；抽取器补抽
  三态一致率与联网行（抽不到不写键）；三条规则改按实测定阈值 + 样本量门槛；
  产物历史行报出取样口径。

**验收**：探针 32 项（含 6 组负对照）；冒烟 0 ✗ / 210 ✓；7 个变异体
  全部判红（含首版 3 处假绿被修）；真跑对照两点；`load_config` 差异 ∅；
  AST 登记两向对账绿。

**未做**：up6/up10 的完整上限扫描（≥3 个点，约需 2 小时真跑）、联网侧两条规则
  （仍零触发，不能说已校准）、窗口加权的进一步设计（分层 + 时间桶）。

v1.23.14 相对 v1.23.13

【主题】把「自动调度」真正接上**真实历史语料**：修一个让它读不到历史的静默 bug，
  取样从 1 份扩到 217 份，阈值从「拍脑袋」换成**实测分位 / 相对判据**。

【为什么】v1.23.13 的十二项自适应读不到历史，两个原因：
  ① `_auto_history` 只扫 `**/*.packed.json` —— 而 `outputs/` 里有 **368 份产物 md**、
     只落了 **1 份** packed（旧版本不落 packed）⇒ 历史样本=1，所有阈值实际都在走
     「无历史」分支；
  ② 它把「实际停圈」的字段名读成了 `rounds`，真实字段是 **`rounds_run`**
     —— `dict.get` 静默返回 None，「实际停圈」**一整版都没生效**；
     而产物里也没有任何渲染点写这个量 ⇒ 信号既没被读、也没被记。

【做什么】
  · 修字段名（`rounds` → `rounds_run`）；产物头部新增「**实际停圈**」一行
    （`rounds_run` + `rounds_cap`），并把这条信号落进产物 —— 语料此后才积累得起来。
  · 历史取样**扩到三类来源**：packed 全量 / 产物 md 头部（只读前 8KB）/
    仓库根 `*_runs.json` 跑批记录。实测样本 **1 → 217**（1 + 200 + 16），
    扫描耗时 0.16s。新增 `history_md` / `history_batch` 两个开关可关。
  · 读数扩到**分位**（token / calls 的 p50 / p75）+ **按题型分桶**
    （事实型 / 决策型），策略变成「同类题比同类题」。
  · 阈值改实测：
    · 成本档降档改**相对判据**（同类成本中位 ≥ 全语料 p75 才降档），
      不再写死「40 万 token」——实测该读数对**取样窗口敏感**
      （p75 全语料 1,050,814 vs 最近 200 份 711,161，差 1.5 倍）。
    · 圈数改**三级回退**：实际停圈（需 ≥3 份样本）→ 种子上限（实测 p50：
      修行 4 / 研究 4 / 对撞 5 / 元 6）→ 按层实测默认。**样本数不足不采纳**，
      防单条噪声盖掉 200 份分布。
  · `auto.history_limit` 20 → **200**；新增 `auto.history_md` / `auto.history_batch`。
  · 产物的历史读数行**报出样本量、来源与每个读数的 n**，让人自己判断可信度。

【验收】
  · 语料分析：`_hist_corpus.py`（快速）/ `_hist_corpus_calib.py`（校准版：
    引擎判据分组 + cap 与实际停圈分开）；读数落 `_hist_corpus_summary.json` /
    `_hist_calib.json`。**全语料 384 条**（1 packed + 367 md + 16 batch）。
  · 探针 `_probe_v12314_hist.py` 41 项读数（三源 / 字段名 / 分桶 / 三级回退 /
    相对判据 / 落产物），含 **6 组负对照**（关掉两源掉回 1 份、空串抽取返回 {}、
    packed 里 `rounds` 不认、样本不足退回上限、同类不贵不降、一致率低不降）。
  · 冒烟 exit 0 / 0 ✗ / 209 ✓（守卫 101→102）。
  · 变异体 7 个全部判红（字段名读错 / md 源不扫 / 跑批源不扫 / 不按题型分桶 /
    忽视样本门槛 / 成本档退回绝对阈值 / 实际停圈不落产物），control 判绿。
  · ★ 首版判据在 **M5 / M6 上假绿** —— 两条都是「判据选错了分辨样例」：
    M5 用 0/1 层测样本门槛，那一层 `_layer_floor` 是 4，「采纳 2」与「不采纳 4」
    都被钳到 4；改**元层**（floor 5）才判红。M6 的合成样例里「绝对阈值」与
    「相对判据」结论恰好一致；补一条**两者会分歧**的样例（同类 90 万 < 全语料
    p75 500 万）才判红。⇒ **判据的样例要选在两种实现会分歧的地方**。
  · `load_config` 差异 == `{auto.history_limit}`（20→200，本版有意改）；
    yaml 覆盖 DEFAULT_CONFIG 全键（缺 0）并写出全部 5 个 `auto` 键；
    AST 登记 added 132→142 两向对账；主文件 17984 → 18286 行 / 纯 CRLF。

【未做 / 边界（如实记账）】
  · 三条规则**当前无数据支撑**：被截断率只有 6 层样本、三态一致率 n=1、
    联网失败与空结果 0 次。规则保留 + 在产物里标注 n，**不宣称已校准**。
  · `history_limit=200` 仍有窗口效应（读数随窗口变），未做分层抽样 / 时间衰减。
  · 未真跑：取样与阈值都是纯规则，真实语料 + 合成样例即可覆盖。

  ────────────────────────────────────────────────────────────
★ v1.23.14 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.14.py`（18286 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + `auto` 段两个新键 + `history_limit` 20→200 + 升级段）。

**改了什么**：修「实际停圈」字段名静默 bug + 产物新增该行；历史取样扩到三类来源
  （1 → 217 份样本）；读数扩到分位并按题型分桶；成本档改相对判据、圈数改三级回退
  （带样本门槛）。

**验收**：语料分析 384 条 + 探针 41 项（6 组负对照）；冒烟 0 ✗ / 209 ✓；
  7 个变异体全部判红（含首版两处假绿被修）；`load_config` 差异恰为本版有意改的
  一项；AST 登记两向对账绿。

**未做**：三条零样本规则的校准、窗口加权、真跑验证。

v1.23.13 相对 v1.23.12

【主题】把「自动」从散落的 8 处收进**一个统一自适应调度器**：十二项逐项可
  单独接管，每项按「题型 / 成本质量 / 效率 / 历史读数」自适应，逐项留痕；
  并清掉 `auto_plan()` 的双实现与双 schema 技术债。

【为什么】v1.23.12 之前：成本档 / 联网 / 思考强度散在 main 三条纯规则；
  模式与圈数散在 run 两次 LLM；取向路由一处；停止 / 联网降级 / 配额写死在
  yaml。三个后果 —— ① 读者答不出「这一次是谁定的 route / 圈数 / 联网」；
  ② 做不到「只让 auto 管一项」（`--rounds` 默认 `"0"`、`--route` 默认全四层，
  「没给」与「给了」不可区分）；③ 停止 / 降级阈值是常量，不吃题型与历史。

【做什么】
  · 新增 `auto_dispatch()`：十二项一次算完 —— 层集合 / 成本档 / 并行模式 /
    圈数 / 取向路由 / 联网 / 思考 / 强度 / 停止阈值 / 联网降级 /
    可判定性判定 / 落地层模板。每项按 `显式 ＞ 配置 ＞ auto ＞ 默认` 取值，
    逐项留痕（值 / 来源 / 理由）。
  · auto 的输入三类，**全部零 LLM**：`_auto_features`（纯规则题型特征）、
    已给的 cost/effort/rounds（成本质量意图与效率约束）、
    `_auto_history`（扫最近 N 份 `*.packed.json`：成本中位 / 被截断率 /
    各层实际停圈 / 三态一致率 / 联网入池与失败 / 取向错配）。
  · 逐项策略：12 个纯函数 `_auto_pick_*`。规则能定的不调 LLM（事实短题直接
    `serial`，省一次调用），拿不准才交 `_decide_parallel_mode` 兜底。
  · 落点三类、**都不改判定语义**：直接进 `run()` 参数（route/mode/rounds/
    orientation/landing/decidability）；写 `cfg["runtime"]` 由既有
    `_apply_runtime` 落（web/thinking/effort，唯一写入者）；写既有阈值键
    （`spiral.*` / `web_search.*`）。
  · 产物头部新增「**自动调度**（逐项来源）」十二条表格 + 题型特征 + 历史读数。
  · CLI：`--route/--rounds/--appendix` 默认改 **None**（区分「没给」与
    「给了」）；新增 `--landing` / `--decidability`。
  · 取向与落地层**解耦**：v1.23.12 之前 `auto` 在路由侧按 decision、在模板侧
    按题面分流，同一趟自相矛盾（靠「取向错配」告警自证）；现在取向管砍层、
    landing 管模板，各有自己的来源与理由。
  · 全关开关 `auto.enabled: false` ⇒ 十二项一律退回配置 / 默认，
    行为回到 v1.23.12（**可回退**）。

【技术债】`auto_plan()` 双实现 + 双 schema（v1.21.71 F8 起挂账）：
  · 新增 `_assemble_plan()` —— **唯一装配器**，三条出口（单调用正常 / 低置信 /
    失败 + 两段式出口）全过它 ⇒ schema 只有一种；单调用路径因此也带上了
    `route` / `cost_profile` / `max_calls`（由缺变有）。
  · 新增 `_normalize_orientation(v, fallback)` —— **唯一实现**，`fallback`
    做成显式参数（外部 API 要保守值、热路径要「未知」），原三份归一化消失。
  · 顺带把 `P5.2.b` 从「数源码字面 `"orientation": _ori`」改成**行为判据**
    （低置信打桩 ⇒ 断言 `mode == "serial"` 且 `orientation == "boundary"`）。

【验收】
  · 探针 `_probe_v12313_dispatch.py`（零 LLM，合成输入 + 合成历史）71 项读数：
    十二项齐全与留痕；**逐项显式接管 10 项各验一次**（每项都断言「只改这一项」）；
    总开关关掉后无一项为 auto；历史自适应 5 正 3 负；技术债（唯一实现 +
    两路 schema 逐键相同）；产物十二行表。
  · 冒烟 exit 0 / 0 ✗ / 208 ✓（守卫 100→101）。
  · 变异体 8 个全部判红（显式泄漏 / 总开关失效 / 历史不读 / 单调用绕过装配器 /
    两段式绕开装配器 / 产物表不渲染 / **显式值不落配置** / stop 策略空），control 判绿。
  · ★ 首版判据有**两处假绿**，靠变异体抓出：M3（判据把 hist 直接喂进调度器，
    绕过了 `_auto_history` 本身）与 M7（判据从没看过 `stop` 算出来的**值**）。
    分别补「真实介质驱动」与「值断言」后才判红。
  · ★ **修掉一个自己引入的功能级 bug**：`_apply_auto_dispatch` 首版只写
    「来源是 auto」的项 ⇒ `--web off` / `--profile quality` / `--thinking on` /
    `--effort max` **全部失效**（值只存在于 plan 里、没人搬进 cfg）。正确规则：
    写来源 ∈ {auto, 显式} 的项；`source` 是给**留痕**用的，不是给「写不写」用的。
    是既有的**接线判据**（smoke `v1.23.4` 与 `_v122_verify` `V7.a`）抓到的。
  · ★ 三条判据随实现更新（都不是放宽，是换成**行为断言**）：
    `P5.2.b`（原数源码字面 `"orientation": _ori`）、
    smoke `v1.23.4` 的三开关接线、`v1.23.11` 的联网接线（原查
    `_web_auto_for_facts(" ".join(args.question))` 与 `"web": _web` 两处字面）。
    ★ 同一判据可能在**多个文件里有副本**（`P5.2.b` 同时在 `smoke_test.py` 与
    `_v122_verify.py`），改判据前要 grep 全仓库。
  · `load_config` 逐字差异 ∅；yaml 覆盖 DEFAULT_CONFIG 全键（缺 0）
    且文本层面写出 `auto.*` 三键。AST 登记 added 104→132（两向对账）。
  · 主文件 17275 → 17984 行（+709）/ 纯 CRLF。

【未做 / 边界】未真跑（十二项都是纯规则或配置写值，合成输入即可覆盖；
  唯一 LLM 交互走既有 `_decide_parallel_mode`，未改）。**历史读数在真实样本
  下的稳定性**要攒够样本才看得出（当前 `outputs/` 只有 1 份 packed），属采样
  而非工程。`stop` 只调两个阈值，未动 `similarity` / `stalled` 一族。

  ────────────────────────────────────────────────────────────
★ v1.23.13 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.13.py`（17984 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 新增 `auto` 三键 + 升级段）。

**改了什么**：新增统一自适应调度器（一次算完十二项，逐项来源留痕）+ 12 个
  策略纯函数 + 历史读数加载器 + 产物「自动调度」表；CLI 三个默认值改 None 并
  新增 `--landing/--decidability`；取向与落地层解耦；清 `auto_plan` 双实现
  技术债（唯一装配器 + 唯一取向归一化）。

**验收**：探针 71 项读数（含逐项独立、总开关、历史 5 正 3 负）；
  冒烟 0 ✗ / 208 ✓；8 个变异体全部判红（含首版两处假绿被修）；
  `load_config` 差异 ∅ 且 yaml 覆盖出厂全键；AST 登记两向对账绿。

**未做**：真跑验证（属采样问题，非工程问题）。

v1.23.12 相对 v1.23.11

【主题】把「外部锚点」拆成**两条通道**分别写明：文本锚点（`external_anchor`
  —— 锚点**文件**）/ 联网检索（`web_search` —— **联网**）。全在渲染层。

【为什么】v1.23.11 真跑产物里，联网明明收了 6 条（`pool.meta` 的
  `[W-OK] …收 3 条` ×2，W1–W6，零失败），但产物只写一行
  「**外部锚点**：无（本产物不含外部事实校验；…）」—— 读者据此会认为
  本次**没有做任何外部校验**。两套机制互相独立（一个关着不代表另一个没跑），
  旧实现只渲染其中一套。

【做什么】
  · 新增 `_web_lane_stats(res)`：联网侧读数（开/关/未记录、条数、W# 编号、
    环节数、tier 分布、失败条数与 kind），纯函数、零 LLM。
  · 新增 `_anchor_lane_lines(res)`：**单一实现**，输出两条通道行，在产物
    **四处**共用 —— 头部 / 显化说明 / decision 落地 / boundary 落地。
    两处落地层各加一节「### 七、外部锚点（两条通道分开记账）」，节首写明
    两者独立、一条没有时也各自写明。
  · `save_result`：头部改由 `_anchor_lane_lines` 出两条通道行；
    锚点的**明细**（对照 / 分级 / triage 降级 / 冲突 / 入池）**原样保留**
    —— 两条通道是**多一条出口**，不是换掉这些读数；
    「本次未接入外部校验」留痕**改为仅在联网关时**出现（旧实现只看锚点
    文件在不在 ⇒ 联网开着也写「未接入」，口径错位）。

【验收】
  · 探针 `_probe_v12312_anchor_lanes.py` 用 **v1.23.11 真跑的 packed 原文**
    驱动 `save_result`（零 LLM 调用）：改前「外部锚点 · 联网」在产物里
    不可见，改后**四处同时出现**，头部写出
    `**外部锚点 · 联网**（`web_search`）：**开** —— 收 6 条
    （W1、W2、W3、W4、W5、W6；2 个环节；tier 3×6）；失败 0 条`，
    文本通道写「无」。7 组对照（三态 / 失败留痕 / 零条 / 异常 / 决策题
    不提示 / 收 0 条）全部符合预期。
  · 冒烟 exit 0 / 0 ✗ / 207 ✓（守卫 99→100）。
  · 变异体 `_probe_v12312_mutants.py`：control 判绿；
    M1 丢联网通道 / M2 联网恒报关 / M3 错误数清零 / M4 落地层漏接 /
    M5 头部漏接 / M6 锚点明细被吃掉 —— **六个全部判红**。
  · ★ 首版判据在 M5 上**假绿**：头部那处调用被删后仍判过 —— 产物正文后面
    还有「显化说明」，两条通道又从那里出现一次，而判据查的是「整篇产物」。
    已收紧为**首个二级标题之前**的头部区间。
  · ★ 首版改动把锚点明细当「旧单通道块」整段撤掉 ⇒ `--phase all` 的
    `[4.7] 头部含『锚点分级』+『triage 降级』` 判红（那是**信息**，
    不是旧形态）。已恢复明细，并把这条写进判据 G 段 + M6 变异体。
  · 旧关闭态断言（`v1.21.73` 的 `[A]`）**随实现更新**（语义不放宽）：
    仍要求「关闭时不许出现『已接入』」，锚点改到新实现那条文本通道的写法，
    并**新增**「联网通道整条不许丢」。
  · `load_config` 逐字差异 0 项；AST 登记 added 102→104（两向对账）；
    主文件 17171 → 17275 行（+104）/ 纯 CRLF。

【未做】无。

  ────────────────────────────────────────────────────────────
★ v1.23.12 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.12.py`（17275 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 升级段，**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：两个新纯函数（`_web_lane_stats` / `_anchor_lane_lines`）+ 产物
  四处渲染点接线 + 锚点明细保留 + 未校验留痕改为仅联网关时出现。

**验收**：真实 packed 驱动的 before→after 对表（联网 6 条在产物里由不可见
  变为四处可见）；冒烟 0 ✗ / 207 ✓；6 个变异体全部判红（含首版两处假绿被修）；
  `load_config` 差异 0 项；AST 登记两向对账绿。

**未做**：无。

v1.23.11 相对 v1.23.10

【主题】把「如实记账」里剩下的两条做完 —— R1 后半（自省诊断 → 动作回写）、
  R10 后半（事实题默认接入外部校验）。

【为什么】自省的高置信结论一直躺在 `views.*.self_check` 里（真跑实证：
  `unsaid_is_escape=true` + `quality_flags=["unsaid_overused(8)"]`），却从没变成
  任何动作 —— **诊断与动作之间是断的**。而事实题的外部校验，v1.23.10 只做了
  留痕，默认仍是没接。

【做什么】
  · R1 后半：新增 `_append_self_check_writeback(res, body)`，把高置信诊断
    （`unsaid_is_escape` / `xxx_overused(n)` / `action_incomplete` /
    `not_do_missing`）提升为落地层里的一条**可执行动作**；
    **没有高置信信号时不渲染**；顺序固定「形态声明 → 自省回写」。
  · R10 后半：新增 `_web_auto_for_facts(question)`；`--web auto`（默认）跑
    **事实型**询问时自动视同 `on`。要关掉：`--web off`。

【验收】
  · 探针 `_probe_v12311_writeback.py`（真实 packed 驱动 + 合成正/负对照）：
    自省回写 0 → **2 条**；无诊断不渲染（负对照不变）；事实题 True / 决策题 False。
  · 冒烟 exit 0 / 0 ✗ / 206 ✓（守卫 98→99）。
  · 变异体：control 判绿；M1 自省不回写 / M2 事实题不联网 **两个判红**。
  · **真跑一次**（`--route 1 --rounds 1`，不显式传 `--web`，走默认 auto）：
    终端留痕「事实型询问 + --web auto ⇒ 自动接入外部校验」；
    packed `_runtime` 里 `web_enabled=true`；
    **`pool["1"].meta` = `[W-OK] research_decompose 收 3 条（W1–W3）` +
    `[W-OK] research_evidence 收 3 条（W4–W6）`，`web_errors=[]`**
    —— 联网真的跑了 6 条、零失败。
  · `load_config` 逐字差异 0 项；AST 登记 added 100→102。

【未做】**无** —— R1–R10 十条至此全部落地。

  ────────────────────────────────────────────────────────────
★ v1.23.11 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.11.py`（17171 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 升级段，**无新键**，`load_config` 逐字差异 0 项）。

**改了什么**：自省回写（高置信诊断 → 落地层动作）+ 事实题默认接入外部校验
  （`--web auto` 下事实型询问视同 `on`）。两个新纯函数 + `main()` 一处接线。

**验收**：探针（真实 packed）0→2 条回写、事实 True / 决策 False；冒烟 0 ✗ / 206 ✓；
  2 个变异体判红；**真跑验证联网实际发生（W1–W6，零失败）**；
  `load_config` 差异 0 项；AST 登记两向对账绿。

**未做**：无。

v1.23.10 相对 v1.23.9

【主题】剩余四项一次做完（形态声明 / 附录外置 / 成本自动档 / 未校验留痕）——
  全部落在渲染 / 落盘层。

【为什么】v1.23.9 的真跑产物 9987 行 / 544,747 字节里**75% 是机械 JSON 附录**；
  而「落地层用了哪套模板」「事实题有没有外部校验」读产物的人只能自己猜。

【做什么】
  · R1 形态声明：新增 `_with_form_declaration`，在落地层标题**之后**插一行，
    写明本次用哪套模板与依据（模板分节是渲染约定，不等于提问者的要求）。
  · R8 附录外置：新增 `_appendix_to_file`，把内联全量 JSON 搬到旁挂
    `<产物名>.packed.json`。`_render_full_appendix` **一字未改**（它依旧是
    「机械全量」的权威实现），只做搬运；搬运失败自动退回内联并留痕。
    `--appendix inline` 回旧行为。
  · R9 成本档自动路由：新增 `_auto_profile`（纯规则，不调 LLM），
    `--profile auto` 启用；无决策语境 → economy，有 → balanced。
  · R10 事实题未校验留痕：事实型询问显式写明「本次未接入外部校验 + 怎么接」。

【验收】
  · 探针 `_probe_v12310_render.py` 用 **v1.23.9 真跑产物的 packed 原文**驱动
    `save_result`（零 LLM 调用）：产物 9987 → **1431 行**、544,747 →
    **138,288 字节（-75%）**；附录占比 75% → **0%**；旁挂文件 415,819 字节；
    四项读数全部翻转。（`_probe_v12310_before.txt` / `_after.txt`）
  · 冒烟 exit 0 / 0 ✗ / 205 ✓（守卫 97→98）。
  · 变异体 `_probe_v12310_mutants.py`：control 判绿；M1 声明不插 / M2 附录不外置 /
    M3 成本档恒 quality / M4 未校验留痕关——**四个全部判红**；
    另加交叉验证「M2 落在 v67 判据上仍须绿」（不外置 = 内联 = 旧行为）。
  · `check_v67_full_appendix` 取源改到「内联 / 旁挂」两路（**意图一字未改**），
    并顺带修一个真 bug：旁挂文件读在 `with TemporaryDirectory()` 块外 ⇒ 目录已删。
  · `load_config` 逐字差异 0 项；AST 登记 added 97→100（两向对账）。

【未做】R1 只做了「形态声明」这一半（「自省诊断自动触发换模式」仍需真跑验证）；
  R10 只做留痕与指路，没把外部校验变成事实题的默认行为。

  ────────────────────────────────────────────────────────────
★ v1.23.10 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.10.py`（17107 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 升级段，**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：渲染 / 落盘层四项 —— 形态声明、附录外置、成本档自动路由、
  事实题未校验留痕。三个新纯函数 + 一处 CLI 扩展（`--appendix`、`--profile auto`）。

**验收**：真实 packed 驱动的 before→after 对表（产物 **-75%** 且信息零丢失）；
  冒烟 0 ✗ / 205 ✓；4 个变异体全部判红；`load_config` 差异 0 项；AST 登记两向对账绿。

**未做**：R1 的后半段、R10 的默认联网。

v1.23.9 相对 v1.23.8

【主题】取向分流守卫 —— 无决策语境的题面不再套 decision 模板。

【为什么】v1.23.7 的真跑（题面「新中国的成立时间是什么时候」）在落地层留下一整套
  **不存在的执行流程**：行动清单里写着「负责人：党史研究室编研岗」
  「时限：定稿会前2个工作日」「验收：出具四节点原文摘录，逐条注出处并签字」。
  这个岗、这个会、这个签发人全是按 decision 模板的字段结构填出来的。
  根因不在模型，在**分流**：`orientation=auto` 无条件走 decision 模板。

【做什么】（只在渲染层分流壳 `render_landing`）
  · 新增纯函数 `_has_decision_context(question)` + 决策语汇词表（只增不减）。
  · `render_landing` 加一条分流：`auto` **且**题面无决策语境 → boundary 五块模板。
  · **显式 `--orientation decision` 仍走 decision**（不覆盖用户显式选择）；
    `boundary` 与「关掉开关」两条老短路保持原样；题面取不到（空 / 缺 `question`
    键）时保守走 boundary —— 不知道题面就不套决策模板。

【验收】
  · 探针 `_probe_v1239_orientation.py` before→after 7 例：auto+事实题
    decision→boundary；auto+决策题**不变**；显式 decision+事实题**不变**；
    空题面 / 缺 question 键 decision→boundary；词表 3 例命中 + 4 例不命中。
    （`_probe_v1239_before.txt` / `_probe_v1239_after.txt`）
  · 冒烟 exit 0 / 0 ✗ / 204 ✓（守卫 96→97）。
  · 变异体 `_probe_v1239_mutants.py`：control 判绿；M1 ctx 恒 True / M2 ctx 恒 False /
    M3 删 auto 短路 / M4 短路放宽到 decision —— **四个全部判红**。
  · **真跑一次**（同题、对照 v1.23.7 旧产物，`_cmp_v1237_vs_v1239.py`）：
    落地层由 decision 模板变为 boundary —— 「行动清单」段与「负责人：党史研究室编研岗」
    这类编出来的执行流程**整段消失**；产物无空节；头部出现
    `**停止**：自然 4 层 / 被截断（体力耗尽）0 层`；悬置渲染出现合并标注。
    ★ 如实记账：`--profile economy` 只改 token 裁剪、不改圈数上限，本次实跑
    188 次 LLM / 141.8 万 tokens，比 quality 那次更贵 —— 要控成本须同时限 `--rounds`。
  · AST 登记 added 96→97（两向对账）；`load_config` 逐字差异 0 项。

【未做】R1 自省→动作回写 / R8 附录默认裁剪 / R9 成本档按难度路由 /
  R10 事实题外部锚点开关 —— 逐条记账在 `v1239_报告.md` §五。

  ────────────────────────────────────────────────────────────
★ v1.23.9 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.9.py`（17013 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 升级段，**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：`render_landing` 的分流加上「题面有无决策语境」这一维 ——
  新增纯函数 `_has_decision_context` + 词表；`auto` 且无决策语境 → boundary 模板。

**验收**：探针 7 例分流全中（含 3 例负对照）；冒烟 exit 0 / 0 ✗ / 204 ✓；
  4 个变异体全部判红；真跑一次同题对照 —— 落地层转为 boundary 模板、
  编出来的执行流程整段消失、无空节、头部停因行 4/0、悬置去重标注生效；
  `load_config` 逐字差异 0 项；AST 登记两向对账绿。

**未做**：R1 / R8 / R9 / R10（理由见报告 §五）。

v1.23.8 相对 v1.23.7

【主题】渲染层三处守卫 —— 把最近一次真跑暴露的「形态错配」在产物层收口。

【为什么】2026-10-09 09:33 一次真跑（题面「新中国的成立时间是什么时候」）在产物里暴露：
  · 落地层出现**有标题、没内容**的节（`### 三、所需数据清单`）；
  · 四层**全部**「体力耗尽（被截断不是自然停止）」，但读者从产物头部看不出来 ——
    与「四层都自然收敛」在头部长得一样；
  · 「决定不消解」6 条里有 **2 组同 target 重复**（池内已有 ⊘ 去重，这一类没接）。

【做什么】（全在渲染层：不碰 prompt / 不碰 LLM 调用 / 不碰判定语义）
  · `_render_landing_decision`：「三、所需数据清单」与「六、如果只能做一件事」
    在无内容时输出**显式说明**，不再留空标题，节编号保持连续。
    ★ 首版补丁把「六」的节标题一起吞掉了 —— 被探针读数 `A1_节数` 当场抓到（6→5）。
  · 新增纯函数 `_stop_kind_summary(views)`：把各层 stop_reason 归纳成
    「自然 n 层 / 被截断（体力耗尽）m 层」，接在产物头部「**调度**」之后；
    全被截断时带 ⚠️「无一层自然收敛」；无停因时返回空串（不印 0/0）。
  · 新增纯函数 `_dedup_suspensions_for_render(items)` + `_susp_key(target)`：
    按 target 的**首个分句**归并同 target 的重复条（真跑里同一条张力被登记成
    「X」与「X；元层决定不消解。」，全长不等 ⇒ 按全长去重完全无效）；
    合并条数打印留痕，不假装池里没有重复。

【验收】
  · 探针 `_probe_v1238_rendering.py` before→after 对表：空节 2→0（无 actions）与
    1→0（有 actions），三/六标题仍在；停因三个读数正确；去重 5 条 → 保留 3 / 合并 2；
    异 target 不误合并、单条不吞。文件 `_probe_v1238_before.txt` / `_after.txt`。
  · 冒烟 0 ✗；新增判据 `check_v1238_render_guards`（守卫 95 → 96）。
  · 变异体 `_probe_v1238_mutants.py`：control 判绿；M1 空节复活 / M2 停因恒空 /
    M3 去重失效 **三个全部判红**。
  · AST 登记表同步（added 93→96，current → 本版）。

【未做】（逐条记账在 `v1238_报告.md`）
  R1 自省→动作回写、R2 取向路由短路（单点事实询问不套 decision 模板）、
  R8 附录默认裁剪、R9 成本档按难度路由、R10 事实题外部锚点开关 ——
  都属于**机制级改动 / 需要真跑才看得出效果**，与本轮「不跑真跑、只做离线可验」
  的约束不匹配。

  ────────────────────────────────────────────────────────────
★ v1.23.8 收束摘要
  ────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.8.py`（16973 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  头部版本 + 升级段（**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：渲染层三处守卫 —— ① decision 模板的空节显式化（三/六两节）；
  ② 产物头部新增一行「停止：自然 n 层 / 被截断 m 层」；③ 悬置条目渲染时按
  target 首个分句归并同 target 重复条。三处都是**加性 / 守卫型**：不改任何判定
  语义、不加任何配置键。

**验收**：探针 before→after 对表逐项符合预期；冒烟 exit 0 / 0 ✗ / 203 ✓；
  3 个变异体全部判红；验收档 `--phase all` PASS 310 / FAIL 5（5 条**全部**在
  v1.23.7 基线上也存在，无新增红；另修好 2 条旧红）；`load_config` 逐字差异 0 项；
  主文件纯 CRLF（CRCRLF 0）；AST 登记两向对账绿。

**未做**：R1 / R2 / R8 / R9 / R10 五条（机制级改动或需真跑验证），理由见上。

v1.23.7 相对 v1.23.6

【主题】把 changelog 从代码里搬出去 —— 代码文件只剩代码。

【为什么】v1.23.6 清掉了代码正文里的版次批注，但模块 docstring 里还留着 **4957 行 /
  22.7%** 的 changelog（含各版收束摘要）。它和代码混在一个文件里：读代码要滚过
  近 5000 行历史；而任何「在源码上数形态」的判据都必须先记得抠掉它。

【做什么】
  · 模块 docstring 里的版本段（`v1.23.6 相对 v1.23.5` 起）**原样**搬进仓库根目录
    `CHANGELOG.md`；本版段（本节）写在最前。
  · 代码里的模块 docstring 换成**短版**：标题 `元 DGTF · v1.23.7` + 一句话说明 +
    指向 `CHANGELOG.md`。★ 标题必须留在前 4000 字符内 ——
    `_probe_v1232_audit.py` 的 C1「docstring 标题版本 == __version__」按这个范围取。
  · 判据随实现更新 2 处（是**位置变了**，不是放宽）：
    `check_v72_changelog_hygiene` 与 `check_v76_changelog_wording` 原来读
    `SRC`/模块 docstring，现改读 `CHANGELOG.md`。

【零行为变化】模块 docstring **不参与执行**，且引擎自己**不读自己的 `__doc__`**
  （全文件仅 1 处 `__doc__`，且在注释里）。硬断言：抠掉 docstring 后代码部分逐字
  相同 + AST 严格等价。

【规模】21841 → **16894 行**（-4947 行；模块 docstring 从 4957 行降到 8 行）。


★ v1.23.7 收束摘要

**交付物**：`元DGTF-V1.23.7.py`（16894 行 / 纯 CRLF）；`CHANGELOG.md`
  （4988 行 / 27 段，v1.23.6 及更早**原样搬迁**）；`_mk_v1237_extract.py`（搬移器，
  三条硬断言）；`_mk_v1237_smoke_checks.py`（取源改造 + 新判据 + 守卫 94→95）；
  `_probe_v1237_mutants.py`（4 个变异体）；`_mk_v1237_config_sync.py`；`v1237_报告.md`。

**做了什么**：模块 docstring 里的版本段（4954 行 / 188,747 字符 / 占原文件 22.7%）
  搬进仓库根 `CHANGELOG.md`；代码里的 docstring 换成 8 行短版（标题 + 一句话 +
  指向）。21841 → **16894 行**。

**零行为变化**：模块 docstring 不参与执行，且引擎**不读自己的 `__doc__`**（全文件
  仅 1 处，且在注释里）。硬断言：① 抠掉 docstring + 归一化 `__version__` 后
  **代码部分逐字相同**；② 抠 docstring + 归一化后 **AST 严格等价**；③ 搬出的段数
  == 原段数（26 → 27，新增本版段），段序仍严格递减。

**判据随实现更新（是位置变了，不是放宽）**：`check_v72_changelog_hygiene` 与
  `check_v76_changelog_wording` 的取源从「源码 / 模块 docstring」改到 `CHANGELOG.md`；
  前者另抽纯函数 `_changelog_lint()`，并把负对照从「切换 SRC 指向」（取源外移后
  失效）改成喂**合成坏样本**。新增 `check_v1237_changelog_outside_code`（两向对账：
  代码里 0 处版本段 + `CHANGELOG.md` 段数 ≥ 10，防「搬出去」变「删掉」）。

**验收**：冒烟 exit 0 / **0 个 ✗ / 202 ✓**（上一版 201 ✓ + 新增 1 条判据）；
  新判据 **4 个变异体全符合**（M1 版本段 / M2 收束摘要 必须判红；M3 只在**模块**
  docstring 里塞必须仍绿 —— 证明判据真的抠掉了模块 docstring）；
  `load_config` 前后**逐字差异 0 项**、缺键无；主文件纯 CRLF。

★ **判据补洞（变异体抓出来的）**：`check_v1237` 的段标题正则原来只认 `^v1\.2\d`，
  变异体 M1 注入 `v1.99.9 相对 v1.99.8` **竟没判红** ⇒ 已放宽成
  `^v\d+(?:\.\d+)+ 相对`。**这就是「变异体必须打在判据读的那个东西上」的价值。**

**未做**：docstring 正文中段的版本提及（40 处 / 76 行）仍不动（同上一版口径）；
  本版不做真跑（零功能改动，且已证到 AST 级别）。

---

v1.23.6 相对 v1.23.5

【主题】代码正文不再留「版次批注」—— 变更记录统一由本 docstring 的 changelog
  承担；代码正文里的注释只解释「这段**当前**为什么长这样」。

【做什么】模块 docstring 之外，凡带版次标记的注释与文档串一律清理：
  · A 全行批注块：整行注释且含标记 → **连块删**（378 块 / 1476 行）
  · B 行尾批注：代码 + 同行注释含标记 → 只删注释部分（9 处）
  · C 文档串前导标记：函数/类 docstring **以**标记开头 → 只剥标记（66 处）
【两条保护，都因为「判据在读」】
  · P1 含 `[AUDIT-n]` 的注释行**不删**（冒烟按它数 pending_fix 条数）；行内的
    版次标记另行抹掉，所以保护行也不含标记（2 行）。
  · P2 **判据需要的片段**一个都不许消失：从 `smoke_test.py` + `_v122_verify.py`
    收集全部 `"X" in src` / `"X" not in src` 与 `src.count("X")` 的 X（156 个），做「最小代价
    保护」—— 某片段若**全部出现处**都在待删行里，只保住其中**最短的那一行**
    （实保 3 行），而不是整块。★ 本项目实踩：`assert "修行层不追求收敛" in src,
    "缺红线注释"` 只出现在一行带版次标签的**宪法红线注释**里 —— 盲目按标记
    删会直接打掉红线。

【版次标记的口径】`[v<数字>…]` 方括号短标签（如 [v122 P6 G6.2]）｜裸 v+数字
  （v1.21.59 / v1.19 / v59）；两侧用 `(?<![A-Za-z0-9_-])` / `(?![A-Za-z0-9_-])`
  挡掉 `deepseek-v4-pro` 这类假阳性。★ **必须按「块」量**：块内只有首行带标记，
  按行数会把规模低估到 28%（v1.23.5 定口径时据窄口径报 395 行，实为 1470 行）。

【零行为变化的机器证明】四条一起，等价于「只删注释 + 只剥 docstring 前导标记」：
  ① A+B 删完后 AST（抠掉模块 docstring + 归一化 `__version__`）**严格等价**；
  ② C 之后逐字符串常量比对：差异 **66 处**，每一处都恰好等于「剥掉一个前导
     版次标记」（`old == tag + new`），不多不少；
  ③ 把所有字符串常量的值抹空再比 AST —— **严格等价**，结构与非字符串常量
     一个都没动；
  ④ 判据需要的 156 个片段，**一个都没少**（全局断言）。

【规模】23237 → **21761 行**（-1476）；1296038 → **1169589 字节**（-123 KB）。
  被删内容**全文存档**在 `docs/版次批注存档-v1.23.5.md`（3092 行，带行号与最近的
  def/class 归属），配 git 历史可完全复原。

【明确不动】docstring **正文中段**的版本提及（40 个字符串常量 / 76 行）—— 例如
  「★ 兼容 v1.21.75 的布尔：True → evidence」。那是**文档行文**（在说这条规则
  何时定下来），不是「代码前面的修改描述」；要清它属于**编辑决策**而非机械操作，
  故留待需要时单独一批。

【未做】无功能改动 —— 阈值、常量、控制流、返回值一律未动。

  ────────────────────────────────────────────────────────────
  ★ v1.23.6 收束摘要
  ────────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.23.6.py（纯 CRLF，21761 行）；`_mk_v1236_strip.py`（剥离器：
    三类处置 + 两条保护 + 四条断言，`--dry` / `--go`）；`_mk_v1236_head.py` /
    `_mk_v1236_smoke_checks.py` / `_mk_v1236_config_sync.py`；三支 `_fix_v1236_*.py`
    （随实现更新的判据与夹具）；`_probe_v1236_mutants.py`（5 个变异体）；
    `v1236_报告.md`；`docs/版次批注存档-v1.23.5.md`（被删内容全文存档，3092 行）。

  **做了什么**：把代码正文（模块 docstring 之外）的版次批注清掉 —— A 全行批注块
    **378 块 / 1476 行**（连块删）、B 行尾批注 **9 处**（只删注释、代码不动）、
    C docstring 前导标记 **66 处**（只剥标记、正文保留）。23237 → **21761 行**。

  **两条保护（都因为「判据在读」）**：P1 含 `[AUDIT-n]` 的行不删（冒烟按它数
    pending_fix 条数）；P2 **判据需要的片段**（156 个）做**最小代价保护** —— 只在
    某片段会全部消失时保住最短那一行（只多保 3 行）。★ 实踩：`assert "修行层不追求
    收敛" in src` 只出现在一行带版次标签的**宪法红线注释**里。

  **零行为变化的机器证明（四条）**：① 删注释后 AST（抠模块 docstring + 归一化
    `__version__`）**严格等价**；② 剥 docstring 前导标记后逐字符串常量比对：差异
    **66 处**、每处都 `old == tag + new`；③ 抹空全部字符串常量后 AST 仍**严格等价**；
    ④ 156 个判据片段**一个都没少**。

  **验收**：冒烟 exit 0 / **0 个 ✗ / 201 ✓**（上一版 200 ✓ + 新增 1 条判据）；
    新判据的 **5 个变异体全部符合**（M0 绿 / M1~M3 判红 / M4 只在模块 docstring
    里塞标记仍绿 —— 证明判据真的抠掉了 docstring）；负对照（对上一版跑同一判据）
    扫到 **441 行**成块批注；`load_config` 前后**逐字差异 0 项**、缺键无。

  **判据随实现更新 2 处（是判据过时，不是放宽）**：`check_v72_bbarrier_semantics`
    的锚点 `[v1.21.72 #13]` → 换成同一段注释里的两条内容短语；变异体 M3 的锚点
    去掉注释、只锚代码行。两处的**判据意图一字未改**。

  **明确不动**：docstring 正文中段的版本提及（40 个字符串常量 / 76 行）—— 那是
    文档行文（在说规则何时定下来），不是「代码前面的修改描述」；要清它属于
    **编辑决策**，需另开一批并另配证法。

v1.23.5 相对 v1.23.4

【主题】清 `docs/机制审计-v122.md` 的挂账：把调度归一化从「三处各写一份」
  收口成唯一实现（pending_fix #1），并给布尔兼容路径加留痕（#3）。

【为什么现在做】那份审计文档停在 v1.22.2，落后 5 个版本，三条 pending_fix
  的真实状态**只能靠人工抽查** —— 抽查才发现文档写「两份实现」，实际是**三
  处**（模式白名单 3 / 圈数归一化 2 / conf 解析 3 / 低置信退 serial 3）。
  文档低估了重复面，这正是「登记表没有判据盯着」的直接后果。

【S1】调度归一化收口成三个唯一实现
  · 新增 `_plan_conf(data)` / `_normalize_plan_mode(data)` /
    `_normalize_plan_rounds(data, hard, route=None)`，放在 `_layer_floor`
    之后。三处调用点各留一行：
      - `MetaDGTF._decide_parallel_mode`（单目标决策，只定 mode）
      - `plan_resources`（两段式路径，要按 route 裁 rounds）
      - `auto_plan` 的单调用分支（`run()` 走的就是它，不裁 rounds）
  · 形态计数（抠掉模块 docstring 后）：`_up = mode.upper()` 3 → 1、
    `if rnd and len(rnd) < 4:` 2 → 1、`_layer_floor(k, hard, _floor)`
    2 → 1、`conf = float(data.get(` 3 → 0。剩下的那 1 处就是唯一实现本体。

  ★ **刻意不合并**的部分：「低置信退 serial」三处处置不同 ——
    单目标决策与单调用会**改写 reason 并提前 return**（「低置信(x)，退回
    serial：原 reason」），两段式只把 mode 改回 serial 后继续、reason
    **不动**。合并它就会改变返回值形状。这个差异由冒烟
    `check_v1235_pending_fix` 用三处对照钉住 —— 是**有意的差异**，不是
    「忘了合并」。

  ★ 顺带修掉一个潜在崩溃：单调用分支的 `conf = float(...)` 原来是**裸调**、
    不在 try 里 ⇒ 模型返回非数字 confidence 会抛 ValueError 逃出
    `auto_plan`；`_plan_conf` 统一兜成 0.0，且兜的方向是**保守**的
    （0.0 < 阈值 ⇒ 退 serial）。

  ★ 一条**日志**层面的差异（非返回值）：「漏层按中位数补齐」的 info 日志
    原来只在单调用分支打，收进唯一实现后两段式路径也会打一条。
    已 grep 确认没有判据读这条日志。

【S2】pending_fix #3：as_evidence 布尔兼容**留痕**
  · 原状：`_anchor_tier` 静默接受 `True/False`（True → evidence）。
    「还有没有人在用布尔写法」因此**永远没人知道**，这条待办也就永远清不掉。
  · 现在：走兼容路径就 `logger.warning` 一次，文案带原始值与迁移目标。
  · ★ **没有删兼容分支**。仓库内实测**零**布尔调用点（出厂 yaml 与主文件
    DEFAULT_CONFIG 两处都是字符串档），但「外部调用点」在本仓库之外；
    删了就是让外部配置**静默降级**（true → "true" 不在五档 → off，
    从「作证据」掉到「关闭」且无任何提示）—— 比留着更糟。
    正解是先让它**可观测**，等留痕确认没人走再删。

【行为变化】返回值层面**零变化**（改前/改后同一支探针逐行对表：16 组输入
  × 三处的 mode/rounds/conf/reason 全部逐字相同，低置信一组亦然）。
  唯一可观测变化是上面两条：一个潜在 ValueError 被兜住、一条 info 日志
  多了一个出口。

【未做】pending_fix #2（`_adjudicate_sub_tristate` 单票实现归档）本版
  **不动代码**：它是「等 tri_multi_vote 稳定若干批后评估」的等待型挂账。
  本版只给它配判据（可观测 + 可归档时立刻看得见）。

  ────────────────────────────────────────────────────────────
  ★ v1.23.5 收束摘要
  ────────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.23.5.py（纯 CRLF；本段只是 docstring 追加，
    可执行语句零改动 —— 见文末「收束自检」）；`smoke_test.py`（SRC 指向
    本版 + 新增 `check_v1235_pending_fix`）；`_mk_v1235*.py` 补丁链
    （每处替换断言命中恰好 1 次）；`v1235_报告.md`；`_probe_v1235_mutants.py`
    / `_probe_v1235_real.py`（变异体 + 真模型单点）；`_mk_v1235_config_sync.py`。

  **清掉三笔挂账**（`docs/机制审计-v122.md`）：
    · #1 调度归一化收口成 `_plan_conf` / `_normalize_plan_mode` /
      `_normalize_plan_rounds` 三个唯一实现 —— 实测重复面**比文档记的大**：
      模式白名单 3 处 / conf 解析 3 处 / 圈数归一化 2 处 / 低置信退 serial 3 处
      （且最后一处的处置各不相同）。刻意**不合并**低置信的 reason 处置差异，
      由冒烟判据 `[1e]` + 变异体 M3 三向钉住。
    · #2 `_adjudicate_sub_tristate` 单票实现 → **等待型**：不动代码，只配判据。
    · #3 `as_evidence` 布尔兼容路径 → **留痕而不删**（仓库内零布尔调用点；
      但删了会让仓库外配置从「作证据」静默降级成「关闭」）。

  **验收**：冒烟 exit 0 / **0 个 ✗ / 200 ✓**；4 个变异体全部判红 + 正对照绿；
    改前 / 改后 16 组输入逐字相同（含低置信反事实）+ 真模型单点逐字相同；
    `load_config` 前后**逐字差异 0 项**；注入器连跑两轮逐字节相同；
    `--phase all` **PASS 314 / FAIL 1** —— 唯一红是 `L1.src`（10 跑回归批仍是
    v1.23.4 的读数）。定为**诚实的已知未做**：本引擎「逐字一致不可达 ⇒
    跨版本差异 ≈ 同文件重跑差异」，重跑只买采样噪声，不重跑。

  **本版同时建起的安全网**：仓库 git 化（初始快照 / 归档 157 个顶层孤儿
    临时文件 / `.gitattributes` 的 `* -text` 挡住 `autocrlf=true` 的换行符转换）；
    推送前闸门 `_pre_push_check.py`（四项，带负对照）；已推送 `liao-wc/meta-dgtf`。

  **下一版（v1.23.6）的起点**：清掉代码正文里的**版次批注**（`# [vX.Y.Z …]`
    形态；抠掉 docstring 后**清前实测 300 行**）。判据与做法见
    `~/.workbuddy/skills/dgtf-version-bump/SKILL.md`。

v1.23.4 相对 v1.23.3

【主题】给「联网 / 思考 / 思考强度」加**运行期三项总控**，并让它们在**交互与
  命令行**里可选 —— 之前这三项只能靠改 `dgtf_config.yaml` 再重跑，
  交互里问不到、命令行也传不了。

  【形态】顶层新增一段（与既有的 `cost_profile` 顶层总控同构）：
      runtime:
        web: auto        # auto | on | off      联网总开关
        thinking: auto   # auto | on | off      思考总开关
        effort: auto     # auto | low | high | max      思考强度
    ★ 默认三项全 `auto` = **不覆盖任何既有键** ⇒ 本版与 v1.23.3 的行为
      **逐字相同**（判据：冒烟 `check_v1234_runtime` 对「配置逐字相同」
      做断言）。
    ★ `auto` 的语义是「**按配置文件**」，不是「跟上次一样」。

  【为什么「思考总开关」要连 stages 整表一起改】
    `LLM.call` 的档位优先级是「显式 thinking > 环节 stage 配置 > default」
    （fix-112）。只改 `default` 会被 `stages` 表**盖住** ⇒ 用户以为关了、
    实际大半环节还在开 —— 「总开关」成了一句空话。所以 on/off 一律把
    `default` 与 `stages` 的**每个键**写成同一个值（探针变异体 M2 专钉
    这一条：只改 default 必须判红）。
    ★ 同理，`effort` 只在思考**开启**时才会进 `extra_body`；用户设了
      强度而思考是关的，这一项**完全无效果** —— 这种「配了却不生效」
      必须当场说出来（`_apply_runtime` 的最后一条留痕）。

  【实现】一个纯函数 + 两条入口：
    · `_apply_runtime(base_cfg, runtime=None) -> (cfg, notes)`：**深拷**
      一份再改，**绝不改入参**。交互里若就地改 cfg，第二轮选 auto 就会
      读到第一轮改过的值 —— 「auto」会退化成「跟上一次一样」。
    · `_runtime_snapshot()` / `_runtime_summary_line()`：生效读数与一行
      摘要，写进产物 `_runtime` 键、并在两处横幅里打印（**共用同一个
      函数**，避免交互与 CLI 各写一份而慢慢走样）。
    · `load_config` 外面**套一层**（`_load_config_raw` 仍是原体）。
      为什么不在函数体中间插：它有**四个** return 出口（空路径 / yaml
      解析失败 / 顶层非 mapping / 正常），插中间要改四处、漏一处就
      「某些路径不生效」且**没有判据看得见**。
    · 交互：`_ask_runtime()` 三项逐个问（回车=auto），`_ask_config`
      的返回值由 4 元组变 **5 元组**；总控在**深拷副本** `run_cfg` 上
      生效，共享 cfg 不动 ⇒ 每轮独立、不跨轮记忆。
    · 命令行：`--web / --thinking / --effort`（choices 收紧在合法值上，
      合法值上，敲错 argparse 直接拦）；位置在 `load_config` 之后 ⇒
      命令行覆盖 yaml。

  【验收】冒烟 `check_v1234_runtime`（auto 恒等 + 三项各自落键 + 思考关
    必须连 stages 全关 + 非法值不静默 + 强度在思考关时给出提示）；
    探针 `_probe_v1234_runtime.py`（与 `LLM(cfg)` 联动验真实解析，
    含 **3 个变异体**必须判红）；验收档 `--phase v1234`。
v1.23.3 相对 v1.23.2

【主题】把 `v1232_报告.md` §十「仍未做 / 如实记账」五条**逐条清空**：
  不是「多跑几次」，而是把每一条**换成可判定的口径 / 受控实验 / 真跑旁证**。

  【遗留1 正交度：观测口径 → 受控实验】
    原判据「组间 ≥ 组内」（组 = 题、组内 = 同题重复跑）**结构性不可判定**：
    子问题集合**每跑重新拆解**，于是组内变异里混进了**上游拆解**的变异。
    实测同题两跑 `agree13` = 0.0 vs 1.0（组内极差 1.0 > 组间差 0.083）——
    再跑一百次也一样，测得的是「拆解每次都不一样」。
    修法：`_ab_tri_votes_v1233.py` **受控实验** —— 固定 12 条子问题 + 固定
    外部材料，只让三票重投（W4 关/开 × 温度 0.0/0.7 四臂）。
    判据落两个口径：① 信度 ICC(1,1) + 自助区间（组 = 子问题、组内 = 重复）；
    ② 字面口径「组间 ≥ 组内」= |臂间配对差 Δ| ≥ 配对残差 σ。
    ★ 温度 0.7 那一对是**负对照**：注入随机性后 ICC 不降 = 这个 ICC 没有判别力。

  【遗留1 顺带抓到的真 bug：三票 id 整票错位一格，且无声】
    受控实验实测：某票返回的 `judgments[].id` 是 **0 起**，引擎按 1 起对齐
    ⇒ 该票**整票错位一格**（第 2 条拿到本该给第 1 条的标签），第 1 条没人投。
    两处实现（`_adjudicate_sub_tristate_multi` / `_adjudicate_sub_tristate`）
    都直接 `sid = int(it.get("id", 0))`，没有任何校验。
    修法：新增 `_normalize_judgment_ids(judged, n)` 纯函数（1 起原样 /
    0 起整体 +1 / 其他**弃票**），两条路径都过它，并把「空票 / 0 起归一 /
    越界弃票」三个计数写进池级留痕（全 0 时**不写**，保持加性）。
    ★ 只归一、不猜：越界一律弃票而不是硬塞。
    ★ 连带修掉同一族的第二处：产物里的 `votes[].voter` 原先记的是
      **位置**（`enumerate(vs)`），只要有一张票被丢，剩余票就被重新编号
      ⇒ `agree13`（第 1 与第 3 张票）实际比的是**别的 prompt 对**。
      改为记**真票号**（无弃票时与改前逐字相同，只有弃票时才不同 ——
      而那时改前的值是错的）。
    ★ 审计探针新增的 L 类（「读模型返回的 id 必须归一化」）又报出两处
      **同类但不同点**的问题：`_parse_subs` / `_decompose_from_pool` 的
      子问题 id 直接取自模型（`int(sq.get("id", len(out) + 1))`）⇒ 可能是
      0 起 / 带洞 / 重复，而下游一律按 1..n 用。新增 `_canonical_sub_ids()`
      在出口处按位置重编号（加性：只改 id）。

  【遗留2 思考分档：注释里的断言 → 录播式 A/B】
    那 15 行在 yaml 里写着「关：思考无收益」，但那是**注释里的断言**，
    从没测过（v1.23.2 只是把值改到与实际行为一致）。
    修法：`_ab_thinking_v1233.py` 先包住 `llm.call` 抓一次真跑的
    **真实 (stage, system, user, 温度, max_tokens) 输入**，再逐 stage 用
    同一批输入跑 thinking 关/开，量 JSON 合法率、输出规模、延迟与**评分**，
    判据用等效检验（区间落在 margin 内 = 无收益），输出逐 stage 结论。

  【遗留3 tier 确认：空表 → 真跑旁证】
    `web_search.tier_confirmed` 机制通了但表是空的（生效路径只有离线判据）。
    修法：先用真跑采集真实域名，再按观察把域名写进确认表（低质域 → 4
    踢出引用表 / 权威域 → 1），重跑并验产物里 `[W-TIER✓]` / `tier_effective`
    与引用表的排斥效果；未确认域作**负对照**（不挂键 = 与默认逐字一致）。

  【遗留5 triage 频度：顺手捞到的读数 → 专项批 + Wilson 区间】
    原读数 1/10 是**顺手**得到的，不是专项测量。修法：`_run_v1233_triage.py`
    用定制题 + 定向锚点跑 N 跑，报 k/N + Wilson 95% 区间（区间不含 0 即
    「频度可判定」，无论高低）。

  【声明】本版对**离线验收集**（冒烟 / 7 份探针 / 验收档）与**出厂配置**
  一并同步：新增 `_normalize_judgment_ids` 进 AST 登记表；新增冒烟判据
  `check_v1233_vote_ids`（含端到端错位修正 + 变异体）；审计探针补一类
  「读模型返回的 id 必须过归一化」。


※ 版本段读法：v1.21.55 有「第一批 / 第二批」两段，不是重复条目——
  第一批是改之前的假设与实现，第二批是跑出第一份真模型产物之后的
  修订（编号续 P2-9）。v1.21.56 是再跑一轮真模型之后的修订。
  v1.21.57 是本轮收束版：从「代码自查 + 真跑复查」出发的九项改动。
  v1.21.58 是本轮收束版：报告改名 + 预算定标 + per_entry 去掉 + 停止条件审计。
  v1.21.59 是本轮收束版：整体运行质量验证 + 可判定性三态互转 /
  评估→拆解不再一次传播 / 复债（判定不再定成终审）。
  v1.21.60 是本轮收束版：全息剖析 + 七条修正 + 真跑验收 + 评估时机
  统一到研究层拆解时（⑩）+ 判定机制方向性说明（⑪）。
  v1.21.61 是本轮修正版：F/H/G + E/H/G 两批真跑（6/6 OK）跑完之后，
  按真跑实证修两处 —— 不可判定的判定范围（①）+ reclassification
  的证据编号（②）。
  v1.21.62 是本轮工艺改进版：锚点重述补 touched、"至少碰一个"改成
  代码硬约束、三态视觉区分、ing 结构化尾块、对撞层独立 he、revisit
  白名单、取向判据 P2-7、auto_plan 拆两段、新增显化层。
  （P1-6 白名单当天返修：初版 6 条 pattern 过窄，实测 1213 条真实
  回访条件只放行 2%、且被拦的无声消失；已改成三类宽特征 + 留痕。）

  v1.21.63 是本轮修正+补全版：C 段修复（元层 tension_id 对账）+
  三项可观测性（悬置一圈内自解 / 外部锚点 / 语义不一致转化观测）。
  ★ C 段根因最终查到底：不在 prompt，在**串行通道的上游接线**。

  v1.21.64 是本轮兑现版：把 pool.meta 的渲染出口补上（v1.21.62 起
  承诺、一直欠着）、把 by_id 口径从「只数 active」改成「数池里真实存在」、
  并对 v1.21.60 遗留的四项零触发机制做了只读审计（已跑出两项真证据）。

  v1.21.65 是本轮观测版：把 `_starve_rounds`（机制一的「离门槛差多少」）
  的渲染出口补上、审计探针接上；研究层「给足圈数」按项目约定走运行时
  `--min-rounds`，不动出厂配置。
  v1.21.66 是本轮兑现版：机制一的计数从「最终快照」改成**同时报运行期
  峰值**（快照会被清零、峰值不会），并补「覆盖计数」把真 0 与
  「机制没跑」分开 —— 快照答不了「离门槛差多少」，峰值能。
  v1.21.67 是本轮完整性版：产物 md 追加「全量字段」附录（正文没渲染的
  packed 字段一律落盘），真跑日志改成**收全**（stdout + stderr +
  logging + 完整性自检）。
  v1.21.68 是本轮留痕版：每层每圈把 view 的**全部字段**机械打进日志
  （`DGTF.dump_round`），并让 **ing 正文**就地可见 —— 此前每圈只打摘要。
  v1.21.69 是本轮修正版：A/B/C/D/E 五项（两处真 bug + 一处口径错 +
  一处潜在串层 + 一处"没出口"误诊成"重复"），**每项先量后改**，
  冒烟带负对照；外部评审有两项诊断与实际不符，照实写。
  v1.21.70 是本轮收尾版：F/K 补齐 v1.21.69 [B] 的两个出口（轨迹口径
  + 触发时机）、G 修锚点占位符闸门（仅剩的真 bug）、H/I/J 是 [E] 的
  延伸与卫生。
  v1.21.71 是本轮缺陷修复版：外部代码检查报告（24 项）逐条复核后落地
  F1~F11 十一项，**3 条外部结论经实测不成立**（照实写在该段内）。
v1.23.2 ── 整体性检查 + `v1231_报告.md` §十 遗留全清

  【整体审计】新增 `_probe_v1232_audit.py`：对**整份工程**做 8 类机械检查
    （出口完整性 / 死类 / 白名单四处一致 / 版本一致 / 宪法红线 / 圈号口径 /
    used_as 枚举 / 配置键可达性），自带 **3 个变异体**证明审计有判别力
    （抠掉 `to_dict` 出口、抠掉 `dec_norm` 白名单行、把圈号换回拆解序号
    —— 对应判据都必须判红）。审计报出 6 类真问题，本版**全部处置**：

  【★ 15 个 `api.thinking.stages.*` 键永远选不中（装饰品 + 静默）】
    `thinking_stages.get(stage)` 只在 `stage` 非空时才生效，而
    `_decompose_normal` / `_probe_*` / `_settle_research` / `re_anchor` …
    **一共 16 个调用点根本没传 `stage=`** ⇒ 一律掉回 `thinking_default`。
    后果：用户把 `decompose_normal` 改成 `enabled` 会**毫无效果**，
    且没有任何提示。修法：新增 `_thinking_stage(cfg, name)`（**以配置为准**：
    只在键已声明时返回该名，拼错就返回 None），并给 16 个站点接线。
    ★ **行为不变的可机器验证证明**：这 15 个键的出厂值都是 `disabled`，
      与 `thinking.default` 相同 ⇒ 接线前后解析出的 `th` 逐字相同
      （判据 `K2` 用 DEFAULT_CONFIG 直接证）。

  【★ `web_search.stages` 里两个键是「声明了不做」】`practice_term_calibration`
    与 `stop_criteria` 永远不会被调用（任务书 §七 明确不做）⇒ 进豁免表
    `_AUDIT_CONFIG_EXEMPT`（**两向对账**：未登记判红 + 过期登记判红）。

  【★ 死类 `Amp` / `Probe`】定义后**零引用**。按项目纪律**不删**，
    登记进 `_AUDIT_DEAD_CLASSES`（只标不删，且下次审计不会再当新发现）。

  【遗留3 · tier 确认生效（人确认后才生效）】新增
    `web_search.tier_confirmed`（域名 → tier 的人工确认表，**默认空**）
    + `_web_tier_confirmed` / `_web_tier_floor` / `_web_enters_citation`。
    · W# 进引用表加 **tier 门**（与 X# 同纪律：有效 tier ≤ floor）；
    · 命中确认表时挂 `item["tier_effective"]`（**不改** `tier` 本身）；
    · `web_search.tier_floor` 由 2 改 3 —— 它此前**从未被读过**（又一个
      装饰品键），改成 3 后与 v1.23.1 行为一致（客户端初值 3 仍可进表），
      而人把某域名确认成 4（博客/论坛）就会被挡在引用表外；
    · ★ **从提案到生效没有自动路径**：`_web_tier_confirmed` 只读人写的
      确认表，绝不读 `tier_proposal` 的产物（判据 + 变异体钉住）。
    · 留痕 `[W-TIER✓] 人工确认表生效 N 条`（关闭态不出现 ⇒ 加性）。

  【遗留4 · `used_as` 语义】W4 第三票的检索原标 `arbitration`，而它的
    `stage` 是 `research_evidence` —— 两个标签对不上，读者无从判断
    「这条给谁用」。新增 `_WEB_USED_AS` 枚举（封闭集合）并改为 `tri_vote`。
    ★ 澄清一个事实（审计顺带查清）：`used_as` **没有程序消费方**，
      它是写给**读者与分析脚本**的；枚举化的价值在于「不得出现未登记取值」。

  【遗留1 · 空票重试】新增 `actions.tri_vote_retry_empty`（默认 1）：
    某票返回**合法 dict 但 `judgments` 为空**时重试一次 —— 空票是**失败**
    不是弃权（实测 10 跑里 4 跑因此只有 2 票可用）。留痕改成报
    **重试后**的可用票数。★ 不改 `ok_votes` 的位置（「三票全失败」分支不变）。

  【判据形态修正 · `P2.4.a`（采样 → 构造性证明）】原先断言「三题真跑里
    ≥1 题 triage ≥1 条」—— 那是对**低概率随机机制**做 n=3 采样：实测同配置
    两次批次给出 `[1,0,0]` 与 `[0,…]`，本质是掷硬币。修法：
    · 把 triage 的**组装逻辑**从 `_anchor_crosscheck` 抽成纯函数
      `_triage_suggestions(und_aspects, anchors, cfg)`（行为一字不改）；
    · 判据改为**构造性证明**：喂已知合格输入 ⇒ 断言必产 ≥1 条；配 3 条负对照
      （真·自指 / 不属「缺外部材料」/ 锚点 tier 超门）+ **2 个变异体**
      （破坏 tier 门 / 破坏自指剔除 ⇒ 对应负对照必须判红）；
    · 真跑采样读数降为**观察项**（只打印，不判红）。
    ★ 通则：**能力存在性用构造性证明，效果大小才用采样。**

  【声明】本版对**离线验收集**（冒烟 / 6 份探针 / 验收档）与
    `dgtf_config.yaml` 都做了同步；`--phase all` 目标 0 FAIL。

v1.23.1 ── 遗留收尾（真圈号 / tier 提案待审 / 三场景 + 三票正交度实证）

  【遗留3 · round_no 换真圈号】原先所有环节的 round 都取「拆解序号」
    （`_web_prep_seq`）—— 拆解每跑只发生一次 ⇒ 所有 round 恒为 1 ⇒
    `quota.per_stage_round`（任务书写明「每环节**每圈**」）退化成
    「每环节每跑」，**三层配额实际只剩两层**。这是语义名不对带来的
    **实质**后果，不只是命名问题。
    改法：`_web_evidence_hook` 用 `update_deferrals` 传进来的真圈号；
    `_web_duel_arbitration` / `_web_meta_clean_check` 加 `round_no` 形参，
    由 `_finalize_layer_common` 传 `r_actual + 1`；拆解前置（圈循环之前，
    确实没有圈号）统一为 **0**，并在每条 W# 上留 `round_kind`（pre/in）
    与 `pre_seq` —— 让「前置」与「圈内 1..N」在产物里可区分。

  【遗留2 · 联网结果 tier 提案（**待审**）】W# 的 tier 现在一律是客户端
    初值 3（= 未知），`tier_floor` 是 2 ⇒ 这批材料的 tier **没有信息量**。
    但直接让它自动判 tier 比没有更危险（一条 tier=1 的二手转述能支撑
    →decidable）。所以只做**提案**：
    · 新增纯函数 `_web_tier_proposal(results, cfg, known_domains)`，
      按 `domain_tier_rules`（前缀 → tier）给建议档；未知域名保守取 3；
      返回 `{url, domain, proposed_tier, why, first_seen, confirmed: False}`。
    · 新增 `WebSearchCache.domains_load()/domains_save()`：首次出现的域名
      落 `cache/websearch/_domains.json`（**只登记，不判 tier**）。
    · 结果写 `pool.web_tier_proposals` + 池级留痕 `[W-TIER?] ...（待审，未生效）`。
    · ★ `web_search.tier_proposal` **默认 False**（= 与 v1.23.0 逐字相同）；
      即便打开，也**绝不**改 `item["tier"]`、**绝不**进任何判定路径 ——
      判据带着变异体（把提案写进 item["tier"] ⇒ 判红）。

  【遗留1 · 三场景命中率 + 三票正交度】按项目口径「每题只跑 2 次」设计
    最小可判实验：3 场景 × 2 跑（联网 ON）+ 1 场景 × 2 跑（联网 OFF
    负对照）。命中率 = 「联网结果与场景预期一致」的跑数占比；
    正交度用两两一致率矩阵（agree12 / agree13 / agree23）——
    只有**组间差 ≥ 组内极差**才许下结论，否则如实写「不可判定」。

  【遗留4 · v1.22.2 遗留的两条 `P2.4.a/b`】判据的锚是
    `outputs/p2_run{1,2,3}`（v1.22.1 时点的产物，本机已被清理）⇒
    「缺失即判红」。按本版口径用**当前版**重跑这 3 题补齐产物，
    判据在**当代码**上重新为真（不是冻结快照）。

v1.23.0 W5-fix ── 池出口白名单 + 成功留痕

  【W5-fix】`Pool.to_dict()` 是**显式白名单**，W2/W3 新增的 5 个联网字段
    没被列进去 ⇒ 真跑里 tavily 明明返回了结果（`cache/websearch/` 4 个文件
    n=3/8/8/8），产物里 W# 却是 **0** —— 静默吞掉。已补进白名单（仍加性：
    无联网痕迹时不挂键，关闭态 packed 与 v1.22.2 逐字相同）。
    ★ 与 W2 的 `dec_norm` 是**同一类坑**，这次栽在**池出口**这一层。
    对策：加通用前向守卫 `check_v123_pool_export`（把 Pool 所有 dataclass 字段
    填满后断言它们**全部**出现在 `to_dict()` 里）—— 任何人再加字段忘了出口，
    判据立刻红。

v1.23.0 W3+W4 ── 对撞层/元层接入（仲裁材料 / 缺失核对）+ 三票正交化

  【W3 · 三池分离】`Pool` 新增 `web_arbitration` / `web_clean_check`。
    为什么不共用一个 list：三者**消费方**不同（判定 / 对撞 / 元层），
    混在一起后「W# 到底有没有进对撞内容」就没法按池判。
    新增 `_duel_arbitration_queries(tensions)` / `_meta_clean_queries(uncovered)`。

  【W3 · 接入点收在 `_finalize_layer_common`】
    · `entry == "both"` → `_web_duel_arbitration(view)`：从本层
      `adjudications[*].tension` 出仲裁问句；结果进 `pool.web_arbitration`
      + 池级留痕 `[W-ARB]`。**不进 ing、不进对撞第三者**（未对齐合法）。
    · `entry == "all"` → `_web_meta_clean_check(view, uncovered_aspects)`：
      只对 `uncovered` 核对；结果进 `pool.web_clean_check` + `[W-CHK]`。
      **不碰 deferred 的清算**（停止与清算分开）。
    · 两条都 try/except 吞掉只留痕 —— 联网是锦上添花，绝不能把层带走。

  【W4 · 三票正交化】第三票改「外部证据裁判」：system 追加
    【外部检索摘要】+ 一句「**只看**外部材料与锚点，池内产物不计入」。
    仅当 `web_search.enabled` 且 `research_evidence` 授权**且**该次检索
    确有结果时替换；否则三票逐字与 v1.22.2 相同（加性）。

v1.23.0 W1 ── 核心联网 · 基础设施（骨架 / 客户端 / 缓存 / 独立通道 / 配额三层）

  ★ 本 Phase **不接入任何环节**（research_decompose 等全部「只配不接」）。
    验收通过即成 W1 门；未通过不许进入 W2。

  【前置】W 系列任务书本身先经过核验（v1.22.2 阶段 0 范式），
    3 处卡点已回写成执行版 `_v123_taskbook.md`：
    · [修正 B1] W2 的判据「apply_decidability_change(evidence=[W#], to=partial)
      → applied」依赖「W# 进 _citation_table」——原方案把这一项排在 W4，
      判据与交付物不同阶段 = **判据不可达**。已把该项移到 **W2 前置**。
    · [修正 B2] `dgtf.websearch` 是 `dgtf` 的**子 logger**，propagate 默认 True
      ⇒「所有 web 日志只进这个 logger」这条红线无法成立。已加 `propagate = False`。
    · [修正 B3] 原 §6.3 声称「连续 3 次失败 → disabled = True」，但代码片段里
      **没有任何一处**给 disabled 赋值（allow() 只返回 False）⇒ 产物里读不到
      「本跑已降级」。已让 `note_failure()` 显式置位并留痕 `[W-DISABLED]`。

  【新增配置段】`DEFAULT_CONFIG["web_search"]`（加性；`external_anchor` 一键未动）
    · enabled=False（默认关：不显式打开 = 零调用）
    · quota 三层：per_stage_round / per_stage_total / per_run_total
    · stages：修行层 term_calibration 与 stop_criteria 默认 **False**
    · backend / api_key_env / timeout / max_retries / backoff / cache_ttl_hours
    · auto_disable_after_failures = 3

  【新增符号】
    · `logger_web` = logging.getLogger("dgtf.websearch")，**propagate=False**
    · `WEB_FAIL_KINDS` = timeout / rate_limit / empty / dirty / api_error（五档）
    · `WebSearchCache`：sha256 + TTL，`cache/websearch/`
      —— **不复用** `cache/anchors/`（那是锚点快照的命名空间，混用会污染其语义）
    · `WebSearchClient`：超时 / 重试 / 退避；`search()` 返回 `(results, fail_kind)`，
      **失败分类返回而不是抛裸异常**（否则「0 条」与「超时」在调用方长得一样）
    · `WebSearchGate`：授权 + 三层配额 + 连续失败降级（三个否定方向都给可读理由）
    · `build_web_search(config)`：从配置造一套，**不发起任何调用**

  【与既有组件的关系】
    · 不合并 `AnchorRetriever`（锚点 = 事先落盘的冻结事实）与 `WebSearchClient`
      （联网 = 运行时活检索）；编号 `X#` / `W#` 不互换。
    · `_overlap_coef` / `_UNTRACED_OVERLAP` / `0.6` 等阈值一律未动。

  【本 Phase 不做】任何环节接入；W# 进 `_citation_table`（属 W2）；三池（属 W2/W3）。

v1.22.2 ── 收尾补充 + W 系列前置（任务书核验 / P4 口径统一 / not_do / answers 长度 / W 清单）

  ★ 本版是**最后一个单文件版** —— W 系列（核心联网）启动后代码结构会变。
  性质：v1.22.1 的收尾补充 + W 系列的前置。四阶段全部是**收口**，不新增能力。

  【阶段 0】任务书核验（新范式）
    · 把「前提不成立 / 骨架 bug / 判据不可达 / 授权不清」前移到**执行前**。
    · 本轮实测发现 **9 处**（`_taskbook_audit_v1222.md`），其中 8 处改了设计。
    · 最有价值的一条：任务书只描述了「入口」（prompt schema），
      没描述「出口」——`dec_norm` 是显式白名单 dict，不列新键就**静默吞掉**
      模型产出，现象与「模型不产」一模一样。凡加新产出字段，必须同时核
      **prompt schema → 归一化白名单 → 抽取函数 → 渲染点**四处。

  【阶段 1】P4 OFF 臂口径统一
    · 根因：`stability` 只有多票路径写；单票（OFF）臂连键都没有，
      而头部却按 `stability` 统计 → 印出「三态多票 high 0 / medium 0 /
      low 0　一致率 0% ⚠️ unstable」——**非读数被当成测量值**。
    · 新增模块级 `_single_vote_stability(sq)`：单票口径 = 单票 vs 拆解原标签
      （一致 high / 不一致 low / 有判无原标签 medium / **未被判到 = abstained**）。
    · 新增 `MetaDGTF._write_tri_stability(subs, mode, from_votes)`，
      并在**每个出口前**调用（单票实现有 5 处早退 `return 0, 0`，只写尾部
      会让「判决失败」这一情形在产物里彻底读不到 —— 那正是同一个 bug 的形态）。
    · ★ 单票口径里先看 `label_disagreed`：只看「first_label vs 当前标签」
      会漏掉一格 —— 分歧落点恰好是 `partial`、而原标签本来就是 `partial`
      时两者相等 ⇒ 被误判成 `high`。**真跑实测**：OFF 臂 stability 6×high
      而同产物「三态判决一致率」只有 5/6，两行对不上就是这一格。
    · 头部改成**按 `_vote_mode` 分口径**印：`三态判决（单票/多票）` +
      `口径=单票 vs 拆解原标签 / 三票之间`；分母**只数已判条**，弃权条单列。
      **不再把单票路径印成「三态多票」**。
    · 两臂的 `stability` **不是同一把尺子**（多票量的是「三票之间」），
      拿两臂的数直接比会得到错结论 —— 所以口径必须印在标题里。

  【阶段 2】schema 加 not_do（decision 取向的第三分）
    · `_he` 的 `decidable_product` schema 加 `not_do[]`（what ≤40 字 / why ≤40 字）
      + 约束段（「至少 1 条，最多 3 条；不硬凑」）。
    · ★ `dec_norm` 白名单同步加 `"not_do": _norm_schema_not_do(...)` ——
      不加这一行，模型产了也进不了 `view.decidable_product`。
    · 新增 `_norm_schema_not_do`（空 what 丢弃、最多 6 条，与
      `_norm_schema_actions` 同款）；`_extract_not_do` 改成 schema 优先 +
      词法兜底（原实现整体改名 `_extract_not_do_lexical`，正文一字未动）。
    · `not_do_missing` 语义更新：= **模型没按 schema 产出 not_do**，
      不是「词法没抽到」；只认 `_source == "schema"`。
    · rubric **判据一字未改**（`score_actions` 早已 `if nd: s += 1`）——
      改的是「能不能拿到这个量」。上限 2/3 → 3/3 由 schema 打通带来。

  【阶段 3】answers 最短长度约束
    · 动机：`_overlap_coef` 分母取 `min`，2 字 answer 被长 aspect 包住
      就是 1.000（假命中）—— W 系列自动生成 short answer 会放大它。
    · `external_anchor` 加 `answers_min_len: 6` / `answers_max_n: 5`
      （后者原先是硬编码 `[:5]`，本版提成配置，值不变 = 行为不变）。
    · `_load_anchors` 过滤并留痕 `anchors.<id>._answers_dropped`。
    · ★ **两条告警必须分开**：`_anchor_answers_warning`（「全部 N 条锚点
      **未声明** answers」）已被 v1.22.1 P2b 占用，任务书原本要复用它 ——
      直接赋值会静默摧毁既有留痕，且过滤后 answers 全空会**反向**触发它、
      说出假话。本版新增独立属性 `_anchor_answers_filtered`，
      并把「已声明但被过滤」从「未声明」里刨掉。
    · 产物头部加「⚠️ **锚点 answers 警告**」一行；packed 加 `answers_filtered`。
    · 阈值一律没动：`_overlap_coef` 分母仍是 min、0.6 一字未改。

  【阶段 4】W 系列启动检查清单（只出清单，不出代码）
    · `docs/W系列启动检查清单-v1222.md` 六类 A~F：前置 / W 任务书核验 /
      四条宪法级特性（每条带冒烟断言路径）/ 独立通道 / 配额三层 /
      锚点与联网的边界。
    · 结论二选一（可以启动 / 不启动），每条带断言或命令依据。

  【配置同步】`dgtf_config.yaml` → v1.22.2：头部版本 + 升级段 +
    补 `answers_min_len` / `answers_max_n`（按默认值写。
    `load_config` 前后逐字对比为 **True** = 行为不动）。

  【怎么退回旧行为】
    · P4 单票口径：`actions.tri_multi_vote` 置 false → 走单票路径（口径仍会印）。
    · not_do：`_extract_not_do` 自动回落词法（老产物 / 未升级 schema 的跑批）。
    · answers 长度：`external_anchor.answers_min_len` 置 0 → 不过滤。

  【未做 / 遗留】
    · 全量 20 题跑批未做（本轮口径：**主要做检查**，每题只跑 2 次）。
      P4 的两臂对照证据以**离线 mock E2E**（确定性、可复现）为主，
      真跑仅作分布量级观察。
    · W 系列本体未启动（本版只出清单）。

v1.22.1 ── 三档收尾（P1 行动闭环 / P2 triage / P3 负对照 / P4 对照 / P5 取向 / P6 tier / P7 不做）
  本版是 v1.22.0 的**三档加性**收尾：第一档（P1/P2/P3）→ P2b（第一档续做）→
  第二档（P4/P5/P6）→ 第三档（P7 只出说明）+ 全局收尾。
  ★ 第一档的 P2 **单档未通过**（触发条件修通、效果判据未达标），按任务书
  停在第一档；续做 P2b 换匹配对象后打通，P2 才**重判为通过（P2a + P2b 合并）**。
  红线守住：rc1 起累计纯删除行 0、AST 符号消失 0 项、新增 6 项逐条登记
  （见 _v122_ast_registry.json）。逐档报告见 v1221_p1~p6_报告.md + v1221_报告.md。

  【第一档（无前置）】
  P1 研究层直接产出结构化 actions（本档通过）
    · `_he` schema 加 `decidable_product.actions[]` + 约束段；
    · ★ `dec_norm` 白名单加 `actions` —— 不加就是**静默吞字段**（新函数
      `_norm_schema_actions` 立据）；
    · `_extract_actions` 改「schema 优先 + 词法兜底」：原词法版改名
      `_extract_actions_lexical`（正文一字未动），兜底结果带 `_source` 标签；
    · `action_incomplete` 语义改「没按 schema 产出」；新增 `action_fields_missing`
      并**同时进 `_V122_HARD_FLAGS`** —— 这条是读真跑 packed 才抓到的真 bug：
      flag 写进了 errors，却被 19 行后的 quality_flags 整体重算冲掉。
    实测：三题真跑 action 5/6/4（全 ≥3）；rubric 平均 2.00；`action_incomplete`
    从改前 4/4 份全触发 → 改后 0/3。动词白名单仍 19 条（未拟合数据）。

  P2 triage 触发条件改挂结构标签（**本档未通过**，由 P2b 补齐）
    · 新增 `_TRIAGE_STRUCTURAL_PREFIXES`（`[外]`）/ `_is_triage_candidate`
      （结构标签 ∪ 语义关键词）/ `_is_never_downgrade`（真·自指不许降级）；
      旧词表 `_TRIAGE_KEYS` 一字未删（加性）。
    · 机制判据 15 项全绿，但三题真跑 triage = [0, 0, 0]：触发条件已修通，
      卡在下游 `_similar(aspect, anchor.claim, 0.6)`（14 条侧面最高词重叠
      0.167 / 中位 0.000 / ≥0.6 的 0 条）——根因是**语义类型不匹配**：
      `undecidable_aspects` 说「缺什么材料」，`anchor.claim` 说「是什么事实」。

  P3 仅源码机制做负对照（本档通过；本版不删任何机制）
    · 对审计判「仅源码」的 5 条各写负对照：4 条**能触发**（条件窄但成立，
      保留）、1 条 `_all_settle_streak` 判**条件不可达**（内联在 `_run_layer`
      的圈循环里、无宿主可调用）→ 归档 `pending_fix`。
    · 与审计报告「仅源码」5 项做**两向对账**（集合相等判据）。
    · `no_push_when_idle` 用**差分**负对照（同输入换开关看分支是否真变），
      不是「函数返回了东西就算工作」。
  ⇒ 第一档整体：P1 通过 / P2 未通过 / P3 通过 → 按任务书禁令停在第一档。

  【P2b（第一档续做，单点）→ P2 重判通过】
    · **不改阈值、不改触发条件，只换匹配对象**：锚点快照加 `answers`
      （「我能回答哪些侧面」）；新增 `_hit_by_answers`（`_overlap_coef` +
      `_UNTRACED_OVERLAP`=0.6，双向）与 `_hit_by_claim`（老路径，`0.6` 字面
      **一字不动**），两条取 OR，都在 tier 门内；`_load_anchors` 加 `answers`
      键（不加仍是静默吞字段）；`_anchor_crosscheck` 的 `_hit` 改双路径。
    · 实测：三题真跑 triage **[1, 0, 0]** → 主判据达标；命中的是**语义轴**
      而非某串写死的字（P2a 那条侧面原文与本次措辞不同，仍被 a2 命中）。
    · ★ 顺带查清两件事：① `_overlap_coef` **是对称函数**（分母取 min，与方向
      无关）→ 任务书的「反向再查一次」与正向**等价**（冗余，留待下一版）；
      ② triage 只出**建议清单**、**没有任何写 `decidability_log` 的路径**
      （crosscheck 里 `apply_decidability_change` 只出现在注释里、`append` 0 次）
      → 「triage 引起的 und→partial」结构上恒为 0，P2.4.b 降为观察项是对的。
    · 附带把 `base` 加了 `answers_all_missing` 留痕键（answers 全缺时提示）。
  ⇒ **P2 重判为「通过（P2a + P2b 合并）」**，第一档解冻。`--phase p2` 的
    15/2 保留为 P2a 单档历史，不改写；该档输出里加了一行非判定性说明防误读。

  【第二档（前置：第一档通过）】
  P4 一致率 ON/OFF 对照（本档判据全绿；**结论「无结论」**）
    · 每臂 3 次、同题同配置（route 1 / rounds 1:4 / 默认 profile）。
    · ★ 任务书指定的口径（产物 md 的「三态多票：high/medium/low」行）在
      **OFF 臂不可用**：那一行读每条子问题的 `stability`，而 `stability`
      **只有多票路径才写** —— OFF 臂子问题里连键都没有，引擎照 `(0+0)/n`
      印出「一致率 0% ⚠️ unstable（＜50%）」。**那是「没算」，不是测量值。**
      照抄口径会得出「多票更好 +100%」这个建立在不存在读数上的结论。
    · 改用**两臂都可得**的口径 `tri_state = [agree, total]`：
      ON 80/80/80%（组内极差 0.0%）、OFF 50/80/60%（组内极差 30.0%）、
      组间差 +16.7% → 按 P4.4 自己的两向规则（组内极差 ≥ 组间差 → 无结论）
      ⇒ **无结论**。
    · P4.1 要的运行时开关在 v1.22.0 就已存在（`_action_on(config,
      "tri_multi_vote")` + `DEFAULT_CONFIG.actions.tri_multi_vote=True`）
      → 本档**未改引擎**，rc2 与 rc1b **逐字节相同**。
  P5 auto 取向回填（本档通过）
    · ★ 任务书前提不成立：`auto_plan` 的**单调用**分支（`run()` 走的就是它）
      原来不带 `orientation` → `_auto_plan_used` 永远拿不到取向、头部那行
      一行都印不出来。修法：在**同一次调用**的 prompt 里一并要取向
      （schema 加 `orientation` 段），三处 return 都带出，**成本不变**
      （冒烟用打桩断言 `len(calls) == 1` 钉住）。
    · 头部加「**取向判定（plan_orientation）**」+「⚠️ **取向错配**」告警
      （触发条件：声明 auto 且判定非 decision）。
    · 真跑：auto 判 boundary → 两行双双命中；显式 boundary → 无错配告警
      （负对照）。
    · ★ 顺带看到：**取向判定本身有噪声** —— 同题两次 auto 跑判出一 boundary
      一 decision。P5 的价值就是让它**可见**；要下「稳不稳」的结论需同条件
      ≥3 次重复（本档只跑 2 次，不下结论）。
  P6 tier 缺省时的显式提示（本档通过）
    · ★ 任务书骨架**恒不触发**：`sum(1 for a in out if "tier" in a and
      a["tier"] is not None)` 的 `out` 里每条都已被补过缺省 `tier`，两个
      条件恒真 → 计数恒等于总数 → 警告永不出现。正解是在**补默认值之前的
      原始条目**上数（`_n_explicit_tier`），并加冒烟断言钉住这一点。
    · 全缺省 → 头部「⚠️ **锚点 tier 警告**」（**不阻断**：tier 没写只等于
      「对照会空转」，把它升级成致命错误是没必要的失败）。
    · 真跑：全缺省快照有警告、有一条 `tier=1` 的无警告（负对照）；
      红线保留 —— 无 tier 的锚点仍**不进引用表**。
  ⇒ 第二档整体：P4 通过 / P5 通过 / P6 通过。

  【第三档（前置：第二档通过）】
  P7 明确不做（只出说明，不动代码）
    · 决策记录 `docs/不做什么-v1221.md`：不拆模块 / 不扩动词白名单·不放宽
      `min_actions` / 不删任何机制。三条都写了依据与前置条件。
    · **不进产物头部**（决策记录不是产物级告警）；冒烟带负对照钉住。

  【全局收尾】
  F.1 20 题全量回归（economy + 每层 2~3 圈；降档如实写在报告头与 index.json）；
  F.2 版本号 + 本 changelog（三档分段）；F.3 v1221_报告.md 十节；
  F.4 交付物清单核对。

  【新增符号 6 项，逐条登记在 _v122_ast_registry.json】
  `_norm_schema_actions` / `_extract_actions_lexical` / `_is_triage_candidate`
  / `_is_never_downgrade` / `_hit_by_answers` / `_hit_by_claim`
v1.22.0 ── 六阶段改造（目标分层 / 效果可测 / 外部可对账 / 机制精简）
  本版是 v1.21.77 的六阶段**加性**改造。红线守住：不删任何机制代码
  （纯删除行 0；AST 符号消失 0 项；新增 27 项逐条有解释，见
  _v122_ast_registry.json）。逐阶段报告见 v122_phase1~6_报告.md。

  一、Bench 骨架 + 目标函数分层（本版目标 1+5）
    · bench/questions 20 题 / bench/gold 3 题；
      bench_run / bench_score / bench_diff / bench_report / bench_calibrate
    · Phase.objective 四层：manifest / truth / collision / closure
    · coverage_of / coverage_parts 加 entry 形参：entry 不是 "1" 就返回
      None —— 修行层不再被覆盖率评价（那是用错的尺）
    · _classify_unsaid（real / lazy，View 与 dict 两形态都吃）
      + 修行层 stop_reason 追加「本轮显形 / 未生质量」
    · 产物头部四行「分层目标」（**计数**口径，objective 折进括号）
  二、三态多票 + 冻结 + 人工校准（本版目标 3）
    · _TRI_VOTE_PROMPTS 三票独立（严格 / 宽松 / 中立），多数票定标签
    · 无多数票 → partial + unstable + 进校准队列。不落 undecidable ——
      那会把分母砍一截，正是 v1.21.62 修过的形态
    · DecidabilityFreeze：签名覆盖 id / 当前标签 / 当前可答性 /
      冻结布尔 / 冻结标签五元组
      ★ 走过的弯路：早先签名里 is_answerable 是**由当前标签现推**的，
        于是「只翻 _frozen_answerable、不动标签」改不动签名。任务书
        Step 3.3 的冒烟标的正是这一刀；探针实测返回「未判红」，已修，
        并把这条收进冒烟当负对照。
    · bench_calibrate export / import（人在「人工 verdict」列填）
  三、decision 模式强制行动闭环（本版目标 4）
    · actions.landing_decision 开关；render_landing 退成分流壳，
      原实现整体改名 _render_landing_boundary（一行没删）
    · _render_landing_decision 六段模板；_extract_actions 六字段
      （verb / object / owner_role / deadline_hint / acceptance / fallback）
      + _extract_not_do
    · 硬约束：action_incomplete（行动 < 3 条）/ not_do_missing
    ★ 判据随实现更新：v64 A 那条「落地层顶部池级留痕」在新模板上丢了。
      修法不是把判据改宽，而是把那段抽成 _pool_meta_summary 给两个模板
      共用 —— 本项目头号复发问题就是「同一条逻辑两条通道各写一份」。
  四、外部锚点变真证据（本版目标 2）
    · as_evidence 五档（off / record / crosscheck / evidence / gate）
      + tier_floor / api_key_env / cache_ttl_hours / retriever；
      旧布尔写法仍被 _anchor_tier 认（True → evidence）
    · AnchorRetriever：snapshot 零调用；tavily 真检索 + 24h 落盘缓存
    · X# 进引用表加 tier 门（tier ≤ tier_floor 才收）
    · 冲突留痕：view.errors + pool.meta；gate 档进 blocked_conclusions
    · triage 降级清单（**只出建议，不自动改判定** —— 无证据的自动降档
      正是本版要避免的事）
    ★ 踩到的坑：往 DEFAULT_CONFIG["external_anchor"] 加 as_evidence 时，
      那个键**已经存在** —— dict 字面量后者胜，新值被静默丢掉，直到
      验收报「as_evidence=False ∈ 五档」才暴露。为此加了全文件 AST 判据
      「dict 字面量不许有重复常量键」（check_v122_dup_dict_keys）。
  五、机制审计（本版目标 6A，只标不删）
    · _audit_v122_dead_mechanisms.py → audit_v122_dead_mechanisms.md（13 项）
    · docs/机制审计-v122.md：## pending_fix **2 项**（v1.23.5：#1 归一化
      已收口并移入 ## resolved；与源码 `# [AUDIT-122]` 注释**两向对账**）
      + ## 双实现清单 + ## resolved
    · 产物头部渲染「机制审计：pending_fix N 项，双实现 M 项」
  六、双实现收口（本版目标 6B）
    · auto_plan 收口：唯一实现在模块级。给了 llm 走**单调用**路径
      （原 _auto_plan 的正文原样搬入并**内联**，不新增函数节点）；
      不给 llm 走 plan_orientation + plan_resources 两段（对外 API）。
      MetaDGTF._auto_plan 退成薄壳
    · _compute_rephrase_streak：串行 _run_layer 与并行 _b_check_stop
      各写一份的那行数合并为唯一实现（AST 定义数 = 1）
    ★ 行为对照：_probe_v122_phase6.py 的 before / after 快照里，
      A（方法入口）/ B（模块两调用入口）/ D（复述圈数结果）三格逐字相同；
      唯一差异是新增的 C 入口（auto_plan(..., llm=)）与 D 的实现标签。

  未采纳项（如实记，不假装做过）：
    · 拆模块（6C）只出方案不落地 —— docs/拆模块方案-v122.md
    · auto_plan 的**归一化规则**仍是两份（模式白名单 + 逐层钳位 +
      中位数补漏 + 低置信退 serial）：合并要贯通 plan_resources 的签名，
      列入 pending_fix #1
    · as_evidence 的布尔兼容路径保留一版 → pending_fix #3
    · 单票 _adjudicate_sub_tristate 整段保留作退路 → pending_fix #2

v1.21.77 ── 两处未完成项收口（M1 顺序修正 + 输入自检无条件渲染）

  【M1'】★ **v1.21.76 报告里「M1 没解决」要改判：不是层次问题，是顺序**
    现象：v1.21.76 把 `views[*].candidates` 加成 claims 第一来源后，
      真跑 B 模式仍「0 印证 / 0 冲突 / 12 无对应、anchor_used 0」，
      取到的 12 条全是研究层的操作性论断（「现金维持期是本轮唯一已显形的
      约束」），当时的结论是「换了层但还是不同层」。
    根因：`_anchor_claims` 的循环顺序写成 `（1,0,both,all）` ——
      **层 1 排最前**，12 条配额被它占满，层 0 的领域事实层论断一条都
      挤不进来。修行层的展开（attribute 0x1 = 阴展开，非判断）才是
      「关于世界的陈述」，与外部事实锚点同层。
    实测（同一份已跑完的 B 模式 packed、同一把对照尺、只换顺序）：
      旧 (1,0,both,all)：印证 0 / 冲突 0 / 无对应 12，用到锚点 **0**
      新 (0,1,both,all)：印证 **4** / 冲突 0 / 无对应 8，用到锚点 **3**
      4 条印证的 note 具体可核，例：a2 给出改造成本结构仅含设备、集成、
      调试培训，未含停产流失与人员安置，支持该说法。
    ★ 教训：**加了改动不等于修好了；把「没解决」当天条之前，先回头查
      自己那一版新加的代码有没有低级错**（这次是遍历顺序）。

  【S2】`input_sanity` 的产物出口从**条件渲染**改成**无条件三态**
    v1.21.75 曾登记「该字段没有渲染点」—— **那个判断不准确**：渲染点
    一直存在，只是写成「有问题才写」的条件渲染。检查跑了、没发现问题的
    产物里看不出它跑过，读的人分不清「检查了没问题」和「没检查」。
    改成：未启用 / 已检查未发现问题 / 发现问题（逐条列出）。

  验证：探针 `_probe_v77_claimorder.py`（同 packed 双臂对表，只换顺序）
    + 冒烟 `check_v77_*`（顺序 + 三态渲染，各带负对照）
    + 真跑 1 次 route=[0,1] 确认生产路径生效。

  刻意不做（与 v1.21.76 一致）：真联网 / 池判逐圈重跑 / confidence 数值 /
    不动 `_normalize_decidability` 等三处 / 不合并 auto_plan /
    不改 `per_round` 默认值。

v1.21.76 ── 独立复核（7 项）落地 + 上一轮两处未完成项

  ★ 来源：对 v1.21.75 的独立复核，逐条**先核对再改**（7 项：2 硬伤 +
    4 中等 + 1 组轻微）。**不改阈值/常量**，只修接线与出口。

  【A1】`_anchor_round` 只挂在 serial 通道（硬伤）
    改前实测：全源码 `self._anchor_round(` 只有 **1 处**调用点（在
    `_run_layer` 里），`_before_round` **0 处**；`_run_one_round_B`
    函数体含 `_print_polarity_snapshot` 但**不含** `_anchor_round`。
    后果链：B/C/D-H 七模式跑动 → 锚点从不入池 → `pooled` 恒 0 →
    收尾对照拿不到锚点 → 那条链上的所有锚点读数全是假的（不是
    「没效果」，是「没接上」）。
    做法：抽 `_before_round(entry, pool, layer_no)` 作**统一圈前入口**
    （极性快照 + 锚点入池），`_run_layer` 与 `_run_one_round_B` 都调它。
    做成一个方法而不是两处各写一份 —— 本项目「同一条逻辑两条通道
    各写一份」已发生过 7 次以上，这是第 8 次的防线。
    判据：`check_v76_anchor_two_channels`。

  【A2】`_anchor_calls` 从未被赋值（硬伤）
    改前实测：`_anchor_calls` 全源码出现 **2 次，都是读**
    （`_budget_exhausted` 的 `getattr` + packed 输出），**0 次写**。
    后果：v1.21.75 宣称的「检索调用纳预算」是**空转**——恒为 0 的项；
    同时 packed 里 `anchor_calls` 永远写 0，看起来像「没花过钱」。
    做法 3 条：① `__init__` 显式 `self._anchor_calls: int = 0`；
    ② `_budget_exhausted` 里**只算 `llm.total_calls`**（收尾对照不在
    圈循环内，不该混进这个守卫）；③ `_anchor_crosscheck` 里做**独立
    预算判断**（用尽则跳过并留痕），并在真正发起调用前自增。
    判据：`check_v76_anchor_calls`。

  【B1】changelog 措辞与实现不符：原来写「重做锚点接入（接入点从外判
    改到池）」，但外判接入点**还在**（`_assess_decidability` 仍收
    anchors）—— 实际是**新增**池接入点。已改措辞。
  【B2】`per_round` 分圈投放与「池判只跑一次」的关系没写清：池判在
    评估阶段只跑一次、只读**第 1 圈**的池，后面几圈继续入池它看不到。
    写进 `_anchor_view_ctx` docstring。
  【B3】`Pool.anchor_as_evidence` 只有内部赋值、**无任何出口** ——
    产物里看不出锚点有没有被授权当证据。已在 `to_dict` 里跟着
    `anchors` 一起挂（仍是加性）。
  【B4】`_retrieve_anchors` 的返回值是**死参数**（调了不接）。现在只有
    真检索后端才走那一层，snapshot 直接跳过（接口位保留）。
  【B5】分诊判据原先在 **system** 段，靠 user 段的「按上面的判据处理」
    跨段引用。已整段挪进 `_anchor_view_ctx`（user 段），
    `_anchor_triage_sys` 退化成空壳（保留，仅供外部脚本调用）。

  【M1】上一轮未完成项：`_anchor_claims` 的**取值处**
    三轮（v73/v74/v75）× 6 道题实测：32 条 claims 全部判「无对应」、
    `anchor_used` 全 0。根因不是锚点没用 —— 是抽取器只取「成品答案 +
    已答子问题」，两处都是**认识论层**；引擎的领域论断在
    `views[*].candidates`。同一份已跑完的 packed、同一份锚点、同一把尺，
    只换取值处：沾边 0/5 → **7/12**、用到锚点 0 → **9/12**。
    今起 candidates 作为**第一来源**（领域层优先占满 12 条配额）。
    ★ 这是 M1 口径变更，会改变对照结果，按预注册纪律单独记录。
  【S1】上一轮未完成项：输入自检补「形似标准记号的非标准记号」判据。
    负对照实测（v1.21.75）：`P=PN` 被判成「P与PN均为标准术语」放行。
    —— 而 `_check_input_sanity` 正是为 `P=PN` 那次事故才建的。
    它防住了别的笔误，唯独没防住让它诞生的案例。

  刻意不做（6 条）：不加真联网 / 不让池判逐圈重跑 / 不加 confidence
    数值 / 不动 `_normalize_decidability` 等三处 / 不合并 `auto_plan`
    双实现 / 不动 `per_round` 默认值。

  验证：前置量化探针 `_probe_v75_anchor.py`（P1..P6 对表）+ 冒烟 7 条
    `check_v76_*`（各带负对照）+ 判别力验证（SRC 指回 v1.21.75 时
    `check_v76_changelog_wording` 必须判红）+ 真跑 1 次 B 模式。
    ★ **未跑 serial 对照** —— A1 修的是「B 也能跑」，serial 那条改前
    就通，再跑一次买不到新信息。如实记录，不假装做过。

v1.21.75 ── 按外部评审方案**新增池接入点**（原有的外判接入点保留、但不再是主接入点）

  ★ 前提：v1.21.73/74 把锚点塞进了 `_assess_decidability`（外判，
    题面级）。评审明确列为「不要碰」——外判是另一个 LLM 看问题，锚点是
    外部事实，两回事。两次真跑 claims 全判「无对应」印证了这个判断。

  1. `Pool.anchors` —— 锚点成为**池对象**。原来只在 MetaDGTF 上挂一份，
     池里看不见，候选/对偶/ing 全读不到，evidence 也引不了。
  2. `_citation_table` 打通 `X#` 编号，锚点可被证据引用。
     ★ 评审把这步写成「纯加性」，**它不是**：进了引用表就自动获得支撑
       →decidable 的资格（`apply_decidability_change` 只拦「全是 d_ 开头」一种情况）。所以默认关（`as_evidence=False`），先量后改。
     编号用 `X1..Xn` 而非评审建议的 `X_001`：现有风格是 P#/A#/T#/S#/C#，
     `X_001` 的下划线会和债务编号 `d_00X` 混。
  3. 圈循环里触发检索并入池（`MetaDGTF._run_layer`，`DGTF` 保持纯生成器）。
     ★ `retriever` 目前**只有 `snapshot` 一个真实现**（零额外调用）；
     其它取值抛错留痕，**不静默降级** —— 引擎没有联网能力，假装搜过
     比承认没搜更糟。分圈投放 `per_round` 条模拟逐步检索。元层不检索。
     ★ **这句当时是错的**：`_run_layer` 只是 serial 通道，B/C/D-H 七模式
     走别的入口，压根没接上 —— 已在 v1.21.76 A1 修（抽 `_before_round`）。
     另：`per_round` 分圈投放与「池判只跑一次」并不矛盾，但池判只看得见
     **第 1 圈**那批（受 `max_items` 约束），v1.21.76 B2 已写进 docstring。
  4. 锚点摊进 `_assess_decidability_from_pool_view`（池判）+ 分诊判据。
     分诊（`triage`）**默认关**，评审自己要求「先量后改」。
  5. 检索调用纳预算 —— v1.21.73/74 的收尾对照发生在打包阶段，压根不在
     圈循环内，守卫看不见（评审点名的坑，实测确认漏算）。
     ★ **这条当时没实现**：它在 `_budget_exhausted` 里加了个 `+ _anchor_calls`，
     而那个字段从头到尾没被赋过值（实测 2 处读、0 处写）—— 恒为 0 的项。
     已在 v1.21.76 A2 重做（初始化 + 从守卫移除 + 收尾对照独立判断并自增）。

  不改：`_normalize_decidability` / `_untraced_undecidable` /
      `_check_input_sanity`（评审列为「不要碰」，实测均未动）。
  不加：`confidence: 0.0-1.0`。给了数字下游就会当可计算量用，实际那是
      主观标注；保留 `kind` 文字性质标注（行业媒体转述/企业自述/设备商
      口径），判读时按来源打折这件事不会因为写了个 0.7 就变客观。

  验证：关闭态 packed 键集合 / prompt / 产物文案与 v1.21.74 **逐字相同**
     （加性成立）；开启态 `pooled` 无条件写入。
     ★ 「`anchor_calls` 计入预算」在 v1.21.75 是**名义上的**（该字段无写入），
     实际生效在 v1.21.76 A2。

  v1.21.74 是本轮「让外部锚点可被审计」版。只改一处：`_merge_decidability`
  原先 `merged = dict(pool_res)` 只继承池判，`_assess_decidability` 算好的
  `anchor_refs` / `_anchors_given` 在合并时被丢掉 —— 因此 v1.21.73 的 ON 臂
  产物里 `anchor_refs` 是 None，**看不出外判到底有没有引用外部事实**。
  探针 `_probe_v73_refs.py` 实测（同一题、同一份锚点、直接调 assess）：
    带锚点   anchor_refs = [a1,a2,a3,a5,a6,a7,a8,a9]（8/12）_anchors_given=12
    不带锚点 anchor_refs = []                        _anchors_given=0
  即引用是真的算出来了、真的被合并丢掉了。本版在合并时把它带上，
  ★ 只在「确实给了锚点」时挂键（refs 非空或 _anchors_given 非 0）——
    锚点关闭时两条都空、一个键都不加，packed 键集合与 v1.21.72 逐字相同。
  未采纳：给对照条目加「来源标签」（view / pool）用于自动诊断层次错配。
    理由：本轮靠读 claims 原文 30 秒就定位了错配，收益不足以抵消它带来的
    冒烟耦合面（`_anchor_claims` 返回值形状变更，冒烟里 3 处直接调用）。
  v1.21.73 是本轮「接外部锚点」版。v1.21.63 起产物头部那句
  「外部锚点：无」是**写死的承认**，不是开关 —— 探针
  `_probe_v73_anchor.py` [1][3][4] 实测：全文 `external_anchor` /
  `web_search` / `external_facts` 引用数**均为 0**，`_assess_decidability`
  只收题面（system 788 字符、无「锚点」二字）。也就是说所谓「外判」一直
  是模型的第二意见，没有外部事实源。本版把它做成**真能接的通道**。

  ────────────────────────────────────────────────────────────
  外部锚点（external_anchor）
  ────────────────────────────────────────────────────────────

  **根因**：螺旋跑 N 层到底是「逼近真理」还是「绕圈」，没有外部参照无从
  判断。v1.21.63 的选择是让产物自己承认没有 —— 承认不等于可测。

  **做法（三处）**
  1. 配置 `external_anchor.{enabled, path, max_items, crosscheck}`，
     默认 **enabled=False**。★ 关闭时 packed 键集合、assess 的 prompt、
     产物文案与 v1.21.72 **逐字相同**（加性；冒烟 `check_v73_anchor`
     有专门的反证）。
  2. `_load_anchors()`：读快照 JSON，逐条校验（缺 claim 的丢弃），截断到
     `max_items`。失败**一律留痕**写进 `external_anchor.error`，不静默
     降级成「没接入」——那正是本项目反复踩的坑。
  3. 两处消费：
     · `DGTF._assess_decidability(question, anchors)`：锚点作为**可引用的
       外部事实**附在 prompt 后，要求把用到的编号填 `anchor_refs`；
       anchors 为空时 `system` **一字不改**（拼接空串）。
     · `_anchor_crosscheck()`：收尾**只读**对照 —— 本次结论条目 vs 锚点，
       逐条标 印证 / 冲突 / 无对应，计数进产物。

  **★ 红线不动**：锚点**不进池、不参与对撞与清算、不改任何 view**。
  它是校验标尺，不是题面输入（「输入是形状不是数据」这条不变）。
  因此它的价值是**测出结论与外部事实差多少**，不是让结论更正确。

  **为什么是读文件，不是引擎自己联网**：引擎没有联网能力（v9.1 的
  `web_search` 在 v1.21 重写后 0 处引用，v1.21.61 已核过）。与其假装
  联网，不如把外部事实**显式落盘**再读 —— 每条锚点带来源、URL 与检索
  时刻，可复现、可核对、可事后逐条复查。

  **验证**：冒烟 `check_v73_anchor`（关时逐字同构 + 开时挂键 + 失败留痕 +
  三条负对照）+ 探针 before/after + 真跑 OFF/ON 对照（见 v73_报告.md）。

  v1.21.72 是本轮文档与可观测性版：补 #13 的代码注释、changelog 去重 +
  版本段序重排（#20）、加「机制→唯一实现点」与「长度异常」两条形态冒烟
  （#22 / #24 的**窄版**）；**引擎可执行语义逐节点未变**。

  ════════════════════════════════════════════════════════════
v1.21.72 相对 v1.21.71 的改动（文档整理批 + 可观测性/形态断言窄版）
════════════════════════════════════════════════════════════

  来源：v1.21.71 交付报告的「遗留」段 + 外部清单「刻意不做」里**本批可以
  安全收口**的四项。★ 引擎可执行语义**逐节点未变**（AST 等价，见下
  「验证」），所以本版**不产生新的真跑数据**，也不改任何判据 / 阈值。

  ────────────────────────────────────────────────────────────
  [A] #13 · B 模式预算耗尽「停所有层」的语义写进代码
  ────────────────────────────────────────────────────────────

  **为什么本轮必须做**：外部清单 #13 把它列成「疑似 bug」，任务书给的
  处置是「**本轮只写注释说清，不改代码**」—— v1.21.71 只在报告里写了
  理由，**漏了代码侧那条注释**。本版补上。
  **做法**：在 `_run_parallel_B` 的预算停机分支加注释：同时停掉所有层是
  **barrier 制**的必然（每一波所有层一起跑，预算耗尽 = 这一波谁也跑不
  起来），与 serial / C / D-H 的「本层截断」（只置自己的 `stopped`）是
  **两种都合法**的语义，不要互相「对齐」。
  **行为零改动**：注释不进 AST。
  **判据**：`check_v72_bbarrier_semantics` 两个方向都锁 ——
    · `max_calls=30` 的 mock B 跑 → **四层全部**带「预算用尽」；
    · 不限预算 → **0 层**带（守卫不误触发）。
    ★ 同时是回归锁：若有人把「一起停」改成「只停一层」，`1..n-1` 的
      形态会立刻被抓住。

  ────────────────────────────────────────────────────────────
  [B] #20 · changelog 去重 + 版本段序重排（纯文档）
  ────────────────────────────────────────────────────────────

  **改前实测**（`_probe_v72.py` [C]）：`★ v1.21.63 收束摘要` **出现 2 次**
  （doc 行 1454 / 1491，两段**逐字相同** —— 复制粘贴事故；6/8/12 行窗口
  的重复块扫描都只命中这一处，全库无第二处重复）；版本段序**不单调**
  （…70, **68, 69**, 67…）。
  **做法**：删掉第二次出现的整段；v1.21.68 与 v1.21.69 两段**互换**，
  使段序按版本号严格递减；前言补 v1.21.71 / v1.21.72 两行（前言本来按
  版本累积，v1.21.71 那行也漏了）。
  **判据**：`check_v72_changelog_hygiene` —— ① 任一「★ vX 收束摘要」
  标题不得出现 2 次以上；② `^v1.21.NN 相对` 的版本号必须**严格递减**。
  ★ 把「改前实测」的两种瑕疵变成**常驻断言**，以后再犯当场红；
    把 SRC 指回 v1.21.71 时这条必须判红（那是它的判别力来源）。

  ────────────────────────────────────────────────────────────
  [C] #22（窄版）· 「机制 → 唯一实现点」形态断言
  ────────────────────────────────────────────────────────────

  **不做什么**：任务书把全局调用图框架留给架构批，本版**不建框架**。
  **做什么**：只钉本项目反复栽过的那几个机制，在**抠掉 docstring 的源码**
  上断言：
    · `_normalize_decidability` / `_untraced_undecidable` / `_stop_reasons`
      / `_finalize_layer_common` / `_cached_ext_assess` / `_dispatch_for_pack`
      / `_layer_guard` / `_quality_check` / `_merge_decidability` /
      `_assess_decidability_dynamic` 的 `def` **各只有 1 处**；
    · `_assess_decidability(` 的**调用点恰好 1 处**（= F6 的唯一入口：
      任何「再补一个直调」的改动会立刻红）；
    · `_finalize_layer_common` / `_stop_reasons` 各 **2 个调用点、1 份
      实现**（两通道共用同一份 —— 正是 v1.21.71 F1 的教训）；
    · v1.21.71 删掉的两处旧门**不得复活**（`rounds_n > 1` 的收尾门、
      `total_rounds <= 1` 的早返回）。
  ★ 量的时候必须**先抠 docstring**：changelog 里也写着这些函数名与旧写法。
    第一版在全文上数，`old_finalize_gate_serial` 数出 1（代码里其实是 0）。

  ────────────────────────────────────────────────────────────
  [D] #24（窄版）· 长度异常自动冒烟警告
  ────────────────────────────────────────────────────────────

  **不做什么**：不改 `dump_view_fields` 的 `_OVERSIZED` 机制（v1.21.70 [H]
  有意只钉字段名、不维护「该打什么」的清单，理由成立）。
  **做什么**：把「**超长字段如果不在 `_OVERSIZED` 里就会被整段打进日志**」
  这个失效模式变成常驻告警：
    · 统计走**产物格式**（`View.to_dict()` 的字符串字段长度），阈值 2000 字，
      基线异常数上限 0（v1.21.72 实测：mock 跑 8 个字符串字段全 < 2000）；
    · **负对照**：造一个 `collision` = 8000 字的 view 喂生产入口
      `dump_view_fields` → ① 输出里**有正文**（失效模式真实存在）、
      ② 同一个统计函数必须把它**检出为异常**（判据不是死的）；
    · 反向锁：同长度的 `manifest`（在 `_OVERSIZED` 里）只打长度、无正文。
  ★ 这条的判据形态**必须带负对照**：基线是 0，不喂合成 view 的话这条
    断言永远通过、等于没写。

  ────────────────────────────────────────────────────────────
  刻意不做（本版仍在范围外）
  ────────────────────────────────────────────────────────────

  · **#21 拆文件**：与项目**形态**冲突 —— 单文件 `元DGTF-V1.21.xx.py` 是
    所有探针 / `_run_verif.py` / `smoke_test.py` / `_convergence_matrix.py`
    的加载契约。**不拆，理由是形态本身**，不是工作量。
  · **#23 零触发机制阈值复查**：需要**新数据**（同条件 ≥N 题）才有判别力；
    本轮两次真跑是「四层各 1 圈」的短跑，对「零触发」没有证据力。
    在拿到交叉验证之前**不动任何阈值**（纪律第 5 条）。
  · **F8 方案 B（两份调度实现合一）**：任务书写的是「选其一，不要两件都
    做」，v1.21.71 选了方案 A。它不是「未完成」，是**平行方案**；真要换，
    需要贯通 `plan_orientation` / `plan_resources` 的 `llm` 参数并重测
    自动调度的 route 选择语义 —— 属架构批。
  · **F11 的「按内容去重」替代方案**：同样不是缺口，且会重新引入收尾
    站点的写入（与 F1 的耦合要重算），留待可观测性批。

  ────────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────────

  **零语义改动的机器证明**（本版最重的一条）：两版源码把**模块 docstring
  归一化**后 `ast.dump(ast.parse(...))` **逐节点完全相同**（节点数
  1735681）⇒ 本版对引擎的全部影响 = docstring 文本 + 一条 `#` 注释。
  **也正因为如此，本版不做真跑验收**：判据是「这条通道会不会经过我改的
  那行代码」，答案是**没有任何一行**；再跑一次只会得到同一份代码的另一
  次采样。这不是省事 —— 替代证据是 AST 等价 + 全套冒烟 + 4 条新判据。
  **冒烟**：exit 0 / **0 个 ✗**；新增 4 条 `check_v72_*`（每条带负对照或
  反方向），11 条 `check_v71_*` 继续全 ✓。

  ════════════════════════════════════════════════════════════
v1.21.71 相对 v1.21.70 的改动（F1~F11 十一项缺陷修复）
════════════════════════════════════════════════════════════

  来源：外部代码检查报告（24 项）+ 修复任务书（F1~F11 十一项）。
  ★ 逐条**复核前提**之后才动手 —— 复核结论写进每条的「根因」里，
    其中一条（外部清单说 `_build_inp_duel` 也有 KeyError 风险）经实测
    **不成立**，登记在 F3 的注里，不作改动。

  ────────────────────────────────────────────────────────────
  P0
  ────────────────────────────────────────────────────────────

  **F1 · 单圈层跳过全部收尾逻辑**
  **位置**：`_run_layer` 收尾调用点；`_b_finalize_layer` 的守卫。
  **根因**：两处各有一道 `> 1` 门（serial 是 `rounds_n > 1`，B/C/D-H 是
  `state["total_rounds"] <= 1`），`rounds = 1` 的层于是拿到一个**没有
  roles_run / rounds_cap / round_log / stop_reason** 的 view，
  合并后二次去重与质量检查也全不执行。改前实测（`_probe_v71.py` [A]，
  四层各请求 1 圈）：0/1/both 三层这四个字段**全为 0 / 空**。
  更难看的是 entry == "all"：`_total_rounds = rounds_n + all_extra_rounds`
  实际跑了 2 圈，收尾照样被跳过 —— 「跑了两圈却不留收尾」。
  **做法**：serial 侧 `if view is not None and rounds_n > 1:` →
  `if view is not None:`；B/C/D-H 侧删掉 `total_rounds <= 1` 早返回。
  两处即本项目「同一条逻辑两条通道各写一份」的第 7 次，这次两处一起改。
  **连带**：`_finalize_layer_common` 的 docstring 里「调用方只在
  rounds_n > 1 时才进入」这句已经不成立，同步改掉（self 记忆仍然**不**
  放进去，双写风险不变）。

  **F2 · main() 里 save_result 没有兜底**
  **位置**：`main()` 末尾。
  **根因**：`_interactive_run` 早就有 `try/except`（打印「保存失败」继续），
  而 `main()` 直接裸调。改前实测（`_probe_v71.py` [B]，把 save_result
  打桩成抛 OSError）：异常**冲出 main()**，终端没有任何「保存失败」字样，
  整轮结果丢掉。
  **做法**：包 try/except，失败打印原因 + `sys.exit(1)`；成功路径不变
  （probe [B] 两个方向都测了）。

  ────────────────────────────────────────────────────────────
  P1
  ────────────────────────────────────────────────────────────

  **F3 · `_build_inp_meta` 的 KeyError 隐患**
  **位置**：`_build_inp_meta` 的 `upstream_pools=[self.pools[getattr(v,
  "entry", "0")] for v in up]`。
  **根因**：上游 view 的 entry 若不是四层之一（例如 "9"），配对取池会
  **KeyError 打崩元层**。改前实测（`_probe_v71.py` [C]）：`KeyError: '9'`。
  **做法**：配对过滤 —— entry 不在 `self.pools` 里的上游 view **与其池
  一起剔除**，并留痕两处以上（`logger.warning` + 实例字段
  `_build_inp_dropped` + verbose 终端）。★ 不静默换成默认池：换池等于让
  元层读错形状还不自知。
  **注**：外部清单说 `_build_inp_duel`「同样处理」—— **实测不成立**，
  那里 `upstream_pools` 是固定的 `[self.pools["0"], self.pools["1"]]`，
  没有这个风险，本版不动它。

  **F4 · `load_config("")` 误报解析失败**
  **位置**：`load_config` 的入口守卫。
  **根因**：`Path("")` 就是当前目录、`.exists()` 为真 → 继续走
  `open("")` → FileNotFoundError → 打出一条**误导性**的
  「读取  失败」（路径是空的，用户根本没给配置）。改前实测
  （`_probe_v71.py` [D] empty_path）：`警告=True`。
  **做法**：`if not path or not (HAS_YAML and Path(path).exists()):`。
  负对照：真正坏的 yaml 仍必须报「配置文件解析失败」（probe [D] bad_yaml
  改后仍为 True）；不存在的路径本来就不该报（外部清单说「不存在.yaml
  应打印警告」，**实测那是错的** —— 现在也是静默回落，本版不改这个语义）。

  **F5 · C / D-H 早退时 dispatch 为空**
  **位置**：`_run_parallel_C` 与 `_run_parallel_stage` 的 `if not active`。
  **根因**：这两条早退路径 `return self._pack_result(...)`，而
  `_pack_result` 里 dispatch 是**空 dict** —— `_layer_guard` 读
  `skipped` / `missing` 全读不到，守卫等于短路。改前实测
  （`_probe_v71.py` [E]）：两条路径的 dispatch 键集都是 `[]`。
  **做法**：早退也补 `_dispatch_for_pack(mode, {...})`，模式名**取实际
  变量**（C 处 "C"，D-H 处用 `mode`），不硬编码。

  **F6 · 单次运行跑两次外部可判定性评估**
  **位置**：`_route_by_decidability`（开跑前定 route）与
  `_assess_decidability_dynamic`（研究层拆解时读池）。
  **根因**：两处各自 `d._assess_decidability(question)`，一次 run 会打
  **两次**外部评估，白花 token。改前实测（`_probe_v71.py` [F]，站点计数）：
    外部评估调用次数 = 2  （route_by_decidability=1 / assess_dynamic=1）
  **做法**：加运行内缓存 `_ext_assess_cache`（`__init__` 建、`run()` 开头
  重置 —— 重置必须放在 `_route_by_decidability` **之前**，否则会把刚刚
  填进去的那条抹掉）+ 薄壳 `_cached_ext_assess`；两处调用点都改走它。
  **边界**：失败不缓存（异常照旧上抛给调用点的既有 except）；跨运行、
  跨配置不复用（每 run 重置）。

  **F7 · J 修承诺的「完整 evidence」没兑现**
  **位置**：`_assess_decidability_from_pool_view` 的返回值 /
  `_merge_decidability` 的兜底重算分支。
  **根因**：v1.21.70 [J] 在 changelog 里写明「缓存值用完整 evidence 算，
  重算路径读的是 `evidence[:8]`，两者会不一致」—— **只写了没改**，
  承诺与实现不符。改前实测（`_probe_v71.py` [G]，故意造 9 条 evidence、
  追溯落在第 9 条）：缓存路 `_und_untraced = []`，兜底路
  `= ['清分规则未定，断面客流与线路客流不可互证']`，两路口径不一致。
  **做法**：池评估返回值新增**加性**键 `_evidence_full`（不动 `evidence`
  本身），兜底分支优先用它；`_merge_decidability` 的注释同步说明。

  ────────────────────────────────────────────────────────────
  P2
  ────────────────────────────────────────────────────────────

  **F8 · 模块级 `auto_plan` 与方法级 `_auto_plan` 双实现**
  **位置**：`MetaDGTF._auto_plan` 与模块级 `auto_plan`（= `plan_orientation`
  + `plan_resources`）。
  **根因**：两份实现各写一份「模式白名单归一 + 逐层圈数钳到
  `[_layer_floor, _layer_ceil]` + 漏层按中位数补 + 低置信退 serial」，
  长期并行必然漂移；模块级那份在文件里没有任何内部调用点。
  **做法**（选**方案 A**，保守）：两份都留，`_auto_plan` 的 docstring 显式
  标注关系与共同遵守的规则，并加一条一致性冒烟
  （`check_v71_auto_plan_agreement`）：同一 mock 输入下两实现的
  `mode` 与（按 route 裁剪后的）`rounds` 必须逐字相同；负对照用子类把
  方法级那份的圈数改坏，断言**必须**判不一致。
  **未采纳**：方案 B（统一成唯一实现、`_auto_plan` 退成薄壳）改动面涉
  `plan_orientation` / `plan_resources` 的 `llm` 参数贯通，属架构批，
  本轮不做 —— 但**漂移检测器已经就位**。

  **F9 · `_STOPWORDS` 是一组字符不是词**
  **位置**：`_STOPWORDS` 定义 + `_tokenize` 的
  `len(t) >= 2 and t not in _STOPWORDS`。
  **根因**：原集合是**单字**集合，而 `len(t) >= 2` 已经把单字滤掉了 ——
  这份集合在分词结果里几乎不起作用；真正的多字停用词（的话 / 一种 /
  进行）一个都挡不住。改前实测（`_probe_v71.py` [H]）：
  `stopwords_is_chars=True`，分词结果里 `的话/我们/通过/一种/进行` 全在。
  **做法**：拆成 `_STOPCHARS`（原单字集合，保留、不再被引用——加性不动旧行）
  + `_STOPWORDS`（**按词**匹配的多字集合，取任务书给定的 21 个词）。
  `_tokenize` 一个字都不用改，它读的就是 `_STOPWORDS`。
  ★ 这是**运行期可见变化**：key_terms / 相似度会跟着变（内容词不受影响：
  螺旋 / 结构 / 整理 实测仍在）。

  **F10 · `coverage_parts(pool, {})` 的隐式假设**
  **位置**：`_refresh_settlement`。
  **根因**：签名要求一个 dict 而函数当前不读它；传 `{}` 等于隐式假设
  「这个函数永远不看 cfg」。将来给它加 cfg 相关分支，这里会静默走默认值。
  **做法**：签名改 `cfg: Optional[dict] = None`（docstring 说明）；调用点
  改传 `self.config`。改前实测（probe [I]）：`coverage_parts(pool)` 直接
  `TypeError: missing 1 required positional argument`。

  ────────────────────────────────────────────────────────────
  P3
  ────────────────────────────────────────────────────────────

  **F11 · 收尾二次 `_quality_check` 多写一份 position 诊断**
  **位置**：`_finalize_layer_common` 的收尾质量检查。
  **根因**：`_quality_check` 在 `position_all_same` 时会调
  `_dump_position_diagnostic` **写文件**；收尾（合并后重跑一次）会再写
  一份同名不同时间戳的 `outputs/diagnostic_position_*.log`。
  改前实测（`_probe_v71.py` [J]，一次 serial 四层跑）：
    dump 尝试次数 in_round=0 / in_finalize=4；13 次 `_quality_check`
    调用里 0 次带 write_diag=False。
  **做法**：`_quality_check` 加关键字参数 `write_diag: bool = True`
  （圈内调用**保持默认 True**，行为不变）；收尾调用传 `False`，
  且不静默 —— 压制时打一条 `logger.info` 说明「本该写、因收尾复核没写」。
  ★ 观测到的**副作用**必须记下来：在 mock 这一跑里 dump **全部**来自
  收尾站点（圈内的候选 position 是交错的，本来就不触发 all_same），
  所以改后该跑不再产出诊断文件。这是「不再重复」与「保住唯一那份」之间
  的取舍：真正的诊断对象是**圈内那一份**，收尾复核只是拿合并后的候选
  再看一眼。若日后要两个都留，正确做法是按内容去重而不是按站点关一张，
  归到可观测性批。

  ────────────────────────────────────────────────────────────
  刻意不做（本轮明确不碰）
  ────────────────────────────────────────────────────────────

  · #20 changelog 重复 / v1.21.68 与 v1.21.69 段序颠倒 —— 纯文档性，
    一次性脚本去重 + 重排，留待文档整理批。
  · #21 拆文件（17k 行 → 多模块）—— 结构性重构，涉全部 import / 循环
    依赖 / 打包 / 测试基线，单独立项。
  · #22 「同一逻辑两条通道各写一份」的全局调用图 —— 需要专门设计
    「机制 → 唯一实现点」的断言框架，留待 v1.22 架构批。本轮只在 F1 / F6
    的具体点上各配负对照。
  · #23 「零触发机制」的阈值复查（如 `escalate_starve_rounds`）——
    v1.21.65 已裁决「保留、题不匹配」，需后续交叉验证；本轮**不改任何
    阈值 / 常量**。
  · #24 `_OVERSIZED` 硬编码字段名清单 —— v1.21.70 [H] 有意只钉字段名、
    不维护清单（新增字段不误伤），理由仍成立。留待可观测性批。
  · #13 B 模式预算耗尽「停所有层」—— B 是 barrier 制，每波所有层一起跑，
    预算耗尽时一起停是**合理的**；与串行/C 的「本层截断」是刻意的语义
    差异，不是 bug。本版只在报告里写明，不改代码。

  ────────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────────

  **前置量化**：`_probe_v71.py`（接受目标 py 作参数，走生产入口：
  `MetaDGTF.run` / `_b_finalize_layer` / `DGTF._quality_check` /
  `load_config` / `main()`），改前 / 改后各跑一次对表
  （`_probe_v71_before.txt` / `_probe_v71_after.txt`）。判据：
    · [A] 四层各 1 圈：roles_run / rounds_cap / round_log 从 0/0/0 变成
      非零；`_b_finalize_layer(total_rounds=1)` 同样；
    · [B] 保存失败：从「异常冲出 main()」变成「SystemExit(1) + 打印」；
    · [C] 非法 entry：从 `KeyError: '9'` 变成被剔除 + 留痕；
    · [D] `load_config("")`：警告从 True 变 False，坏 yaml 仍 True；
    · [E] 空 active：dispatch 键集从 `[]` 变成含 ran/missing/failed/skipped；
    · [F] 外部评估次数从 2 变 1；
    · [G] 缓存 / 兜底两路口径从不一致变一致；
    · [H] 多字停用词从全在变被挡，内容词仍在；
    · [I] `coverage_parts(pool)` 从 TypeError 变可用；
    · [J] `in_finalize` 的 dump 尝试次数从 4 变 0；
    · [K] 两实现一致（负对照必须判不一致）。

  **冒烟**：`SRC` → v1.21.71；新增 11 条 `check_v71_*`，每条带**负对照**
  与接线断言（`inspect.getsource`）。判据：exit 0 / 0 个 ✗。

  **真跑验收**（结果见下面的收束摘要）：同题（老城区内涝）跑两次，
  都是 `--route 0,1,both,all --rounds "0:1,1:1,both:1,all:1"`：
    · V71S（serial）10.3min / 49 calls；
    · V71B（B 模式）7.3min / 52 calls。
  两跑都满足 F1 的判据：日志 **4 段**「收尾留痕」（圈数 1/1/1/2、
  角色记录齐）、**4 条** ⏹ 停止交代；产物 md **4 处**`**螺旋停止**`、
  **4 处**`**实际走了`、**4 张** round_log 表，头部调度
  `修行(1圈) → 研究(1圈) → 对撞(1圈) → 元(2圈)`。
  ★ **没有**跑「默认四层 2 圈」的真跑 —— 那条路径被改动的只是**条件
    变宽**（`rounds_n > 1` → 恒真），`rounds_n > 1` 时的行为逐字未变；
    它由冒烟矩阵（各模式 2 圈全跑通）+ 离线 2 圈复核（4 段收尾留痕、
    圈数 2/2/2/3）覆盖，花钱再跑一次买不到新信息。

  ────────────────────────────────────────────────────────────
  ★ v1.21.71 收束摘要
  ────────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.71.py（纯 CRLF，18524 → 行数见下）；
    smoke_test.py 加 **11 条** `check_v71_*`（每条带负对照 / 反方向）；
    `_probe_v71.py`（F1~F11 改前 / 改后同一支探针）；
    `_probe_v71_render.py`（F1 的**出口** E2E：日志 + 产物两侧）；
    `_mk_v71_patch.py` / `_mk_v71_smoke_patch.py`（27 + 3 处替换，
    每处断言命中恰好 1 次）；`v71_报告.md`；真跑 sidecar
    （`verif_V71S.*` / `verif_V71B.*`）。

  **改了 11 处代码**（F1~F11），**没动任何阈值 / 常量**：
    · F1 两处 `> 1` 门（serial + B/C/D-H）去掉；
    · F2 `main()` 的 save_result 包 try/except + `sys.exit(1)`；
    · F3 `_build_inp_meta` 上游 view 与池**配对过滤** + 三处留痕；
    · F4 `load_config` 加 `not path` 短路；
    · F5 两处早退补 `_dispatch_for_pack`（模式名取实际变量）；
    · F6 加运行内缓存 `_ext_assess_cache` + 薄壳 `_cached_ext_assess`，
      两处调用点改走它，`run()` 开头重置；
    · F7 池评估加性带出 `_evidence_full`，兜底重算改用它；
    · F8 只加**漂移检测器**（docstring 标注 + 一致性冒烟），不合并实现；
    · F9 `_STOPWORDS` 拆成 `_STOPCHARS`（保留）+ 21 个多字停用词；
    · F10 `coverage_parts` 的 `cfg` 改可选，调用点传真配置；
    · F11 `_quality_check` 加 `write_diag` 开关，收尾复核传 False
      （压制时打 `logger.info`，不静默）。

  **改前 / 改后量化对照**（`_probe_v71_before.txt` / `_after.txt`）：
    · [A] 四层各 1 圈：0/1/both 三层 roles_run·rounds_cap·round_log
      从 0/0/0 → 1/1/1；`_b_finalize_layer(total_rounds=1)` 从空 → 有；
    · [B] 保存失败：从「异常冲出 main()」→ 「SystemExit(1) + 打印」；
    · [C] 非法 entry：`KeyError: '9'` → 剔除 + 留痕；
    · [D] `load_config("")`：警告 True → False，坏 yaml 仍 True；
    · [E] 空 active：dispatch 键集 `[]` → 8 键（含四个守卫键、模式名 C/G）；
    · [F] 一次 run 的外部评估：**2 → 1**（站点计数 1+1 → 1+0）；
    · [G] 缓存 / 兜底 `_und_untraced`：不一致 → 一致；
    · [H] `_tokenize`：12 → 7 个词，多字停用词被挡、内容词保留；
    · [I] `coverage_parts(pool)`：TypeError → 可用（cfg 默认 None）；
    · [J] 收尾站点的 dump 尝试：4 → 0（圈内站点仍写，反向锁成立）；
    · [K] 两实现三组输入逐字一致；把一份改坏立刻判不一致。

  **出口 E2E**（`_probe_v71_render.py`，四层各 1 圈，离线）：
    · v1.21.70：serial「收尾留痕 0 段 / md 螺旋停止 1 处 / round_log 表 0 张」，
      B「1 段 / 1 处 / 1 张」；
    · v1.21.71：两种模式都是「4 段 / 4 处 / 4 张」。
    ⇒ F1 不只是"字段回填了"，**两个出口都通了**。

  **冒烟**：exit 0 / **0 个 ✗**；11 条新 check 全 ✓。调用次数的间接证据：
    同一套 mock 作业里 **9 个模式的 LLM 调用数一律 −1**（78→77、91→90、
    38→37）—— 正是 F6 省掉的那一次重复外部评估（没有别的改动会改计数）。

  **真跑**：V71S（serial，四层各 1 圈）10.3min / 49 calls / 0 异常 /
    views 四层齐、views_errors 全空、meta_closure clean=True（by_id=2）；
    V71B（B 模式，同参数）7.3min / 52 calls / 0 异常 / 同上。
    两跑都满足「4 段收尾留痕 + 4 条停止交代 + md 4/4/4」。

  **零触发的项（如实记，不当成"生效"）**：
    · F11 在两跑里**都没触发**收尾站点的压制（两跑各只有 1 个诊断文件、
      且来自圈内站点，抑制日志 0 条）——它的有效性由定点探针与冒烟证明；
      价值在**预防**：F1 之后单圈层也进收尾，若不同时加这个开关，
      单圈跑会**新增 4 份**收尾诊断。
    · F3 / F4 / F5 / F7 / F8 / F10 都是边角路径，正常真跑不经过；
      证据全在探针 + 冒烟。
    · F9 是运行期可见变化（分词变了），但两跑没有可归因的差异读数，
      不作"生效"宣称。

  **未采纳 / 留存项**：
    · F9 的 `_STOPCHARS` 保留但已无引用（加性优先，不删旧行）；
    · F11 的替代做法「按**内容**去重、两个站点都留」比关一张更精确，
      但要多一个内容指纹键；归可观测性批；
    · F8 的方案 B（统一成唯一实现）未做，见上。

  **纪律**：先量后改（before/after 同一支探针）；加性优先（新键
    `_evidence_full` / 新参数默认值 / 新方法，不删旧行）；失败必须留痕
    （F2 打印 + 退出码、F3 三处、F9 注释、F11 的 logger.info）；
    不改任何阈值 / 常量；docstring 里零反斜杠。

  ════════════════════════════════════════════════════════════
v1.21.70 相对 v1.21.69 的改动（F~J 六项修复）
════════════════════════════════════════════════════════════

  来源：一份**外部任务书**（针对 v1.21.69 的 F/K/G/H/I/J 六项补丁清单）。
  六项前提逐条复核过，并在下面改正了任务书自身的两处笔误（标 ★）。
  F/K 是 v1.21.69 [B] 项的**必然收尾**（B 拆了两个覆盖率口径，轨迹与
  触发时机没跟上）；G 是唯一还没修的真 bug；H/I/J 是 v1.21.69 [E] 的
  自然延伸与卫生。

  ────────────────────────────────────────────────────────
  [F] 不可判定轨迹与 B 的双口径对齐（补 aligned_trace）
  ────────────────────────────────────────────────────────

  **位置**：`Pool.add_undecidable` 尾部（记轨迹处）+ `save_result` 里
  渲染 `struct_trace` 的那一段。

  **根因**（v1.21.69 [B] 的收尾没做）：B 把覆盖率拆成两个数 ——
  `last_struct_coverage`（撞 `structural_amps`，受 prompt 约束"不得直接
  复述 und_aspects 的原话"，**结构性必为 0**）与 `last_aligned_coverage`
  （撞 `aligned_amps`，真正能回答"有没有对上 und_aspects"）。但**轨迹
  只有一条**：产物里会同时出现「结构覆盖率 0.00（独立结构）｜对齐覆盖率
  0.38（对齐结构）」与「覆盖轨迹：L1 0/8 → L2 0/8」—— 两个数打架。
  改前实测（`_probe_v70_six.py`）：`aligned_trace` / `aligned_first_hit`
  **都不存在**，`last_aligned_coverage` 已经是 0.5，而轨迹行仍只印
  `L1 0/2 → L2 0/2`。

  **做法**：轨迹记录抽成内部函数 `_append_trace`；`struct_trace` /
  `aspect_first_hit` **原样保留**（历史对比），**新增**
  `aligned_trace` / `aligned_first_hit` 一对同构的，只是输入换成
  `aligned_hits`。渲染同样抽成 `_render_trace`，两条轨迹分别渲染为
  「不可判定独立结构覆盖轨迹」与「不可判定对齐结构覆盖轨迹」。

  **★ 任务书笔误一**：任务书写「加性 …… 旧断言（"不可判定覆盖轨迹：
  L1 …"）原样成立」。**不成立** —— 结构那条的标签从「不可判定覆盖轨迹」
  变成「不可判定独立结构覆盖轨迹」，是**破坏性文案改动**、不是加性。
  仓库里没有任何断言依赖这串字（实测只命中文档与历史产物），所以照改；
  但必须记在案，不能写成"加性"。

  **★ 任务书笔误二**：任务书要求断言 `aligned_first_hit == {"A 的复述": 1}`
  —— 键是**方面**、不是 amp（`_hit_of` 返回的是 `und_aspects` 的条目）。
  正确断言是 `aligned_first_hit == {方面: 圈号}`。另外样例若用单字方面
  （"A"）也撞不上：`_kw("A")` 是**空集**（单字被分词器滤掉），
  `_overlap_coef` 直接返回 0.0 —— 冒烟样例一律用长句方面。

  ────────────────────────────────────────────────────────
  [K] 覆盖率段的触发时机（route 不含 all 时给研究层也调一次）
  ────────────────────────────────────────────────────────

  **位置**：`MetaDGTF._finalize_layer_common` 第 6 步（元层闭环 + 覆盖率段）。

  **根因**：`_coverage_segment()` 原来**只挂 `entry == "all"` 的收尾**。
  于是 route 不含 `all` 的运行（例如 V68 的 route=0,1）里它**一次都不会
  被调** —— v1.21.69 [B] 改好的「对齐覆盖率」在那种 route 下根本没有
  出口。v1.21.69 changelog 自己把这条记成「可达性限制（既有行为）」，
  本版补上。改前实测（`_probe_v70_six.py`，把 `_coverage_segment` 换成
  返回哨兵）：`entry=1` 收尾后 manifest **不含**覆盖率段，`entry=all` 含。

  **做法**：把「追加覆盖率段」抽成内部函数 `_append_coverage(view, where)`；
  `entry == "all"` 分支照旧调它；**新增 `elif entry == "1"`**，研究层收尾
  也调一次 —— route 不含 all 时这就是**唯一**出口。

  **★ 为什么不是改 `_coverage_segment` 的触发条件**：它是**渲染**函数，
  不该承担"什么时候渲染"的调度职责。触发时机是收尾的事。

  **★ 口径说明（不是 bug）**：route 含 all 时两处都追加（研究层 view 一份、
  all 层 view 一份），内容一致 —— 覆盖率本来就是研究层的东西。两处的
  追加时机都与原先的 all 层**完全相同**（都在 `_apply_keep` /
  `_settle_research` 之前），所以不会"一个是一个不是"。

  ────────────────────────────────────────────────────────
  [G] 锚点重述的占位符闸门（仅剩的真 bug）
  ────────────────────────────────────────────────────────

  **位置**：`DGTF._re_anchor` 里的 `_clean` 闭包。

  **根因**：候选侧早有占位符闸门（`_parse_candidate_line` 挡「（无）」
  「(无)」「无」三种写法），**锚点重述这条路没设闸** —— 本项目
  「同一件事两处各写一份」的又一处变体。V68 真跑产物里的实际案例：
  `/views/0/untouched[0].desc == "此处未生"`（source=anchor），渲染成
  「尚未触及的方面：💭 此处未生（anchor）」—— **一条占位符被当成一条
  方面**。

  **做法**：在 `_clean` 前定义 `_ANCHOR_PLACEHOLDERS`（「此处未生」
  「无」「暂无」「未知」「n/a」等，含全角 / 半角两种括号写法），逐条比对；
  全角括号先归一成半角再比。空串照旧丢。
  只挡**完全相等**的占位符，不做子串匹配 —— 否则会把「无仲裁规则」
  这类正常方面误杀。

  ────────────────────────────────────────────────────────
  [H] `rendered` / `manifest` 只打长度（超大覆盖字段）
  ────────────────────────────────────────────────────────

  **位置**：`dump_view_fields` 的字段循环。

  **根因**：v1.21.69 [E] 用**差分**压掉了"累积型"字段的重复，但
  `rendered`（修行约 4551 字 / 研究约 6378 字）与 `manifest` 是
  **每圈覆盖、每圈都变** —— 差分对它们**无效**，每圈都得整段打出来。
  V68 日志 3696 行的大头就在这两个字段上。改前实测（`_probe_v70_six.py`，
  rendered=5000 字 / manifest=3000 字）：单圈留痕 **9499 字符**，
  两个字段的正文**全文都在**。

  **做法**：字段名硬编码成集合 `_OVERSIZED = {"rendered", "manifest"}`，
  命中且是 str 时只写一行 `├ rendered：str 5000 字（超大覆盖字段，
  正文见产物 md）`。
  · 仍用 `├ ` 前缀 ⇒ 字段覆盖计数（v1.21.68 那条 ≥ 字段数）不受影响；
  · 正文**完整留在产物 md**（与 [E] 同一条哲学）；
  · 不维护"该打什么"的清单，只钉**字段名** —— 新增字段不会被误伤。

  ────────────────────────────────────────────────────────
  [I] `dump_round` 顶部加「本圈留痕」说明
  ────────────────────────────────────────────────────────

  **位置**：`DGTF.dump_round` 顶部（`╚…╝` 之后、`dump_view_fields` 之前）。

  **根因**：跨圈**回填**的字段（`roles_run` / `round_log` / `rounds_cap` /
  `carry_*`）在本圈 dump 时**还没发生**，所以每圈都打 0 项 —— V68 日志里
  每圈 `roles_run：list 0 项`，而收尾后是 2 项。不是 bug（每圈新建 view），
  但读日志的人会把 0 项误读成"整层为空"。

  **做法**：加一句提示 ——「本段是**本圈**留痕；跨圈回填字段……最终值见
  该层收尾留痕」。不改变任何数据，只说明白。

  ────────────────────────────────────────────────────────
  [J] `_merge_decidability` 复用 `_und_untraced`
  ────────────────────────────────────────────────────────

  **位置**：`MetaDGTF._merge_decidability` 里算 `_untraced_pool` 那段。

  **根因**：池评估（`_assess_decidability_from_pool_view`）**已经**算好
  并把 `_und_untraced` 放进返回值（v1.21.61 起），合并路径又拿
  `undecidable_aspects` + `evidence` **重算了一遍** —— 「同一逻辑两处
  各写一份」，本项目反复栽的坑。v1.21.69 [D] 刚改了
  `_untraced_undecidable` 的阈值（`_UNTRACED_OVERLAP`），两处要么都改、
  要么都不改，迟早分叉。

  **做法**：优先读 `pool_res["_und_untraced"]`；**兜底** —— 调用方没带这个
  键时（历史数据 / 手造桩 / external-only 路径）退回重算一次，不静默吞。
  改前实测（`_probe_v70_six.py`，故意给一个与 evidence 矛盾的缓存值
  `["CACHED_SENTINEL"]`）：改前合并结果用的是**重算值**，改后用**缓存值**。

  **★ 一处顺带的语义修正（不是本项目标，但必须记）**：缓存值是用
  `_assess_decidability_from_pool_view` 里的**完整 evidence** 算的，而重算
  路径读的是 `pool_res["evidence"]` = `evidence[:8]`（**截断到 8 条**）。
  两者在 evidence 多于 8 条时会不一致 —— 复用缓存更准，方向上是对的。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **前置量化**：`_probe_v70_six.py`（接受目标 py 作参数），改前 / 改后各跑
  一次对表（`_probe_v70_before.txt` / `_probe_v70_after.txt`）—— 没有对照
  的"修好了"不算数。判据：F 的 trace 键从 1 组变 2 组、渲染行从 1 行变
  2 行；K 的 `entry=1` 从 false 变 true 且 `entry=all` 保持 true（不许
  回归）；G 的占位符从穿透变被挡；H 的单圈留痕字符数掉下来且正文不再
  泄漏；I 的提示出现；J 的 `cached_used` 从 false 变 true。

  **冒烟**：`SRC` → v1.21.70；新增 6 条（F/K/G/H/I/J），每条带**负对照**：
    · F：`struct_trace` 必须**仍有 2 条**（原样保留），且渲染断言要求两条
      轨迹行**同时**出现；
    · K：`entry=all` 的路径不许被改坏（两个方向都锁）；
    · G：全占位符时返回空表（不留残渣）+ 正常方面不被误杀；
    · H：超大字段只留长度 + **非超大字段（collision）正文仍必须在**；
    · I：说明文字在源码与输出里都在；
    · J：缓存被用 + 不带缓存时退回重算且**不崩**。

  ────────────────────────────────────────────────────────
  ★ v1.21.70 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.70.py（纯 CRLF）；smoke_test.py 加 6 条 check；
    `_probe_v70_six.py`（改前 / 改后同一支探针）；`v70_报告.md`；
    真跑 sidecar（`verif_V70.log/.json/.full.json`）。

  **改了 6 处代码**：F 轨迹拆两条 + 渲染拆两条；K 触发时机（抽
    `_append_coverage`）；G 占位符黑名单；H `_OVERSIZED`；I 一句提示；
    J 复用缓存 + 兜底。

  **刻意不做**：不动 `last_struct_coverage` 的语义（保模型输入不变）、
    不改 `_render_trace` 之外的产物结构、不动 docstring 里 v1.21.68 与
    v1.21.69 两段的**段序**（已知这两段次序颠倒 —— 68 在 69 前面，
    是 v1.21.69 引入的既有瑕疵；本版只**记录**不代改）。

  ════════════════════════════════════════════════════════════
v1.21.69 相对 v1.21.68 的改动（A/B/C/D/E 五项：先量后改）
════════════════════════════════════════════════════════════

  来源：一份**外部评审**（对 v1.21.68 一次真跑 V68 的结构分析）列出 A-E
  五项。本版**不照单全收** —— 每一项都先用生产入口量出改前基线
  （`_probe_v69_abcde.py`，可重复运行），量出来与评审不一致的地方照实写。
  五项里 **2 项真 bug**（A/B）、**1 项潜在串层**（C，现网不可达）、
  **1 项判据误报**（D）、**1 项评审诊断反了**（E）。

  ────────────────────────────────────────────────────────
  [A] `_b_merge` 的 `all_amp_cands` 缩进错（真 bug · 会算错数）
  ────────────────────────────────────────────────────────

  **病灶**：并行通道（B/C/D-H）的 `_b_merge` 里，逐圈累加候选数那几行
  写在 `for a in (view.amps or [])` 的**循环体内**：
    · `view.amps` 为空 → 那一圈的 `_amp_cand_count` **漏累加**；
    · `view.amps` 有 N 条 → 同一个数被**重复累加 N 次**。
  而串行通道（`_run_layer`）里同名的累加本来就在体外。同一条逻辑两条
  通道各写一份、只错一份，且没有任何断言看住 —— 本项目第 N 次的老毛病。

  **实测**（`_probe_v69_abcde.py`，改前）：
    · amps=3 条、`_amp_cand_count`=5 → `all_amp_cands`=**15**（应为 5）；
    · amps=0 条、`_amp_cand_count`=7 → `all_amp_cands`=**0**（应为 7）。

  **影响面**（改之前先查下游）：`all_amp_cands` 只有两个出口 ——
  ① 产物 packed 里的同名键；② `_finalize_layer_common` 里那行
  「[P3] & 候选（各圈累计）N 条 / 本层 amps M 条（比值 …）」的**分母**。
  分母虚高 3 倍（或漏算）会把这行观测直接带偏；修完才是与 `all_amps`
  真正同口径。

  **改法**：累加移出循环体，与 `_run_layer` 对齐。

  ────────────────────────────────────────────────────────
  [B] 不可判定覆盖率算错了输入（真 bug · 口径内部矛盾）
  ────────────────────────────────────────────────────────

  **病灶**：`Pool.add_undecidable` 拿 `structural_amps` 去撞
  `und_aspects` 算「结构覆盖率」。但喂模型的 schema 里
  `structural_amps` 明确要求**「不得直接复述 und_aspects 的原话」**，
  而 `aligned_amps` 才是要求**「正好对应 und_aspects 中的某一项」**的
  那一列。拿前者算命中 —— **结构性必为 0**：这个数指向的不是"模型没
  做到"，是"它永远算不出别的值"。

  **实测**（V68 真产物 / `_probe_v69_abcde.py`）：
    · `und_aspects` 8 条；`structural_amps` 8 条 → 旧口径 **0/8 = 0.000**
      （产物里记的就是 `last_struct_coverage = 0.0`）；
    · `aligned_amps` 3 条（三条与 und_aspects 前三条同义）→
      **3/8 = 0.375**。也就是说 aligned 这一列**早就算出来了，却没有出口**。

  **改法**：两个覆盖率**分开算、都留出口**。
    · `last_struct_coverage` / `last_struct_hit` **语义一个字不改** ——
      它是 `_pool_shape` 喂给模型的输入，改它的值等于改模型输入，
      那要真跑对照，不在本版范围；
    · 新增 `last_aligned_coverage` / `last_aligned_hit` /
      `aligned_coverage_history`，只在**产物 md**（`_und_channel_line`）
      与**日志**（`_update_trackers` 那一行）两个渲染点出现；
    · 渲染**加性**：旧产物 / 手工 dict 里没有 `aligned_coverage_history`
      时不打这一行 —— v1.21.57 的冒烟断言（"结构覆盖率 0.60"、
      "已对上 6/10"）因此原样通过，不必改旧断言。

  ────────────────────────────────────────────────────────
  [C] `object_desc` 的兜底分支串层（潜在 · 现网不可达）
  ────────────────────────────────────────────────────────

  **评审的说法**：研究层（entry=1）落到 `else` 分支，拿到「整体与每一个
  局部」当对撞对象。**实测：不成立。** 三条独立证据：
    ① 生产入口 `_build_inp_base` 必定带 `question` ⇒ `Input.is_base`
       恒为 True ⇒ 0/1 层永远走第一个分支；并且 `_ENTRY_CONTENT_DEPS`
       里 0/1 的内容依赖都是**空表**，本来也不会有上游 view；
    ② 探针按生产构造逐组合跑（entry 0/1/both/all × is_base 真/假），
       0/1 只出现「这个问题里的 0 和 1」；
    ③ V68 日志里 135 行 ing 正文，含「各个局部」**0 行**、含「上游」
       **0 行** —— 模型从没收到过那句话。

  **但分支本身确有隐患**：`else` 同时兜住「元层(all)」与「修行/研究层
  (0/1)」，两者的对撞对象根本不同。这正是本项目反复栽的「兜底分支混层」。
  **改法**：对象映射写成**显式四支**（is_base / both / all / 0-1），
  不可达的那一支也不再给错标签。
  **刻意不动**：`_fix83_block` 的 `_upstream_label` 对 0/1 仍写
  「上游 view」——那是措辞瑕疵不是错误，改它要真跑对照，留给下一版。

  ────────────────────────────────────────────────────────
  [D] `_untraced_undecidable` 的误报（判据自己变成噪声源）
  ────────────────────────────────────────────────────────

  **病灶**：`_similar` 的分母取 **max**。不可判定条目句长、evidence 里的
  aspect 句短，同一语义被写成「长句 ⊃ 短句」时比值被长句拉低，
  于是**有追溯的被判成无追溯**。

  **实测**（V68 真产物 / `_probe_v69_abcde.py`）两条误报：
    · 「时间尺度（一场雨/汛期/管网寿命）结论相反且无仲裁规则」
      ↔ evidence「时间尺度无仲裁规则」：_similar 够不着 0.55，
      包含度 **1.000**；
    · 「行政档案与居民记忆两份留痕之差不能被对撞消掉」
      ↔ evidence「两份留痕之差不可对撞消减」：包含度 **0.667**。
  改前 `_und_untraced` 记的 2 条（合并路径已滤掉 [外]）**全是误报**。

  **改法**：再加一层 `_overlap_coef(...) >= _UNTRACED_OVERLAP`（0.6）——
  它的分母取 **min**，短句被长句包住时接近 1，正是需要的方向。
  阈值定 0.6：实测 0.667 能救回、0.75 就救不回，再低会把泛化同义也算成
  追溯。

  **影响面（必须记）**：`_untraced` 是 `_normalize_decidability` 的输入
  —— **误报少了，采信就多了**，decidable 更可能被拉成 partial。方向是
  刻意的（探针实证那 2 条本来就是采样抖动），但它动的是**三态判定**，
  属运行期可见变化，不能只当"日志好看了"。V68 这两条剔除后判值仍是
  partial（`_und_traced` 由 2 条变 4 条，都非空）。

  ────────────────────────────────────────────────────────
  [E] 累积型字段的出口（评审诊断反了 · 换成真问题）
  ────────────────────────────────────────────────────────

  **评审/上一版的说法**：v1.21.68 遗留 1 ——「每圈留痕含 `round_log` 等
  **累积型**字段，同一信息随圈重复出现（n 圈约 n(n+1)/2 份）」。
  **实测：不成立。** 直接数 `verif_V68.log` 的 4 段留痕：`round_log` /
  `roles_run` / `carry_checks` / `carry_dropped_all` **每段都是 0 项**；
  每段 26k-31k 字符全由 `candidates` / `rendered` / `untouched` 撑着
  （逐圈内容，不是累积）。
  **真正的问题正相反**：这些字段是**回填**的，回填发生在最后一次
  `dump_round` **之后** ⇒ 它们在任何一段留痕里都恒为空 ——「全量留痕」
  对这几个字段**从来没兑现过**。上一版把"没出口"误诊成了"重复"。
  （教训：**"某指标很稳/很吵"要先确认它不是被下游机制压出来的**，
  这里连"有没有出口"都该先数一遍再下结论。）

  **改法**：跑圈 + 回填都结束后，补一段**收尾留痕**：
    · `DGTF.dump_final(view)`，头是「收尾留痕 · entry · 共 N 圈 · 角色」；
    · **增量模式**：只打与上一圈 dump 有差异的字段，并交代省略了几个 ——
      差分是**算**出来的，**不维护**"哪些字段是累积型"的清单
      （那种清单一定会漏，本项目「无渲染点」事故就是这么来的）；
    · 差分基准是 `dump_round` 打完那一刻挂在 `view._dump_canon` 上的
      规范化快照 —— 必须取在**那一圈真打出来的时刻**；取在收尾之前会把
      圈后的后处理（`carry_checks` 等）算进基准，于是又漏掉一次；
    · 字段落盘收口成模块级 `dump_view_fields()`（唯一实现），
      `DGTF.dump_round` 与 `dump_final` 共用 —— 同一件事两条通道各写一份
      也是本项目反复栽的坑；
    · `_dump_canon` 是**内部账**：`_view_field_map` 与 `View.to_dict`
      （`asdict`）都不带它，产物 packed 不受影响。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **冒烟**：`SRC` → v1.21.69；新增 `check_v69_abcde`，A-E 各若干条，
  并带**负对照**（证明判据有判别力，不是随口放宽）：
    · D：真·凭空一条仍须被抓出；带来源后缀的仍须判为有追溯；
    · B：旧键 `last_struct_coverage` 仍须原样渲染；
    · E：增量模式必须**真省略**掉没变的字段（省略数 > 0），
      且 `round_log` 必须出现在收尾段。
  **前置量化**：`_probe_v69_abcde.py`（接受目标 py 作参数），改前/改后
  各跑一次对表 —— 没有对照的"修好了"不算数。
  ────────────────────────────────────────────────────────
  真跑验收（补做 · 同题同参数：route 0,1 / rounds 0:2,1:2 / serial）
  ────────────────────────────────────────────────────────

  题面与 V68 完全一致（老城区暴雨内涝…怎么权衡？）。共 8 次：
  V68 原跑 + V68 重复 3 + V69 单跑 + V69 重复 2 + V69 mode B 1。

  **[A] 要并行通道才有判别力** —— 原 V68/V69 都是 serial：`_run_layer`
  里累加本来就在体外，新旧输出**必然相同**（实测 V68 serial 两层
  Σcount = 11 / 12，与该层 `[P3]` 行的 N **逐层相等**）。补跑一次
  `mode=B`（Jacobi，走 `_b_merge`）：
    · entry 0：各圈 `_amp_cand_count` = 3/3 → Σ=6，`[P3]` 实测 **6**
      （旧实现预测 Σ(count×len(amps)) = **24**）
    · entry 1：各圈 = 6/2 → Σ=8，`[P3]` 实测 **8**（旧实现预测 **32**）
  即真实并行路径上，N 与 Σcount 严格相等，而旧实现会给出 4 倍值。

  **[B] 日志渲染点 ✅**：V69 真跑出现
  `📘 不可判定对齐覆盖率 0%（0/3 und_aspects 命中）` 2 次（V68 为 0 次），
  并把「对齐结构 N 条（另计）」改成「（计入对齐覆盖率）」。
  ★ **可达性限制（既有行为，非本轮改动）**：产物 md 那行
  `研究层不可判定通道：…` 由 `_coverage_segment` 产出，而它只在
  `entry == "all"` 时被追加 ⇒ route 不含 `all` 的运行**整个第七节都不
  出现**（V68/V69 产物实测都是 0 行）。备查。

  **[C] ✅**：V69 真跑 ing 正文 153 行里含「各个局部」**0 行**；含
  「上游」3 行全是模型自己的水文措辞（「下游水位反超上游出口」等），
  与标签无关 —— 与「0/1 层走 is_base 分支」的结论一致。

  **[D] ✅（本批多数运行没触发到）**：把每一跑的 (池内 und_aspects,
  evidence) 分别喂给 V68 码与 V69 码做**反事实对照**：
    · 原 V68 那一跑：V68 码判 2 条无追溯（全是误报）→ V69 码 0 条 ✅
    · 其余 7 跑：池子**自列 und_aspects 为空**（只剩 `[外]`）⇒ 两版结果
      都是 0 条，D 在这些运行上是**可证明的无操作**。
  即：D 的修在被触发的数据上确实生效，且**没有**改变其余运行。

  **[E] ✅**：V69 真跑出现「收尾留痕」**2 段**（entry 0 / 1），增量省略
  **40/54** 与 **38/53**，`round_log` 2/2 项、`roles_run` 2/2 项、
  `carry_checks` 1/1 项；V68 同题同参为 0 段，四个累积字段在 4 段圈留痕里
  **每段 0 项**。

  **同题同参的横向指标**（V68 原跑 vs V69 单跑）：43 / 43 calls；
  194993 / 185901 tokens；9.7 / 8.9 min；dispatch 都是
  order=['0','1'] missing=[]；views errors 都是空；日志 123313 →
  152825 字符（多出的是 2 段收尾留痕 + 更多 ing 行）。

  **一项无法归因的观测（按纪律定性，不硬说）**：`tri_state`（三态二次
  判决的「一致条数」）V68 原跑 4/6、V69 单跑 0/6。补做同条件重复后：
    · V68（n=4）：4 / 1 / 3 / 2 → 均值 2.50，组内极差 **3**
    · V69（n=3）：0 / 2 / 2    → 均值 1.33，组内极差 **2**
  组间差 1.17 **小于**组内极差 3 ⇒ 按「组内极差 < 组间差才有判别力」这条
  纪律，本轮样本量**不支持**把它归给本版改动。并且 A/B/C/E 对 serial +
  route 0,1 是**可证明的无操作**（A 走 `_run_layer`；B 只改渲染与新增键，
  `_pool_shape` 喂模型的仍是 `last_struct_coverage` 原值；C 是不可达支；
  E 只写 stdout），D 又在上列 7 跑上无操作。故记在**引擎自身的采样抖动**
  名下。要坐实需更大样本，本轮止步于此、如实记数。

  ────────────────────────────────────────────────────────
  ★ v1.21.69 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.69.py（纯 CRLF）；smoke_test.py
    +`check_v69_abcde`；`_probe_v69_abcde.py`（改前/改后同一支探针）；
    `_cmp_v68_v69.py`（真跑对照 + A 的不变量校验）；`v69_报告.md`；
    8 次真跑的 sidecar（`verif_V69*.log/.json/.full.json`）。

  **改了 6 处代码 + 1 个模块级常量**：A 缩进；B 覆盖率口径 + 2 个渲染点；
    C 对象映射四支；D 追溯判据 + 阈值常量；E 留痕收口 + 收尾增量。

  **刻意不做**：不动 `last_struct_coverage` 的语义（保模型输入不变）、
    不动 `_fix83_block` 的措辞、不改 `_pool_shape`（把对齐口径也喂模型
    等于改模型输入，要另起一轮真跑对照）。

  

  ════════════════════════════════════════════════════════════
v1.21.68 相对 v1.21.67 的改动（每层每圈全量留痕 + ing 正文可见）
════════════════════════════════════════════════════════════

  要求：「每层每圈所有产物以及标记等都要输出记录，ing 也要在日志中显示」。

  ────────────────────────────────────────────────────────
  [A] 每圈全量留痕：`DGTF.dump_round(view, inp)`
  ────────────────────────────────────────────────────────

  **实测缺口**：v1.21.67 的日志"流收全了"，但引擎**每圈只打摘要** ——
  候选只报**条数**（明细 `c.desc[:50]` 截断）、ing 只报**字数**、
  悬置/债务/清算只报计数。正文与明细**根本不落日志**；出问题只能从产物
  反推，而产物只留**最后一圈**的 view（`_run_layer` 每圈新建 view）。

  **做法**：在 `DGTF.run` 末尾（`return view` 前）挂一次 `dump_round`，
  把本圈 view 的**所有字段**逐条写进当前输出流（真跑时即日志）：
  · `dataclasses.asdict` 逐字段输出，**不截断**；
  · 动态挂上去的属性（如 `_expanded_descs` 去重账）单独补 —— asdict 盖不到；
  · 列表/字典走 `json.dumps(indent=1)`；多行字符串**逐行带 `│` 前缀**；
  · 连 asdict 抛异常也要写一句，不许静默。

  **为什么挂在 `DGTF.run` 而不是各个跑圈循环里**：全库只有 3 个 `dg.run(`
  调用点（serial / 汇流 / 其它通道）—— 挂在 `run` 里**一次覆盖所有通道与
  并行模式**（A–H），不必在 10 个模式里各补一行。

  ★ 与产物 md 的「全量字段」附录同一条哲学：**不挑字段、机械全量**。
    新增字段自动被覆盖，不会因为漏写一行 print 而丢。

  ────────────────────────────────────────────────────────
  [B] `ing` 正文就地打印
  ────────────────────────────────────────────────────────

  原来只有 `🔥 ing 输出 {N} 字`。现在紧接着把**正文逐行**打出
  （`🔥 │ …`），放在它被产生的位置 —— 读日志时不必翻到圈末的留痕段。
  圈末留痕段同样含 `collision` 全文（两处重复是有意的：一处就地、一处留痕）。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **冒烟**：`SRC` → v1.21.68；新增 `check_v68_round_dump`，八条：
  ① 留痕标记（entry / 圈号 / 角色）；② **ing 正文两行都在**；
  ③ `collision` 字段名在；④ 动态属性在；⑤ 长文本不被截断；
  ⑥ **字段覆盖 ≥ `dataclasses.fields(View)` 的字段数**（机械全量的硬判据）；
  ⑦ **接线检查**：`self.dump_round(view, inp)` 必须在源码里（否则是死代码）；
  ⑧ ing 就地打印接上了。全套 exit 0 / 0 ✗。

  **真跑（V68）**：route 0,1 / 0:2,1:2 / 43 calls / 9.7 min。
  · 日志 `verif_V68.log` **123313 字符 / 3759 行**
    （v1.21.67 的同题短跑只有 17553 字符 / 447 行）；
  · `圈全量留痕` 段 **4 段**（0 层 2 圈 + 1 层 2 圈 + 汇流，每圈一段）；
  · ing 正文行 `🔥 │` **135 行**；
  · `[completeness] stdout 行 3696｜stderr 行 0｜logging INFO=43｜异常：无`。

  ────────────────────────────────────────────────────────
  ★ v1.21.68 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.68.py（17433 行 / 纯 CRLF）；smoke_test.py
    +`check_v68_round_dump`；`_run_verif.py` 本轮**未改**（v1.21.67 的收全能力
    直接复用）。

  **验证覆盖**：冒烟 exit 0 / 0 ✗（含字段覆盖数与接线检查）；V68 真跑
    逐项实测（留痕段数 / ing 行数 / 日志体量）。

  **经验教训**：**"日志收全"分两层** —— ① **流要收全**（v1.21.67 做的：
    stdout / stderr / logging 都进同一个文件）；② **流里得有东西**
    （本轮做的：引擎每圈真的把全量打出来）。只做 ① 会出现
    "日志很完整地记录了摘要"。判据可量化：**留痕字段数 ≥ View 的
    dataclass 字段数**。

  **遗留**：
    1. 每圈留痕含 `round_log` 等**累积型**字段，同一信息会随圈重复出现
       （n 圈约 n(n+1)/2 份），日志因此偏大（V68 两层两圈已 123313 字符）。
       若要压，可对累积字段只打增量 —— 属格式决策，当前**完整性优先**。
    2. 四层 5 圈的日志会到 MB 量级 ⇒ 判卡死**不要按字节数看推进**，
       按层/圈标记推进（已有约定）。

  ════════════════════════════════════════════════════════════
v1.21.67 相对 v1.21.66 的改动（日志收全 + 产物全量附录）
════════════════════════════════════════════════════════════

  要求：① 每次运行的日志不得有遗漏、要显示所有内容；② 保存的产物 md 要
  包含所有内容 —— **显示的未显示的都要有**。两件事：一件在工具侧
  （`_run_verif.py`），一件在引擎侧（`save_result`）。

  ────────────────────────────────────────────────────────
  [A] 产物 md 追加「附录 · 全量字段（packed 原文）」
  ────────────────────────────────────────────────────────

  **实测缺口**（`_probe_packed_vs_md.py`，离线桩，route 0,1 各 1 圈）：
  packed 有 **429 条叶子路径**，产物 md 正文只有 3900 字符 —— **405 条**
  的字段名在正文里根本不出现。正文各节是 packed 的**可读视图**，天然带
  省略：`input_sanity` / `layer_contribution` 这类顶层键从来没有渲染点。
  真跑（V67）实测更极端：**925 条叶子、815 条**正文里找不到名字。

  **做法**：正文写完后，把 packed **原样 JSON** 追加进同一份 md，并给一行
  完整性统计（叶子路径数 / 正文找不到名字的条数 / JSON 体积）。
  ★ **刻意不做「再挑几个字段渲染」** —— 挑字段等于又维护一张「该渲染什么」
  的清单，新增字段会再次静默漏掉；本项目的「无渲染点」事故就是这么来的。
  序列化失败也要往产物里写一句，否则产物会看起来「完整」而其实缺一段。

  ────────────────────────────────────────────────────────
  [B] `_run_verif.py` 日志收全（stdout + stderr + logging + 自检）
  ────────────────────────────────────────────────────────

  **实测缺口**：旧版只 `redirect_stdout`，三类内容根本不进日志：
    1. 引擎的 **6 条 `logger.info`** —— 模块方式导入时 `logging.basicConfig`
       没被调用，根 logger 只剩 lastResort，INFO 被**整条丢弃**；
    2. **49 条 `logger.warning` + 9 条 `logger.error`** —— 只落到 stderr；
    3. 引擎写到 stderr 的其它内容。

  **做法**：stdout / stderr **分流捕获并各自计数**；logging 挂显式 handler
  （INFO 起）写入同一日志；wrapper 自己的消息（banner / question / module /
  min_rounds 覆盖 / 计数 / 调度 / 产物路径）也进日志；首尾打
  `#### LOG BEGIN/END ####` 哨兵；末尾输出 `[completeness]` 统计行
  （stdout 行数 / stderr 行数 / 各 logging 级别条数 / 异常有无）。
  ★ 显式把 openai / httpx / httpcore / urllib3 / asyncio / jieba /
  charset_normalizer / filelock 降到 WARNING —— 否则 DEBUG 会把请求体
  （含 key）整个倒进日志。httpx 的每次请求行**保留**（那是"跑了多少次"的
  直接证据）。
  ★ 另存 `verif_<tag>.full.json`（packed 全量侧车），与产物附录同源。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **冒烟**：`SRC` → v1.21.67；新增 `check_v67_full_appendix` —— 断言附录
  标题 / json 块 / 统计行，把附录里的 JSON **解析回来**并断言顶层键齐全，
  且特意塞一个**正文绝无渲染点**的深层内部量（`_probe_only_internal`），
  用它区分「机械全量」与「又挑了一批字段渲染」。全套 exit 0 / 0 ✗。

  **流捕获的确定性单测**（`_probe_log_capture.py`，不联网）：直接对捕获
  机制断言 10 条 —— stdout / stderr / logger.info / logger.warning /
  logger.error 五类都进同一份日志，计数各为 1。
  ★ 为什么必须单测：V67 真跑恰好 stderr=0 行、引擎也没吐 warning，
  这两条**没有被那次运行证明**。

  **真跑（V67）**：route 1 / 1:2 / 23 calls / 4.7 min。
  · 日志 `verif_V67.log` 17553 字符 / 447 行：BEGIN、banner、
    question、module、logging 配置、`[completeness] stdout 行 404｜stderr 行 0｜logging INFO=23｜异常：无`、产物三条、END 齐备。
  · 产物 md 59267 字符（正文 14477 + 附录 44767）：附录
    `- 叶子路径 925 条；正文里**找不到字段名**的 815 条（按「字段名是否在正文出现」粗算，不是精确覆盖判定）`、`- JSON 44576 字符 / 1432 行`；JSON 可解析、17 个顶层键；附录里能直接看到
    `input_sanity` / `layer_contribution` 这两个**从来没渲染过**的顶层键。

  **回归**：`_regress_revisit.py` 放行 **1291 条（97.9%）** / 拦 28 条，
  判据线 ≥96% ✅。★ 重点：附录往 `outputs/*.md` 灌了 44K 字符的 JSON，
  回归语料只从 1312 → **1319 条**（+7，全部来自 V67 的正文）——
  说明附录**没有污染** `revisit_condition` 的抽取（否则会暴涨几百条）。

  ────────────────────────────────────────────────────────
  ★ v1.21.67 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.67.py（17298 行 / 纯 CRLF）；`_run_verif.py`
    （日志收全 + packed 全量侧车）；smoke_test.py +`check_v67_full_appendix`；
    新增两个只读探针 `_probe_packed_vs_md.py` / `_probe_log_capture.py`。

  **验证覆盖**：冒烟 exit 0 / 0 ✗；流捕获 10 条确定性单测全过；
    V67 真跑对日志与产物双向实测；回归 97.9% 且语料未暴涨。

  **经验教训**：**「没渲染点」与「渲染了但值为 0」是同一类事故的两面** ——
    v1.21.66 用「覆盖计数」治了后者，这一轮用「机械全量附录」治前者。
    共同解法是：**别维护「该渲染什么」的清单，让结构自己说话**
    （覆盖计数 = 无条件写；全量附录 = 整包落盘）。
    另：**日志收全不是"多写几个 print"**，而是要能证明 —— 所以给
    stdout/stderr/logging 各自计数，并用单测覆盖最容易漏的那几类流
    （干净跑里引擎不吐 warning，光靠真跑验不出来）。

  **遗留**：
    1. 产物 md 体积随 packed 线性增长（V67 单层 2 圈已 59267 字符；
       四层 5 圈预计 300K+）。要不要给全量附录加体积阈值 / 拆侧车，
       属格式决策，等实际需要再定 —— 现在**完整性优先**。
    2. 附录是 JSON，人读不友好；将来若要「人读版全量」应另开一节，
       不要动附录的机械性。

  ════════════════════════════════════════════════════════════
v1.21.66 相对 v1.21.65 的改动（机制一改报运行期峰值 + 覆盖自检）
════════════════════════════════════════════════════════════

  兑现 v1.21.65 遗留 1：`🍽` 那行原来只报**最终快照**，而 `_starve_rounds`
  按设计「本圈有任何进展就清零」—— 对“自然停”的层，末尾那次快照结构性
  接近 0，「离门槛差多少」永远答不出来。本轮加运行期峰值，并把
  「真 0 / 没观测点」分开。

  ────────────────────────────────────────────────────────
  [A] 3 处写入点收敛成「写一次、记一次峰值」
  ────────────────────────────────────────────────────────

  `_starve_escalation` 里原本有 3 处直接写 `sq["_starve_rounds"]`
  （被触碰 记 0 / 无进展 加一 / 升级走 记 0）。收敛成一个内部函数
  `_set_starve(sq, val)`：写计数的同时把峰值抬到「该值」与「旧峰值」的较大者。
  ⇒ 峰值 = `_starve_rounds` 整段运行里**取到过的最大值**，两个清零点都带不走。

  **为什么不写成「在清零前各抄一次」**：3 个写入点里，**末圈那次加一
  没有“下一圈”来抄它** —— 只有“写时即记”才不会漏。

  ────────────────────────────────────────────────────────
  [B] `🍽` 行**加性**输出（旧探针不动，新探针另接）
  ────────────────────────────────────────────────────────

  新格式（前缀与旧格式逐字相同，只在中间插新段）：
    `- 🍽 无进展计数：最高 {本轮} 圈（{分布}）｜运行期峰值 {峰值} 圈
     （{峰值分布}）｜名下有挂账的子问题 {M} 条｜计数已写 {k}/{n} 条`

  **为什么要加性**：审计脚本的机制一正则吃的是从「🍽 无进展计数：最高」
  一直到「名下有挂账的子问题 N 条」的**整条** —— 只保留前缀也救不了它。
  改口径会让已有探针**静默失配** → 又一份“看着像没触发”的空报告。
  所以产物侧加性输出，审计侧把新段写成**可选组**：v1.21.65 的旧产物仍能解析。

  ────────────────────────────────────────────────────────
  [C] 覆盖计数：把「有渲染点且为 0」与「压根没这个渲染点」分开
  ────────────────────────────────────────────────────────

  `_starve_escalation` 若没跑（该层没走到 / 开关为 0），字段**不存在**，
  而渲染取值带默认 0 —— 出来**同样是 0**。也就是说：新加的峰值列自己就会
  掉进本项目反复踩的那个坑。所以行末补一列 `计数已写 k/n 条`（为 0 时显式
  写「★ 计数未写（机制未运行）」）。审计脚本同步把它读出来，并据此把
  「峰值 0」**三分**：真 0（覆盖在）/ 未运行（覆盖为 0）/ 无法区分（老产物）。

  ────────────────────────────────────────────────────────
  ★ 实测发现（G1q）：峰值出口第一次把「够到过」显出来
  ────────────────────────────────────────────────────────

  与 v1.21.65 的 G1 **同配置同题**复跑（route 1、min_rounds 1:5、eng 类
  「老城区内涝」）：14.8 min / 63 calls / 研究层 6 圈。
  产物那一行：
    `- 🍽 无进展计数：最高 0 圈（0圈×6）｜运行期峰值 1 圈（0圈×5、1圈×1）｜名下有挂账的子问题 0 条｜计数已写 1/6 条`
  ⇒ **快照 0 圈、峰值 1 圈** —— “某个子问题确实有过连续
  1 圈没被碰”，而最终快照把它抹平了。这正是本轮要解决的问题，
    它现在**在产物里看得见**了。

  ★ **顺带修正 v1.21.65 的一处推断**：v1.21.65 曾据债务行里的「回答 0」
  推断「条件一（连续 ≥2 圈没被碰）在圈 4 达到过」。本轮直接测出峰值只到
  **1 圈** ⇒ 那条推断**偏松**：在“被回答”之外，还有「深入 /
  挂新账 / 分类变更」这些**也算被碰**的动作，所以“某圈没人被回答”不等于
  “某子问题连续两圈没被碰”。**以本轮的直接测量为准**：机制一离触发
  差的是「再攒够到 2 圈」+ 条件二，不是“差一道更难的题”。

  ────────────────────────────────────────────────────────
  ★ 自伤缺陷与修正（G1q 撞出、G1r 复验）
  ────────────────────────────────────────────────────────

  G1q 同一行还暴露了 [C] 自己的缺陷：`计数已写 1/6 条`
  —— 覆盖计数**报了假数**。根因：`_set_starve` 原本只在「抬升」时写峰值字段，
  于是「字段在不在」度量的是**峰值是否为 0**，而不是「机制跑没跑」；
  只要某子问题一直是 0，它就永远不带字段。**自检列自己变成了假自检**
  —— 与 [C] 要防的是同一个病。

  **修正**：峰值**无条件写**（跑过就带字段），并补一条**直调生产函数**的
  冒烟 `check_v66_starve_writes_key`（不经产物）：断言函数跑一次后
  **每个子问题都带 `_starve_max_seen`**，且第 2 圈被触碰清零后**峰值仍留 1**。
  **复验（G1r）**：同题短跑（route 1、2 圈）5.2 min →
  `计数已写 5/5 条` ✓（机制确实每圈都写了计数）。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **冒烟**：`check_v65_starve_render` 原样保留（只给桩补上新字段）+
  `check_v66_starve_peak`（快照 0 / 峰值 2；**旧前缀正则仍匹配**；
  **字段缺席必须显式报「机制未运行」**）+ `check_v66_starve_writes_key`
  （写入语义）。全套 exit 0 / 0 ✗。

  **审计脚本的后向兼容（负对照）**：v1.21.65 旧产物（无峰值段）→ 仍解析出
  快照 `0圈×5`、最高 0 圈，并显式标注「本产物是 v1.21.65 口径」；
  v1.21.66 无覆盖计数产物 → 走峰值分支，但**主动声明**「没有覆盖计数 ⇒
  无法排除机制没跑」。⇒ 正则没被改哑，“没有观测点”会被说出来而不是当成 0。

  ────────────────────────────────────────────────────────
  ★ v1.21.66 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.66.py（17133 行 / 纯 CRLF）；`_audit_v64_zero_triggers.py`
    机制一探针改吃峰值 + 覆盖计数（新增段全为可选组，旧产物仍可解析）；
    smoke_test.py +`check_v66_starve_peak` / +`check_v66_starve_writes_key`。

  **验证覆盖**：冒烟 exit 0 / 0 ✗（三条 v66 断言）；两份产物负对照证明
    正则没被改哑；G1q 给出「快照 0 / 峰值 1」的直接证据；
    G1r 复验覆盖计数修正（5/5）。

  **经验教训**：**新增一个“计数列”时，必须同时加“这一列有没有被写”的自检**
    —— 否则新列自己就会变成下一个“看着像 0 的空报告”。本轮 [C] 想防这个病，
    结果 [C] 的实现（只在抬升时写）又犯了一次，是**真跑**把它抓出来的：
    自检逻辑必须用「无条件写」实现，不能用「有值时写」。
    另：**观测出口要报过程极值，不是瞬时终值**；**加性改产物格式**比改口径安全。

  **遗留**：
    1. 峰值是逐子问题存的（`_starve_max_seen`），产物只报**全池最大与分布**；
       要看单个子问题的历史，读 pool JSON（字段已在）。
    2. 机制一的裁决不变：接受为「设计上狭窄」并保留（见 v1.21.65 遗留 2）。
       本轮把它的“离门槛”从推断变成了**可测量**：峰值 1 / 门槛 2。

  ════════════════════════════════════════════════════════════
v1.21.65 相对 v1.21.64 的改动（机制一的观测出口 + 研究层圈数下限走运行时）
════════════════════════════════════════════════════════════

  本轮两件，都是 v1.21.64 审计的直接后续：
  A 把 `_starve_rounds` 的观测出口补上 —— 审计机制一时最需要的那个数，
    以前只活在内存里；
  B 给研究层「给足圈数」—— 走**运行时** min_rounds，刻意不动出厂配置。

  ────────────────────────────────────────────────────────
  [A] `_starve_rounds` 兑现渲染出口（机制一的「离门槛差多少」）
  ────────────────────────────────────────────────────────

  **根因**：v1.21.64 的审计只能写「升级合计 = 0」，写不出「离 2 差 1」——
  因为 `_starve_rounds` 全库 8 处引用**全在代码/注释里**，产物里没有出口。

  **做法**：池段「子问题 N 条」下面加一行：
    `- 🍽 无进展计数：最高 N 圈（0圈×a、1圈×b…）｜名下有挂账的子问题 M 条`
  —— 把机制一**两条条件**的进度都摆出来（分布 = 条件一离门槛差几圈；
  挂账条数 = 条件二有几个人在排队）。
  **配套**：审计脚本的机制一探针接到这个出口上（否则 A 白做）。

  **验证**：冒烟 `check_v65_starve_render`（构造 3 条子问题：_starve_rounds
  0/1/2 各一 + 1 笔 deferred、1 笔 handled）→ 分布、最高值、挂账计数全对。

  ────────────────────────────────────────────────────────
  [B] 研究层「给足圈数」—— 走运行时，不写回出厂配置
  ────────────────────────────────────────────────────────

  **根因**：机制一要「连续 2 圈无进展 + 名下有债」。实测 4 次真跑（D3/E2/F1
  与研究层）都只走 **3 圈**（自然停），候选窗口只有一个，且常被正常清偿吃掉。

  **做法**：**刻意不改出厂配置** —— `dgtf_config.yaml` 与 `DEFAULT_CONFIG`
  里都明确写着「按层下限走运行时（`spiral.per_entry` / `--rounds`），
  别写回这里」；v1.21.58 也已把 min_rounds 全层归零。所以给
  `_run_verif.py` 加 `--min-rounds`（**load_config 之后**显式改 cfg ——
  yaml 一旦写了某个键，环境变量会被 `_deep_merge` 吞掉，这是本项目的老坑）。

  **验证**：G1 真跑带 `--min-rounds '{"1": 5}'` → 日志出现
  `⏸ 停止理由「结构饱和度判定连续无新维度 + 连续 3 轮无线头新增（方向
  走完了），螺旋停止」被 min_rounds=5 拦截，继续第 5 圈`
  → 研究层从 3 圈提到 **5 圈** ✓（(B) 生效。）

  ────────────────────────────────────────────────────────
  真跑（G1）：机制一仍然 0，但这次能说清「为什么」
  ────────────────────────────────────────────────────────

  配置：`--route 1 --rounds "1:6" --min-rounds '{"1": 5}'`；题面取题库
  「6 领域各 1 题」的 **eng 类**（老城区内涝：重建 vs 局部改造加海绵）。
  53 calls / 12.7min；研究层 5 圈；子问题 5 条；延迟债务 3 条。
  产物里：`🍽 无进展计数：最高 0 圈（0圈×5）｜名下有挂账的子问题 0 条`。

  ★ 逐圈对债务行，**两条件错开**看清了：
    圈1 `新增1 回答3` ／ 圈2 `清偿1 回答2` ／ 圈3 `新增1 回答0`
    ／ 圈4 `清偿1 回答0` ／ 圈5 `新增1 回答0`
    · 条件一（连续 ≥2 圈没被碰）在圈 4 确实达到过（圈 3、4 都 `回答0`）；
    · 但**能达到条件一的 sub，恰好是从来没被挂过账的** ——
      而每圈「新增的那 1 笔账」都落在**当圈刚被碰过**的 sub 上；
      挂上的账又在 1~2 圈内被 `清偿`（圈 2、圈 4 各清偿 1 笔）。
    ⇒ 两条条件在时间上**互相错开**：被挂账的都在动，不动的都没挂账。

  ★ 这不是 bug，是**设计前提在当前 prompt 行为下几乎不成立**：
    `_starve_escalation` 的注释明写「只认挂着的账当证据」（为防它乱判
    不可判定）。所以机制一**不是「差题」，而是「差一个会先挂账再晾着的题」**。
    要它可达，得先回答一个**设计问题**（见下「遗留 2」）——
    **已拍板：接受为「设计上狭窄」并保留，不再换题。**

  ────────────────────────────────────────────────────────
  验证与遗留
  ────────────────────────────────────────────────────────

  **冒烟**：新增 `check_v65_starve_render`（4 条断言）；全套 exit 0 / 0 ✗。

  **遗留（一条待做 + 一条已拍板）**：
    1. ★ `🍽` 报的是**最终快照**，而计数按设计会被清零 —— G1 里圈 3/4
       明明够到过 1~2，最终却全 0。要回答「离门槛差多少」，需要**运行期
       峰值**（`_starve_max_seen`）。纯观测，1 处赋值 + 1 处渲染，
       但会改产物格式 → 单独一轮做。
    2. ★★ 机制一**已拍板（v1.21.65）：接受为「设计上狭窄」并保留**。
       它要求「名下有债」+「连续 N 圈没被碰」同时成立，而实测这两集合
       在时间上错开（被挂账的都在动、不动的都没挂账）。这种情况**确实少**，
       但机制本身正当 —— `_starve_escalation` 只认挂着的账当证据，
       为的是不拿「没人提」去乱判不可判定。
       ⇒ **不必再为它换题**，也不改「证据」的定义；等题面自然出现
       「先挂账、再连着 N 圈没人碰」时触发即可。

  ────────────────────────────────────────────────────────
  ★ v1.21.65 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.65.py（16980 行 / 纯 CRLF）；
    `_run_verif.py` 加 `--min-rounds`；`_audit_v64_zero_triggers.py` 的
    机制一探针接上 `🍽` 出口；smoke_test.py +`check_v65_starve_render`。

  **验证覆盖**：冒烟 exit 0 / 0 ✗；(B) 由 G1 日志里「被 min_rounds=5 拦截」
    直接证明；(A) 由冒烟的构造用例 + G1 产物里的 `🍽` 行双重证明。

  **经验教训**：**观测出口要报"能回答问题的那个量"**。(A) 报了最终值，
    而计数天生会被清零 —— 对"自然停"的层，最终值结构性地接近 0，
    等于把"离门槛差多少"这个问题又答糊了一次。**报峰值才是对的口径**。
  另：机制一最后**不是靠换题解决，而是拍板接受为「设计上狭窄」** ——
    当两条判据在真实数据上**结构性错开**时，正确动作是先用观测把它
    测清楚（G1 的 `🍽` 行证实了「错开」），再决定「改机制」还是「认下」，
    而不是往「换个更难的题」上使劲。

  **档期修订（同日）**：本段 changelog 曾因脚本重复插入而**整段出现
    两次**（去重删去 101 行重复副本）；同时把「遗留 2」从"待拍板"
    更新为**已拍板**。

════════════════════════════════════════════════════════════
v1.21.64 相对 v1.21.63 的改动（留痕兑现 + 口径修正 + 零触发审计）
════════════════════════════════════════════════════════════

  本轮三件事：A 把 v1.21.62 起就承诺的 pool.meta 渲染兑现；
  B 把 by_id 从「只数 active」改成「数池里真实存在」；
  C 用已有真跑产物审计 v1.21.60 遗留的四项零触发机制。
  ★ C 是**只读审计** —— 不改主文件、不预设结论、只为下一轮定方向。

  ────────────────────────────────────────────────────────
  [A] pool.meta 渲染兑现（v1.21.62 起承诺，一直欠着）
  ────────────────────────────────────────────────────────

  **根因**：v1.21.62 的 [P1-6 修] 声称「被拦下的 deferral 进
  view.errors + pool.meta 两份留痕」。v1.21.63 的 C2 段自己承认
  「`pool.meta` 实测不进产物」—— `packed["pools"]` 里有，但「## 池」
  段只打计数、`_pool_shape` 不含 meta，**读产物的人看不到**。
  而 `view.errors` 每圈新建会丢、`pool.meta` 跨圈累积 ——
  **真正扛「中间圈留痕」的那份反而没出口**。

  **做法**：
    · `save_result` 的「## 池」段每个池加一行：
      `- 📝 池级留痕（pool.meta）N 条：P1-6 拦截 a / 自省回流 b / …`
    · `render_landing` 顶部加一句汇总：`**池级留痕**：N 条（分类计数）`
    · 分类判据按前缀：`[P1-6]` / `[自省回流未生效]` / 含 "self-check"
      或 "上一圈" / 其它。

  **验证**：冒烟 `check_v64_pool_meta_render`（构造最小 packed result，
  跑真 `save_result` 落盘再 grep 产物）—— 池段与落地层顶部的行都在、
  三类分类都识别对。真跑侧见下「真跑证据」。

  ────────────────────────────────────────────────────────
  [B] by_id 口径修正（v1.21.63 自己在「已知遗留」里认过）
  ────────────────────────────────────────────────────────

  **根因**：v1.21.63 的 `_settle_meta` 里 `by_id` **只对最终 active 的
  对撞张力计数**（`for s in duel: … by_id += 1`）。元层引用一个
  **已 resolved** 的编号（例如 t_001）—— 这本身是**有效交代**
  （交代了历史张力）—— 但因为它不在 `duel` 里，不被计入。
  v1.21.63 changelog 自己写「本轮就有这种」。

  **做法**：`by_id = len(_covered_ids & _all_duel_ids)`（无论状态）；
  `uncovered` 仍只对 active 计（已了结的本来就不该进 uncovered）。
  ★ 顺手把 v1.21.63 里**重算一遍** `_all_tids` 的地方改成复用同一份
    集合 —— 同一份逻辑不许两处各写一份。

  **验证**：冒烟 `check_v64_by_id_scope`（2 active + 1 resolved，
  元层引用 3 个真实编号 + 1 个不存在编号）→ by_id=3 / covered_ids=4 /
  inactive=1 / unknown=1 / unsettled=0。真跑侧见下。

  ────────────────────────────────────────────────────────
  [C] 零触发机制审计（v1.21.60 遗留四项）
  ────────────────────────────────────────────────────────

  **目标**：用**已有的真跑产物**（v1.21.63 D3：135 calls / 39.1min）
  回答：四项零触发机制 —— `escalate_starve_rounds=2` /
  `no_push_when_idle=1` / `_reopen_closed_debt` / `stable_layers 2→3`
  —— 在那一跑里**有没有触发？没触发的话差什么？**

  **做法**：新增**只读**独立脚本 `_audit_v64_zero_triggers.py`：
    · 输入：产物 md（默认取 outputs/ 最新一份）+ 可选 `--log` 真跑日志
    · 输出：审计报告（控制台 + `audit_zero_triggers_<ts>.md`）
    · 每个机制三段：**直接证据** / **离触发差多少** / **设计方向**

  ★ 与提示词版的两处不同（都是为了审计**不空转**）：
    1. 加了 `--log`。只读产物 md 时，很多「没触发」其实是「产物里没有
       这个渲染点」。真跑 verbose 日志里有更硬的证据（例如机制二的
       `[fix-88b] … 不推迟`），读它才能分清「没触发」和「看不到」。
    2. 加了「格式自检」段：逐条说明每个探针期望的渲染格式在本产物里
       **存在 / 不存在**；不存在时显式写「本产物无法回答」，不把 0
       当成「没触发」。
    ★ 提示词给的脚本原文有几十处 ASCII 引号嵌套（会把字符串提前闭合，
      直接 SyntaxError），这里按意图改写成可执行版本。

  **审计结果（读 v1.21.63 D3 产物 + verif_D3_v63.log）**：
    · 机制一 `escalate_starve_rounds=2`：**0 次**。直接证据：日志里
      「迁向不可判定」0 处；全部 `⏳ 债务` 行的「升级」合计 = 0。
      差什么：D3 研究层 3 圈、子问题 6 条，但每个子问题都被
      「深入/回答」触碰过（债务行里 `深入N` 非 0）→ **没有出现
      「连续 2 圈无进展」的子问题**。差的是**题的结构**，不是圈数。
      设计方向：选一道研究层**一次挂多个 deferral、圈数不够逐个碰**的题。
    · 机制二 `no_push_when_idle=1`：★ **已触发，3 次** ——
      日志里 `⚠️ [fix-88b] 有 N 条未深入方向，但停止判据是空转类
      （再给一圈也消化不掉），不推迟` 出现 3 处（N=4/4/6）；
      产物侧有 3 层（`1` / `both` / `all`）的螺旋停止是空转类。
      ⇒ **该机制不再是「零触发」**。
    · 机制三 `_reopen_closed_debt`：**0 次，且结构上不可达** ——
      它的前置是机制一（得先有人迁向 undecidable 才谈得上被救回），
      机制一 0 次 ⇒ 机制三没有机会。
      格式自检：本版本渲染的是累计**覆盖轨迹**，**没有**逐条
      「不可判定→可判定」账 → 这一项的 0 **不能**单独当证明。
    · 机制四 `stable_layers 2→3`：**0 次，但结构上可达** ——
      元层走了 4 圈（≥3）；`自然安住` 0 处、`转稳` 全场 0。
      差的是「悬置决定连续 3 圈保持同一批」：元层每圈都还在
      新增/撤回，**批次没稳下来**。设计方向：选价值选择 / 制度设计类
      （边界模糊、悬置明显）的题。
    · 格式自检：4 个机制探针里 3 个有渲染点（螺旋停止 4/4 层、
      实际圈数 4/4 层、延迟债务 `{1:1, all:1}`），1 个无渲染点
      （逐条变更账）—— 已显式标注。

  **纪律**：**不改主文件**。审计结论已落报告；下一轮**据此**决定要不要
  动判据 / 设计新题 —— **不许拍脑袋收紧**。

  ────────────────────────────────────────────────────────
  真跑证据（一次，v1.21.64）
  ────────────────────────────────────────────────────────

  **选题依据**：题面从**已有题库** `upstream_batch01.txt` 的
  「6 领域各 1 题」（tech / biz / med / eng / law / org）里选，用 **org 类**
  ——「政府或企业内部多个部门要共享数据提升效率，但涉及隐私和权限，
  边界怎么划？」。选它的理由有两条：
    · 与已跑过的题不重复（D3 抽象题 / D4 欧盟 / D5 biz）；
    · 它是「边界怎么划」，天然产生多个悬置与张力 → 正好给审计报告
      里「机制四差的是悬置批次没稳下来 / 机制一差的是没出现连续
      无进展」这两条**设计方向**一个机会（附带观测，不是主目的）。

  配置：`--route 0,1,both,all --rounds "0:3,1:4,both:5,all:5"
  --mode serial --orientation boundary`（与 D3/D4/D5 同口径，
  便于横向比）。

  **跑**：`E2_v64`，149 calls / 36.5min，dispatch 四层齐、missing 空。

  **A 的验收（真产物）** —— `池级留痕` 在产物里出现 **5 处**：
    · 落地层顶部：`**池级留痕**：41 条（自省回流未生效 5 / 自省反馈 5 / 其它 31）`
    · 池段 4 行（0/1/both/all 各一行）：`8 / 8 / 14 / 11 条`，合计正好 41 —— 两处口径一致。
  **B 的验收**：`by_id = 4`、`covered_ids = 4`、`by_id_inactive = 0`、`by_id_unknown = 0`、`clean = True`；元层引用的 `t_009 / t_008 / t_006 / t_005` **四个全在对撞池里**。（本跑引用的都是 active，旧口径也会是 4 —— **口径差异由冒烟的构造用例区分**，真跑只作不倒退的回归。）
  **附带观测（本题给审计的两个「设计方向」各一次机会）**：
    · 机制四 **被触发了** —— 元层第 4 圈「悬置决定稳定，自然安住，螺旋停止」（`转稳2`）→ 见 `audit_zero_triggers_E2.md`。
    · 机制一 仍是 0（`迁向不可判定` 0 处）—— 这道题的子问题同样都被「深入/回答」触碰过。
  ⇒ **遗留四项里已有两项拿到真跑证据（机制二 · 机制四），剩两项的成因写清楚了**。

  ────────────────────────────────────────────────────────
  验证与遗留
  ────────────────────────────────────────────────────────

  **冒烟**：新增 `check_v64_pool_meta_render`（5 条断言）+
  `check_v64_by_id_scope`（5 条断言）；全套 exit 0 / 0 个 ✗（新增 10 条断言）。
  全库回归 `_regress_revisit.py`：1265 条真实条件放行 1239（97.9%）。

  **已知遗留**：
    1. 逐条「不可判定→可判定」在产物里仍无渲染点（只渲染累计轨迹）
       —— 机制三的产物侧证据因此不可读，只能靠日志。
    2. 机制一/四本轮 0 次：不是判据错了，是**该跑的题没有那个结构**。
       下一轮按审计给的「设计方向」选题，别去动判据。

════════════════════════════════════════════════════════════
v1.21.63 相对 v1.21.62 的改动（C 段修复 + 三项可观测性）
════════════════════════════════════════════════════════════

  本轮由 v1.21.62 的真跑验收（A/B/C 三段）驱动：A 通过、B 通过但暴露
  `view.errors` 跨圈丢失、C 未生效。三项可观测性来自对 v9.1 的哲学层复查。
  ★ 三条都用真跑验收过；本轮一共跑了 5 次真跑（168/166/172/187 + 注入版），
    每一次的数字都写进下面各段——**没验过的东西不写进来**。

  ────────────────────────────────────────────────────────
  [C1] 元层 tension_id 对账：**根因不在 prompt，在接线**
  ────────────────────────────────────────────────────────

  **症状**：`meta_closure.by_id` 连续三次真跑恒为 0 ——
    168 calls/37.7min（v1.21.62）、166 calls/39.9min、172 calls/44.5min。

  **根因（第 4 轮才查到底，前 3 轮都猜错了）**：
    `_ENTRY_DEPS = {"0": (), "1": (), "both": ("0","1"), "all": ()}`
    是**调度**表 —— "all" 不硬等任何层（靠软闸放行），所以 `"all": ()`
    对调度是对的。但它被**复用**去做**内容**查找：
      · `_make_pipeline_provider` / `_make_jacobi_provider` 都**单独**
        给 "all" 补了 `("0","1","both")`（说明差异早被发现过）；
      · **唯独 `_make_serial_provider` 漏了** → `provider("all")` 恒空
        → `_build_inp_meta` 走 `if len(up) < 2: return Input(无 upstream)`
        → 元层从第一圈到最后一圈都**看不到对撞张力清单**。
    留下的铁证：解析处的留痕写着「当前可引用的只有 **[]**」——
    清单是空的，模型只能自造（`t_all_residual` / `s_001` / `t_000`）。
    ⇒ 因此 prompt 再怎么写都没用：**清单里根本没有编号可抄**。

  ★ 这是本项目第 5 次「同一条逻辑两条通道各写一份」：四个 provider 里
    三个补了、一个漏了。修法是把差异**收口成一张表**：
    `_ENTRY_CONTENT_DEPS = {"0": (), "1": (), "both": ("0","1"),
                            "all": ("0","1","both")}`，
    三条 provider 全读它。另把元层的 `len(up) < 2` 守卫放宽成 `not up`
    —— route 不含 both 时上游仍有 0/1 两条，旧守卫会把它们一起丢掉。

  **prompt 侧的两处收口（仍然要做，但只是必要条件）**：
    · `_probe_meta` / `_phase_probe` 的 JSON schema 里 `t_001` / `s_001` /
      `s_002` 全部换成占位符（实测模型会把示例字面量原样抄回来）；
    · 明写**两套编号不能互换**（`t_` = 对撞层张力编号 → `tension_id`；
      `s_` = 元层自己的悬置编号 → `suspension_id`）。实测模型确实把
      `s_001` 填进了 `tension_id`。
    ★ 教训：上一条把 `t_001` 去掉、却又在指令里写进 `[t_005]` ——
      **新引入的示例和旧示例一样会泄漏**。

  **代码侧的确定性校验 + 留痕（失败必须留痕）**：
    · 解析 engagements 时，引用的编号必须**此刻真在清单里**；不在就写
      `view.errors`，且**区分两种错**：池里有但已了结（口径问题）/
      池里根本没有（自造 / 抄示例 / 串了命名空间）。
    · `_settle_meta` 把"没命中"拆成 `by_id_inactive`（引用了已了结的）
      与 `by_id_unknown`（引用了不存在的），一起进产物。

  **验证**：D3 真跑（135 calls / 39.1min（同命令，0 层减到 3 圈））——
    对撞张力 9 条（active 4 条 —— t_006 / t_007 / t_008 / t_009）；
    元层 engagements 的 tension_id ['t_006', 't_009', 't_007']（**全部落在 active 清单内**）；
    `meta_closure`：by_id=**3**（首次 > 0） / covered_ids=3 /
    inactive=0 / unknown=0（不再自造/串号）、clean=True（未交代 0 类）。

  ────────────────────────────────────────────────────────
  [C2] view.errors 跨圈累积（B 段真跑暴露的限制）
  ────────────────────────────────────────────────────────

  **真跑实证**：`_run_layer` 每圈新建 view、`return view` 只交出**最后
  一圈**那个 → 中间圈的 `view.errors`（含 P1-6 的「deferral 被拦」）随
  view 一起丢。B3 真跑（route 0,1 / 0:2,1:4 / 每圈注入一条带圈号的必不
  合格 deferral）：`view.errors` 只剩**最后 1 条**，与改前一样；
  `pool.meta`（跨圈累积）收了 4 条。

  ★ 提示词给的收集点（放在 `dg.run(inp)` 之后）**收不到它** ——
    P1-6 的留痕是**同一圈更晚**在 `update_deferrals` 里写的。
    已在两处补收集点：serial 的 `update_deferrals` 之后 +
    B 通道的 `_b_lifecycle` 之后（C/D-H 都走 `_run_one_round_B`，
    两处即覆盖四条通道）。

  **验证**：B4 真跑（66 calls / 21.5min）**4/4 全在**，产物【失败记录】
  段可见「第 1/2/3/4 圈」四条。冒烟同时覆盖**早写者**（DGTF 内部）与
  **晚写者**（后置步骤）两个写入时机，并用**负对照**证明判别力
  （去掉新收集点 → 晚写者 1/3 → 断言失败）。

  ────────────────────────────────────────────────────────
  [P1] 悬置"一圈内自解"统计
  ────────────────────────────────────────────────────────

  **根因**（v9.1 复查）："LLM 不会真的悬置，LLM 永远在生成。"
  `SUSPENSION_VS_THREAD_RULE` 已经在 prompt 里要求悬置写成
  「我看清了 X，可以碰，但选择不碰，因为 Y」，但**没有统计**回答
  "模型有没有把'暂时没生成'包装成'决定不碰'"。

  **判据**：一条悬置若在**被创建的同一圈**就被 engagements 命中并
  resolved，它就不是"决定不碰"——决定不碰的东西不该在同一圈被碰。

  **做法**：`update_suspensions` / `update_duel_suspensions` 的 stats 加
  `self_resolved`（`x["layer"] == layer` 才计）；跑圈日志显示 `⚠️自解N`
  （`_run_layer` 与 `_b_lifecycle` 两条通道）；产物池统计段显示
  「其中一圈内自解 N/M（比例）」，比例 > 0.3 挂 ⚠️。

  **验证**：冒烟三条行为断言（同圈命中→1 / 旧账被碰→0 / 对撞层同口径）
  + 产物渲染断言。D3 真跑产物：见「池」段 「0/2（0%）」「1/6（17%）」—— 都低于 0.3，未挂 ⚠️。

  ────────────────────────────────────────────────────────
  [P2] 产物显式承认"没有外部锚点"
  ────────────────────────────────────────────────────────

  **根因**（v9.1 复查）："螺旋跑 N 层，到底是'逼近真理'还是'绕圈'？
  没有外部锚点，容易自我强化。" ★ 这不是缺陷（DGTF 的目标是"显形过程"
  不是"逼近真理"），但**产物应该自己说出来**。

  **做法**：`save_result` 头部加 `**外部锚点**：无（…设计边界，不是
  缺陷）`；`render_manifestation` 的"没有显化的"段**永远**列一条外部
  锚点（不再"没有缺点就不列"）。

  **验证**：冒烟断言 + D3 产物头部与显化段各 1 处。

  ────────────────────────────────────────────────────────
  [P3] 「语义不一致 → 结构信号」观测
  ────────────────────────────────────────────────────────

  **根因**（v9.1 复查）："'0/1/both'是本体论范畴，但 LLM 判断极性靠的是
  语义相似，不是存在状态。" `attribute` 已代码锚定，`position` 仍由 LLM
  判断；`&` 候选（attribute != position）的出生地就是这两者的不一致。

  **做法**：`DGTF.run` 记 `view._amp_cand_count`；
  `_run_layer` / `_b_merge` **逐圈累加**到 `all_amp_cands`（与
  `all_amps` 同口径）；`_finalize_layer_common` 追加一条到
  `view.meta`（走【元反思】段渲染）。

  ★ **D1 真跑暴露的第一版指标是假的**：分母取"最后一圈"的候选数、
    分子取跨圈累加的 `view.amps` → 实测出 750% / 283% 这种 >100% 的
    "转化率"。修法：分母改成逐圈累加，并且**不再叫"转化率"**
    （amps 还可能含 adjudications / 上游合并的贡献，比值只作方向参考）；
    ⚠️ 只在"候选有、amps 一条都没有"时挂 —— 那才是真的没落地。

  **验证**：冒烟四条源码断言 + D3 产物【元反思】段的比值 0.61 / 0.64 / 0.48（都在 1 以内，不再是 750% 那种假比值）。

  ────────────────────────────────────────────────────────
  验证与遗留
  ────────────────────────────────────────────────────────

  **冒烟**：新增 `check_v63_c_fixes`（13 条结构 + 4 条行为）与
  `check_v63_observability`（6 条）。全套 exit 0 / 0 个 ✗。
  另加 `_regress_revisit.py` 全库回归：1254 条真实条件放行 1227（97.8%）。

  **真跑**：D3（--route 0,1,both,all --rounds "0:3,1:4,both:5,all:5"
  --mode serial --orientation boundary）135 calls / 39.1min；dispatch 四层齐、missing 空。

  **已知遗留（未改，留给下一轮）**：
    · `by_id` 只对**最终 active** 的对撞张力计数；早期被引用、后来
      resolved 的编号即使填对也计不进来（本轮就有这种）。现在至少
      `by_id_inactive` 会把它显出来，不再无声。
    · `pool.meta` 仍无产物渲染点（"## 池"段只打计数）—— 留痕的产物
      可见性由 `view.errors` 独担；这一条如实记着。

  ────────────────────────────────────────────────────────
  ★ v1.21.63 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.63.py（16558 行 / 纯 CRLF）；
    smoke_test.py（+check_v63_c_fixes 17 条 / +check_v63_observability 6 条）；
    _regress_revisit.py（全库回归，只读）；v63_收束报告.md（编号分节）。

  **验证覆盖**：
    · 冒烟 exit 0 / 0 个 ✗；判据/阈值与 62 版**一字未动**
      （_SUSP_SAME_SIM / SUSPENSION_VS_THREAD_RULE / both_tighten_ratio
      三个常量的出现次数与 62 完全一致）。
    · 全库回归 1265 条真实 revisit_condition：放行 1239（97.9%）。
    · 真跑 3 次（换题，n=3）：D3 135 calls / 39.1min、D4 159 / 43.6min、
      D5 154 / 40.9min；三次 dispatch 四层齐、missing 空。
    · C1：by_id = 3 / 4 / 2，unknown = 0（三次都 0），inactive = 0，
      clean = True×3 → **可以结案**。
    · P1 自解比例：0% / 0–17% / 80% ← ★ **组内极差 80 个百分点**。
    · P3 比值：12 个观测落在 0.21–2.00（中位 ≈0.7），>1 出现 3 次。

  **已知遗留**：
    1. by_id 只对**最终 active** 计数（口径待定：是否把 +inactive 也算命中）。
    2. pool.meta 无产物渲染点，留痕可见性由 view.errors 独担。
    3. 自解比例 n=3 方差过大（0%~80%），**不能**据此改机制 —— 下一轮做
       专项（预注册判据 + ≥5 题），再决定"改 prompt"还是"改行为层约束"。
       ★ 这条正是本项目自己的纪律：新指标先测饱和度与重复观测，
         单次／少次观测一律先当噪声。

  **经验教训（三条，已同步 MEMORY.md）**：
    1. **手造输入会绕过生产接线** —— 上一轮用"手搭一个 Input 传 upstream"
       证明了"接线是对的"，而 bug 恰在那个被绕过的地方。**验接线要用
       生产入口**（调真实 provider / 跑整条 run），别手搭输入。
    2. **一张表两个用途必漂** —— 调度依赖 ≠ 内容依赖。四个 provider 里
       三个单独补过、一个漏了，这类"三处对一处错"最难查，因为看起来是对的。
    3. **留痕要说清原因** —— 这次救命的是「当前可引用的只有 []」这一句。
       校验类代码要把"**为什么**判它不合格"写进留痕，而不只写"不合格"。

════════════════════════════════════════════════════════════
v1.21.62 相对 v1.21.61 的改动（工艺改进 · 六步 + 三底线）
════════════════════════════════════════════════════════════

  [P0-1] 锚点重述补全 touched —— 重述必须带出"已被触及的"
  [P0-2] "至少碰一个"从 prompt 软约束改成代码硬约束（重试一次）
  [P0-3] 产物三种状态视觉区分（💭未决 / ⏸悬置 / 📘不可判定）
  [P1-4] ing 输出加结构化尾块（shared/tensions/third）
  [P1-5] 对撞层 he 独立 prompt（& 必须带 tension_from）
  [P1-6] revisit_condition 从黑名单改白名单（要求可观测锚点）
  [P2-7] _route_by_decidability 判据从"能不能判"改成"想要什么"
  [P2-8] auto_plan 拆成 plan_orientation + plan_resources
  [P2-9] 加显化层 render_manifestation
  [P3-10] 元层 tension_id 对账 —— 待真跑验证（不改代码）
  [P3-11] 三态判决一致率加可信度分级

  ────────────────────────────────────────────────────────
  [P1-6 修] revisit_condition 白名单**做反了** —— 98% 真实条件被静默吞掉
  ────────────────────────────────────────────────────────

  **问题**：v1.21.62 初版白名单只有 6 条 pattern（全是"当X动词"一族句式），
  实测全库 1213 条真实 revisit_condition **只放行 24 条（2.0%）**，
  1189 条被拦下。被拦下的多是明显合法的（"T2探针给出边界判据后"、
  "谓词类型区分完成后"、"相对化屏障被形式化后"）。
  更严重的是被拦下的 deferral 只 `stats["invalid"] += 1` 然后 continue，
  **不进 vp、不进产物、不进池**——98% 的账在用户不知情下消失，
  违反宪法级"失败必须留痕"。

  **修法**（两处）：
  1. **白名单扩充成三类宽特征**（召回优先）：①时间/条件词；②状态变化
     动词；③引用对象（T#/P#/S#/C#/d_###/ing/覆盖率/距离/权重）。
     再加一层兜底：长度 ≥ 10 且不含黑名单词 → 视为有具体描述。
     判据顺序：**先黑名单排除，再白名单放行**。目标召回 ≥ 90%。
  2. **被拦下的必须留痕**：进 `view.errors`（→ 产物【失败记录】段，
     **这才是产物可见性的唯一承载**）+ `pool.meta`（进 packed 的 pools，
     但本版「## 池」段只打计数、`_pool_shape` 也不含 meta —— 所以它
     **不进产物**，且会被 `_apply_keep` 在 keep 受限时清掉）。限流 20 条
     防刷屏；超过 20 条时写一条汇总。

  **验证**：冒烟新增 4 条断言 —— 边界 13 例双向（纯空词拦 / 各类合法
  条件通过 / 长度兜底通过 / 长度不足拦）；3 条被拦时 view.errors 与
  pool.meta 各 3 条且合格那条照常入池；30 条被拦时明细封顶 20 条 +
  meta 一条汇总；渲染路径断言产物 md 里查得到「deferral 被拦」。
  新旧白名单对照重跑同一 1213 条真实条件：**放行 1147 条（94.6%）**，
  仍拦 66 条（5.4%）。

  ────────────────────────────────────────────────────────
  [P1-6 修-2] 白名单微调：长度兜底 10→8 + 补获取/核查动词族
  ────────────────────────────────────────────────────────
  起因：修-1 后仍拦 66/1213（5.4%），其中大多数是合法条件
  （"拿到两项金额"、"取到部署顺序记录"、"调上月现金流量表"）。
  本次：兜底 8 字 + 补 10 个动词（拿到|取到|取得|查到|抄出|
  核出|调出|调取|观测|比对）。
  实测：放行率 **98.0%**（1189/1213，拦 24 条）—— 脚本
  `_regress_revisit.py`（独立、只读，可复跑）输出：
    样本 1213 / 放行 1189（98.0%）/ 拦下 24（2.0%）；
    对照：旧 6 条 pattern 口径放行 24 条（2.0%）。
  残留 24 条多为短碎片（"裁决侧落位"、"当一种格式"、"原文未给"、
  "引入并测"），少数是可辩的短引用（"第25条"、"查第43条"、
  "探针3有结果"、"找到可判决实例"——汉字编号/找到 不在引用与动词
  族里）。
  ★ 不再继续压：剩下的应是真正模糊的边界，**没有模糊边界的
    判据 = 精确率换召回率**——这一轮到此为止。
  ★ 补一条判据顺序的护栏：黑名单必须**先于**长度兜底生效。
    冒烟里放了两条够长却该拦的用例（"等以后再处理这件事" 9 字、
    "看情况再说吧后面再定" 10 字）钉住这个顺序 —— 否则把兜底下调
    就等于把黑名单架空。

  ────────────────────────────────────────────────────────
  [收尾验证] A/B/C 三段（2026-10-03，含两轮真跑）
  ────────────────────────────────────────────────────────

  A · P1-6 白名单微调：兜底 10→8 + 补 10 个获取/核查动词
    （拿到|取到|取得|查到|抄出|核出|调出|调取|观测|比对）。
    全库回归 1213 条：放行 **1189 条（98.0%）**，拦 24 条（2.0%）。
    残留 24 条多为短碎片（"裁决侧落位"、"当一种格式"、"原文未给"）；
    少许可辩的短引用（"第25条"、"查第43条"、"探针3有结果"）——
    汉字编号形式不在 _REVISIT_CITATION 里。**不再放宽**。

  B · 留痕链路端到端（真跑 #1）：route 0,1 / 0:2,1:4 / serial
    63 calls · 15.0min · served_by=deepseek-flash
    用**临时注入版**（单独复制成 _tmp_B_inject.py，**未动交付文件**）：
    _valid_revisit 拒魔法子串 + 每圈塞一条必然不合格的 deferral。
    产物 20261003_073317_*.md：grep "deferral 被拦" = 1 处，
    【失败记录】段里是完整描述（"子问题[1] 条件='ZZTEST_INVALID…'"）。
    ★ 结论：view.errors → save_result → 产物 这条链路**通**。
    ★ 但第一跑（只在第 1 圈注入）**什么都没留下** —— `_run_layer`
      每圈新建 view、`return view` 只交出**最后一圈**那个，中间圈的
      view.errors 随 view 一起丢。同一场景下 pool.meta（跨圈累积）收了
      4 条，view.errors 只剩 1 条。
      ⇒ **P1-6 留痕只在最后一圈可靠**；中间圈被拦的 deferral 无痕。
        本版**未改**（要改得让 errors 跨圈累积）—— 这是新发现的限制。
    ★ pool.meta 实测**不进产物**（"## 池"段只打计数、_pool_shape 不含
      meta），与 [P1-6 修] 的补记一致：产物可见性由 view.errors 独担。

  C · 元层 tension_id 对账（真跑 #2／P3-10）：
    route 0,1,both,all / 0:4,1:4,both:5,all:5 / serial / boundary
    168 calls · 37.7min · 产物 20261003_074320_*.md
    ① 对撞层编号：**发得出来** —— duel_suspensions 7 条 t_001~t_007
      （active 3 条 t_005/006/007；resolved/revoked 4 条被正确排除）。
    ② 元层引用：**写了但抄错** —— all 层 engagements 里 3 条写 t_001、
      2 条写 t_none，与实际 active 编号（t_005~t_007）**无一匹配**。
    ③ meta_closure：by_id=**0**、covered_ids=2、clean=False、
      total=3／unsettled=3、closed=4、duel_total=7。
    ④ by_id / covered_ids **未渲染进产物**（只打 clean/total/unsettled/
      closed/duel_total/uncovered）→ 本版不改，如实记。
    ★ 根因（离线单测证，不靠推断）：**wiring 是对的** —— 元层 probe 的
      user 里确实列了 `[t_005]（③）…`、`[t_006]（③）…`，resolved 的
      t_001 被正确排除。问题在 **prompt 里的字面示例被抄走**：
        · system 的 JSON schema 里 `"tension_id":"t_001"` 出现 2 次；
        · user 里还写着「带上它的编号（t_001）」。
      模型于是照抄 t_001（一个已 resolved 的旧号）。
      ⇒ **P3-10 未真正生效**。下一轮第一件事：把示例字面量改成占位符
        （如 `"<从清单原样复制>"`）并明写"不许自造编号"。
        这部分属提示词问题、不是 bug，**本版不改**，留给下一轮。

  ────────────────────────────────────────────────────────
  [收尾·第四轮] 编号占位符 / view.errors 跨圈累积 / by_id 渲染
  ────────────────────────────────────────────────────────

  三处改动（按提示词落地）：
  1. [P3-10 修] 元层 probe 的 schema 去掉 `"t_001"` 字面示例 → 换
     `<从清单原样复制>`；user 改成硬指令（原样复制 / 不许自造 / 不许抄示例）。
  2. [P1-6 补] `view.errors` 跨圈累积：`_run_layer` 每圈新建 view、只
     return 最后一圈 → 中间圈留痕随 view 丢。
  3. [P3-10 补] 产物【闭环清算】段补渲染 `by_id` / `covered_ids`。

  ★ 改动 2 有个坑（真跑暴露，已修）：提示词的收集点放在 `dg.run(inp)`
    之后，但 P1-6 的留痕是**同一圈更晚**在 `update_deferrals` 里写进
    view.errors 的 → 那个点收不到它。真跑 B3（route 0,1 / 1:4 圈，每圈
    注入一条带圈号的必不合格 deferral）实测：view.errors 只剩**最后 1 条**
    （第 4 圈），与改前一样。已在两处补收集点（serial 的 update_deferrals
    之后、B 通道的 `_b_lifecycle` 之后）→ 真跑 B4 实测 **4/4 全在**，
    产物【失败记录】段可见「第 1/2/3/4 圈」四条。
    冒烟断言同步修了：旧断言只注入在 `DGTF.run` 内部（**早写者**），所以
    假通过；现在**早/晚两个写入时机都验**（serial + B），并用负对照证明
    它有判别力（去掉新收集点 → 晚写者 1/3 → 断言失败）。
    覆盖范围：全库只有 3 个 `dg.run(` 调用点，2 个是跑圈通道（serial /
    `_run_one_round_B`），C/D-H 模式都调 `_run_one_round_B` → 两处补点即
    覆盖四条通道，不必各写一份。

  ★ 改动 1 的验证：**未达标**。C2（同命令：0,1,both,all /
    0:4,1:4,both:5,all:5 / serial / boundary，187 calls · 49.9min）
    `meta_closure.by_id = 0`、`covered_ids = 5` —— 与改前一样。
    失败模式变了，也更清楚：all 层 engagements 填的 tension_id 是
      · `t_001`（×1；对撞池里存在，但已 resolved）
      · `s_001` / `s_002` / `s_003`（×4）—— **元层自己的悬置编号**
      · `（无）`（×1）
    根因（离线清点 prompt 得，不靠推断）：
      · system 的 JSON schema 里还剩 `"s_001"` / `"s_002"` 两个字面示例
        （reconfirmations / revocations 的 `suspension_id`）；
      · 新写的 user 硬指令里又引入了 `[t_005]` 字面（本轮 active 集是
        t_004/006/008/009/010，[t_005] 不在其中）；
      · 更根本的是**两套编号挤在一个 JSON 块里**：`tension_id` 要 t_XXX、
        `suspension_id` 要 s_XXX，而【元层之前的悬置决定】清单显示的正是
        `[s_XXX]` → 模型把 s_ 填进了 tension_id。
    ⇒ 下一轮该做：把**全部**示例字面量换成占位符 + 明写"两套编号不能
      互换"。另有一条口径待定：`by_id` 只对**最终 active** 的对撞张力
      计数，早期被引用、后来 resolved 的编号即使填对也计不进来
      （本轮 t_001 就是这种）。
    本版**不再改**（一次只动一个变量），留给下一轮。

  ────────────────────────────────────────────────────────
  [应用记录] 本段由编码助手按补丁逐条落地后的实测与核对
  ────────────────────────────────────────────────────────

  · 来源：v1.21.62 完整补丁。补丁共 25 对「查找/替换」+ 4 段按标记
    插入，已逐条断言「命中且唯一」后落地（开版脚本：_apply_62.py）。
  · ★ 补丁漏洞（已修，否则跑不起来）：_re_anchor 开头有一段**提前
    返回**（entry in (both, all) 且 inp.root_question 的透传路径），
    补丁的「查找」块从 system = ( 开始，漏掉了它 → both/all 层按三元组
    unpack 时抛 ValueError，整层变 missing。冒烟的 P1-4 条正是靠这条
    暴露的（route 含 both 时必挂）。已补成 return 三元组（后两项为空，
    透传不是重述，语义正确）。
  · ★ 补丁未覆盖的连带项（已补齐，否则静默降级）：auto_plan 拆成
    plan_orientation / plan_resources 后 stage 名变了，而
    api.thinking.stages 里没有新名 → thinking_stages.get() 取不到，
    两次规划调用会从 "enabled" **静默**掉回 default("disabled")。
    已把两个新 stage 名同时加进 DEFAULT_CONFIG 与 dgtf_config.yaml
    （值 enabled），旧键 auto_plan 保留不动。
  · ★ 实测发现（[P1-6] 本次已修；其余三条留给下版决定）：
    - [P1-6 已修 · 两轮] 白名单过窄 + 失败无声。全库 outputs/*.md 里
      真实渲染出的 revisit_condition 干净抽出 1213 条：
        · 初版（6 条 pattern）：放行 24 条（2.0%）—— 且被拦下的
          deferral 只记 stats["invalid"] += 1 后 continue，invalid
          **不在任何 vp / 产物渲染里** → 98% 的延迟债务无声消失，
          与红线「失败必须留痕」冲突。
        · 修-1（三类宽特征 + 长度兜底 10 + 留痕）：1147 条（94.6%）。
        · 修-2（兜底 10→8 + 补 10 个获取/核查动词）：**1189 条（98.0%）**，
          拦 24 条（2.0%）。
      残留 24 条见上文 [P1-6 修-2]；按提示词要求**不再放宽**。
      回归脚本 `_regress_revisit.py` 可复跑（只读，不改主文件）。
    - [P1-6 修·补记] 补丁说「进 view.errors + pool.meta（池段）」——实测
      本版 `pool.meta` **没有产物渲染点**（「## 池」段只打计数，
      `_pool_shape` 不含 meta；只有 View.meta 走【元反思】）。所以产物
      可见性实际全由 view.errors 承担；pool.meta 那半只进 packed，且
      `_apply_keep` 在 keep 受限（如 `--keep "0:amps:..."`）时会把它清掉。
      留痕仍然成立（冒烟已断言产物 md 可查），但"两份留痕"只兑现了一份。
    - _route_by_decidability 原 docstring 的 §7.16 / 负向探针实证在
      补丁里被删；已改成函数尾部注释保留，证据未删。
    - plan_resources 丢了 v1.21.61 的「低置信(x.xx)退回 serial」留痕：
      mode 仍会退回 serial，但 reason 里不再说明原因。
    - _interactive_run 这条入口没传 orientation（补丁只改了 CLI
      main 那处），交互模式恒 auto（按 decision 处理 + 打印提示）。
  · 验证：smoke_test.py 全绿（exit 0，0 个失败）。check_p162_units 共 13
    条断言，覆盖 P0-1 / P0-2 / P0-3 / P1-4 / P1-5 / P1-6 / P2-7 / P2-8 /
    P2-9 / P3-11，其中 [P1-6 修/修-2] 占 4 条（边界表 20 例双向、两份
    留痕、明细限流 + 汇总、渲染路径产物可查）；9 种并行模式 + auto 全跑通。
    另加 `_regress_revisit.py`（全库 1231 条真实条件回归，放行 97.9%）。
    真跑：B 段（留痕链路，63 calls／15min）通；C 段（元层 tension_id 对账，
    168 calls／37.7min）**未生效** —— 明细见上文 [收尾验证]。
    第四轮又跑了 B3/B4（66 calls／16.5+21.5min）与 C2（187 calls／49.9min）：
    跨圈留痕已修好（4/4），编号对账**仍未达标** —— 见 [收尾·第四轮]。

════════════════════════════════════════════════════════════
v1.21.61 相对 v1.21.60 的改动（承接真跑复核）
════════════════════════════════════════════════════════════

  [①][②] 两处源自**真跑实证**（真模型产物）；
  [③] 源自**端点实测**（对官方 API 逐个模型 ID 打的探针），不是自查推想。

  ────────────────────────────────────────────────────────
  [③] 模型 ID 迁移：摆脱 legacy 别名 + thinking 显式化（fix-111）
  ────────────────────────────────────────────────────────

  **起因**：起新批次前做了一次模型配置核查，查出三处缺陷。
  全部是**实测**结论——配置看起来是对的，这本身就是问题的一部分。

  **实测表**（2026-10-02，本账号 + 官方端点）：

    请求 model           实际 resp.model     thinking
    deepseek-chat        deepseek-flash      OFF
    deepseek-reasoner    deepseek-flash      ON
    deepseek-flash       deepseek-flash      ON（★ 默认就是开）
    deepseek-v4-flash    deepseek-flash      ON（兼容路由）
    deepseek-v4-pro      deepseek-v4-pro     ON
    乱写的名字           400，并列出可用名   —

  最后一行是**阴性对照**：乱写 ID 会明确报错，说明端点不会默默兜底。
  所以上面那些「返回 OK」是真的通了，不是假阳性。

  **改了什么**：

  1. **别名 → 显式 ID**。`default_model` / `reasoner_model` 都改成
     `deepseek-flash`，thinking 靠新的 `api.thinking` 段区分。
     官方公告 `deepseek-chat` / `deepseek-reasoner` 于 2026-07-24 停服；
     实测当天仍通，但 served_by 由服务端决定，不可控且此前无任何留痕。
  2. **`_is_reasoner()` 按名字猜 → 显式开关**。旧判据检查名字里有没有
     "reasoner"/"-r1"/"reasoning"，对任何新式 ID 一律判 False：
     → 不再强制 `max_tokens≥32000`（推理 token 吃满预算 → finish_reason=length）
     → json_mode 走错分支。⚠️ 而且新配置里两个 ID **同名**，
       所以「`model == reasoner_model` 就算推理调用」这种改法会**把所有调用
       判成推理调用**——必须靠调用点显式传 `thinking=`。
     `_is_reasoner` 保留但标注废弃，只为兼容外部脚本。
  3. **served_by 留痕**。`LLM.last_served_by` 记录 `resp.model`，
     与请求不一致就 `logger.warning("模型别名漂移")`。
     2026-10-02 之前全部 124 跑都不知道自己实际跑的是哪个模型。

  **为什么这次迁移是行为保真的**（实测，不是推断）：

    旧 config(deepseek-chat)  vs  新 config(flash+thinking.disabled)
      → 同一道题输出**逐字同头**：len=84 / len=84，head 完全一致
    旧 config(deepseek-reasoner) vs 新 config(flash+thinking.enabled)
      → 都给推导过程；json_mode 两套都解析 OK
    同名不串档：default 与 reasoner 都叫 deepseek-flash，
      默认调用给「3 换行接推导式」（非思考，28 字），显式 enabled 给
      「3小时。接推导：…」（思考，52 字）—— 两个档位确实分开了。

  **顺带修掉的文档虚言**：yaml 注释宣称「DGTF_MODEL 覆盖本字段」，
  实际 `_deep_merge` 让**本文件覆盖环境变量**，与注释相反。已改正。
  另：`reasoner` 失败降级那段是对的（6255 确有），但降级语义已变
  —— 不再是"换模型"，而是"同模型关掉 thinking"，日志文案已改。

  **第 6 次单点刹车**：探针过程中非思考模式把水池题答成 2.4（错），
  思考模式答对 3。差点据此建议"默认开 thinking"。补一组 6 道可判分题
  → 两种模式都 6/6，信号消失。**那 6 道题同时暴露天花板饱和**（两组满分），
  本身没有判别力，不能用来分辨模型/模式差异。

  ────────────────────────────────────────────────────────
  [①] 「不可判定」落实范围：从「给了区分」到「给了两道闸」
  ────────────────────────────────────────────────────────

  **真跑实证**（post10G 池判原文，三条全被放进 undecidable_aspects）：
    · "授权链节点从哪来，不在 0/1 交换里，**此处未生**"
    · "追认前后两个日期哪个会被用来归责，**需适用动作**"
    · "同一义务句 0/1 并存持续多久，**由外部动作决定**"
  这三条全是**未决**，不是不可判定。

  **为什么 [⑧] 的区分没拦住**：它只讲了"未决 ≠ 不可判定"这一条**原则**，
  没给判据的**边界**。[⑨] 之后 F/G/H 改读 0 层跑满的完整形状，于是修行层
  产出的"此处未生 / 需外部动作"条目成倍增加，池评估从中挑"原则性对不上"
  就越容易 → **判定随「读多少材料」漂移**：欧盟法案在 1 圈薄形状下是
  decidable，读完整形状后**稳定变 partial**（fhgG 与 post10G 两次都变）。

  **做法**（`_assess_decidability_from_pool_view` 提示词）：一条要进
  undecidable_aspects 必须**同时**过两道闸——
    · 闸一（范围）：落在**核心诉求**上，不是"某一列的读法""某处的计数方式"；
    · 闸二（性质）：原则上判不出，并**点名排除**五类误判：此处未生 /
      需外部动作 / 计数需额外记录 / 定义未规定或文本没给次序（**可规定**）/
      两侧量纲不可比（**可分别报告**）。
  另加**主导性**规则：可判定方面明显占多数且核心诉求可判时，不让一两条
  局部细节把整体拉成 partial。

  ★ 自我约束：没有做成"partial 一律抹成 decidable"。地铁运营那道题的
  partial 是事实如此（上一轮已定论），闸一只挡**附属细节**，不挡核心诉求。

  ────────────────────────────────────────────────────────
  [②] reclassification 的 evidence：喂**校验用的那张表**
  ────────────────────────────────────────────────────────

  **真跑实证**：6 run 里只有 F 提过 2 条 reclassification，**全被驳回**——
    ⛔ 子问题[5]→可判定（证据在池中定位不到：['T8','T12']）
    ⛔ 子问题[6]→部分可判定（['T9','T10']）
  该圈池里线头只有个位数，T8/T12 根本不存在。

  **根因不只是"模型瞎编"，还有两套 T# 同屏**：
    · covers 用的 T# = `view.untouched` 的编号（只记录、**不校验**）；
    · evidence 校验用的 T# = `_citation_table` 里的 `pool.threads`。
  同一份提示词里两个 T# 指的不是同一批东西 → 模型从【本层未触及项】抄了
  T8 当 evidence，校验却去 pool.threads 找，必然定位不到。

  **做法**：
    · `_probe_research` 的 user 里新增【可引用的证据编号】，直接把
      `_citation_table(view, pool)`（**就是校验查的那张表**）摊给模型，
      喂的和查的是同一张，不会错位；
    · system 第 8 条与 und_text 的 nudge 都改为"照抄清单里的编号"，
      明说清单外一律定位不到；
    · 清单里点明两套 T# 各管各的（清单给 evidence，未触及项给 covers）。
  ★ 不动编号体系本身：covers 不校验，改命名体系动静大且没必要。

  **验证**：冒烟 58 项全绿。①②都是 LLM 提示词改动，**必须真跑确认**：
  ① 看欧盟法案是否从 partial 回到 decidable、地铁运营是否**仍**是 partial
  （若也变 decidable 就是过度修正，要回退）；② 看 reclassification 是否
  从"提出即驳回"变成有**成立**的。

  ────────────────────────────────────────────────────────
  [③] 把「判定对不对」的判据**换成可自动查的东西**（不再死记期望值）
  ────────────────────────────────────────────────────────

  **起因（同一处连栽两次）**：
    · 上一轮我先预设"地铁运营该 decidable"，把它的 partial 当成修复没生效；
    · 这一轮我改完又预设"地铁运营该 partial"，把它的 decidable 当成过度修正。
  两次都是**拿预设当判据**。预设是猜的：题面问"用什么指标、数据从哪来"，
  这句话本身就在问操作化，判 decidable 并非说不通。

  **判据换成两条能自动查的**：
    1. **池判与外判分不分叉** —— 两路各列了什么、理由是否成立；
    2. **每条不可判定有没有池内追溯** —— 没追溯的就是凭空说的。
  判定的**值**（decidable / partial）只是结果，不是判据。

  **做法**：
    · `_merge_decidability` 落 `_pool_status`（原来只留 `_ext_status`，
      分叉时**查不到池判当时说了什么**）+ `_und_untraced`；
    · 新增 `_untraced_undecidable(und_aspects, evidences)`：逐条核对
      undecidable_aspects 有没有 evidence 对得上，挑出没追溯的；
    · 新增 `_stamp_decidability_criteria()`，**所有出口**都盖戳——
      ★ 单边路径（external-only / pool-only / off）**没有分叉可言**，
        `_divergent` 记 False 而不是缺失（缺失 = 验收无从下手）；
      ★ `_und_untraced` 只在**有池**的路径算：外判本就没有池可追溯，
        拿"无池内追溯"否定它的理由是误报，故 external-only 时置空；
    · 日志：分叉行明写两路状态（`池=partial / 外=decidable`），
      无追溯的不可判定条目**当场点名**；
    · 汇总（`_run_v60.py`）新增两行：`分叉=…(池=…/外=…)`、`无追溯=N`。

  ★ 这个改动**当场就抓到了东西**：新加的冒烟 [P0-3] 一跑就报
  `D/E: _divergent 缺失`、`A(no-all): 拿不到原始字典`——判据字段在单边
  路径上根本不存在，等于这两条路径下的判定**一直没法验收**。已按上面补齐。

  **验证**：冒烟 58 项全绿（含新增 [P0-3]：只断言字段存在且自洽，
  不断言判定值是什么）。

  ────────────────────────────────────────────────────────
  [④] 外部审计清单（v9.1 的 P0-P3 × 35 条）逐条核对：**只有 3 条适用**
  ────────────────────────────────────────────────────────

  **先说结论：那份清单是针对 DGTF v9.1 的，v1.21.61 架构已重写。**
  逐条 grep 核对后，35 条里 **32 条在当前代码里不存在**（不是改名，是
  整个功能没了）：

  | 类 | 条数 | 结论 |
  |----|------|------|
  | A（P0）| 4 | **全不适用**。A1 system 双塞已修（`self.llm.call(system, lines, …)`
  |    |    | 两个参数分开传）；A2 联网（`web_search`/`search_enabled`/
  |    |    | `external_facts`）全 0 处引用 —— 功能整个没了；A3 `llm_tokens`
  |    |    | 已用 `self.llm.total_tokens` 真实统计；A4 只实例化一个 `LLM(config)` |
  | B（P1）| 8 | **3 条适用**（B3/B4/B5，已修）；B1/B2/B6/B7/B8 不适用 |
  | C（P2）| 13 | **全不适用**。12 个"定义了未读取"的配置字段只剩
  |    |    | `min_distance_improvement` 还在用；`auto_modes`/`ask_origin`/
  |    |    | `_FRAMEWORK_MARKERS`/`coverage_details`/`extend_timeout`/
  |    |    | `cache_per_layer`/`export_json` 全 0 处引用 |
  | D（P3）| 10 | **全不适用**。D5 的三套阈值已改成命名常量
  |    |    | （`_BAN_SIM`/`_REPHRASE_SIM`/`_DUP_SIM`/`_SUSP_SAME_SIM`）|

  ★ **没有照单全修** —— 对着一个不存在的架构改 35 条，改出来的全是
  臆想。真正修的 3 条：
  · **B3** `_tighten_both`：对称度原来只算 `min/max(len)`，模型把两侧
    写成**长度相近的空话**就能刷满对称性。改成「内容不重合度为主、
    长度比为辅」+ 最短 12 字门槛（一侧过短就没有实质论证）。
  · **B4** `save_result`：`safe_q` 原来允许「，。？」和空格进文件名。
    只留字母数字/中日韩文字/连字符下划线，空格转下划线，并 strip 首尾点。
  · **B5** `_extract_items`：`desc.count("?")` 只过滤英文问号，中文「？」
    和全角「…」漏网 —— 整段问号的伪候选照样进池。三种写法都算。

  ────────────────────────────────────────────────────────
  [⑤] 落地层 render_landing()：产物要有「能拿去用」的五块
  ────────────────────────────────────────────────────────

  **原来的产物是逐层平铺内部字段**，读的人要自己从四层里拼结论。
  现在 `save_result` 在最前面渲染落地层，逐层明细降级为「附」。

  五块：决议书 / 待办清单 / 风险登记表 / 边界 / 未决缺口，
  末尾另起一块「停止 vs 清算（两件事）」。

  ★★ **硬约束（写在函数注释里，改这里等于造假）**：
  1. **不可判定与悬置原样保留，绝不强行收口。**
     · 悬置**不进待办** —— 「决定不碰」本身就是一种结论。
     · 未对齐合法：`aligned_amps` 不是缺陷，只是没对上 und_aspects。
     · **未决 ≠ 不可判定**：未决进「未决缺口」，不可判定进「边界」。
       把未决写成待办 = 把「还没查」伪装成「要去做」。
  2. **停止与清算分开**：停止 = 螺旋不再推进；清算 = 遗留有没有交代。
     合并成一句"跑完了"会让人以为两件事都完成了。

  渲染失败**不拖累落盘**，但必须留痕（否则"没有落地层"和
  "落地层崩了"长得一样）。

  ────────────────────────────────────────────────────────
  [⑥] 自动调度 _auto_plan()：模式和圈数都不用人工设
  ────────────────────────────────────────────────────────

  原来 `_decide_parallel_mode` 只定**模式**，圈数还得人自己填
  （命令行 `--rounds` 默认 0 → 全层 hard_max，靠 stop 判据兜着）。

  新增 `_auto_plan(question)`：一次调用定**模式 + 每层圈数**。
  `_run_v60.py` 支持 `rounds=auto`（配合 `mode=auto`）。

  ★ 两个边界，都是刻意的：
  · **只在用户什么都没指定时才接管**。指定了模式或圈数任一就尊重用户，
    退回单目标决策 —— 自作主张覆盖显式参数是另一类 bug。
  · **成本档不在这里定**。它在 `__init__` 里就按 profile 裁剪完
    shape_chars 了，run 阶段改不动。塞进返回值只会造成"我调了"的错觉。
  · 圈数越界/脏值**不采纳该值**，但**不落回配置兜底** —— 见下方真跑实证。

  **★ 真跑实证（a61H）**：调度只给了 修行4/研究4，对撞和元**漏了** →
  那两层走配置兜底 = `hard_max`（12/13）→ 元层**跑满 13 圈、体力耗尽
  被截断**，整轮 20.7min / 239 calls；而给全四层的 a61F 只要
  9.7min / 160 calls。

  `hard_max` 是"最坏情况预算"，拿它当默认值等于**默认最贵**。
  所以改成：漏给的层用**已给合法值的中位数**补齐（模型既然给了别的层，
  就说明它对这题的量级有判断）；一层合法值都没有时才交给配置兜底
  —— 那时没有任何依据，凭空补比交给配置更糟。

  ────────────────────────────────────────────────────────
  [⑦] 输出 redesign：去掉调试日志味
  ────────────────────────────────────────────────────────

  `self_check` 原来无条件打印「可疑候选：[]」「可疑 &：[]」
  「诚实承认空：True」「整体流程评价…」—— 空列表 + 模型自评占了
  大半篇幅，读起来像调试日志。

  改成：**只在有点名时才写**；模型的自评（`flow_verdict`/`view_verdict`/
  `amp_ratio_verdict`）**不进产物** —— 那是模型给自己打分，不是可核对的
  事实。要事实看代码实算的数字（`rephrase_ratio`/`unsaid_count`，保留）。

  ────────────────────────────────────────────────────────
  [⑧] 判定稳定性：**探针实测**，定位到判定漂移的机制
  ────────────────────────────────────────────────────────

  **背景**：同题（地铁运营）三次真跑判定不一致 —— decidable →
  partial(3 条无追溯) → decidable。这已经不像噪声，得查机制。

  **探针设计**（`_probe_decision_stability.py`）：把「输入随机」和
  「采样随机」分开 —— 先跑一次修行层拿到**固定的** zero_view，
  再对**同一个 view** 重复评估 5 次。

  **实测结果**（candidates=31 amps=11 threads=12 collision=1043字）：
    · 判定值：5/5 都是 partial
    · **不可判定清单：5 次全不一样**（4/4/5/5/4 条，措辞与来源标注各异）
      同一条语义被写成：
        '清分规则未定，断面客流与线路客流不可互证'
        '清分规则未定时断面客流与线路客流不可互证（候选16）'
        '清分规则未定，断面客流与线路客流无法互证（悬置1）'

  ★ **结论：判定值稳定是假象，真正不稳的是方面清单。**

  **根因链条**：`_normalize_decidability` 的规则是
    `decidable + 有 und_aspects → partial`
  判定值实际上由「模型这一次列了几条 und」决定，而清单是温度 0.3 的
  采样产物 → 这次没列 decidable、列了 1 条就 partial。

  **修法（两处）**：
  1. **无追溯的不可判定不参与归一化** —— 理由不成立的东西不该把
     decidable 拉成 partial。这把两条判据打通：「无追溯」不再只是
     报出来给人看，而是**真的不采信**。清单本身仍原样返回留痕。
  2. **`_untraced_undecidable` 抗噪**：比对前剥掉「（候选16）」
     「(&印记)」「[外]」这类来源标注和标点。否则**有追溯的**会被
     误判成无追溯 —— 判据自己变成噪声源。

  ★★ 顺带抓到**我自己上一轮引入的 bug**：`[外]` 前缀是**外判**列的
  条目，外判本来就没有池可追溯，把它算进"无追溯"是**误报**。
  我在写 `_stamp_decidability_criteria` 时想到了这点，却只在
  external-only 分支处理了，**合并路径漏了** —— a61F 报出的 5 条
  无追溯里，3 条是这种误报。已按同一口径修正。

  ────────────────────────────────────────────────────────
  [⑨] 自动规划扩到五维 + 动态提前停
  ────────────────────────────────────────────────────────

  `auto_plan()`（模块级）：一次调用定 **route / mode / rounds /
  cost_profile / max_calls**，调用方不需要设任何执行参数。

  ★ **必须在构造 MetaDGTF 之前跑**：`_profile_plan(config)` 是纯函数，
  只读 `config["cost_profile"]`，而 `__init__` 里就按档位裁剪完
  shape_chars 了 —— 构造之后再改档位，改不动。（上一版 `_auto_plan`
  因为拿不到这个时机，成本档只能放弃，这次补齐。）

  **动态提前停**（`max_calls` 总调用预算）：
  · 每圈开始前检查，用尽就收尾；与层内自然停止判据**不是一回事**
    （那些看"还在不在产出新东西"，预算看"一共花得起多少"）。
  · ★ **必须留痕**：理由并进 `stop_reasons`，产物里写「预算用尽…
    提前收尾（不是自然停止）」。静默少跑几圈，看着和自然停止一样，
    就是"错了却看不出来"。
  · `max_calls=0` 表示不设限（完全交给层内判据）；低于 20 也按
    不设限处理 —— 设了只会让每层都跑不满一圈。
  · 覆盖 4 处圈循环（`_run_layer` / C 模式 / stage 模式）。

  **route 三档预设**：full(0,1,both,all) / no_meta(0,1,both) /
  light(0,1)。★ 提示词明写"拿不准就用 full" —— 少给一层省下的调用，
  远不如缺一层的代价。rounds 只保留 route 里真要跑的层。

════════════════════════════════════════════════════════════
v1.21.60 相对 v1.21.59 的改动（本轮收束版）
════════════════════════════════════════════════════════════

  本轮主题：**开跑前先做一次全息剖析，然后按剖析给出的优先级修 5 处，
  最后真跑验收。**

  剖析产物见 `元DGTF-全息剖析-v1.21.60.md`（六轴：设计方向 / 架构 /
  机制 / 功能 / 可靠性 / 价值；每条结论带证据，并区分
  「设计如此 / 缺陷 / 未验证」）。**最重的一条发现：机制数 ≫ 实际使用量**
  ——真跑里 min_rounds 拦截 / 双通道均收敛 / 双通道均停滞 / 漂移标记 /
  本层空转 / 债务 dropped / both 配额 / escalation **全是 0 次**；
  约 **62% 的层收尾是「体力耗尽」被截断**（产物口径 50 截断 vs 30 自停）。
  所以本轮**不加任何新机制**，只修「实现 ≫ 验证」的缺口。

  ────────────────────────────────────────────────────────
  [①] 层完整性守卫：失败了不许静默消失
  ────────────────────────────────────────────────────────

  **根因是一个错误习惯：拿"实际结果"当调度记录。**
  `_pack_result` 与四条并行路径都写死 `order = results.keys(),
  skipped = []`，于是：
    · B/C/D-H 里某层第 1 圈抛异常 → `state["stopped"]=True`，但
      `_results[entry]` **永不写入** → `_b_finalize_layer` 见 `view is None`
      直接 return → **该层从 views/pools/self 段整层消失**，下游也当它不存在；
    · 而**所有**校验（含冒烟）都拿实际 views 当基准 → **层真缺了会自动缩水，
      永远判不出来**；
    · 并行路径压根没调 `_plan_dispatch`，所以蓝图 D4「依赖不满足 →
      如实跳过 + 写原因」的留痕**在并行模式下全丢**；
    · `order` 取完成序 → **C/D-H 的键序每次不同**，破坏「可独立复现」。

  **做法**：
    · `self._dispatch_plan`（`run` 里算一次）＝**唯一基准**；
      `_dispatch_for_pack()` 以它为基准，另记 `ran / missing / failed / skipped`。
      ★ `missing` 必须**把失败层也算进去**——失败层会留占位 View，
      只判「在不在 `_results` 里」会被自己留的占位骗过去（我第一版就写错了）。
    · 五处失败点全部记账（`_note_layer_failure` → `self._failed_layers`）；
      失败层留**占位 View**（在场但不可用：`_view_usable` 对它返回 False，
      所以不会骗下游）；**串行也加了逐层隔离**（原来一层抛异常 → main 丢
      result → **整轮零产物**）。
    · 统一收口后 `_layer_guard()` 核对「计划的层是不是都在」，缺了就在
      运行时和产物**头部**明写「❌ 缺层 + 原因」。
    · 四条并行路径改用 `_planned_active(route)`（取计划，不是 route）。

  **验证**：冒烟 `check_layer_guard` 4 条——注入失败后层**不消失**且
  `missing=['1']` + 原因留痕 / 产物明写缺层 / 串行逐层隔离（其余层照常产出）/
  跳过的层不再被并行模式偷跑且留痕在。9 模式在 mock 下 `missing` 全空。

  ────────────────────────────────────────────────────────
  [④] 跨层池读加锁：修一个破坏"可独立复现"的竞态
  ────────────────────────────────────────────────────────

  `_align_suspensions_and_deferrals(pools["0"], pools["1"], …)` 在两处被调用，
  **都不在 `with self._pool_lock` 里**；而 A 模式下这两个池正在各自线程里
  `Pool.merge`。不持锁就读 → 四象限匹配率/象限**每次运行可能不同**，
  并经 `_probe_duel` 影响产物 —— 直接顶撞蓝图 §四「三层可独立复现 =
  可检验性的基础」。两处已加锁。

  ────────────────────────────────────────────────────────
  [⑤] 停止判据收口：一套判据只留一处实现
  ────────────────────────────────────────────────────────

  停止判据原来在两条跑圈通道里**各写一份**：`_run_layer` 里 92 行、
  `_b_check_stop` 里 84 行。措辞一模一样、条件一模一样，只有变量名不同
  （`layer_no`↔`r`、`_total_rounds`↔`total_rounds`…）。而唯一的守卫
  （`check_stop_reason_parity`）**只查理由字面量在不在**，改了一边的
  **条件**两边就悄悄分叉。

  现在抽成 `_stop_reasons(...)`：**纯判据**（不改池、不设 stopped），
  返回 `(reasons, idles)`；两条通道各调一次。`_b_check_stop` 239 → 167 行，
  `_run_layer` 606 → 540 行。

  **等价性证据**（重构最怕"看起来一样"）：
    · 先存 9 模式**行为快照**（每层 stop_reason / 圈数 / idle 计数 /
      round_log 的 why / 池计数 / llm_calls）→ `_stop_baseline.py save`，
      sha256 = `8e8510756be0`；
    · 重构后重取快照 → **sha 相同**；`_stop_baseline.py diff` 9 模式全一致。
    · ★ 这个基线**当场抓出了我重构里的一个真错**（改名时把
      `_rephrase_streak` 的定义一起删了 → NameError，四层全失败）。
      没有它我会以为"改完还能跑"就算对了。
    · 守卫改为**反向不变量**：理由字面量只在 `_stop_reasons` 里、
      两条通道必须各调一次、谁都不许自己 `append/extend`。
      （旧写法在收口后会**误报失败**，所以连检查一起改。）

  ────────────────────────────────────────────────────────
  [⑥] 清理误导性声明 + 一个真 bug：配置从未生效
  ────────────────────────────────────────────────────────

  ★ **查出真 bug**：`dgtf_config.yaml` 里有两段示例（`spiral: / per_entry: /
  "all": {...}`）写在注释块中间却**忘了注释掉** → 整个文件解析失败 →
  `load_config` 走 except**退回默认配置** → **yaml 从来没生效过**
  （v59 真跑日志里就留着「⚠️ 配置文件解析失败」）。更险的是它带着**过期值**：
  `min_rounds."1": 2`（v1.21.58 已定「全层归零」）、
  `structure_saturation_every_n: 2`（而它自己的注释写的是 3）—— 一旦有人
  把语法修好，这两个过期值会**静默推翻上一版的决策**。
  → 已注掉示例、把这两个值对齐出厂默认，并加冒烟 `check_config_parses`
  （yaml 必须能解析 + 生效后与 `DEFAULT_CONFIG` 一致 + `load_config`
  真的吃进 yaml）。

  另清理：
    · `dgtf_config.yaml` 里「self 通道：**跨问题累积**」与实现不符
      （`self_text` 是进程内 list，每次 run 重置）—— 已更正为
      「单次运行内各层 view 的自我累积」，**这条注释误导过我一次**；
    · 删 4 个死配置（`output`/`actions` 的 `plain_speak`、
      `layer_summary`/`summarize_views`：只出现在别名表与 DEFAULT_CONFIG，
      13 个 `_action_on` 消费名里没有它们）；
    · 删 `_pack_lock`（定义后全项目无人使用）。

  ────────────────────────────────────────────────────────
  [⑦] 文档同步：把已推翻的断言标出来
  ────────────────────────────────────────────────────────

  · `docs/三层递归蓝图.md §二`：「escalation 立刻挪、**单向（不可逆）**」
    已被用户 2026-09-30 定案推翻 → 原句保留但划掉，旁附**为什么站不住**
    （三条）+ 现行规则（三态互转·须证据·新开不复活）；
  · `docs/元DGTF整体框架.md §I`（已被推翻的旧判断表）新增 4 行：
    蓝图 §二 单向不可逆 / “yaml 是生效的配置” / “判据可以各写一份” /
    “拿实际结果当调度记录”。
  · 代码注释里对 §二 的引用改成"那句已被推翻，这里只保留账链"。

  ────────────────────────────────────────────────────────
  验证与遗留
  ────────────────────────────────────────────────────────

  **冒烟 58 项全绿**（59 轮 53 项 → +5）。新增
  `check_layer_guard`(4) / `check_config_parses`(1)，
  重写 `check_stop_reason_parity`（不变量反转）。

  **★ 仍然是下一轮第一件事：真跑看分类分布**（59 遗留原样保留）：
  v1.21.59 把「undecidable + 任一侧列了可判定方面」归一化成 partial 之后，
  `_decompose_koan` 会**变得少见**。要回答：
    · 分类是否**一边倒地偏向 partial**？（若是就稀释了「不可判定」信号；
      收紧方向是「要求可判定方面来自池侧 / 或禁止形式化列举」，
      但那需要证据，不许拍脑袋）
    · `_decompose_koan` 是否还进得去？（进不去 = 这条路径事实上死了）

  **★ 第二件事（本轮仍未解决）**：59 的三条修正 + 本轮 5 处，
  **全都还没有真跑证据**（v59 一次 escalation 都没发生）。C/E/G/H 在
  真跑里也从未出现过（产物统计：串行 20 / B 4 / A 3 / D 1 / F 1）。

  其余遗留：`stable_layers` 2→3 待验 / `_divergent` 该按原始还是归一化后
  的状态算 / 修行层单独设上限压成本 / 零触发机制（双通道收敛停滞、
  漂移标记、both 配额…）的条件可达性待查。

  ────────────────────────────────────────────────────────
  [⑧] 真跑验收 + 分类分布的机制修正（承接 ②③）
  ────────────────────────────────────────────────────────

  **真跑结果**：5/5 全 OK（serial 43min / C 10.6 / E 21.3 / G 18.8 /
  H 22.4，共 906 调用），`dispatch.ran=order`、`missing=[]`，C/E/G/H
  四模式全部跑通——① 层守卫真跑通过；停止判据收口后自然停止与
  体力耗尽截断都正常出现。

  **★ 分类分布实锤了剖析里的预警**：顶层判定 **5/5 全 `partial`**，
  `_decompose_koan` 一次没进。但深挖判定来源后，发现**这是机制问题，
  不是题的性质**：
    · 外判（独立评估器，看问题本身）对**欧盟 AI 法案**、**地铁运营**
      都判了「✓ 以可判定为主」（理由正确：法律条款查询 / 经验问题）；
    · 池判（读修行层形状）却把这两道明显可判定的题也判成 partial，
      合并后把外判的 decidable 拖成 partial；
    · 根因：池评估提示词把「& 候选 / 主动悬置 / 悬空线头 / 此处未生」
      ——**这一圈还没判出（未决）**——误当成「**不可判定**」。修行层
      「宁可标未生，不硬凑答案」是机制常态，所以池判几乎恒为 partial。

  **修正**：`_assess_decidability_from_pool_view` 的提示词加了一条
  「区分未决 vs 不可判定」：未决（未生/悬置/线头）不算不可判定；
  只有自指循环 / 无共同参照系 / 本体论判断（无经验判决实验）这类
  「原则判不出」才进 `undecidable_aspects`；partial 只留给
  「真的有可判定部分 + 真的有不可判定部分」。三态口径与外判对齐。

  **验证结果（重跑欧盟法案 / 地铁运营，各 4 圈，与改前同模式 A/B）**：
    · 欧盟法案：池判 partial → **decidable** ✅（"未决项属查得到的经验/定义
      问题，非原则判不出"——新区分直接起效）
    · 地铁运营：池判 **仍 partial** —— 重判后确认是**事实如此**，不是机制
      问题：「运营效率」本身有不可判定的核心（产出选乘客体验还是运输产出、
      投入选成本还是容量，是价值选择；乘客时间体验与运营成本账**量纲不可比**）。
      所以 partial 可辩护、甚至比外判的 decidable 更准确。
    · ★ 教训：验证修复时，测试样例**不能预设答案**——先问这道题真实的
      可判定性，再判断判定对不对；两个评估器分叉，先问"题目本身有没有歧义"，
      不要默认"哪个符合预期哪个就对"。

  ────────────────────────────────────────────────────────
  [⑨] 评估时机按「0 层先行策略」对齐调度表（F/G/H 跑满，D/E 不预热）
  ────────────────────────────────────────────────────────

  **根因**：`_run_parallel_stage`（D~H 共用）起跑前一律
  `_warmup_and_assess(active)` —— 0 层固定跑 `parallel_warmup_rounds`（默认 1）
  圈就判可判定性，和 `_MODE_GRAPH` 的先行语义对不上：
    · F/G/H：1 层用硬闸 `("0",)` 等 0 层**跑完所有圈**，评估却只读 1 圈
      薄形状就把判据定死 —— 白白浪费「0 层本就要跑满」这个已知条件；
    · D/E：0/1 **双起并行**（都无硬闸上游），却被人为让 0 层领先 1 圈，
      制造了调度表里并不存在的错位。

  **做法**：0 层的先行策略改由 `_MODE_GRAPH` 推导，不硬编码模式名：
    · `warm_full=True`（F/G/H）：预热圈数 = 0 层 total_rounds（跑满），
      评估在 0 层收工后读**完整形状**；0 层在 stage 里 start_r>total 空转，
      只放行下游，语义与「0 跑满才起下游」一致；
    · `warm_rounds=0`（D/E）：不预热，0/1 同时从第 1 圈起跑，评估在起跑
      那一刻读池——起跑时池还空，自然退回外部评估（`_source="external"`）；
    · C（下游只等 0 层出第一圈）与 B（齐步）保持 1 圈预热不变。

  **验证**：冒烟全绿。`预热` 列：F/G/H 1→2（跑满）、D/E 1→0（不预热）、
  B/C 仍 1；`判定源` 列：D/E → external，其余仍 pool+external。
  **verifyG/verifyH 之前的结论基于 1 圈薄形状，需下一轮真跑用完整形状复核。**

  ────────────────────────────────────────────────────────
  [⑩] 彻底取消「起跑前全局快照」：评估统一到研究层拆解时动态做
  ────────────────────────────────────────────────────────

  **根因（用户追问逼出）**：上一版评估仍是「起跑前算一次存成
  `decidability_result` 全局快照」，研究层第 1 圈拆解又独立地判断
  `has_zero_prod`（读池 or 外部）——**两套时机、两个源**。D/E 双起并行时，
  快照起跑时池空=外部，而拆解可能动态读到池，同一圈信息源分叉。
  用户的方案：不要快照，研究层拆解时「有产物读池，没产物才外部」——
  读到哪就是哪。

  **做法**：
    · 新增 `_assess_decidability_dynamic(question, zero_view)`：读池有产物
      → 池评估（merge 外部），无产物 → 外部评估。这是判定的**唯一**确定点。
    · `_warmup_and_assess` / `_run_zero_then_assess` / `_run_serial` 三处的
      评估职责**全部删除**，只保留「跑 0 层」；评估改在 `_run_layer`（串行）
      与 `_b_pre_layer`（并行）的研究层拆解处调用。
    · `run()` 每次重置 `decidability_result={}`，并在收口兜底：route 不含
      研究层、或 `decompose_question` 关时评估没触发，跑完所有层后补一次
      动态评估（读 0 层此刻留下的形状），保证产物判定字段不空。
    · ★ 顺带修掉 fix-102 的**休眠 bug**：研究层拆解读 0 层原来走
      `provider("1")`，而 `_ENTRY_DEPS["1"]=()` 使 provider 恒空 → `use_internal`
      恒假、「修行池内部」拆解分支**从未真正执行过**。改为直接读
      `self._results.get("0")`，`_decompose_from_pool` 路径这次才真正生效。

  **验证**：冒烟 58 项全绿。`判定源`：0 层先行的模式（serial/A/B/C/F/G/H）
  都是 pool+external（拆解时读到 0 层形状），D/E 是 external（双起并行，
  拆解时池空）。**verifyG/verifyH 及此前所有评估结论都需下一轮真跑复核。**

  ────────────────────────────────────────────────────────
  [⑪] 判定机制方向性说明（reclassification / 复债 / escalation）
  ────────────────────────────────────────────────────────

  用户确认「这套机制是不是双向的」，查证后成文（对应蓝图 §二被推翻的
  「单向不可逆」，这里是代码落实后的权威说明）：
    · reclassification（三态互转）：**双向，6 个方向**。
      `apply_decidability_change` 是唯一入口，不做方向限制——只要
      from≠to、目标态合法、证据在池中定位得到，就 applied。
    · 复债（`_reopen_closed_debt`）：**双向**。迁向 undecidable 时把该 sub
      名下 deferred 关成 escalated（"不再欠了"）；转回 decidable/partial 时
      重新挂一笔账（`reopened_from` 接旧账、`revisit_condition` 原样归还）。
    · escalation：**单向**（只指"迁向不可判定"），但它不是独立机制，只是
      双向互转的"往不可判定"这一半；反方向由复债接住，不是"降级 escalation"。
  即：`escalation` 单向只是命名，判定 + 债务这套机制整体是双向闭环。

  ────────────────────────────────────────────────────────
  ★ v1.21.60 收束摘要
  ────────────────────────────────────────────────────────

  交付物：
    · 全息剖析 `元DGTF-全息剖析-v1.21.60.md`（六轴，7 条建议）；
    · 代码 ①层守卫 ④跨层池锁 ⑤停止判据收口 ⑥清理(含 yaml 从未生效的真 bug)
      ⑦蓝图同步 ⑧真跑验收+分类机制修正 ⑨评估时机对齐先行策略
      ⑩评估统一到研究层拆解时 ⑪方向性说明；
    · 冒烟 `smoke_test.py` 58 项全绿（SRC 指向本版）。

  验证覆盖：
    · 真跑 5 次（serial/C/E/G/H，906 调用）+ 并行 3 次（koan1/reclass/koan2，
      810 调用），全部 OK、`missing=[]`、`skipped=[]`；
    · 欧盟法案 / 地铁运营 判定复核（verifyG/verifyH）。

  已知遗留（下一轮第一件事）：
    · ★ [⑩] 修了 fix-102 休眠 bug（"修行池内部"拆解从没真正执行）+ 评估
      统一到研究层拆解时——**但都还没有真跑证据**。此前 8 次真跑（含并行
      3 次）全是旧代码跑的，结论（koan 没进 / reclass 0 次 / 判定源）已过时，
      需下一轮用新代码重跑复核。
    · koan 整体不可判定路径：旧代码下 8/8 顶层判定全 partial，`_decompose_koan`
      一次没进；归一化把"undecidable + 有可判定方面"归成 partial 是主因。
      要不要收紧（救活 koan）需证据，不许拍脑袋。
    · reclassification/复债/escalation：旧代码下 0 次（nudge 加了，模型仍只做
      deferral 挂账、不主动 reclassification）。新代码下拆解路径变了，能否
      触发待验。
    · stable_layers 2→3 / `_divergent` 口径 / 零触发机制达性 待真跑观察。

  经验教训：
    · 连续几轮"评估时机"的纠结（⑨⑩），根子是同一个错误：把「评估」和
      「跑 0 层先行」耦合在一个函数里。⑩ 拆开——评估只认研究层拆解一个
      时机，0 层先行只负责跑。
    · fix-102 的教训：改"硬编码 False"成"看 provider"时，没验证 provider 对
      "1" 是否真能返回 0 层——`_ENTRY_DEPS["1"]=()` 使 provider 恒空，
      "修行池内部"分支从没真正执行，直到 ⑩ 才暴露。改完"看某处"要当场
      验证那处真能返回非空。

════════════════════════════════════════════════════════════
v1.21.59 相对 v1.21.58 的改动（本轮收束版）
════════════════════════════════════════════════════════════

  本轮主题：**验证 DGTF 的整体运行质量**。
  v1.21.58 把出厂默认改成全层一致（soft_max 3 / hard_max 12，无
  per_entry）之后，有两件事没验证过：
    · `hard_max: 12` 的实际成本——判据判不了「做完了」，四层可能各
      跑到 10+ 圈，预计是 `--rounds 3` 的 3–5 倍；
    · `stable_layers` 2→3 是**行为变化**（元层自然安住门槛提高），
      未真跑验证。
  本轮就跑这两条，并对整体质量分层取证。

  [整体运行质量验证 · 默认预算 12]
  ────────────────────────────────────────────────────────

  配置：v1.21.59 · 不传 rounds（走配置）· balanced · serial · 同题。
  产物 `outputs/20260930_064821_…md`，日志 `v59_default.log`，
  完整记录见 `元DGTF-真跑验证报告.md` 第十三节。

  **成本**：333 次调用 / 1 585 809 token / 47 分钟
  （省档 125 次、中档 220 次）。

  **★★ 最重要的一条：停止判据是活的，前提是预算够长。**
    四层停成 **12 / 8 / 10 / 5** —— **3/4 层由判据自己停**：

      修行 0    12 圈   体力耗尽（唯一走满的）
      研究 1     8 圈   结构饱和度判定连续无新维度
      对撞 both 10 圈   自省连续 2 圈点名同一批问题未消化
      元 all     5 圈   自省点名 + 连续 4 轮无线头新增

  → **这修正了 v1.21.58 第十二节的结论**（那里写「当前版本没有自然停止点，
    预算就是决定量」）。正确表述是：
    **停止判据有"累计窗口"，预算必须至少覆盖那个窗口（实测约 5–10 圈）。**
      · 「连续 N 轮无线头新增」要累计 **4** 轮，预算 3 时**结构上到不了**
        （v1.21.57 拉的分布印证：线头计数观测到 2×4、3×1，从没到 4）；
      · 「结构饱和度」每 3 圈才跑一次，预算 3 时只在第 3 圈跑一次，太早；
      · 「自省连续 2 圈点名同一批问题」要**同一批** banned 重复出现，
        内容每圈都在变时 3 圈内很难重复，8–10 圈才有机会。
    所以真正的成本不是"预算上限"，而是**各层自然停止点之和**；
    给 12 时 3 层提前停，没把预算花满。

  **质量**：三次里最好的一档——
    质量线索 **0 条**（省档/中档各 1 条）；
    all 池 & 101 / 线头 59 / 探针 104 / 主动悬置 23（省档 41/28/38/12）；
    张力悬置 16（省档 7）；产物 141 KB（省档 101 KB）。

  **机制面全过**：复述计数全 0；自省回流注入 31 次；fix-88b 推迟 5 /
  放行 4；元层语义下限推迟 1；`min_rounds` 拦截 0 次；覆盖率双口径在
  （走回退分支：清晰度 0.70 + 结构覆盖率 0.00）；不可判定命中轨迹在；
  成本档位留痕在；漂移标记无；四层池齐全。

  **`stable_layers` 2→3：本轮没有可见影响** —— 元层第 5 圈就停了，
  停因是「自省点名」不是「自然安住」，那一处没机会起作用。待另找场景验。

  **一个必须说清的结果**：研究层末态没有可判定答案（`answer：无`、
  `answered_sub_ids：[]`，`distance = 1.0`；产物里逐条写了"为什么落不进值格"）。

  ★ **自查更正（本轮末）**：这条我一开始写成「5 条可判定子问题被**升级**为
  不可判定」——**错了，那是我读产物读出来的假因果**。真相是：评估阶段就把
  这道题判成 undecidable，`_decompose_question` 走 `_decompose_koan`，
  5 条子问题**生下来就是 undecidable**（日志：「分解出 5 个子问题
  （可判定 0 / 不可判定 5）」），全程**一次 escalation 都没发生**
  （日志无 `⬆ 升级`、产物无「升级留痕」行）。所以 `coverage_of`
  从第 1 圈就返回 None（日志「📊 可判定覆盖率 N/A」×3）。
  误读的源头是池段那行把 `sub_questions` 的**总数**标成
  「可判定子问题 5 条」——已修（现在写「子问题 N 条：可判定 a / 不可判定 b」），
  并加冒烟 `check_pool_sub_label` 防复发。
  按宪法（不可判定合法、留痕）这是诚实收束；按「想要的回答回答了」则是"没答"。
  同一题换可判定性更强的变体（欧盟 AI 法案）时同配置给了 3/3 ——
  **更像题目敏感，不像机制缺陷**——下一轮值得专门看。

  **建议**：要压成本，正确的位置**不是**调低全局 `hard_max`（那会把累计
  窗口重新关上、退回"体力耗尽"），而是**给唯一停不下来的那一层单独设上限**
  ——修行层 12 圈全跑满、一条理由都没触发。运行时 `--rounds "0:6"`。

  [可判定性三态互转 · 判定不再是终审]
  ────────────────────────────────────────────────────────

  用户判定：**「这是机制的漏洞，应该是双向的。」** 三态
  （decidable / partial / undecidable）之间**任意方向**都可转移，
  只要有足够证据推翻上一次判定。

  **旧实现的问题**（三层）：
    1. 只有 `decidable→undecidable` 一条腿，且**全文没有回写路径**
       ——"不可逆"不是靠守卫，是靠"没人写反向代码"。
    2. 蓝图 §二 的「立刻挪，单向（不可逆）」**未加论证**；最像原则的
       §四「读写关系（单向，不回写）」讲的是**层间不写别人的池**
       （"书评不改书"），是另一件事。
    3. 证据上不对称：正向只要一句 ≤40 字 reason，反向一刀禁止。

  **做法**：
    · 新增 `Pool.decidability_log`（append-only）：三态任意方向的变更**与
      被驳回的提案**都记（`status` / `why` / `evidence`），失败留痕。
    · 新增 `View.reclassifications`（研究层提案）：
      `{sub_id, to, reason, evidence[]}`。旧的 `escalations` 字段照吃
      （等价 `to="undecidable"`），**两条走同一个入口**。
    · 唯一入口 `apply_decidability_change(...)` ——
      **「有足够证据」是确定性校验**：每条 evidence 必须能在**此刻的池里**
      定位到对象（编号 `A2/P1/T3/S1/C4/ing`，或直接引原句模糊匹配
      ≥0.5）。定位不到 → **整条驳回并留痕**，不靠 prompt 恳求。
    · 迁向不可判定时仍连旧账链（该 sub 名下 deferred → escalated）；
      留痕措辞从「单向不可逆」改为「三态可转·须证据」。
    · **tracker 去掉了"只升不降"**：原来 `effective_cov = max(cov_before,
      cov)` 会把覆盖率下降全抹平；现在用当圈真值，并在**分母变化**的那一圈
      只重置基线、不计停滞/改善（否则"新挂上一条可判定子问题"会被误判成
      停滞、"改回去"会被误判成进步）。新增 `ChannelTracker.note_rebaseline`。
    · 池段渲染：`📐 可判定性变更轨迹` + `📐 被驳回的可判定性变更`，
      成立的与被驳回的**都摆出来**——这个账是"判定可被推翻"的凭据。

  **验证**：冒烟 `check_decidability_transitions` 8 条——
  三态 6 个方向全可转 / 无证据必驳回且留痕 / 悬空证据必驳回 /
  原句引用也算证据 / 履历 append-only（来回转两条都在）/ 同态不记账 /
  迁向不可判定仍连账且措辞改口 / 产物同时摆出轨迹与驳回。

  [评估→拆解 · 判定不再"一次传播"就定死]
  ────────────────────────────────────────────────────────

  上一条把"改回去"的路径补上了；这一条修的是**初始判定本身**。

  **根因（三处一处都没有守）**：不变量是「undecidable ⇔ 没有可判定方面」，
  而三处没人守它：
    1. `_assess_decidability`（外部评估）**有**归一化 —— 但
       `_assess_decidability_from_pool_view`（读修行池那次）**没有**。
       v59 池判就是「undecidable + 3 条 decidable 方面」。
    2. `_merge_decidability` **无条件采信池的状态**
       （`merged = dict(pool_res)`），外判状态只进 `_ext_status` 供展示。
       于是那条不自洽的池判原样通过，外判说 partial 也没用。
    3. `_decompose_question` **只看 status 标签**分派：标签说 undecidable
       就 `_decompose_koan`，而 koan **根本不接收 `dec_aspects`** ——
       那些方面一条都进不了子问题。
  → 结果：覆盖率分母从出生就是 0，`coverage_of` 一路返回 None，
    12/8/10/5 圈的材料全白跑（v59 实测）。

  **做法**：
    · 抽出全项目**唯一一份** `_normalize_decidability(status, dec_aspects,
      und_aspects, where)`（规则与旧 sanity check 等价，只是以前只有一处用），
      **三处都改用它** + 在分派点再归一化一次（不指望每个调用方都记得）。
    · `_merge_decidability`：先并集方面清单，**再**按同一份归一化定状态 ——
      任何一侧列出的可判定方面都算数。`_ext_status` / `_divergent` 仍如实
      保留（"外判当时说了什么"是历史事实，不改）。
    · 统一「欠一个答案」的集合为 `_DEC_ANSWERABLE = (decidable, partial)`：
      `coverage_of` / `deferred_ratio_of` / tracker 已答计数 / 产物的
      "已答 x/y" 全部改用它。**以前只有 `_probe_research` 的 shape 把
      partial 算成"必须回答"，分母却只认 decidable** —— 三态可转之后
      partial 真会落到子问题上，不改就是静默漏账。
    · `_parse_subs` / `_decompose_from_pool` 接受 `partial`（不再降级），
      三处子问题 JSON schema 放开到 `decidable|partial|undecidable`；
      分解日志改为三数（可判定 x / 部分 y / 不可判定 z）。

  **验证**：冒烟 `check_decidability_normalize` 6 条——
  真值表 7 例 / v59 场景合并后为 partial（可判定方面不再被丢）/
  两侧都无可判定方面时仍保持 undecidable（不矫枉过正）/
  分派按归一化后的状态（有可判定方面→hybrid，没有→koan）/
  coverage_of 分母含 partial / 源码无硬编码的可回答集合。**48 项全绿。**

  **★ 一个要观察的后果**：`undecidable + 任一侧列了可判定方面 → partial`
  意味着 `_decompose_koan` 会**变得少见**（只有两侧都列不出可判定方面才走）。
  v59 那道题在新规则下会判 partial。这**可能是对的**（那道题确实有可判定的
  部分），但也可能让"不可判定"这个信号被稀释。**下一轮真跑时留一眼：
  分类是否一边倒地偏向 partial。** 若偏了，收紧的方向是"要求可判定方面
  来自池侧/或非形式化列举"，但那需要证据，先不改。

  **仍是下一轮的题**：`_merge_decidability` 归一化后，**分类分布**会怎么变
  （见上「要观察的后果」）；以及要不要收紧可判定方面的判定门槛。

  [复债 · 分类被推翻时，关掉的账要回来]
  ────────────────────────────────────────────────────────

  迁向 undecidable 时会顺手把该 sub 名下的 `deferred` 关成
  `escalated`（"不再欠了"——合理）。**但反方向原来是断的**：判定被推翻、
  转回 decidable/partial 时，那条账永远停在 escalated。

  **为什么这是个真问题**：债务账是**唯一**会被下面这些盯住的地方 ——
  `_probe_research` 的 open_def（喂模型"这一层要交代的债"）、
  `deferred_ratio_of`（反躺平：>0.6 强制下层处理一个）、
  `_settle_research`（终局清算必须 handled/escalated/dropped）。
  它们**都只看 `status=="deferred"`**。没这笔账，这个子问题就只是
  "分母里的一个未答项"，没人会追它。
  （★ 一句自我更正：它不是"完全没人推"——`_probe_research` 会把可判决
   子问题列表当【★ 本层必须回答的可判定子问题】喂给模型。缺的是**账**
   这条线，不是全部推力。实现范围因此收窄为"只把被关掉的账补回来"。）

  **做法**（新增 `_reopen_closed_debt`，在唯一入口里挂钩）：
    三条自我约束，缺一条都会变味：
      1. **只对确实被关过账的开**（存在 escalated 记录）——本来没欠过账的
         子问题开新账等于给债务账灌水；
      2. **新开一笔，不复活旧条**——旧那条"当时确实升级了"是历史事实，
         改它的 `resolved_at`/`resolution_reason` 就是篡改记录；
      3. `revisit_condition` **原样归还**（它当初通过了 `_valid_revisit`，
         仍是我们说好的回访条件），本次重挂的原因另记在 `reason`，
         并写 `reopened_from` 指向被接续的旧账。
    已在挂（存在 deferred）时不重复开。生效条件是
    `frm == undecidable and to ∈ _DEC_ANSWERABLE`（**转 partial 同样算**）。

  **渲染**：变更轨迹行尾加「并重新挂账 d_002」；债务明细给新账标
  「← 重新挂账（接 d_001）」；两处跑圈日志的转移行同步。

  **验证**：冒烟 `check_debt_reopen` 5 条——完整往返（旧条不被改写、
  新条带来源、回访条件原样归还）/ 从没欠过账不开 / 已有在挂不重复开 /
  转 partial 同样复债 / 产物同时可见轨迹与明细标记。**53 项全绿。**

════════════════════════════════════════════════════════════
v1.21.58 相对 v1.21.57 的改动（本轮收束版）
════════════════════════════════════════════════════════════

  ────────────────────────────────────────────────────────
  [④] 报告文件改名：原名与内容已不符
  ────────────────────────────────────────────────────────

  `成本档位验证报告-v1.21.56-economy真跑.md`
    → `元DGTF-真跑验证报告.md`

  为什么改：v1.21.56 建它时只写成本档位（九节）；到 v1.21.57 又追加了
  第十节（P2-3 drift 误报）——名字只覆盖得了一部分内容，而且带死了
  版本号，下一版继续追加只会更名不副实。

  改法：
    · `mv` 改名（内容不动）。
    · 文件顶部加「**文件沿革**」说明：原名是什么、为什么改、
      **v1.21.56/57/58 的 changelog 里按旧名引用的都是本文件**。
    · 加一张「目录（按议题分，不按时间）」表，把每节归到议题下——
      以前只有节号顺序，读者得自己拼出哪几节讲的是同一件事。
    · 原来那个「验证对象/产物/日志/配置」头是**第一轮**的配置，
      会被误读成整份报告的配置，加了 `## 〇、第一轮（…）的实验配置`
      标题把它框住。
  历史快照（v1.21.56/57）里的旧名引用**不改**——那是当时的记录。

  ────────────────────────────────────────────────────────
  [①] max_uncovered_pushes 1 vs 0：A/B 真跑对照 → **结论：别动**
  ────────────────────────────────────────────────────────

  为什么做这个对照：v1.21.57 复查时发现「19 次体力耗尽里 9 次是推迟」，
  于是留下一个待定项——把 `max_uncovered_pushes` 从 1 调成 0
  （第一次触发的判据就直接停）能不能真的早停省钱。这是个取舍，
  不该拍脑袋，所以做 A/B。

  设计：同题（第 7 次真跑那道，已知它会触发 fix-88b）、同档
  （balanced）、serial、四层各 3 圈；**唯一变量就是这一个值**。
  A = 1（现状），B = 0。

  结果：

    指标                     A (push=1)   B (push=0)
    LLM 调用                       125          124
    token                      548 108      560 278   (+2.2%)
    各层实际圈数              3/3/3/4      3/3/3/4   ← 完全一致
    体力耗尽 次数                     3            3
    真实螺旋停止 次数                 1            1
    **fix-88b 推迟 次数**             0            0   ← 关键
    fix-88b 放行 次数                 1            1
    answered                     [1,2]        [1,2]
    answer.distance                0.3          0.3
    综合距离                       0.40         0.40

  ★★ **两臂结构完全相同——这个旋钮在本题条件下一次都没机会起作用。**
    8 个层收尾里唯一一次「停止判据触发 + 还有未深入方向」，落在
    **元层第 4 圈（最后一圈）**，被 v1.21.57 新加的 `is_last_round`
    守卫直接判为「没有下一圈可推」→ **放行**，根本没走到「推迟还是
    不推迟」那个判断。所以 1 和 0 的行为路径完全重合。
    −1 次调用 / +2.2% token 是模型波动，不是档位影响（两臂的停止理由
    都不一样：A 是「自省连续 2 圈点名」，B 是「悬置决定稳定，自然安住」）。

  → **结论：① 这个取舍当前不必做**，`max_uncovered_pushes` 保持 1。
    它要变得有意义，前提是**停止判据能更早触发**（在非最后一圈就触到
    阈值）——那是「圈数预算 / 判据阈值」层面的调整，不是这个值的事。
    先做那个，再回来看这个旋钮。

  ★ 顺带得到的正面证据：**v1.21.57 的 `is_last_round` 修复确实清掉了
    无用推迟**。同一道题、同一档，v1.21.57 之前那次 balanced 真跑
    （010533 号，别的题）有 3 次推迟、全部落在最后一圈；本轮
    A 臂 0 次推迟、唯一的闸门事件被如实判为「最后一圈，放行」。

  附：本次 A/B 的两个脚本保留在仓库里，下次做「改一个值」的对照可复用——
    `_run_ab.py A|B`   跑一臂（tag → max_uncovered_pushes）
    `_ab_compare.py`   两臂逐项对比

  ★ 教训（供下一轮自查）：**做 A/B 之前先确认操纵量在当前条件下可达**。
    这次是先跑完 A 才发现推迟路径根本没被触发——如果只跑 B 一臂就下
    结论，会把噪声当成效果。好在两臂都跑了，「结构一致」这个结论本身
    是稳的。

  ────────────────────────────────────────────────────────
  [⑤] 停止判据与预算：用历史样本（350 份旧产物）定标
  ────────────────────────────────────────────────────────

  用户给了两批历史样本（`元DGTF.outputs.1` 223 项 + `DGTF.outputs`
  127 项），其中能解析出「调度 / 实际走了 N 圈 / 螺旋停止」三元组的
  44 份。分析见 `元DGTF-真跑验证报告.md` 第十二节，这里只记结论。

  ★★ 结论一：**当前版本没有「自然停止点」可等，预算就是决定量。**
    历史样本里「各层自然停在 3–4 圈」是在 **v1.21.56 收紧停止判据
    *之前*** 跑的（旧 `carry_streak` 只要产出 carry 就 +1，停止极易触发）。
    当前版本实测：给 6/4/7/5 的预算，四层跑到 **6/4/7/6，全部顶到上限，
    且每圈仍有 2–4 条真·新增 &** —— 逐圈看 `idle_new_amp`/`idle_new_thread`
    6 圈全是 0，所以「连续 N 轮无新 &」永远不触发。
    两个测点（同题 balanced serial）：
      省档 3/3/3(+1) = 13 圈 → 125 次调用 / 548k token / 池 68 条 &
      宽档 6/4/7/5(+1) = 23 圈 → 220 次调用 / 1059k token / 池 132 条 &
    质量线索两边都是 1 条，answered 2 → 3。
    → **覆盖随圈数近似线性增长、没看到饱和、也没看到质量下降**；
      预算本质是「买多少覆盖」的旋钮，不是「等它自然停」的旋钮。

  ★★ 结论二：查出两个真 bug（都在默认路径上，与预算定多少无关）：
    1) **`rounds=0` 时配置形同虚设**（`_rounds_plan`）。命令行 `--rounds`
       的默认值就是 `"0"`，旧代码把它当成「所有层都用全局 hard_max」——
       `per_entry.<层>.hard_max`（修行配置的 6）与 `min_rounds` 被完全盖掉。
       和 fix-105（`--parallel` 硬编码把配置项架空）同一类病。
       → 现在 0/None 走逐层兜底；显式正整数语义不变。
    2) **`min_rounds` 被当成预算而不是下限**。旧兜底「mr > 0 就用 mr」，
       于是研究层 `min_rounds: 2` 会被当成「预算就是 2」——正撞上配置
       注释里记着的教训（研究层 2 圈 → 可判定覆盖率仅 33%）。
       → 现在：预算 = 该层 hard_max，但不低于该层 min_rounds。

  ★ 顺带修掉一处**旧的隐藏矛盾**：对撞层 `soft_max: 5` 而旧的默认预算 3，
    `3 < 5` → **自然安住永远不可能触发**（软参比预算还大，判据是死的）。

  做法：
    · `dgtf_config.yaml` 的 `per_entry` 补上每层 `hard_max`，
      并取**中间档**：修行 4 / 研究 4 / 对撞 6（soft_max 5）/ 元 4(+1)。
      省档（3/3/3+1）与宽档（6/4/7/5+1）都写了实测数字，一行可切。
    · `_rounds_plan` 两个修正 + `check_rounds_plan` 四条断言
      （rounds=0 逐层读配置 / 显式值语义不变 / min_rounds 是下限不是预算 /
      min_rounds 高于 hard_max 时取 min_rounds）。

  ★ 诚实交代：**这轮没有证明"某个预算是对的"**。数据只说明覆盖随预算
    线性增长、没有饱和点，所以"多少圈合适"是取值取舍，不是模型性质。
    我取中间档是因为它比省档多给一点推进余地、比宽档省一半钱，
    而不是因为数据说它最优。

  ────────────────────────────────────────────────────────
  [⑥] per_entry 去掉：出厂全层一致，按层差异一律走运行时
  ────────────────────────────────────────────────────────

  出厂默认改为**全层一致**：
    soft_max: 3 ／ hard_max: 12 ／ stable_layers: 3 ／
    structure_saturation_every_n: 3 ／ min_rounds 全 0 ／ **无 per_entry**。

  三处跟着改的实现值（都写成全局，行为等价或更简单）：
    · `structure_saturation_every_n` 2 → **3**（全局）。这个检查本来
      只在研究层与元层跑（条件写着 `entry in ("1","all")`），所以
      统一成 3 与原先把这两层各写一个 3 **完全等价**，少两处例外。
      保持 3 而不是回到 2，是因为 v1.21.48 研究层 2 圈就停、
      可判定覆盖率仅 33%（v1.21.49 才放宽到 3）。
    · `stable_layers` per_entry."all" 的 2 **去掉** → 元层用全局 3。
      ⚠️ 这是**行为变化**：元层「悬置决定稳定→自然安住」的门槛从 2 提到 3，
      自然安住更难触发、元层会跑更久。要恢复原样就在运行时加
      `spiral.per_entry."all".stable_layers: 2`。
    · `min_rounds` `"1":2/"both":3` → **全 0**。它想防的「研究层 2 圈就停」
      已由结构饱和度间隔 3 解决；且各层理由自身都带 ≥2 圈的累计门槛，
      下限 2 只能拦「第 1 圈停止」——那件事本来就不会发生。

  `per_entry` **机制保留**（宪法级约定「参数按层可覆盖」），只是不再出厂
  预置值。按层差异三条运行时路：
    1) 命令行：`--rounds "0:4,both:6"`（只管预算，最常用）
    2) 交互式：`圈数 [0=用 hard_max]> 0:2,1:2,both:3,all:3`
    3) 配置文件：临时加 `spiral.per_entry: {"both": {soft_max: 5}}`
       （要改的不只是预算时用）
  配置文件的注释、三套推荐配置示例都按这个口径重写了。

  ────────────────────────────────────────────────────────
  [⑦] 停止与收敛条件审计 + 两路径一致性守卫
  ────────────────────────────────────────────────────────

  新增参考文档 **`元DGTF-停止与收敛条件.md`**（133 行），回答
  「各层、各模式的收敛与停止条件是什么」。核心结论：

    ★ **9 个模式的停止理由集完全一致**——圈循环只有 2 条代码路径：
        `_run_layer`（serial / A）与 `_run_one_round_B`（B / C / D–H），
      两条路径的理由列表**逐条相同**（已逐条比对）。差异只在"谁驱动
      圈循环"，不在"什么时候该停"。所以不必分模式记停止条件。

    文档内容：9 条理由的触发条件 / 累计门槛 / 适用层矩阵；
    理由之后的 4 道闸门（fix-88b / min_rounds / 元层语义下限 / 走满）；
    两个 tracker 的收敛与停滞定义；三个已踩的坑；
    以及三条运行时调参路径。

    模式特有的三件事（都不属于停止条件）：A 的汇流圈（单圈、不走螺旋、
    没有判据）、C/D–H 的预热 `parallel_warmup_rounds`、D/E 的出发时序。

  同时加冒烟守卫 `check_stop_reason_parity`：把两条路径的停止理由块
  分别抓出来（按出现顺序取第 0/1 个 `stop_reasons` 初始化，块长度限定
  20–160 行以防锚点漂移后静默通过），断言 13 条理由字面量在**两条里
  都有**。这是本项目第 N 次防「同一条逻辑两条通道各写一份只改一边」——
  这次是主动加的，不是出事之后补的。

════════════════════════════════════════════════════════════
v1.21.57 相对 v1.21.56 的改动（本轮收束版）
════════════════════════════════════════════════════════════

  [P3-1] 抽 _finalize_layer_common：两条跑圈通道的收尾不再各写一份。

  为什么做：本项目「同一条逻辑两条跑圈通道各写一份」已暴露 5 次——
    跨圈去重 / _flag_all_drift / 覆盖率段 / 成本档的 _final_dedup /
    以及**整段收尾**。每次改都要在两个地方各改一遍，漏一处就分叉
    （v1.21.55 的 next_role 反馈环就是这么来的）。

  做法：
    · 新增 `MetaDGTF._finalize_layer_common(entry, view, state)`，
      收尾的 8 步全在里面：跨圈回填 → 二次去重 → 质量检查（含
      all 层漂移标记）→ 研究层双通道合并 → 池回填 → 元层闭环
      （含覆盖率段）→ apply_keep + 终局清算。
    · `_run_layer`（serial 通道）：143 行收尾 → 1 次调用 + 打包 state。
    · `_b_finalize_layer`（B/C/D-H）：137 行 → 12 行（只留「取 state +
      守卫」）。
    · 两条通道的局部变量名原本就基本一致，实测确认后直接打包成 state。

  统一时发现的差异（都不影响行为，已在注释里写明）：
    · **顺序**：池回填的位置两条通道相反（_run_layer 在后、
      _b_finalize_layer 在前）。已确认互不依赖——_settle_meta /
      _coverage_segment 读的都是**池**（self.pools / self.dec_tracker），
      不是 view 上的副本；_apply_keep / _settle_research 同理。统一成
      「池回填在闭环之前」。
    · **文案**：vp 提示语两边略有出入，统一取较详细的那版。
    · **self 记忆的写入时机**：serial 在收尾里写、B/C/D-H 在
      _run_one_round_B 里逐圈写——**保留差异不统一**（统一会改变时机）。

  验证（两条独立证据）：
    a. **产物逐字对比**：serial / B / C 三条通道，重构前后的 md
       （排除时间戳行）**逐字一致**。
    b. 冒烟 9 模式全绿。

  ★★ 冒烟抓到一个逐字对比没抓到的真实回归（值得记）：
    我一开始把 `_append_self_text` 也收进了公共函数。但两句调用方的
    守卫是 `if rounds_n > 1:`（单圈层不进收尾），而原实现里
    `_append_self_text` 在**块外**——单圈的层也要写 self。
    结果：A(no-all) 模式下（route 不含 all，某些层只跑 1 圈）
    self 段变成 0 层，被冒烟的 [P0-1] 断言抓到。
    为什么逐字对比没抓到：它的默认配置每层都 > 1 圈，覆盖不到这个
    边界。**教训：产物逐字对比必须覆盖边界配置（rounds=1 /
    route 不含 all），否则「无损」是假的。**
    修法：`_append_self_text` 留在公共函数**外**，由 _run_layer
    在块外单独调；公共函数不再有 with_self 参数。

  副产品：`_snap_baseline.py` 保留下来——它是这次用的重构验证工具
    （跑 serial/B/C 的 mock 产物，与基线逐字对比），以后做高风险
    重构可以直接复用。

  ────────────────────────────────────────────────────────
  [② 复查] min_rounds.all：**保持 0，设成 2 是死配置**。
  ────────────────────────────────────────────────────────

  v1.21.55 走查建议把 min_rounds.all 设成 2，当时搁置的理由是
  「根因是 P0-1 的假停止理由」。P0-1 已修且四次真跑确认，现在复查。

  结论不是「影响小」，是「**不可能被触发**」（两头一夹）：
    · 一头的 min_rounds 语义：判据是 `layer_no < min_r`（layer_no 是
      1-based 圈号）。0 → 2 只拦得住「第 1 圈停止」——第 2 圈停下时
      `2 < 2` 为假，拦不住。
    · 另一头 all 层的停止理由最早只能在**第 2 圈**产生：
        - 「ing 连续 N 圈复述」（_rephrase_streak >= 2）
        - 「自省连续 N 圈点名同一批问题未消化」（carry_streak >= 2）
        - 「连续 N 轮无新 &／无线头／有新增无推进」（round_idle_limit
          默认 2，也要累计 2 圈）
        - 「自然安住」「元决策耗尽」另有 layer_no >= soft_max(3) 的门
      第 1 圈没有任何一条能成立。
    → 设成 2 永远等不到它该拦的那一刻，是死代码。

  all 层真正的下限是**语义下限**：收尾第 3 步里「元层闭环未清算 →
  推迟停止」——只要张力没交代清就继续走，比任何数值下限都准，
  而且不看圈号。

  佐证（不是主论据，是旁证）：四次真跑（quality/balanced/economy v1/v2）
  全部「体力耗尽」走满圈数，`被 min_rounds 拦截` 出现 **0 次**，
  日志里「元层闭环未清算」也都是 0 次——因为这几层的 stop_reasons
  从头到尾就没触发过（每个判据都要累计 2 圈以上，3~4 圈的预算
  跑不满）。这反过来说明：现在真正的旋钮是**圈数预算**，不是 min_rounds。

  所以本轮**没有改默认值**，只做两件事：
    · 在 DEFAULT_CONFIG 的 min_rounds 处把这个「两头夹」写清楚，
      免得下一轮再把它当成待办捡起来；
    · 冒烟加断言：`min_rounds.all == 0`，且「元层闭环未清算」这条
      语义下限必须在源码里（数值下限是 0，语义下限没了就等于没下限）。

  ────────────────────────────────────────────────────────
  [③ P2-3] all 层「落到具体」：条件回流，不是无条件硬约束。
  ────────────────────────────────────────────────────────

  走查原话是「all 层 prompt 强制原样引用具体场景」。**没有照做**，
  因为它和「输入是形状不是数据」直接冲突：逼 all 层引用别的 view
  的原文，等于把 all 拽回别层内容，正好违反 v1.21.32 硬约束
  （「候选的对象是 all 这个状态本身，不是任何一个 view 的内容」）。
  走查自己也标了「建议先不做」。

  改成本轮的做法——**条件触发 + 换落点**：
    · 触发条件：只在上一圈 all 候选**确实漂移**时注入。判据直接复用
      _all_candidate_drift_rate / _all_candidate_selfref_rate，
      阈值复用 spiral 里已有的 all_drift_threshold / all_selfref_threshold
      （即 _flag_all_drift 用的那一对）。不漂就一个字都不加。
    · 落点换掉：不再要求「引用别的 view 的原文」，而是要求
      「每条候选都能指到一个具体的东西——谁、什么情况下、发生了什么，
      或者缺了哪一样」。这样既治了「抽象话」，又不把 all 拽回别层。
    · 通道：走既有的自省回流（_build_carry → carry kind=candidate），
      不新增 prompt 分支——下一圈展开时由 _carry_block_text 渲染进去。

  **取样时机与 _flag_all_drift 不同，这一点必须说清**：_flag_all_drift
  只在层收尾算一次（结果挂产物上），这里**每圈都算**。逐圈更密——
  某圈漂了、最后一圈自愈了，产物里看不到漂移标记，但那一圈的下一圈
  确实收到了约束。日志里给这条单独留痕（`🧭 [P2-3] all 候选漂移…`），
  因为它排在 carry 末尾，不在前 3 条的预览里。

  ★ 诚实交代：**现有 6 份真跑产物里，all 层一次都没漂**（
  all_candidate_drift / selfref 标记 0 次）。所以这条是**为未观测到的
  失效模式准备的防御**，在这批数据里证不出价值。之所以还做：判据是
  逐圈算的（比收尾那一次密），且成本为零（不漂就不注入，不涨调用）。
  要验证它，得先拿到一份 all 层真的在讲抽象话的产物。

  ────────────────────────────────────────────────────────
  第 7 次真跑：专挑「容易诱发 all 层抽象化」的题，结论 + 一个误报修复
  ────────────────────────────────────────────────────────

  题：**「复杂问题被拆成几个部分分别研究之后，剩下的那个「整体」
  到底是什么？」**——选题理由：all 层的职责是「作为整体，all 自身是
  什么」，与题目同形，最容易让它把**问题的结构**和**系统的结构**
  混起来。配置：balanced · serial · 四层 · 3 圈。
  结果：126 次调用 / 533 649 token / 1075 s / 探针 65 /
  answered [1,2]（2/2 可判定子问题）/ answer.distance 0.2 /
  综合距离 0.35 / 质量线索 1 条（合法）。答案落到了实处（子问题1
  用集合论 ⟨P,R⟩ 给出整体=部分集+关系集；子问题2 用统计力学的
  极限与粗粒化说明「非加和 ≠ 不可导出」），自省也诚实点名候选 7
  属于「说明而非展开」。题目够抽象，输出没有变空。

  **① P2-3 触发 0 次**（7 份产物累计 0 次）。逐条看过 all 层 14 条
  候选：手工算的漂移 1/14、自指 0/14——**判据没响是对的**，因为那些
  候选虽然抽象，抽象的是**题目本身**（all / 剩余 / 位置），用的不是
  机器词（层名 / view 名），也不是模式里的本层自指字面词。

  **② ★★ 抓到漂移判据的一个误报，并修掉（本轮最实在的产出）**：
  那唯一命中的一条候选是
    『「之后」若两侧各记一次，中间那一拍既不属于拆解也不属于登记，
      all 是否就停在这个无人记的拍上』
  ——「两侧」指**拆解侧 / 登记侧**，是题目自己的两侧，不是两个 view。
  标记表里的「两边 / 两侧 / 上游」属于**可能同时是题目用词**的词，
  当标记就是误报源。
  误报的代价不止是挂错标记：v1.21.57 起 all 层漂移会触发 P2-3 的
  「落到具体」回流约束——对**本来就该抽象**的问题，这条约束会去
  逼它具体，等于压坏质量。也就是说这个误报是**我自己刚引入的机制
  放大了它**。
  修法：drift 判定改用 `_ALL_DRIFT_MARKERS`（只留不可能属于题目的
  机器词：view0 / view1 / view both / 两个|多个|三个|四个 view /
  对撞层 / 研究层 / 修行层）；被拿掉的三个词进
  `_ALL_DRIFT_SOFT_MARKERS` 备查，不参与判定。
  冒烟断言双向钉住：题目的「两侧 / 上游」必须判 0，真漂移
  （view0 / 两个 view / 层名）必须仍判 1——防止有人把判据放宽到失效。

  **③ 第一次在真跑里看到 all 层的真实停止理由**（前四轮全是
  「体力耗尽」）：
    `⏹ 螺旋停止（第 4 圈）：连续 3 轮无线头新增（方向走完了）`
  这是**正面验证**了 [②] 的复查结论——all 层停止理由需要累计
  >= 3 圈才成立，`layer_no < min_r(2)` 永远为假，所以
  min_rounds.all=2 确实是死配置。之前只有「没触发」的旁证，现在
  有了「触发了、而且确实绕过 min_rounds」的正例。
  同一段还有 `[fix-88b] 未深入方向 9 条，放行停止（已达上限 1）`
  ——这是 max_uncovered_pushes 的设计行为，不是 bug。

  **④ 更正一条我此前的说法**：覆盖率双口径不是「方向相反」。
  逐产物看（只有 v1.21.56 起的 3 份带双口径）：
    自报 0.33｜实算 2/2   自报 0.43｜实算 3/3   自报 0.95｜实算 2/2
  ——**同一份产物里，自报从来 <= 实算，没有一次倒挂**。
  真正的问题是**跨运行排序会骗人**：quality(235008) 自报 0.70 而
  economy(002910) 自报 0.33，可按已答数排是 economy(3) > quality(2)。
  所以双口径该留，理由要改成「自报与实算两个口径不一致、且跨运行
  排序不可信」，不是「模型总往低报」。

  **⑤ 同一次复查还发现标签本身写错了，已修**：产物原来印的是
  「（**模型自报**，累计 N 次记录）」，但 LLM 的输出 schema 里
  **根本没有 coverage 字段**（decidable_product 只有 answer /
  answered_sub_ids / evidence / distance）——这个数是
  `coverage_of(pool)` 算出来的 `Σ w·depth / Σ w`，其中 depth 是模型
  在 engagements[].depth 里自给的 0~1 深度，deferred 的子问题另记
  0.2。也就是说它是「**模型自评驱动、代码按权重折算**」，不是模型
  直接报的一个数。标签改成「模型自评折算·depth 加权」。
  两个口径为什么不一样，也一并写进 docstring 了（四处差异）：
    1) 加权 + depth 折算  vs  等权计数；
    2) deferred 记 0.2    vs  完全不计；
    3) 累计最大值         vs  收尾那一刻的瞬时值；
    4) 按 weight 加权      vs  不看 weight。
  冒烟断言同步改成认新标签。

  **⑥ 不可判定通道也补上双口径**（可判定有双口径、不可判定只有单
  口径，是不对称的缺口）。第七节原来只讲可判定通道；不可判定那侧
  的 `clarity` 与 `struct_coverage` **只进了喂模型的 shape，产物里
  看不到**。现在抽 `_und_channel_line()`，两条通道并排显示：
    研究层可判定通道最近一次覆盖率：0.95（模型自评折算·depth 加权，
      累计 3 次记录）｜代码实算：已答子问题 2/2
    研究层不可判定通道：清晰度 0.75（模型自评，累计 3 次记录）｜
      结构覆盖率 0.60（代码实算，已对上 6/10 个不可判定方面）
  两个口径的含义与可判定侧同构：
    · 清晰度 = 模型自给的 `undecidable_product.clarity`；
    · 结构覆盖率 = 评估阶段圈出的 `und_aspects` 里被 `structural_amps`
      命中（`_overlap_coef >= 0.3`）的比例——**这条是代码实算的**。
  只有不可判定通道有数据时（fallback 分支）也一并给结构覆盖率，
  不再只剩清晰度。
  冒烟加断言：两条通道必须并排；结构覆盖率与「已对上 X/Y」必须出现；
  fallback 分支也必须带结构覆盖率。

  **⑦ 不可判定通道补一本轨迹账**（与 deferrals 对等）。可判定那侧
  deferrals 有逐条状态（deferred/handled/escalated/dropped），
  不可判定那侧只有 `last_struct_hit` **一个数**（「这圈对上几个」）——
  轨迹和「哪个方面是从哪一圈开始被对上」全丢了，事后无法回看。
  做法（`Pool.add_undecidable` 加 `layer` 形参，两个跑圈通道都传）：
    · `aspect_first_hit`：{方面 → 首次被对上的圈号}（只记第一次）
    · `struct_trace`：逐圈 [{layer, hit, total, cov, newly}]
      newly = 这一圈**新**对上的方面（重复命中不再进）
  产物池段渲染：
    - 📘 不可判定覆盖轨迹：L1 1/3（+1） → L2 2/3（+1）
    - 📘 首次对上的方面：本体论地位需要先确定登记位置（L1）、…
  调用链要传圈号：`_apply_view_to_pool(..., layer=N)` →
  `_apply_view_to_pool_locked` → `add_undecidable(..., layer=N)`；
  serial 通道传 `layer_no`，B/C/D-H 通道传 `r`。
  `last_struct_hit` 的语义没动（仍是命中条数），_update_trackers 那行
  日志照旧。冒烟断言：圈号序列、逐圈命中数、首次命中圈号**不被后面
  的圈覆盖**、newly 只含新增。

  ────────────────────────────────────────────────────────
  [自查-5] ★ 平一笔账：上一轮我报过「P3-2 加了双向断言」，**其实没做**
  ────────────────────────────────────────────────────────

  v1.21.56 的交付说明里写着「P3-2 的 _MODE_LABEL 加了双向断言，
  没改结构」。查证结果：**代码里没有**，changelog 里也没记。整个文件
  当时只有 1 处 assert，在别的地方（3196 行，跟这事无关）。
  也就是说不是「写了没做」，是**既没写也没做**——而我把它当已完成的
  事项报了。这笔账在这里平掉。

  补上之后的真实状态与理由（不是"补个好看的断言"）：
    · `_MODE_GRAPH` 是**硬索引**（`graph = _MODE_GRAPH[mode]`），
      缺 key 直接 KeyError；
    · `_MODE_LABEL` 用的是 `.get(mode, mode)`，缺 label 会**静默降级**
      成裸字母——产物标题会变成「🧵 F 模式：F」，读的人看不出是漏配。
  两表都是本文件里的硬编码常量，不同键只可能是改文件时漏一处，
  所以**在导入时**就 `raise ValueError`（缺 label / 多 label /
  graph 里出现非法层名三种都报），别等跑完一轮才发现标题不对。
  冒烟加 `check_mode_tables`：两表同键 + 层名合法 + 每个模式都能算出
  时序图 + 标签不允许退化成裸字母。
  失效验证做过：故意删掉 H 的 label → 导入即报「缺 label ['H']」；
  故意在 H 里塞一层 "9" → 导入即报「非法层名 {'H': ['9']}」。

  ────────────────────────────────────────────────────────
  [自查-6] ★★ 停止判据可达性复查：19 次「体力耗尽」里有 9 次是谎报
  ────────────────────────────────────────────────────────

  起因是那句「成本实际由圈数预算决定」想去查清楚。统计 5 份带日志的
  真跑：**「体力耗尽」19 次，真实螺旋停止 1 次**。

  先排除了「判据够不着」这个假设——把三个计数器逐次拉出来看：
    idle_new_amp    分布 {0:57, 1:7, 2:1}
    idle_new_thread 分布 {0:43, 1:17, 2:4, 3:1}
    idle_stall      分布 {0:51, 1:13, 2:1}
  有 **6 次**确实够到了阈值（≥2）。判据是可达的。

  那为什么没停？逐条追那 6 处上下文 → 找到 `fix-88b`：只要「还有没深入
  的方向」，它会 `stop_reasons = []` **把停止理由清空**。而对比圈号发现：
  balanced 那 3 次推迟**全部落在各层最后一圈**（修行/研究/元都是），
  drift 的 2 次里也有 1 次。

  于是这条机制有两处不诚实：
    1) **最后一圈推迟停止毫无意义**——for 循环本来就要结束，推迟买不到
       下一圈，只是把理由丢掉。
    2) 被丢掉的理由**不留痕**，收尾于是永远写「体力耗尽（…未触发任何
       停止判据）」——那些圈里这句话是**假的**。（与 P0-1 同一类病：
       停止理由名实不符。P0-1 修的是「把复述和未消化混成一个数」，
       这次是「把触发的判据擦掉说没触发」。）
  另外：没有上一次测量时（prev_missed_n is None）原来写「减少中」，
  那只是「首次」，无从判断趋势——一并改成如实叫「首次」。

  做法（顺手把这段从两条通道收口到一处，第 6 次同类收口）：
    · 新增 `MetaDGTF._uncovered_gate(...)`，返回
      (stop_reasons, streak, prev_n, deferred_note)。三条放行理由分开写：
      已达上限 / 方向数未减少 / 已是最后一圈没有下一圈可推。
    · `is_last_round=True` 时**不再清空理由**（推迟买不到东西）。
    · 推迟掉的理由进 `deferred_notes`，收尾如实写出来：
      「体力耗尽（4 圈走满；1 次停止判据被「未深入方向」推迟
        （连续 2 轮无线头新增（方向走完了）），是被截断不是自然停止）」
    · 两条跑圈通道都改（serial 传 `layer_no >= _total_rounds`，
      B/C/D-H 传 `r >= total_rounds`）。

  ★★ 顺带查出一个**通道不对称**（比上面那条更严重）：「走满预算」这件事
     **原来只有串行通道会说**。B/C/D-H 的层走满时 `view.stop_reason`
     是空的，产物里连【螺旋停止】都没有——读者分不清「按判据停了」和
     「被截断」。既然 P3-1 已经把收尾收口到 `_finalize_layer_common`，
     就把这句挪进公共收口点（`if not view.stop_reason` 才写），
     9 个模式口径一致，serial 里那份删掉。

  验证（三条，都做了）：
    a. `_uncovered_gate` 四种走向单测：非最后圈+首次→推迟并留痕；
       最后一圈→不推迟；方向数没减少→放行；没有未深入方向→归零。
    b. `_finalize_layer_common` 三种：无推迟 / 有推迟（必须如实报出、
       不许再说「未触发」）/ 已有理由（不得被覆盖）。
    c. **端到端**：把 `round_idle_limit`/`round_stall_limit`/`idle_limit`/
       `soft_max` 全推到 99 强制走满，serial / B / C 三个模式的产物
       各出现 4 次「体力耗尽」——B、C 在修之前这里是**空白**。
  冒烟新增 `check_stop_gate`（含一条源码断言：`f"体力耗尽（"` 只允许
  出现在公共收口点的 2 个分支里，防止有人又在通道里各写一份）。
  ★ 写这条源码断言时自己踩了一次：只排除「# 注释」不够，
  `_uncovered_gate` 的 docstring 里引用了这句话，被多数进来一次——
  改成只数 f-string 形态。

  ── 这次复查**没有改任何阈值** ──
   判据可达、预算也没错，问题全在「推迟逻辑 + 交代方式」。
   19 → 9 的账现在对上了：9 次是推迟，10 次是真的没触发。
   如果想更进一步让判据**真的**早停省钱，那是另一个决定：
   把 `max_uncovered_pushes` 从 1 调成 0（第一次触发的判据就直接停），
   但那样会牺牲「给未深入方向一次机会」——本轮不动，留给你定。

────────────────────────────────────────────────────────────
★ v1.21.59 收束摘要（上一轮定稿，保留备查）
────────────────────────────────────────────────────────────

【本轮做了什么】一次真跑 + 四组代码修正。

  0. **整体运行质量验证**（真跑，不传 rounds → 走配置默认 12）
     333 次调用 / 1 585 809 token / 47 分钟；四层停成 **12 / 8 / 10 / 5**，
     **3/4 层由判据自己停**（研究 8 结构饱和度 / 对撞 10 自省点名 /
     元 5 自省点名+无线头；修行 12 是唯一走满的）。
     ★★ **修正 v1.21.58 第十二节的结论**：那里写「当前版本没有自然停止点，
     预算就是决定量」——不对。正确表述：**停止判据有"累计窗口"，预算必须
     至少覆盖那个窗口（实测约 5–10 圈）**；给 12 时 3 层提前停、没花满。
     真正的成本是**各层自然停止点之和**，不是预算上限。
     质量是三次里最好的一档（质量线索 0 条；all 池 & 101 / 线头 59）；
     机制面逐项核过（复述 0、回流注入 31、fix-88b 推迟 5 放行 4、
     min_rounds 拦截 0、双口径在、命中轨迹在、漂移标记无）。
     `stable_layers` 2→3：本轮**无可见影响**（元层第 5 圈因「自省点名」停）。
     完整记录见 `元DGTF-真跑验证报告.md` 第十三节。

  1. **池段子问题口径**：原来把 `sub_questions` 的**总数**渲染成
     「可判定子问题 N 条」——v59 那 5 条其实**全是 undecidable**。
     这是本轮我自己那条假报告（"5 条被升级为不可判定"）的**直接源头**。
     改为分项计数（总数：可判定 a / 不可判定 b / 另有 c 条 partial 等），
     并加冒烟 `check_pool_sub_label` 防复发。

  2. ★ **可判定性三态互转**（用户判定：「这是机制的漏洞，应该是双向的」）
     旧实现只有 `decidable→undecidable` 一条腿，且**全文没有回写路径**
     ——"不可逆"不是守卫，是没人写反向代码；蓝图 §二 那句也没给论证
     （真正像原则的 §四 讲的是**层间不写别人的池**，是另一件事）。
     现在：三态任意方向可转，**唯一入口 + 证据的确定性校验**
     （每条引用必须能在**此刻的池里**定位到：`A#/P#/T#/S#/C#/ing` 或原句
     模糊匹配），定位不到 → **整条驳回并留痕**；`Pool.decidability_log`
     append-only 记**全部方向与被驳回**；tracker 去掉"只升不降"的 `max()`
     （分母变了那圈只重置基线，不计停滞/改善）。

  3. **评估→拆解不再"一次传播"就定死**
     根因：不变量「undecidable ⇔ 没有可判定方面」**三处没人守** ——
     池评估（读修行池那次）没有归一化；`_merge_decidability` 无条件采信
     池判；`_decompose_question` 只看标签分派、且 koan **不接收
     `dec_aspects`**。→ 覆盖率分母从出生就是 0（v59 整层交白卷）。
     抽出**全项目唯一一份** `_normalize_decidability`，池评估/外判/合并/
     分派点四处都用；合并改为**先并集方面再定状态**。
     ★ **用 v59 原数据回放：合并后从 `undecidable` 变 `partial`，
     那 3 条可判定方面不再被丢，分派走 hybrid。**
     顺带统一「欠一个答案」的集合 `_DEC_ANSWERABLE = (decidable, partial)`
     （7 个取值点；以前只有喂模型的 shape 认 partial，分母不认 = 静默漏账）。

  4. **复债**：分类被推翻时，被关掉的账要回来
     迁向 undecidable 会顺手把该 sub 名下 deferred 关成 escalated（合理），
     **反方向原来是断的**。新增 `_reopen_closed_debt`：**新开一笔、不复活
     旧条**（历史 append-only）、**只对确实被关过账的开**（否则给债务账灌水）、
     `revisit_condition` **原样归还**、记 `reopened_from` 指向被接续的旧账。

【验证覆盖】
  · 冒烟 **53 项全绿**（本轮 31 → 53）：新增 `check_pool_sub_label`、
    `check_decidability_transitions`(8)、`check_decidability_normalize`(6)、
    `check_debt_reopen`(5)。
  · 真跑 1 次（默认预算 12，balanced · serial；产物 141 KB）。
  · 回放验证 3 处：v59 评估数据 → partial；三态 6 方向；复债完整往返。
  · 静态：AST OK、CRLF 一致（脚本改文件后**逐次**核对）。

【已知遗留（下一轮的起点）】
  1. ★ **分类分布**：归一化后「undecidable + 任一侧列了可判定方面 → partial」
     会让 `_decompose_koan` **变得少见**（只有两侧都列不出可判定方面才走）。
     v59 那道题新规则下判 partial —— 可能是对的，也可能**稀释"不可判定"
     这个信号**。**下一轮真跑先看这个**；若一边倒偏向 partial，收紧方向是
     "要求可判定方面来自池侧 / 或禁止形式化列举"，但那需要证据。
  2. **本轮三条修正都还没有真跑证据**：v59 真跑里一次 escalation 都没有，
     所以三态互转 / 复债 / 归一化都只有单测 + 回放。下一轮该跑一次能
     真正触发它们的题。
  3. `_merge_decidability` 归一化后，`_divergent` 仍按**原始**两侧状态算
     （有意保留"外判当时说了什么"），是否该按归一化后的算未定。
  4. `stable_layers` 2→3 仍待场景验证（要有一次"元层走到自然安住"的真跑）。
  5. **成本**：默认 12 是省档的 2.7 倍。压成本应给**唯一停不下来的修行层**
     单独设上限（`--rounds "0:6"`），**别调低全局 `hard_max`**（那会把累计
     窗口重新关上、退回"体力耗尽"）。

【经验教训】
  1. ★ **"读产物"得出的因果，和"读代码"得出的因果，可信度不一样。**
     我在 13.5 编出的"5 条被升级"是读产物读出来的，且读的还是我自己写错的
     一行渲染。**报"已完成/已发生"之前必须回到代码与日志核对。**
  2. **渲染措辞是接口**：一行把总数标成"可判定"的渲染，能让人编出一整套
     不存在的因果链。产物里每个标签都要能被代码核验。
  3. **同一份逻辑一有分身就会漂**（本项目第 N 次：归一化只有外部评估有、
     可回答集合只有 shape 认 partial）。收口到唯一入口 + **源码守卫**有效。
  4. **"不可逆"这类设计断言要问它的论证在哪**：蓝图 §二 只有一句断言，
     被引用的 §四 讲的是另一件事。**两者被并成一句了。**
  5. 脚本改主文件后**逐次核对 CRLF**；多行替换前先把行尾归一化成 LF
     （否则按 LF 拼的 old_string 永远匹配不上），写完再切回 CRLF。
     已写进项目 MEMORY.md 的坑清单。
     ★ 顺带又踩了一次同源坑：本条原写成 `反斜杠-r 反斜杠-n` 的样子，
       docstring 会把它**转义**，于是「摘 docstring 再扫源码」的断言
       当场失效（源码里是字面量、`mod.__doc__` 里是 CR/LF）——
       两个"必须不存在"的历史检查因此误报。**docstring 里别写单个反斜杠。**

────────────────────────────────────────────────────────────
★ v1.21.58 收束摘要（上一轮定稿，保留备查）
────────────────────────────────────────────────────────────

【本轮做了什么】七项，全部由「真跑证据 + 历史样本 + 代码审计」驱动：

  1. [①] `max_uncovered_pushes` 1 vs 0 的 A/B 真跑。
     结论：**保持 1**。A 臂里这个旋钮一次都没机会起作用——8 个层收尾
     里唯一一次「判据触发 + 还有未深入方向」落在**最后一圈**，被新加的
     `is_last_round` 守卫直接放行，1 和 0 的行为路径完全重合。
  2. [④] 报告改名：《成本档位验证报告-v1.21.56-economy真跑.md》
     → **《元DGTF-真跑验证报告.md》**，加「文件沿革 + 按议题分的目录」。
  3. [⑤] 用**历史样本定标**（两批 350 份旧产物、44 份可解析）。
     ★ 结论：**当前版本没有"自然停止点"可等，预算就是决定量。**
     给 6/4/7/5 的预算，四层跑到 6/4/7/6 全部顶上限，每圈仍有真·新增 &。
     两个测点（13 圈 125 次 / 23 圈 220 次）显示覆盖随圈数**近似线性、
     没饱和、质量不掉**——所以"多少圈合适"是取舍，不是模型性质。
  4. [⑥] **去掉 `per_entry`**，出厂全层一致：`soft_max 3` / `hard_max 12` /
     `stable_layers 3` / `structure_saturation_every_n 3` / `min_rounds` 全 0。
     按层差异一律走运行时（`--rounds "0:4,both:6"` / 交互式 / 配置里临时
     加 `per_entry`）。机制保留，只是不预置值。
  5. [⑦] **停止与收敛条件审计** → 新文档 `元DGTF-停止与收敛条件.md`。
     ★ 结论：**9 个模式的停止理由集完全一致**——圈循环只有 2 条路径
     （`_run_layer` = serial/A；`_run_one_round_B` = B/C/D–H）。
  6. **修掉 `_rounds_plan` 两个真 bug**：`rounds=0`（命令行默认值）时
     `per_entry.hard_max` 与 `min_rounds` 形同虚设；`min_rounds` 被当成
     预算而不是下限（研究层 `min_rounds: 2` 会被当成"预算就是 2"）。
  7. **加两路径一致性守卫** `check_stop_reason_parity`：断言 13 条停止
     理由在两条通道里各一份。主动加的，不是出事之后补的。

【验证覆盖】
  · 冒烟 **33 项**（新增：预算解析 4 条 / 停止理由两路径一致性 / 走满文案）。
  · 真跑 **2 臂 A/B**（125 / 124 次调用）+ **预算宽档 1 次**（220 次调用）。
  · **历史样本 350 份**（44 份可解析出圈数与停止理由）。
  · 配置注释里三条「恢复旧行为」写法**逐条跑过验证**。

【★ 本轮最实在的产出：预算定标的结论是"推翻了自己的前提"】
  本来想用历史样本的"自然停止点"（3–4 圈）当目标预算。查证发现那些
  样本跑在 **v1.21.56 收紧停止判据之前**（旧 `carry_streak` 只要产出
  carry 就 +1，停止极易触发）——**判据改过之后那条曲线整个移位了**。
  当前版本给多少预算就跑多少圈。所以"按自然停止点定预算"这个做法
  在当前版本不成立，只能按"买多少覆盖"来取舍。

【已知遗留 · 下一轮的候选】
  ① **`hard_max: 12` 的实际成本没测过**。全层统一 12 + 判据判不了
     "做完了"，四层可能各跑到 10+ 圈，成本估计是 `--rounds 3` 的 3–5 倍。
     下一轮该测的就是这个——同时也是"整体运行质量"的验证。
  ② **`stable_layers` 2→3 是行为变化**（元层自然安住门槛提高），
     未真跑验证。看元层实际跑几圈、有没有触发自然安住。
  ③ P2-3 至今 **0 次触发**（8 份产物）。判据没响是对的，但要证明它
     有用得先拿到 all 层真在用机器词说话的产物。
  ④ `self_layers` 不缩那处防御改动——仍**没有实测差异**，撤或留。
  ⑤ 真跑样本仍偏少（同题同档的对照目前 n≤3）。

【本轮的经验教训（供下一轮自查）】
  · **做 A/B 之前先确认操纵量在当前条件下可达。** 这次先跑完 A 才发现
    推迟路径根本没被触发——如果只跑 B 一臂就下结论，会把噪声当效果。
  · **自报指标与代码实算指标可能方向相反**（本轮是第 2 次）：大预算的
    自报「综合距离」0.64（看着更差）、代码实算「质量线索」1.04（实际更好）。
    一律以代码实算为准。
  · **同题 + 同一天才是受控对照。** 第一次比出来的"大预算标记少一半"
    差点被"后来版本加的检查项更多"这个混淆毁掉，靠日期切开才站住。
  · **别拿旧版本的"自然停止点"当当前版本的目标**——判据改过，曲线移位。
  · **写配置示例必须先跑一遍。** 本轮我凭印象编了一个不存在的键名
    （`min_rounds_override`）还称它"已废弃写法"；已改正为真实写法。
    与上一轮那条"报已完成前必须查证"是同一种病：**凭印象代替验证**。
  · **顺手加的守卫/断言最容易被口头完成**（上一轮的 P3-2 假报告）。
    本轮把两路径一致性做成了冒烟断言，而不是只说一句"我加了断言"。

────────────────────────────────────────────────────────────
★ v1.21.57 收束摘要（上一轮定稿，保留备查）
────────────────────────────────────────────────────────────

【本轮做了什么】九项，都是「代码自查 + 真跑复查」查出来的：

  1. [P3-1] 抽 `_finalize_layer_common`——两条跑圈通道的整段收尾合一。
     产物逐字对比验证无损；冒烟抓到一处逐字对比没抓到的真实回归
     （_append_self_text 被误收进公共函数，单圈层 self 段变空）。
  2. [②] `min_rounds.all` 复查：**保持 0**。判据是 `layer_no < min_r`，
     0→2 只拦得住第 1 圈，而 all 层第 1 圈不可能产生任何停止理由
     （都要求累计 ≥2 圈）——两头一夹，设 2 是死配置。
  3. [③] P2-3：all 层候选漂移时，条件回流一条「落到具体」的约束。
     **没照走查原话做**（它要求「原样引用具体场景」，会把 all 拽回别层
     原文，跟 v1.21.32 硬约束打架）。
  4. 第 7 次真跑（专挑易诱发 all 层抽象化的题）+ 修掉 drift 判据一个误报
     （「两侧」指题目的两侧，不是两个 view；误报会被 P2-3 放大）。
  5. [⑤] 覆盖率标签更正：「模型自报」→「模型自评折算·depth 加权」。
     查证发现 LLM 的输出 schema 里**根本没有 coverage 字段**。
  6. [⑥] 不可判定通道对齐双口径：清晰度（模型自评）+ 结构覆盖率（代码实算）。
     以前这两个量只进了喂模型的 shape，产物里看不到。
  7. [⑦] 不可判定通道补轨迹账：`aspect_first_hit` + `struct_trace`
     （哪个方面从哪一圈被对上），与可判定侧的 deferrals 逐条状态对等。
  8. [自查-5] `_MODE_LABEL` / `_MODE_GRAPH` 加导入时守卫——**并平掉一条
     我上一轮报过但其实没做的账**（详见下面的经验教训）。
  9. [自查-6] 停止判据推迟逻辑修复（见下），并把「走满预算」的交代从
     串行通道挪进公共收口点——B/C/D-H 以前走满时**什么都不说**。

【验证覆盖】
  · 冒烟 **31 项**（本轮新增：P2-3 条件回流 / drift 误报 / min_rounds 结论 /
    模式表守卫 / 覆盖率双口径（两条通道）/ 不可判定命中轨迹 / 停止闸门）。
  · 真跑 **7 份产物**（其中 5 份带 verbose 日志），覆盖 quality×3 /
    economy×2 / balanced×2。
  · 端到端强制走满（serial / B / C 三个模式）验证「走满」文案落地。

【★ 本轮最实在的产出：19 次「体力耗尽」里有 9 次是谎报】
  统计 5 份日志：「体力耗尽」19 次、真实停止 1 次。先排除「判据够不着」
  （三个计数器分布显示有 6 次确实够到阈值），再逐条追上下文，找到
  `fix-88b`：「还有没深入的方向」就把 `stop_reasons = []` 清空。
  对圈号后确认 balanced 那 3 次推迟**全落在各层最后一圈**——
  推迟买不到下一圈，只把理由丢掉，而丢掉的理由不留痕，于是收尾谎报
  「未触发任何停止判据」（与 P0-1 同类：停止理由名实不符）。
  → 抽出 `_uncovered_gate`（第 6 次同类收口）；最后一圈不再推迟；
    推迟过的理由进 `deferred_notes` 并如实写进产物。
  → **没动任何阈值**：19 → 9 的账对上了（9 次推迟 + 10 次真没触发）。

【已知遗留 · 下一轮的候选】
  ① `max_uncovered_pushes` 从 1 调成 0？（第一次触发的判据就直接停）
     这是「真早停省钱」与「给未深入方向一次机会」的取舍，**需要你拍**。
     本轮刻意没动——economy 那轮已证明「少推」会让 unsaid_overused 变多。
  ② P2-3 至今 **0 次触发**（7 份产物）。判据没响是对的（那些候选抽象的
     是题目本身），但要验证它有用，得先拿到一份 all 层真的在用
     view0 / 上游 / 层名 说话的产物。
  ③ `self_layers` 不缩这处防御改动——至今**没有实测差异**，撤或留。
  ④ 报告文件《成本档位验证报告-v1.21.56-economy真跑.md》名不副实
     （里面塞了 v1.21.57 的第十节），该改名或重组。
  ⑤ 真跑样本仍偏少：balanced 2 次、economy 2 次、quality 3 次。
     所有「可复现」的结论都还是 n≤3。

【本轮的经验教训（供下一轮自查）】
  · **报「已完成」之前必须查证。** 本轮抓到一条我自己上一轮报过的账：
    说「P3-2 的 _MODE_LABEL 加了双向断言」——既没写也没做，changelog
    里也没记，而我把它当完成事项报了。同类风险：凡是「顺手加的守卫 /
    断言」这类小改动，最容易被口头完成。
  · **扫源码做断言时，排除「# 注释」不够。** 函数 docstring 里引用同一句
    话会被多数进来（本轮 `f"体力耗尽（"` 那条断言就这么假报了一次）。
  · **下结论前先对齐统计口径。** 19:1 那个比例，第一反应是「阈值结构上
    够不着」，实测是「被推迟逻辑擦掉」——两个完全不同的修法。
  · **优先查「机制是否真的在跑」，而不是先调参数。** 本轮没动任何阈值，
    就把 9 次谎报修掉了。
  · 「同一条逻辑两条通道各写一份」本轮又收口两次（fix-88b 判据、
    走满文案）——新加跨通道逻辑一律先问「有没有统一收口点」。

────────────────────────────────────────────────────────────
★ v1.21.56 收束摘要（上一轮定稿，保留备查）
────────────────────────────────────────────────────────────

【本轮做了什么】三批，都在 56 内完成：
  第一批 修 P0/P1/P2 + 两处自查（正确性与可观测性）
  第二批 参数配置化（散落阈值收成命名常量 + 8 个 spiral 键）
  第三批 成本档位 cost_profile 三档 + --profile CLI，并跑真模型验证

【验证覆盖】5 次真模型产物（同一台机、同一份 .env）：
  quality    113841 / 132911 / 235008（其中 235008 是与 economy 的
             同期对照，134 次调用）
  economy    230737（v1 按圈号跳，108 次）
             002910（v2 按角色跳，110 次）
  balanced   010533（换新题「欧盟 AI 法案」，124 次）
  结论见 `成本档位验证报告-v1.21.56-economy真跑.md`（九节）。

【交付物】
  代码   元DGTF-V1.21.56.py（本文件）
  配置   dgtf_config.yaml（顶层 cost_profile + spiral 新键 + 注释）
  测试   smoke_test.py（9 模式 + 6 组成本档断言，全绿）
  报告   成本档位验证报告-v1.21.56-economy真跑.md
  产物   outputs/ 下 5 份 md + cost_*_run.log（verbose 全量）

【已知遗留 · 下一轮的候选，按建议优先级】
  ① P3-1 抽 `_finalize_layer_common`。
     「同一条逻辑在两条跑圈通道各写一份」在本轮暴露四次
     （去重 / _flag_all_drift / 覆盖率段 / 每次改都要改两处），
     收益在累积。高风险，建议单独一轮做。
  ② `min_rounds.all` 复查。第二轮搁置时写「根因是 P0-1，修完再看」——
     现在 P0-1 已修且四次真跑确认（停止理由全部是新的正确文案）。
  ③ P2-3「all 层 prompt 强制原样引用具体场景」——走查建议，
     风险是与「输入是形状不是数据」打架，一直没做。
  ④ 两处「语义正确但未实测出差异」的防御性改动
     （self_layers 不缩、覆盖率双口径）保留观察。

【本轮的经验教训（写在 changelog 里供下一轮自查）】
  · 判「某改动影响了历史结论」之前必须先拿产物实测复核，别靠推断。
    本轮就出现过一次：靠推断说 self_layers bug 影响了 economy 的结论，
    实测后推翻（self 段两边都是 4 条、都不触发截断）。
  · 扫源码做断言时必须先摘掉模块 docstring 和注释行——changelog 里
    引用了改动前的旧代码，否则断言在跟历史注释打架。
  · 统计产物时先确认提取边界：本轮用「找下一个二级标题」定位章节末尾，
    结果被 manifest 里的「## 一、这一路看到了什么」提前截断，
    把 4 条 self 误读成 1 条。
  · changelog 在模块 docstring 里，写代码示例时反斜杠会被转义
    （本轮写 find 的换行参数时踩到，导致 docstring 与文件原文不一致、
    冒烟的「摘 docstring 再扫源码」断言失效）。要写字面反斜杠得写两个。

────────────────────────────────────────────────────────────
v1.21.56 相对 v1.21.55 的改动
（修 P0 正确性 / P1 可观测性 / P2 质量 + 三处自查发现）
────────────────────────────────────────────────────────────

  这一批来自同一份实测产物：outputs/20260929_132911_…
  （与 113841 是同一个问题，唯一变量是 v1.21.55 的修订），
  加上两份外部代码走查指出的 P0/P1/P2/P3。逐条核对过，
  有三条走查结论与实测不符，写在最后「核对后未采纳」里。

  ── P0 · 正确性 ──

  [P0-1] 停止理由把三种计数器合成一个，然后一律写成「ing 复述」：
           _mi_effective = max(meta_idle_streak, _meta_idle_streak(view),
                               carry_streak)
           stop_reasons.append(f"ing 连续 {_mi_effective} 圈复述")
         三个来源语义不同：前两个是**真·复述**，carry_streak 是
         「本圈产出了自省回流约束」——自省正常工作就会有，跟复述无关。
         实测证据（132911 产物，元层）：
           · 自省：ing 复述（模型自判）：False
           · 代码实算复述率：0%（被显示逻辑吞掉，见 P0-2）
           · 停止理由：ing 连续 4 圈复述（层内空转）
           · 同一层的圈表：第 4 圈 新 & 3 / 新线头 3，连续无新增 0/0
         三个口径里只有第三个在说复述，而且圈表直接反驳「空转」。
         更实际的后果：第 3 圈结尾已满足触发条件，是靠「元层闭环
         未清算 → 推迟停止」那条兜底才保住第 4 圈。若那圈清算刚好
         干净，这层会被一个假理由截断，且没人知道。
         → 拆成两条，各说各的：
           · _rephrase_streak = max(meta_idle_streak, view 上的值)
             → 「ing 连续 N 圈复述（层内空转）」
           · carry_streak → 「自省连续 N 圈点名同一批问题未消化」
         并且 carry_streak 的口径也改了：不再「有 carry 就 +1」，
         而是**同一批问题被反复点名**才 +1（_carry_banned_set +
         _carry_is_repeat，两圈的点名内容要对得上）。
         换一批新的点名说明这一圈长出了新东西，不该算空转。
         两条跑圈通道（_run_layer / _run_one_round_B）都改了。

  [P0-2] rephrase_ratio 为 0 时被 falsy 跳过：
           save_result: if v.get("rephrase_ratio"):   ← 0.0 不打印
         结果最需要这个数字的那层（元层）反而没有这一行，读者只看到
         自省说 False、停止理由说复述，无从裁决。
         → View.rephrase_ratio 默认 0.0 改 None（区分「算出来是 0」
           和「没算」）；打印条件改 is not None；
           None 且自省明确说没复述时，补一行「未计算」说明原因。
         ★ 私有属性 _ing_rephrase_ratio 保持 0.0 默认不动：
           _apply_view_to_pool 的 culture/idle 判据读的是它。

  ── P1 · 可观测性 ──

  [P1-1] carry_check / carry_dropped 每圈覆盖，只剩最后一圈：
         view 对象每层共用一个，跑 3 圈的层在产物里看着像只核对了
         1 次（实测 132911 四层全写「核对 1 条」）。
         → View 加 carry_checks / carry_dropped_all 两个列表，
           逐圈 append（带 round 号）；carry_check / carry_dropped
           单值保留，兼容旧读法。save_result 逐圈渲染 + 合计。

  [P1-2] 两个「both 配额」阈值来源不同、名字还一样：
           _tighten_both(cdicts, max_ratio=0.3)        ← 写死，改判
           _enforce_both_quota: max_ratio = cfg 0.7    ← 可配，追问
         逻辑上能自洽（前者改极性、后者追问缺什么），但读代码的人
         容易以为 0.7 是唯一的配额。
         → 0.3 提成 spiral.both_tighten_ratio（默认 0.3），
           调用处加注释写清「这是改判阈值，不是追问阈值」。

  [P1-3] 闭环清算的分母没写清：
         _settle_meta 只算 active/stable 的对撞张力。实测 both 层
         5 条悬置里 3 条 resolved、2 条 active，产物写「未交代 2 类」，
         读者看着列表里的 [resolved] 会以为清算漏了。
         → 返回值带 closed / duel_total，md 补一行
           「（对撞悬置共 5 类：3 类已了结不参与清算，2 类待交代）」。

  ── P2 · 内容质量 ──

  [P2-1] 线头 / & 的近义改写去重不敏感：
         实测修行层三条线头讲的是同一件事（失语瞬间能否共享），
         0.65/0.70 抓不到。→ & 和线头单独调松到 0.60/0.62，
         候选维持 0.65/0.70（候选比线头更怕误杀）。
         两条通道同一套阈值，不再各写一份。

  [P2-2] all 层候选的**元自指**抓不到：
         现有 _all_candidate_drift_rate 只认「view0 / 两边 / 上游」
         这类跨层标记，抓不到「这个说法本身」「本层候选」
         「all 的候选」这种自指。实测元层自省自己写了
         「候选 3、5 偏自指补写」，但候选还是留下了。
         → 加 _SELF_REF_MARKERS + _all_candidate_selfref_rate，
           > 0.4 时挂 all_candidate_selfref(n) 质量线索。
         只加标记不删候选（悬置不打分，这里也不替模型删）。
         抽成 _flag_all_drift(view)，两条通道共用——原来只在
         _run_layer 里有，B/C/D-H 通道没有。

  ── 自查发现（不是走查指出的，本轮读产物读出来的）──

  [自查-1] 四象限对齐是一条从来没亮过的通道：
         10 份产物（4 个不同问题）匹配率全是 0%。查下来是判据结构上
         不可能达标：_similar 分母取 max(len(a),len(b))，修行层的短
         target 对研究层的长 sub_question，关键词数量差一个量级。
         → 加 _aspect_match：保留原判据，另补一条**包含度**判据
           （短的那侧有多少关键词落在长的那侧，阈值 0.6），
           两条阈值都进了 spiral 配置。
           实测这条补判据确实有效：有共享词的三组（「回位槽开合判据」
           × 回位槽那条问句等）从 0 变成 0.67~1.00，旧判据对它们
           全部返回 False；真正无共享词的仍然判不配对上。
         ★ 但要说清楚它的边界：拿 132911 那两对真数据测
           （「T6 判定权归属」×「AI 是否应被视为与人对等的…」），
           字面交集是空集，补了判据之后**仍然**是 0——这两层本来就
           是用互不相干的词汇在说同一个缺口，那是设计使然，
           字面相似度救不了。
           所以另一半改动是可观测性：practice_n / research_n /
           best_score 进产物，0% 时能看出是「真的没有同一件事」
           还是「判据对不上」。以前这两者在产物里长得一模一样。
           未对齐仍然是宪法级的合法结果，没动。

  [自查-2] 悬置生命周期允许同一实体同时占两个终态：
         实测 132911「研究延迟处理的」里同一个子问题同时挂着
         handled 和 escalated（另一个 handled 和 dropped）；
         113841 里也复现过（AI 伦理规范：handled + escalated）。
         → 悬置总览按目标合并，只显示最新状态，迁移过程写进括号
           （「（dropped，状态迁移 handled→dropped）」）。
           只改渲染，不动池里的账——生命周期的诚实记录要留着。

  ── 参数配置化（把散落的魔法数字收拢成命名常量 + 挑三组提成配置）──

  之前盘过一次：约 80 个顶层参数可配，但还有 30 处相似度/占比阈值
  硬编码在调用点（0.85 出现 18 处、0.75/0.62/0.5 各若干处）。

  · 收拢成命名常量（不配置，模块顶部一张表，见「判据阈值」段）：
      _DUP_SIM=0.85 / _REPHRASE_SIM=0.75+_REPHRASE_OVERLAP=0.62 /
      _BAN_SIM=0.85+_BAN_OVERLAP=0.70 / _CARRY_REPEAT_*=0.70+0.50 /
      _KW_TOP_N=8 / _QC_BACKFILL_RATIO=0.5 / _QC_DIVERSITY_RATIO=0.4 /
      _QC_OVERLAP_POOL_RATIO=0.7 / _TRACKER_COVERAGE=0.7 /
      _TRACKER_CLARITY=0.6 / _ALIGN_MATCH_LO=0.1 / _ALIGN_MATCH_OK=0.3 /
      _PARALLEL_CONF_MIN=0.5
    这些阈值经常成对出现（_similar 分母取 max、_overlap_coef 取 min，
    互补），注释里写清了谁跟谁配对。
    ★ _REPHRASE_* 有意不配置：ing 复述判定样本只有 n=1，调它=过拟合。

  · 提成 spiral 配置的三组（都有默认值，旧配置不改也能跑）：
      去重（_final_dedup 统一读）：
        dedup_candidate_overlap/similarity（0.65/0.70）
        dedup_amp_overlap/similarity（0.60/0.62）
      质量线索（_quality_check）：
        qc_rephrase_ratio（0.5，ing 复述率触发线）
        qc_both_ratio（0.6，候选 both 占比触发线）
      all 层漂移（_flag_all_drift）：
        all_drift_threshold（0.5）/ all_selfref_threshold（0.4）
    同时把三段去重抽成 _final_dedup（两条跑圈通道共用），
    _flag_all_drift 从 staticmethod 改成读配置。

  ── 成本档位（cost_profile · 顶层总控三档开关）──

  顶层加一个 cost_profile，跨段生效（见 _profile_plan）：
    quality  —— 维持现状
    balanced —— （默认）token 精简：③ 候选截断（cand_limit=8）/
                ④ shape 收紧（×0.72）/ ⑤ 低频项惰性化（every_n +1）
    economy  —— balanced 之上再省调用次数：① 阴阳展开合并成一次 /
                ② 探针回归每 2 圈一次，shape 收到 ×0.55、候选截到 6
  实测（mock，2 圈 × 4 层，serial）：
    quality 81 次 → balanced 80 次 → economy 69 次（省 ~15% 调用；
    真模型下 ③④ 的 token 精简还会进一步降总 token）。
  刻意没做的：self_check 降频不在任何档里——上一轮刚验证它是质量的
  核心来源（both 层点名候选 7-12 凑数、all 层点名 3/5 自指都极准），
  降频等于质量滑坡。

  [成本档 ①] 阴阳合并的健壮性（这条值得单独记）：
    合并调用要求模型在第二段前**单独一行原样输出「===== 阳 =====」**，
    机器按这一行切段。prompt 里写明了「改了就切不开」。
    ★ 兜底：模型没按标记分段时，**补跑缺的那半边**，而不是把它静默
      丢掉。所以最坏情况退化成原来的两次调用（成本不亏），
      但永远不会丢内容。解析还带一层容错（整行只含阳字与符号也认）。
    实测证据：mock 一开始不输出标记，economy 调用数从 69 涨回 78
    （补跑生效）→ 说明这条兜底真的在跑，不是摆设。
    冒烟加了 check_merge_fallback 钉住这条（缺标记时必须补跑、
    阴阳两段都要在）。

  三档产物结构对比（mock，不需要真模型）：
    4 层齐全、13 个关键段落全部存在、池统计一致、无 errors——
    降成本档不改变产物结构，只改喂进去的量和调用的次数。

  ── 成本档 · 第二批（economy + quality 真跑对照之后）──

  跑了两轮真模型（同题、紧挨着、唯一变量是档位），结论与改动：
    economy 108 次 / quality 134 次（省 19%）；耗时 1011s / 1055s。

  [② 改版] 探针不再按圈号跳，改按角色跳：
    原实现 `round_no % probe_every == 0`（每 2 圈跳一次），太平均——
    把「深入 / 转向」这类正要铺方向的圈也跳掉了。
    同期对照的硬证据：三次 quality 的探针数稳定在 64~66
    （各层 9/9/9/39），economy 是 42（6/6/6/24），下降完全符合
    ② 的算术 → 探针 -36% 是确定性代价，不是波动。
    而探针 -36% 的同时 & +21%、线头 +29% —— 资源从「问方向」挪到了
    「沉淀内容」，所以 answer 更落地（distance 0.2 vs 0.6/0.9）
    但覆盖率下降、未生变多（both 层 unsaid_overused(6)）。
    → 改成 `_PROBE_SKIP_ROLES = ("收束", "复裁")`：只在**已经不再开
      新面**的圈跳过，保住「摊开 / 深入 / 转向」的推进力。
      `_profile_plan` 的 `probe_every` 相应换成 `probe_skip_roles`。

  [自查-2] 覆盖率双口径（真跑暴露的误导读法）：
    产物只写「最近一次覆盖率 0.40」，那是**模型自报**值；同一份产物
    里代码实算的已答子问题是 3/5，**方向相反**——
    economy 自报 0.40 而 quality 自报 0.70，但 economy 实答 3 个、
    quality 只答 1~2 个。只显示自报值会让读者以为 economy 更差。
    → 抽 `MetaDGTF._coverage_segment()`（顺带消掉「两条跑圈通道各写
      一份」的第三处双写），输出改为：
      「覆盖率：0.40（模型自报，累计 3 次记录）｜代码实算：已答子问题 3/5」

  [自查-3] 产物头部落痕成本档位：
    三份产物摆在一起，光看 md 分不清哪份是 economy、哪份是 quality。
    → packed 在 `MetaDGTF.run` 的统一收口处加 `cost_profile`
      （只加一次，不在 5 个并行模式分支里各写一遍），
      save_result 头部渲染成「**成本档位**：economy（再省调用次数）」。

  [自查-4] shape_scale 误缩 self_layers（结构参数当表述参数缩了）：
    ④ 的实现把 shape_chars / shape_items / self_layers 一起乘了
    shape_scale。前两个是**表述长度**（缩了只是说得简短，信息还在
    池里）；self_layers 是**结构/历史**参数——它决定
    `_merge_self_text` 的 cap = self_layers × per_entry，
    超出 cap 的层被 `blocks[-cap:]` **直接丢掉，别处没有备份**。
    balanced（0.72）下 self_layers 4→2，cap 8 条 → 4 条：
    四层的自我记忆只剩一半。那是机制层面的损失，不是成本优化。
    → 只缩 shape_chars / shape_items，self_layers 保持不动。
      冒烟加断言：balanced 下 self_layers 必须仍是 4，而 chars/items
      必须被收紧（两个方向都钉住）。
    ★ 实测复核（防止把影响说过头）：三份产物的 self 段都是
      **4 条、四层齐全**（每层 1 条可用 manifest，部分圈的 manifest
      为空被 accumulate_self 早退跳过）。修复前 balanced 的 cap = 4、
      修复后 = 8，而 blocks 只有 4——**两边都不触发截断，此前实测
      没有差异**。所以这是一次「语义正确性」修复（内容充足时才起
      保护作用），economy 的质量结论不受它影响。

  ── 核对后未采纳 ──
  × 「四象限 unaligned 是合法结果，不是 bug」——对了一半。
    未对齐合法是宪法级约束，没动。但「判据对不上」导致的恒 0% 是
    实打实的缺陷（补判据后确实能对上一部分），而「两层本来就用
    不相干的词汇说同一件事」那部分确实救不了——那只能靠可观测性
    把它说清楚，见 [自查-1]。
  × P2-3「all 层 prompt 强制原样引用具体场景」——走查自己标了
    「建议先不做」，风险是污染展开质量，与「输入是形状不是数据」
    也可能打架。本轮不做。
  × P2-4「min_rounds.all 设成 2」——根因是 P0-1 的假停止理由，
    那条修完再看是否还需要；现在动默认值会掩盖真实行为。
    all_extra_rounds 的默认值按走查要求没有改。
  × P3-1「_finalize_layer_common 抽公共尾」——高风险，走查自己也说
    「不要和 P0 混在一起改」。本轮只把**共享决策点**继续抽
    （_flag_all_drift / _carry_banned_set / _carry_is_repeat），
    跨圈合并的整段合并留到 v1.22 单独一轮。

════════════════════════════════════════════════════════════
v1.21.55 相对 v1.21.54 的改动（修 P2：自省结论落地 + 三处判据纠偏）
════════════════════════════════════════════════════════════

  [P2-1] 主动悬置 vs 硬边界分界（修行层探针）：
           实测产物里模型自己写过「EDA 闭源许可曾被放在主动悬置里…
           它不是『选择不碰』，而是材料外部的硬边界，推不动」——
           先写错，再自己撤回。与其等它撤回，不如在 prompt 里说死：
             suspensions 只收「我看清了 X，可以碰，但选择不碰，因为 Y」
             threads    只收硬边界：材料不够 / 工具限制 / 外部约束
           ★ 不要把「推不动」伪装成「选择不碰」——写进 suspensions
             就是把边界说成了姿态，下一圈会被当成还能开的选择重新拿出来。
           schema 加 threads 字段并解析进 view.threads（入池前去重）。

  [P2-2] 宁可空，不要凑（对偶判断 + 阴阳展开）：
           对偶判断：judgments 条数**可以少于候选条数**，
             判不了（信息不足 / 与锚点无关）就不输出该条；
             不要为了凑齐把判不出的填成 both。
             配套改：hit < n 不再无条件记 error（少判是合法的），
             只有 hit == 0 才算失败。
           阴阳展开：新增 NO_FILL_RULE，八个展开 prompt 共用。
             「展开出几条就写几条，只能展开 3 条就写 3 条」，
             禁止拿常识补充 / 换说法重述 / 清单整理凑数。

  [P2-3] ing 复述检测只对上游，不对本层候选：
           DGTF.run 里把 candidates 加进 _upstream_texts 的两行删掉——
           ing 本来就是吃候选的，候选不算「上游」。
           _detect_ing_rephrase 补第二判据：原来只有 _similar(0.75)，
           分母取 max，一句话被扩写三倍后相似度就掉到阈值以下，
           「换个说法」抓不到；补上 overlap coefficient（分母取 min）。
           ing 的「不许复述上游」硬约束从对撞层专用扩到所有层。

  [P2-4] 「此处未生」计数：诚实姿态 vs 逃避：
           self_check 加一条自报 unsaid_count + unsaid_is_escape；
           代码侧另按产物硬数一遍（collision/manifest/线头/&/
           不可判定通道），取两者较大值——模型靠少报藏不住。
           超过阈值 → quality_flags 加 unsaid_overused(n)，
           并把「不许再拿未生收尾」作为约束回流进下一圈。
           阈值走 spiral.unsaid_escape_limit（默认 3，支持 per_entry
           按层覆盖；0 = 不设限），兜底常量 UNSAID_ESCAPE_LIMIT = 3。

  [P2-5] 代码清理：
           删掉 v1.21.54 里重复定义的两处（第二个 _view_usable、
           第二个 _expand_pair —— 后者与前者逐字相同）。

  [P2-7] 自省回流（memory.carry_feedback）真正落地：
           [P1-5] 加了回流，但实测产物里自省抓到「候选 9-15 凑数」
           「ing 复述=True」之后下一圈照旧。查下来四处断点：
           a. carry 被塞进 seeds，渲染成「上一圈没带走的自问」——
              一条普通探针，模型当参考看，不当约束听。
              → 新增 Input.carry_constraints，走独立硬约束块，
                置顶进展开 prompt，并按 kind 分流进 ing / 对偶判断。
           b. 注入时把 role 改成「转向」「复裁」，而 _role_text 没有
              这两个 key → 返回空串 → 【本轮形状】整块消失；
              且改的是本圈已用完的变量，下一圈按 r 重算，
              「转向」从来没进过任何一圈。
              → 补两条 role 文案 + 用 next_role 真正传到下一圈。
           c. 只注入不核对：日志一行「注入 N 条」，没有证据说明生效。
              → 新增 _check_carry_response：禁条目是否重现、
                ing 复述率有没有降。结论进 view.carry_check、
                pool.meta、md 的【自省回流核对】段。
           d. 少了一条回路：「此处未生」用过头原本不回流。

  [P2-8] 自省结论补进 md（冒烟测试发现）：
           [P2-4]/[P2-7] 的新字段只进了 view.rendered，
           save_result 的每层段落没有渲染它们 → md 里查不到。
           这正是「自省结论只进 md 没用进下一圈」的镜像问题：
           结论连 md 都没进去。现在 save_result 补两块：
             · 自省段追加「此处未生」计数 / 逃避判定 / 分布
             · 自省段后追加【自省回流核对】：核对几条、违例几条
           还有一处连带 bug：_run_layer / _b_finalize_layer 在合并后
           整体重算 view.quality_flags，把圈内 _self_check 追加的
           unsaid_overused(n)（和 candidates_backfilled）抹掉了 →
           「此处未生超标」永远进不了质量线索。
           新增 _keep_selfcheck_flags：重算后把自省派生的线索补回。
           冒烟实测（9 模式）：核对 4 / 违例 8 / 未生 16 / 逃避 4 /
           超标 4（修前是 0）。
           顺带修掉阈值语义：unsaid_escape_limit = 0 按注释应该是
           「不设限」，但代码写成 unsaid_n > 0 就判逃避 → 0 反而成了
           最严的一档。现在 lim <= 0 一律跳过这条判据（含 prompt 提示、
           逃避判定、质量线索、回流约束四处）。
           实测：0→无 flag，3→unsaid_overused(4)，10→无 flag，
           per_entry."0".unsaid_escape_limit=1 覆盖全局 0 → 有 flag。

════════════════════════════════════════════════════════════
v1.21.55 · 第二批（跑出第一份真模型产物之后的修订，编号续 P2-9）
════════════════════════════════════════════════════════════

  这一批全部来自同一份实测产物：outputs/20260929_113841_…
  串行 3 圈，133 次调用。上文 [P2-1~8] 是改之前的假设，
  这一条之后写的是改完之后的证据。

  [P2-9a] 角色排班被 carry 自己喂回去（next_role 反馈环）：
           `_run_layer` / `_run_one_round_B` 末尾：
             if role == "深入": next_role = "转向"
             elif role == "收束": next_role = "复裁"
             else: next_role = role        ← 这一行把角色喂回下一圈
           两个后果：
             a. 只要每圈都产出 carry（常态），排班永久冻在「摊开」。
                b. 映射还错位一圈 —— 改写的是**本圈已用完**的角色，
                   应该是下一圈的默认角色。
           实测证据：那份产物四层的 roles_run 全是
           「摊开 → 摊开 → 摊开」，而 both 层的注释写着
           「至少 3 圈走完 摊开→深入→收束」。
           → 抽出 `_natural_role` / `_role_for_round` /
             `_carry_next_role`，两条跑圈通道共用同一个排班来源。
           修后：2 圈 = 摊开 → 转向；3 圈 = 摊开 → 转向 → 复裁。

  [P2-9b] 自省回流硬执行（carry 不再只是「记一笔」）：
           上一版注入了约束、也有核对记录，然后——什么都没发生。
           实测那份产物四层里三层「禁条目重现」违例，自省点名
           「候选 7、9 是上圈点名项的复述」之后下一圈照旧出现。
           → `DGTF._drop_banned`：命中 banned 的候选当场丢掉，
             不进对偶判断 / ing / 沉淀。判据抽成 `_banned_hit`，
             硬拦截与事后核对共用同一把尺。
           ★ 两个必须一起做的连带处理，缺一个就坏：
             - 丢之前留痕 view.carry_dropped，`_check_carry_response`
               先认这笔账，否则硬执行会把「违例」压成 0，
               用统计口径的干净掩盖行为没改。
             - 保底留一半（且至少留一条）。mock 里试过全丢：
               无候选 → _self_check 早退 → 这一圈没有自省 →
               下一圈没有 carry → 整层熄火。掐掉整个反馈环比
               放任它重复更糟。
           实测：md 每层多一段【回流硬执行 · 拦下的重现候选】。

  [P2-9c] 「宁可空，不要凑」从补充说明升为第一约束：
           上一版把 NO_FILL_RULE 追加在 prompt 末尾，而 prompt 里
           仍写着「输出 0-8 条」——「8」被当成要交的作业量。
           实测证据：0 层 self_check 点名候选 9-15「与 ing 几乎无咬合，
           像两套材料」；all 层点名候选 7-11「与 1-6 近义重复，
           疑为补写凑数」。
           → 六处 prompt 改写为「能写几条写几条（8 是上限，不是要交的
             作业量）」，并把 NO_FILL_RULE 挪到 system 段最前面。

  [P2-9d] 时序图不再手写：
           _MODE_TIMING 原来是手敲的，和真正执行的 _MODE_GRAPH
           不相符 —— F 的 all 画在 both 第一圈结束之前、
           G 的 all 画在 both 跑完之前、H 的 both 画在 1 跑完之前、
           D/E 各差一列。报一遍 D~H 就能发现。
           → 改由 `_mode_timing_lines()` 从 _MODE_GRAPH 算出，
             图与表不可能再分叉。
           （_MODE_LABEL 的 D「双起并行+撞元并行」/ E「双起并行+
             撞元串行」**与图是一致的**，这次核过，没动。）

  [P2-9e] 圈数上限的显示口径：
           all 层实际跑 _total_rounds = 请求圈数 + all_extra_rounds(1)，
           而停止理由和 md 写的是请求圈数。实测那份产物
           「实际走了 4 圈（上限 3 圈）」，看着像超跑。
           → 新增 View.rounds_cap，两处都用它。

  [P2-9f] ing 复述率进 md：
           实测 all 层出现判据打架：代码实算复述率 ≥50% 判停，
           同一层的 self_check 写「ing 复述 False／比例低」。
           谁对还需要样本，但读产物的人得先看见那个数字。
           → View.rephrase_ratio 导出并在自省段打印。
           ★ 阈值（0.75 / overlap 0.62）这次**没有动**，也没有
             为此加配置项：n=1，改了等于用一次观测去猜一个常数。
             先攒样本。
           ★ 改动时差点踩的另一个坑：_apply_view_to_pool 的空转判据
             读的是私有属性 view._ing_rephrase_ratio，
             不是新的公有字段 —— 两个都得写。

  [P2-9g] 阈值边界进冒烟：
           self_check 的逃避判定在 mock 下走过一轮就没人再验。
           check_p2_units 现在逐组验证：(3,3)→不判 (3,4)→判
           (0,9)→不判 (10,4)→不判，另外验角色排班、
           _banned_hit 的判据一致性、硬拦下之后核对仍认账、
           时序图与表同源。
           ★ 顺带确认一处口径：_self_check 在「无候选且无 &」时
             早退（空圈不值得回看，也不该多花一次调用），
             测试里必须给内容，否则量到的是早退分支。

════════════════════════════════════════════════════════════
v1.21.54 相对 v1.21.53 的改动（加 D~H 五种阶段式并行模式）
════════════════════════════════════════════════════════════

  [feat-109] D~H · 阶段式 DAG 并行：
           五种模式不是五套代码，是一张表 + 一台调度器。
           表 = _MODE_GRAPH，边上只有两种闸门：
             wait —— 上游**跑完所有圈**才放行（硬闸）
             gate —— 上游**交出第一圈**就放行（软闸）
           时序（→ 为时间）：

             D  0:    [r1][r2][r3]…        E  0:    [r1][r2][r3]…
                1:    [r1][r2][r3]…           1:    [r1][r2][r3]…
                both:        [r1][r2]…        both:        [r1][r2][r3]…
                all:            [r1][r2]…     all:                  [r1]…

             F  0:    [r1][r2][r3]…        G  0:    [r1][r2][r3]…
                1:        [r1][r2]…           1:        [r1][r2][r3]…
                both:        [r1][r2]…        both:        [r1][r2][r3]…
                all:            [r1]…          all:                  [r1]…

             H  0:    [r1][r2][r3]…
                1:        [r1][r2][r3]…
                both:             [r1][r2]…
                all:                  [r1]…

           跑圈逻辑仍然复用 _run_one_round_B（同一套停止判据 / 生命周期 /
           跨圈合并），上游供给用 C 那套"读当下最新"（实时快照）——
           D/E 里下游出发时上游已收工或已出圈，吃到的一定是最新的。

  [feat-109b] 闸门用 Event 而不是队列：每层两个事件，
           _st_gate（已交出第一圈）/ _st_done（已全部收工）。
           线程 finally 里两个都 set —— 上游崩了下游也只损失上游，
           不会把整张图吊死。等待另有 pipeline_gate_timeout 兜底。

  [note-109] D/E 的"一起开始"与 0 层预热：
           parallel_warmup_rounds 默认 1，D/E 下修行层先跑一圈再和
           研究层并行 —— 严格讲研究层晚了一圈。
           换来的是研究层第 1 圈能读到修行池（decompose_source=pool
           的内部路径生效）、可判定性走 pool+external。
           要字面意义的"同时出发"：把 parallel_warmup_rounds 设 0。

════════════════════════════════════════════════════════════
v1.21.53 相对 v1.21.52 的改动（加 C 模式 + B/C 的 0 层预热）
════════════════════════════════════════════════════════════

  [feat-106] C 模式 · 流水线并行（Pipeline）：
           四层各自在自己的线程里连续跑圈，**不等上游跑完**，
           只等上游交出第一圈就出发，剩下的圈一路接力：

               0:    [r1][r2][r3][r4]
               1:        [r1][r2][r3][r4]
               both:         [r1][r2][r3]
               all:              [r1][r2]

           层间接力用 threading.Event（原设计里的 queue.Queue 换成 Event
           是刻意的：这里要的语义只有"上游交出第一圈即放行"这一条，
           队列的排队/背压用不上，反而要额外处理"消费者不取就阻塞"）。
           每层每圈读的是**当下最新**的上游 view（实时快照），
           不是 Jacobi 的上一轮定格。
           与 B 的区别：B 每圈 barrier + 读上一圈快照；
           C 无 barrier + 读实时快照。C 更快，时序依赖更强。

  [feat-107] B/C 的 0 层预热圈（actions.parallel_warmup_rounds，默认 1）：
           v1.21.52 的 [P0-2] 把 0 层整层提出来先跑完再让其余层并行，
           修对了可判定性（不再拿问题字符串当判据），但顺手把 0 层
           变成了一段完全串行的瓶颈 —— 正确性赚回来，时间亏回去。
           改成：0 层只先跑 parallel_warmup_rounds 圈，
           拿这一圈的形状去判可判定性，然后 0 层带着已跑的圈数
           回到并行队列里继续跑。
           副作用（正是想要的）：研究层第 1 圈就能读到修行层产物，
           decompose_source=pool 的内部路径自然生效；
           对撞层第 1 圈就有 0/1 两侧可对齐，不再是空对齐占位。
           想恢复 v1.21.52 的"整层先行"：把该值设到 ≥0 层 hard_max。
           设为 0：完全没有预热，四层从第一圈就齐头并进（退化成
           v1.21.50 的 B 模式，可判定性只好走 external）。

  [fix-108] 对撞层不再无条件空对齐：
           _b_pre_layer 里 both 的 duel_alignment 原来只要 r==1 就写死
           "第 1 圈，上游尚未产生，无对齐"。预热落地后第 1 圈可能真的
           有两侧，改为按上游是否就绪判断，就绪就走真对齐
           （与 _run_layer 一致）。

════════════════════════════════════════════════════════════
v1.21.52 相对 v1.21.51 的改动（修 P0/P1 —— 来自四份真实产物的实测证据）
════════════════════════════════════════════════════════════

  [P0-1] _merge_self_text 按层轮转：
           原来是全局 blocks[-keep:]。并行模式下跑得最久的层（all，
           带 all_extra_rounds）最后完成，把其余层的自我记忆全部挤出。
           实测 B 模式两份产物的 self 段 4 条全是「元层」，
           回来通道的 self 只剩一个声部 —— 下一圈展开随之同质化，
           这正是 B-PNP 自省自认「候选 9-15 属补写凑数」的根因。
           改为每层保留 self_layers_per_entry 条，再按 (圈序, 层序) 交错。
           实测：修后 self 段恢复为四层各一条以上。

  [P0-2] 可判定性判定移到 0 层之后（A/B 模式）：
           A/B 原先在开跑前用 _assess_decidability(question) 做纯外部评估，
           判据只有问题字符串本身。实测同一 P=NP：A/B 判 decidable，
           串行判 undecidable —— 串行是对的，它跑完 0 层后用
           _assess_decidability_from_pool_view 读修行层留下的形状。
           A/B 模式下 1 层被迫走可判定通道，覆盖率失去意义
           （P=PN 那份报 1.00）。
           改为：0 层先行串行跑完 → 再判定 → 其余层并行。
           B 模式顺带把 0 层放进第 1 圈的 Jacobi 上游（原来第 1 圈全员无上游）。

  [P1-4] 极性 both 配额 + 强制补裁：
           实测三份产物极性 1 出现 0/0/1 次，both 占绝对多数，
           B-PNP 自省原话「每条 both 只拒绝合并，不判定了什么」。
           both 占比超 spiral.both_quota.max_ratio（默认 0.7）时，
           追加一次调用追问「要裁成 0 或 1 还缺什么」，结果写进
           adjudications[].missing 与 view.both_quota。
           不改裁决本身 —— 那会破坏「未对齐合法」的宪法级约束。

  [P1-5] 自省结论回流（memory.carry_feedback）：
           _self_check 的结果原先只进 md 的自省段落。三份产物的自省
           都精准抓到了「凑数」「ing 复述=True」「可疑 & 全 6 条」，
           然后什么都没发生 —— 花一次调用做质检，结论被丢弃。
           改为把结论翻译成下一圈的约束探针：
             · 可疑候选 → 禁止重述清单
             · ing_rephrased → 要求产出上游没有的句子
             · both_quota.missing → 要求把缺的东西生出来
           并复用已有的「连续复述」停止判据（carry_streak），
           不让空转无限续下去。

  [P1-6] 输入健全性自检（actions.input_sanity）：
           22:50 那次跑的是 P=PN —— PN 不是任何标准复杂度类。
           引擎不知道，把「PN 读法未定」当核心议题跑了 168 次调用。
           宪法允许诚实地说「此处未生」，但不该在第一步就把一个可能
           是笔误的符号当成合法对象收下。
           只报告不改写 —— 替用户改写问题等于替他决定想问什么。

════════════════════════════════════════════════════════════
v1.21.51 相对 v1.21.50 的改动（稳定性 + 并行展开）
════════════════════════════════════════════════════════════

  [fix-97] 终端编码兜底：
           导入期即把 stdout/stderr 重配置为 UTF-8（errors=replace）。
           否则在 GBK 终端或 `python x.py > log.txt` 重定向下，
           第一条 emoji 日志就会抛 UnicodeEncodeError 直接崩。

  [fix-98] LLM 截断标志线程隔离：
           last_finish / last_truncated 改为 threading.local 存储，
           _call_long 不再跨线程读到别的层的截断状态
           （v1.21.50 只给计数器加了锁，这两个漏了）。

  [fix-99] self_text 按层隔离（补完设计 9.7 的并发安全清单）：
           并行模式下每层各写 _self_text_by_entry[entry]，
           全部跑完后 _merge_self_text() 合并并截断到 self_layers。
           v1.21.50 里 4 个线程共享一个 list 做 read-modify-write，会丢条目。
           顺带补上 B 模式此前完全没写 self_text 的缺失。

  [fix-100] 池写入加锁：
           新增 MetaDGTF._pool_lock（RLock），覆盖 _apply_view_to_pool /
           self_text 写入 / _totalize_all_pool。

  [fix-101] A 模式汇流不再依赖 route 含 all：
           只要拿到 >=2 份**可用**的上游 view 就跑汇流圈；
           失败占位 View 不再被当成有效上游。
           route 不含 all 时汇流结果入池 + 写进 packed["confluence"] 并落盘。

  [fix-102] B 模式 _b_pre_layer 死代码清理：
           has_zero_prod 恒假导致"修行池内部分解"分支永不执行，
           改为按上游是否就绪真实判断（与 _run_layer 一致）。

  [fix-103] 配置兜底一致化：
           all_extra_rounds 代码兜底 2 → 1（与 DEFAULT_CONFIG 一致）；
           _rounds_plan 尊重 spiral.min_rounds 与 per_entry 覆盖。

  [fix-105] --parallel 不再硬编码 default="auto"：
           命令行不给时回落配置 actions.parallel_mode（原来配置项形同虚设）。

  [perf-104] 阴阳展开并行（设计 9.1 点名的可并行点）：
           阴/阳两次独立 LLM 调用用 ThreadPoolExecutor 并行发出，
           解析仍严格按 order 顺序串行（去重 seen 依赖先后）。
           每层每圈省一次往返。可用 actions.parallel_expand 关闭。

════════════════════════════════════════════════════════════
保留 v1.21.50 全部改动（并行模式 A/B/serial/auto）
════════════════════════════════════════════════════════════

  [feat-94] 并行模式三选一 + auto：
            a. 新增 parallel_mode 配置项（serial / A / B / auto）
            b. serial：0→1→both→all 严格串行（原逻辑）
            c. A：四层独立并行 + 汇流圈（用已有 View 补回 both/all 语义）
            d. B：轮次并行（Jacobi，每圈 barrier）
            e. auto：由 MetaDGTF._decide_parallel_mode 按问题性质决定
            f. CLI --parallel 与交互模式询问接入

  [refactor-E] MetaDGTF.run 拆分：
            a. 原 run 主体改名 _run_serial
            b. 新 run 做模式分发
            c. 内嵌 run_layer 闭包提升为 _run_layer 方法
            d. 内嵌 _inp_base/_inp_duel/_inp_meta 提升为 _build_inp_* 方法
            e. 新增 _pack_result / _merge_confluence 辅助

  [fix-95] LLM 计数器加锁：
           total_calls / total_tokens 在并发下用 threading.Lock 保护。

  [fix-96] DGTF._expand_from_question 加 entry 分支：
           A 模式下 both/all 从 question 出发，需要专属 prompt。

════════════════════════════════════════════════════════════
保留 v1.21.49 全部改动
════════════════════════════════════════════════════════════
  [fix-90..fix-93] 见 v1.21.49 changelog。

宪法级原则全部保留：
  - 悬置不打分
  - 未对齐合法
  - 停止与清算分开
  - 输入是形状不是数据
  - 失败必须留痕
  - 入池前挡重复
  - 按层覆盖参数
