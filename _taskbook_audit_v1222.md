# v1.22.2 任务书核验

> 核验对象：两份共享链接里的 v1.22.2 任务提示词（阶段 0~4）。
> 核验方式：逐条对照 `元DGTF-V1.22.1.py`（21084 行）与 `bench/bench_score.py` 的**实际实现**。
> 结论：**发现 9 处**（≥3，通过），可进入阶段 1；其中 3 处必须改设计，不能照抄。

---

## 一、发现

| # | 类型 | 位置 | 说明（实测依据） | 处置建议 |
|---|---|---|---|---|
| 1 | 前提不成立 | 阶段3 Step 3.3 | 任务书要复用 `self._anchor_answers_warning` 存「N 条 answer 因短于 6 字被丢弃」。实测该属性**已被 v1.22.1 P2b 占用**（`_load_anchors` 17420：全部 N 条锚点未声明 answers 的告警）。直接赋值会**静默摧毁**既有留痕 | **改设计**：新增 `_anchor_answers_filtered`，两告警并存且文案区分 |
| 2 | 前提不成立 | 阶段3 Step 3.1 | 任务书写 `answers_max_n`「已有，明写」。实测 `external_anchor` 配置里**没有这个键**（实测键集：enabled/path/max_items/crosscheck/tier_floor/api_key_env/cache_ttl_hours/per_round/as_evidence/triage/retriever），5 是 `_load_anchors` 17386-17409 里硬编码的 `[:5]` 与 `[:60]` | 照做，但 changelog 要写清是「把硬编码提成配置」，不是「已有」 |
| 3 | 骨架有 bug（判据不可达） | 阶段1 Step 1.2 | 任务书说「位置：`_adjudicate_sub_tristate` 尾部」写 stability。实测该方法有 **5 处早退 `return 0, 0`**（无 subs / LLM 调用失败 / JSON 解析异常 / 返回非对象 / judgments 空）。放尾部 ⇒ **失败路径一条都不写** ⇒ OFF 臂最需要留痕的情形（判决失败）恰好读不到 | **改设计**：stability 必须在**每个出口前**写（抽成私有方法在 5 个 return 前统一调），不能放尾部 |
| 4 | 判据语义错 | 阶段1 Step 1.2 | `s["first_label"] = s.get("first_label") \|\| str(s.get("decidability"))`：未被判到的子问题（`judged` 里没有 → `continue`，16754）first_label 会等于**当前标签** ⇒ `_single_vote_stability` 判 `high` ⇒ 「判决官弃权」被记成「稳定一致」。**两臂都中招**（多票路径 16687 同样 `continue`） | **改设计**：显式三值 `abstained`（未被判到），不参与 high/low 统计，单列计数 |
| 5 | 判据不可达 | 阶段1 Step 1.3 | `_mode = _sqs[0].get("_vote_mode", "?")` 只取第 1 条；若第 1 条恰是弃权/未写键 ⇒ 整份产物标 `?`。且原渲染（19503）无条件按 `stability` 统计，分母含未判条 | **改设计**：`_vote_mode` 按多数条取值；分母只数**有 stability 的条**，弃权单列 |
| 6 | 前提不成立 | 阶段2 Step 2.4 | 任务书给的 `score_decision_rubric(res, gold)` **不存在**。实测：md 正则版 `score_decision_rubric(md: str)`（bench_score.py:71）+ 结构化版 `score_actions(actions, not_do, min_actions=3)`（bench_score.py:169）。且结构化版**已经是** `if nd: s += 1` | **改设计**：rubric 第三项**不用改**；本阶段真正目标是让 `_not_do` 非空。改判据会掩盖真问题 |
| 7 | 静默吞字段（最危险） | 阶段2 Step 2.1 | 任务书只说在 `_he` 的 schema 字符串里加 `not_do`。实测 `dec_norm`（9788-9797）是**显式白名单 dict**：不列 `not_do`，模型产了也会被静默丢掉，`view.decidable_product` 里根本没有这个键 ⇒ `_extract_not_do` 读 schema 恒 None，现象与「模型不产」**一模一样** | **必须同时改** `dec_norm` 白名单。这是本项目已踩过的「dict 白名单无声吞新字段」 |
| 8 | 授权范围不清 | 阶段1 Step 1.4 | 「ON/OFF 各 5 次」= 10 次真跑。本阶段判据是「两臂是否都产出 stability」——这是**结构性**事实，离线 mock 可确定性证明；10 次真跑引入的是采样噪声而非判别力，且与任务书自己写的「不许靠调参凑指标」冲突（会诱导挑好看的那次） | **改设计**：判据主力用离线 mock 两臂对表（确定性）；真跑降到 ON/OFF 各 3 次，只用于看真实分布量级，不下结论时如实写「仍无结论」 |
| 9 | 判据不可达 | 阶段2 验收负对照 | 「空 answer + 空 not_do → rubric = 0/3」不成立。实测 `score_actions` 第 3 项**只看 `not_do`**，与 answer 无关；空 answer 时若 actions ≥3 仍可得 1~2/3 | 负对照改成「actions=[] 且 not_do=[] → 0/3」+「actions 满但 not_do 空 → 2/3」两向 |

---

## 二、未发现问题的部分（这份任务书在哪几段是干净的）

1. **阶段 2 的「`_extract_not_do` 改 schema 优先 + 词法兜底」**——有同款先例可循：`_extract_actions` / `_extract_actions_lexical` / `_source` 标签在 v1.22.1 已落地（changelog 66-68 行）。照此范式做，不是新发明。
2. **阶段 2 Step 2.3 的位置判断正确**——`_finalize_layer_common` 16334 实测就是 `entry == "1" and str(getattr(self,"_orientation","auto")).strip().lower() == "decision"`，与任务书写的一致。
3. **阶段 1 的现象描述正确**——`save_result` 19500-19507 确实无条件按 `stability` 统计，OFF 臂会印「high 0 / medium 0 / low 0 … 一致率 0% ⚠️ unstable」。非读数被当成测量值，确认。
4. **阶段 3 的动机正确**——`_overlap_coef`（5390-5403）分母是 `min(len(ka), len(kb))`，短 answer 的关键词集小，被长 aspect 包住就是 1.000。假命中成立。
5. **阶段 0 / 阶段 4 的方法论本身**——「任务书本身是审计对象」「W 系列只出清单不出代码」这两条是本版最有价值的部分，无异议，照做。

---

## 三、结论

- 发现 **9 处**（≥3）→ **可进入阶段 1**
- 其中 **#1 / #3 / #4 / #5 / #6 / #7 / #8 / #9 需改设计**，不照抄任务书原文
- #2 照做但 changelog 措辞要更正

### 本轮核验自身暴露的一条方法论

核验时发现 #7（白名单吞字段）**不是靠读任务书发现的，是靠读 `dec_norm` 的实现发现的**。
任务书给的 schema 片段本身没有错——错在它只描述了「入口」，没描述「出口」。
凡涉及「给模型加一个新产出字段」，必须同时核：**prompt schema → 归一化白名单 → 抽取函数 → 渲染点**，四处缺一就静默失败。
