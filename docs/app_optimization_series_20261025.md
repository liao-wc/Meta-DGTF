# App / 调度优化机制汇总（2026-10-25）

本阶段围绕“全自动、少按钮、性能优先”落地了一组机制与功能，目标是在不牺牲质量门的前提下降低操作成本与任务启动延迟。

## 一、机制清单

1. 质量策略全自动（App 2.0.17）
   - 项目相关问题 -> auto:verified（注入项目背景）；
   - 通用问题 -> auto:stable（不注入背景、默认 web off）；
   - 联网/失败重试为 API opt-in（quality_policy=web/web-retry 或 web=on）。
2. 模式融合全自动（App 2.0.18）
   - 前端移除场景选择；默认 quality 优先选 B；
   - fused_* 参数保留为 API opt-in。
3. 事实题 web-retry（App 2.0.16）
   - 首跑 needs_evidence/unverified 时自动补跑一次 web；
   - 首任务记录 retry_task_id/quality_retry；默认不启用。
4. 项目背景 RAG 缓存（App 2.0.19）
   - 32 条 LRU；同题重复建任务不再重复扫文档/知识库；
   - 同题任务 POST 实测 276.8ms -> 69.9ms（约 -75%）。
5. M4 质量预测与模式区间（先前迭代）
   - kNN(k=3,近期加权)：随机 R²=0.916 / 时间 R²=0.521；
   - 用模式历史区间裁剪预测，减少误切档。
6. 真实链路修复（App 2.0.12/2.0.13）
   - behavior_fusion 不再覆盖 M4 选档；
   - rounds 提示 + 项目背景按相关性注入；
   - 默认通用任务实测 310.7s / 588,205 tokens 完成（修复前长跑超时）。

## 二、实测取舍

| 变体 | wall | tokens | quality | answer_quality |
|---|---|---|---|---|
| 无背景、无联网 | 310.7s | 588,205 | 0.8374 | unverified |
| 无背景、显式联网（成功样本） | 320.8s / 330.9s | 765,619 / 747,263 | 0.9783 / 0.9263 | verified |
| 无背景、默认联网（失败样本） | 280.4s | 731,619 | 0.4900 | needs_evidence |
| 项目背景、无联网 | 约1800s 超时 | 1.92M | 0.9598 | verified |

结论：默认 stable 稳定；verified 需要显式联网或项目背景；不要自动把联网强加给默认链路。

## 三、验证

- fast_gate 12/0；V2 39/39（534 检查）；App selftest 371/0；
- pip check 两环境 0 broken；verify PASS；loop 6/0；precheck 5/5；
- App 2.0.19 / engine 2.2.2。

## 四、未采纳/剩余

- dual_judge/self_check 细粒度替换：理论收益 ≤7% 墙钟，质量风险已由负结果验证；
- C/D/E 之外新并行架构：现有并行模式均质量受损，安全方案退化为 B；
- 建议后续如继续，先做小流量 A/B 试点与质量门对照，再考虑引擎版本迭代。

## 五、已验证答案缓存（App 2.0.20）

- 6h 内同题、同 web/parallel 的 verified packed 直接复用；
- 命中创建缓存任务（status=done，cached_from 可审计），不启动引擎；
- 实测：1+1 显式 web 复跑 POST 54.8ms 命中缓存（原约 320s/76万 tokens）；
- 未命中（如默认 stable 无 verified 源）正常启动引擎。

## 六、同题运行任务去重（App 2.0.21）

- running/queued 中已有同题、同 web/parallel/rounds/config/behavior 的任务时，新 POST 直接复用，返回 dedup_hit=true；
- 与答案缓存互补：运行中去重、完成后缓存；
- 实测同题连续两次 POST：第二次 dedup_hit=true 且 id 相同；取消首个任务后无残留。

## 七、语义答案缓存（App 2.0.22）

- 精确缓存未命中时，用本地 BGE 对近期 verified packed 的问题向量比较；
- 仅当余弦≥0.98 且问题类型一致时复用，返回 semantic_cache=true/cache_similarity；
- 实测：“1+1 等于几 ?” 命中 “1+1等于几?”（相似度 0.9806）耗时 134.6ms，原约 320s；
- 默认 use_semantic_cache=true，可 API 关闭；精确缓存优先。
## 八、全自动运行链路（最终形态）

- 质量策略：项目题 auto:verified；通用事实题 auto:web-retry；其它通用题 auto:stable；前端无按钮；
- 模式融合：默认 quality 优先选 B；fused_* 参数仅 API opt-in；
- 联网/爬取：事实题自动 web on，首次失败自动补跑一次；
- 思考：B/serial 走 engine thinking=auto；fast 档 thinking=off；由 M4 显式落参，behavior_fusion=off 防覆盖；
- 缓存：精确（54.8ms 命中）→ 语义（相似度 0.9806，134.6ms）→ 运行中同题去重；
- 项目背景：32 条 LRU，同题 POST 276.8ms→69.9ms；
- 运行态：App 2.0.23 / Engine 2.2.2；质量参考跑 answer_ready=true、answer_quality=verified。

## 九、验证与结论

- fast_gate 12/0；V2 39/39（534）；selftest 371/0；pip 两环境 0 broken；verify PASS；loop 6/0；precheck 5/5；
- 已验证缓存/语义缓存/去重均实测；
- 剩余 dual_judge/self_check 细粒度与新并行架构按“低收益/高风险”保留，不进入生产默认。
