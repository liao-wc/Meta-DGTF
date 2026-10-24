# 剩余优化探索评估（2026-10-25）

## 一、dual_judge / self_check 细粒度替换

实测阶段成本（B 真跑）：
- dual_judge：10–12 calls，约 200–227s；
- self_check：10–12 calls，约 126–139s；
- 两者合计约占 B 墙钟的 25–30%，但均非“可无条件跳过”的辅助调用。

证据：
- B + 全局关 self_check（20261024_221714）：quality 0.940、tokens 1,029,966、wall 985.1s；
  相对 B 1.000/1064.3s，只省 79s，质量降 6%，不采纳；
- dual_judge 是核心位置判定，关闭会让候选 position 默认 0，直接破坏 & 生成，不可用；
- 可想到的细粒度规则：只在“本轮新增候选数 ≥ k”或“池状态变化”时跑 self_check；
  预期最多省 40–60% self_check 调用，即 50–80s（约 5–7% 墙钟），
  但 B-no-self 已显示停止判据与质量线索会受损，风险高于收益；
- 结论：暂不在生产默认实现，保留已有的全局开关供调试/成本档使用。

## 二、C/D/E 之外的新并行架构

已测并行模式矩阵：
- A 层并行：quality 0.220，质量门失败；
- C 流水线：0.9464 / 931,439 / 1266.5s；
- D DAG：0.9500 / 1,093,196 / 1402.3s；
- E DAG：0.9220 / 993,472 / 1513.7s；
- B 与 fast 在所有质量/墙钟组合上支配或接近支配这些并行模式。

现有并行能力已经覆盖：
- 阴阳展开 parallel_expand（默认开）；
- 阴阳合并 merge_expand（默认开）；
- 跨层只有 B 的 barrier 保留对齐，C/D/E 的错位都带来质量损失。

结论：
- “C/D/E 之外的新架构并行”若要保留质量，必须继续给 0/1 层加 barrier，本质上退化为 B；
- 若只并行独立工具调用，收益 <5% 墙钟，且需要大量回归验证；
- 预期收益低、风险高，暂不进入生产默认；已写入分析报告“剩余优化空间”。

## 三、App 质量-墙钟取舍（已实施）

| 变体 | wall | tokens | quality | answer_quality |
|---|---|---|---|---|
| 无背景、无联网 | 310.7s | 588,205 | 0.8374 | unverified |
| 无背景、显式联网 | 320.8s / 330.9s | 765,619 / 747,263 | 0.9783 / 0.9263 | verified |
| 无背景、默认联网失败样本 | 280.4s | 731,619 | 0.4900 | needs_evidence（no_official_source） |
| 有项目背景、无联网 | 约1800s 超时 | 1.92M | 0.9598 | verified |

决策（App 2.0.14）：
- 默认保持 web off 稳定档，通用任务约 5.2min、answer_ready=true、answer_quality=unverified；
- 需要 verified 时使用 opt-in：fused_ground_web=true 或显式 web=on；
- 涉及项目的问题继续按相关性注入背景，质量更稳但更慢；
- 轻量回答契约前缀实测 900s 超时，不采纳。

## 四、结论

本轮探索没有发现可安全提升生产默认质量/墙钟的新配置：
- dual_judge/self_check 细粒度替换：理论收益 ≤7% 墙钟，质量风险已由负结果验证；
- 新并行架构：C/D/E 全部质量受损，安全方案退化为 B；
- App 取舍已通过 opt-in 暴露，默认保持稳定档。

建议：保留 B/serial/fast + web 回退、M4 auto-fused 与 App 2.0.14 opt-in；后续若继续，应先做小规模 A/B 试点与质量门对照，再考虑引擎版本迭代。

## 五、质量策略可选项（App 2.0.15）

- stable：不注入项目背景、默认不联网（约 5.2min，可能 unverified）；
- web：通用事实题 web=on（约 5.3min，verified 概率高但有抓取波动）；
- verified：强制项目背景（约 26min 级，质量更稳）；
- auto：默认按问题相关性选择；前端运行栏已提供下拉，接口字段 quality_policy；
- 实测 cmd：stable/web/verified 分别落 --web off / --web on / 项目背景前缀，均 --behavior-fusion off、--parallel B。

## 六、事实题联网自动重试（App 2.0.16）

- 背景：同一 1+1 事实题显式 web 两次成功（0.9783/320.8s、0.9263/330.9s），但一次默认 web 变体 no_official_source（0.49）；说明官方源抓取有波动。
- 机制：quality_policy=web-retry 时，首跑后若 answer_quality 为 unverified/needs_evidence，自动补跑一次同题 web 任务；首个任务记录 retry_task_id/quality_retry。
- 代价：最坏 2 次任务（约 10min）；不改变默认策略；仅在用户显式选择 web-retry 时启用。
- 验证：cmd 已确认 web-retry→--web on/behavior_fusion off/rounds 提示；取消路径 watcher 不误触发。

- 默认全自动：项目相关 -> auto:verified（注入背景）；其它通用题 -> auto:stable（web off）。
- 联网/重试改为 opt-in：API 显式 quality_policy=web/web-retry（或 web=on/fused_ground_web）才启用；前端不再提供选择按钮。
- 验证：auto-fact -> web off/retry false；explicit web-retry -> web on/retry true；auto-project -> 背景注入。

## 七、App 交互收口

- 2.0.17 移除质量策略选择按钮：项目题自动注入背景，通用题默认 stable，联网/重试为 API opt-in；
- 2.0.18 移除模式融合场景按钮：默认自动按 quality 优先选 B，fused_* 参数保留为 API opt-in；
- 前端运行栏只保留提问、思考/搜索胶囊、演练/DSH 等基础控件。

## 八、App 任务启动性能

- 项目背景 RAG 结果加 32 条 LRU 缓存；同一项目问题重复建任务时不再重复扫文档/知识库；
- 实测同题 POST：首次 276.8ms，命中缓存 69.9ms（约 -75%）。
