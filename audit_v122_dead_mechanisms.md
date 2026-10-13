# 机制审计 v122

- 生成时间：2026-10-13T16:00:03
- 被测源码：`元DGTF-V1.22.0-rc1.py`
- 语料：日志 487 份 / 产物 368 份
- 合计：可达 13 · 仅源码 0 · 需核对 0（共 13 项）

★ 「零触发」不等于「没用」。verdict 只要不是 `需核对`，都说明机制在源码里存在、只是本批产物没走到那条分支 —— 要区分「条件不可达」「条件窄但成立」「机制压根没工作」需要**负对照**，那张表在 `docs/机制审计-v122.md` 的 `## pending_fix` 里。

| 机制 | 触发条件 | 日志标记 | 产物标记 | 源码 | 日志 | 产物 | 判定 |
|---|---|---|---|---|---|---|---|
| `escalate_starve_rounds` | 连续 N 圈无进展 + 名下有账 | `escalate_starve_rounds` | `escalate_starve_rounds` | 7 | 20 | 0 | 可达 |
| `no_push_when_idle` | 空转类判据 + 未深入方向 | `no_push_when_idle` | `no_push_when_idle` | 4 | 20 | 0 | 可达 |
| `_reopen_closed_debt` | 分类被推翻 + 曾有 escalated | `_reopen_closed_debt` | `_reopen_closed_debt` | 10 | 20 | 0 | 可达 |
| `stable_layers` | 悬置连续 N 圈同批 | `stable_layers` | `stable_layers` | 17 | 9 | 0 | 可达 |
| `both_quota.max_ratio` | both 占比超阈值 | `both_quota` | `both_quota` | 3 | 459 | 345 | 可达 |
| `both_tighten_ratio` | 同上，改判 | `both_tighten_ratio` | `both_tighten_ratio` | 5 | 20 | 0 | 可达 |
| `_all_settle_streak` | 元层清算未下降 | `_all_settle_streak` | `_all_settle_streak` | 10 | 20 | 0 | 可达 |
| `min_rounds` | layer_no < min_r | `min_rounds` | `min_rounds` | 54 | 91 | 0 | 可达 |
| `structure_saturation` | 每 N 圈无新维度 | `structure_saturation` | `structure_saturation` | 14 | 57 | 2 | 可达 |
| `_budget_exhausted` | 调用数超预算 | `_budget_exhausted` | `_budget_exhausted` | 10 | 40 | 0 | 可达 |
| `DecidabilityFreeze.verify` | 签名不匹配 | `DecidabilityFreeze` | `freeze` | 0 | 1 | 62 | 可达 |
| `triage_downgrades` | 信息不足型 und + 锚点命中 | `triage_downgrades` | `triage 降级` | 2 | 24 | 1 | 可达 |
| `_anchor_crosscheck.conflict` | 结论与锚点相反 | `锚点冲突` | `锚点冲突` | 0 | 24 | 2 | 可达 |

## 语料清单

日志（487）：
- `_all_final.log`
- `_all_final2.log`
- `_all_final3.log`
- `_all_final5.log`
- `_anchor_matrix_v75.log`
- `_audit_v12328.log`
- `_auto_pipeline.log`
- `_auto_run.log`
- `_batch_full_tail.log`
- `_batch_light_tail.log`
- `_batch_open_full.log`
- `_batch_open_light.log`
- `_batch_policy.log`
- `_bench_p1_real.log`
- `_bench_p1v2.log`
- `_bench_v1221_full.log`
- `_bench_v122_full.log`
- `_cmp_v12325_structcov.log`
- `_ctrl1.log`
- `_ctrl2.log`
- `_diag_f3_trace.log`
- `_evidence_batch.log`
- `_final_verify.log`
- `_final_verify_cfgsync.log`
- `_g64_control.log`
- `_ingest_v77.log`
- `_ingest_v77b.log`
- `_mut_b.log`
- `_mut_c.log`
- `_mut_d.log`
- `_mut_m9.log`
- `_mut_v12325.log`
- `_mut_v12326.log`
- `_mut_v12328_d3.log`
- `_mut_v12328_final.log`
- `_mut_v12328_final2.log`
- `_p1_run1.log`
- `_p1_run2.log`
- `_p1_run3.log`
- `_p1_runs.log`

产物（368）：
- `bench\reports\v1221_full.md`
- `bench\reports\v122_full.md`
- `bench\runs\mock_p1\biz_001\20261004_223416_一家现金流紧张的中小制造企业该先裁员还.md`
- `bench\runs\mock_p1\eng_001\20261004_223417_老城区暴雨内涝越来越频繁排水系统要不要.md`
- `bench\runs\mock_p1\tech_001\20261004_223417_订单系统该选一致性还是可用性CAP怎.md`
- `bench\runs\mock_p1b\eng_001\20261004_230344_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\mock_r1\eng_001\20261005_004258_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\p1_real\biz_001\20261004_224247_一家现金流紧张的中小制造企业该先裁员还.md`
- `bench\runs\p1_real\eng_001\20261004_224043_老城区暴雨内涝越来越频繁排水系统要不要.md`
- `bench\runs\p1_real\tech_001\20261004_224837_订单系统该选一致性还是可用性CAP怎.md`
- `bench\runs\p1v2\biz_001\20261004_235417_一家现金流紧张的中小制造企业该先裁员还.md`
- `bench\runs\p1v2\eng_001\20261004_235918_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\p1v2\tech_001\20261005_000047_订单系统要保证不超卖又要不卡顿下单链路.md`
- `bench\runs\probe_cost\eng_001\20261005_091756_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\probe_cost\eng_001\20261005_092618_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\probe_cost\eng_001\20261005_093301_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\v1221_full\biz_001\20261005_095748_一家现金流紧张的中小制造企业该先裁员还.md`
- `bench\runs\v1221_full\biz_002\20261005_095527_产品要出海定价按成本加成还是按当地竞品.md`
- `bench\runs\v1221_full\biz_003\20261005_095855_关键元器件只有一家供应商要不要强行多源.md`
- `bench\runs\v1221_full\eng_001\20261005_095448_老城区暴雨内涝频发排水系统要不要整体翻.md`
- `bench\runs\v1221_full\eng_002\20261005_095659_早高峰地铁站台拥挤越来越严重运营效率该.md`
- `bench\runs\v1221_full\eng_003\20261005_101556_在役桥梁数量多预算有限维护优先级怎么.md`
- `bench\runs\v1221_full\eng_004\20261005_101955_老城区地下管线反复开挖要不要改成综合管.md`
- `bench\runs\v1221_full\law_001\20261005_102450_业务要接欧洲用户数据跨境传输怎么合规落.md`
- `bench\runs\v1221_full\law_002\20261005_102240_集团内部各子公司数据共享的合法边界在哪里.md`
- `bench\runs\v1221_full\law_003\20261005_102257_法务人手不足合同能不能用模型自动审查.md`
- `bench\runs\v1221_full\med_001\20261005_104114_社区医院人力有限慢性病管理推远程监测还.md`
- `bench\runs\v1221_full\med_002\20261005_104536_慢病随访人数太多随访质量下降分层策略怎.md`
- `bench\runs\v1221_full\med_003\20261005_104347_城区急救车响应时间不均衡调度该怎么改.md`
- `bench\runs\v1221_full\org_001\20261005_104407_多个部门各自建系统数据不互通要不要强.md`
- `bench\runs\v1221_full\org_002\20261005_105513_内部推荐招人质量下滑内推机制该怎么改.md`
- `bench\runs\v1221_full\org_003\20261005_111053_跨团队协作长期卡在交接环节边界责任该怎.md`
- `bench\runs\v1221_full\tech_001\20261005_110938_订单系统要保证不超卖又要不卡顿下单链路.md`
- `bench\runs\v1221_full\tech_002\20261005_110649_分布式订单系统在CAP约束下该牺牲哪.md`
- `bench\runs\v1221_full\tech_003\20261005_110806_业务量上涨主键自增成瓶颈分布式ID.md`
- `bench\runs\v1221_full\tech_004\20261005_112034_灰度发布出错时回滚边界该怎么定义.md`
- `bench\runs\v122_full\biz_001\20261005_003611_一家现金流紧张的中小制造企业该先裁员还.md`
- `bench\runs\v122_full\biz_002\20261005_003649_产品要出海定价按成本加成还是按当地竞品.md`
- `bench\runs\v122_full\biz_003\20261005_003432_关键元器件只有一家供应商要不要强行多源.md`
- `bench\runs\v122_full\eng_001\20261005_005500_老城区暴雨内涝频发排水系统要不要整体翻.md`
