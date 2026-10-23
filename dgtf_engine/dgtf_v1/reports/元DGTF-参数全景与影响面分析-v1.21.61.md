# 元DGTF · 参数全景 / 影响面 / 优化建议（v1.21.61）

> 扫描对象：`元DGTF-V1.21.61.py`（14572 行）
> 实证锚点：`元DGTF-真跑验证报告.md`（v1.21.56 ~ v1.21.59，13 节）、`元DGTF-停止与收敛条件.md`
> 行号引用形如 `源码:10451` = v1.21.61 的行号

---

## 0. 先给三条结论

1. **`hard_max` 是唯一的成本主旋钮，而且它是"买覆盖"，不是"等停止"。**
   v1.21.58 的实测结论写着：预算给 6/4/7/5+1 时，**四层全部顶到上限**，每圈仍有 2–4 条真新增 `&`，「连续 N 轮无新」这条判据永不触发。**别假设"停止判据会替我决定跑多少圈" —— 在当前版本这个假设是错的。**（张力见 §3.1）
2. **配置 surface 有 93 个显式键，但真正的"隐形伤害"来自 25 个硬编码常量 + 3 个未声明的隐式键**
   —— 尤其是**全部 LLM 调用的 `temperature` / `max_tokens` 写死在调用点**（38 处），这是内容输出质量最直接的两个旋钮，当前**无法通过配置调整**。
3. **`cost_profile` 是个陷阱款总控**：它会在 `__init__` 里就地改写 `memory.shape_chars / shape_items`，**晚于 `__init__` 的任何改法都失效**（源码:8370-8380）。想自定义 shape，**必须绕开档位或改代码**。

---

## 1. 数字总账

| 项 | 数量 | 说明 |
|---|---|---|
| `DEFAULT_CONFIG` 顶层段 | 7 | `cost_profile` / `api` / `output` / `actions` / `probe` / `memory` / `spiral` |
| 显式声明的配置键 | **93** | 顶层 1 + 二级 85 + 三级 7 |
| **实际生效**的配置键 | 93（全生效） | 逐键核对过读取点，无死键 |
| 未进 `DEFAULT_CONFIG` 但真生效的隐式键 | **3** | `max_calls`、`spiral.max_uncovered_pushes`、`config.actions.per_entry`（见 §6） |
| 模块级硬编码常量（不可配） | **25** | 见 §7 |
| LLM 调用点 | **38** | `temperature` / `max_tokens` 全部字面量写死 |
| 并行模式 | 9 | `serial` + A~H，`_MODE_GRAPH` 定义 D~H |
| 层入口 | 4 | `0` 修行 / `1` 研究 / `both` 对撞 / `all` 元 |
| 停止理由种类 | 9 | 见 `元DGTF-停止与收敛条件.md` |
| per-entry 覆盖通道 | `spiral.per_entry.<层>.<键>` | 目前**只有 spiral 段**支持，`memory` / `actions` 段不支持 per-entry |

---

## 2. 参数分层地图：改哪一类要付什么代价

```
               ┌─ 调度层 (Dispatcher)  ── ▶ 决定「跑什么、多久、怎么并」
               │    cost_profile / parallel_mode / round 预算 / max_calls
               │    ✦ 代价：钱、墙钟时间
               │
参数 ──────────┼─ 机制层 (Mechanism)  ── ▶ 决定「池怎么长、何时停」
               │    spiral.* 判据阈值 / actions 开关 / memory.*
               │    ✦ 代价：收敛行为、能不能复现
               │
               └─ 质量层 (Output) ──── ▶ 决定「产物像不像样」
                    dedup_* / qc_* / both_* / alignment_* / unsaid_*
                    ✦ 代价：错杀 vs 灌水
```

**关键不对称**：
- 调度层的改动**立刻可见且可回滚**（换 yaml 重跑即可）。
- 质量层的阈值改动**需要对照实验才能评价** —— 项目里已经踩过一次：ing 复述判定（`_REPHRASE_*`）样本只有 n=1，作者明确写了「调它=过拟合」（`dgtf_config.yaml:28-30`）。**这条纪律要守住。**
- 机制层的 `actions` 开关**没有一个是免费的**：关掉任何一个，都有一批产出路径直接消失（见 §5.1）。

---

## 3. A 类 · 调度与预算（决定成本与墙钟）

### 3.1 预算：`hard_max` / `soft_max` / `all_extra_rounds` / `per_entry`

| 参数 | 默认 | 作用点 | 影响面 | 敏感度 |
|---|---|---|---|---|
| `spiral.hard_max` | 12 | `源码:10454` `_rounds_plan` 兜底 | **全局默认预算上限**。radi === 未显式指定时的每圈数 | ★★★★★ |
| `spiral.per_entry.<层>.hard_max` | — | `源码:9893` | **逐层预算**，覆盖全局 | ★★★★★ |
| `spiral.soft_max` | 3 | `源码:10450` | 「自然安住」判据： >= soft_max 圈且达成才允许停 | ★★☆☆☆ |
| `spiral.all_extra_rounds` | 1 | `源码:10458` | 元层额外多给 1 圈做清算 | ★★★☆☆ |
| `config.max_calls` | 0（不限） | `源码:8388` | 总调用预算，每圈开始前检查，用尽**留痕**不伪装 | ★★★★☆ |

**两处实证互相张力，必须一起读：**

| 来源 | 条件 | 结论 |
|---|---|---|
| `真跑验证报告.md` §12.8（v1.21.58, balanced, serial, 预算 6/4/7/5+1） | 宽预算 | **四层全部顶到上限**，没等来自然停止，拨款即刻用完。代价 CALL 125→220、token +93% |
| `真跑验证报告.md` §13.2（v1.21.59, balanced, hard_max=12） | 更宽预算 | **判据会触发**，3/4 层自然停了 |

**我按证据这样解读，也标注它的不确定：**
> 12.8 与 13.2 的差异**没有岔开版本对照来确认**（§13 用的是 v1.21.59，中间改了可判定性三态互转、评估→拆解不再一次传播、复债三件事），所以**不能断言"预算给够判据就一定触发"**。
> **能确定的是**：`hard_max` 在行为上就是「成本上限」，不能当成"收敛保障"。
> **落地建议**：**永远同时设 `max_calls`**。它比 `hard_max` 诚实 —— 到点会留痕写「预算用尽」，而 `hard_max` 用满时长得和"自然停下"一模一样。

**已知的坑（都是出厂默认路径上的，已修但配置仍可能踩）：**

- **软参 > 预算 ⇒ 判据死掉**。历史遗留：`per_entry.both.soft_max: 5` 而预算 3，`3 < 5` → 「自然安住」永远不可能触发。
  **不变量：`soft_max < hard_max` 必须成立。** 体检脚本会查这条。
- **`min_rounds` 现在是全 0**，等于关闭。文档注释说清楚了想要的话用 `per_entry`，不要在 `min_rounds` 根目录写 —— 因为 `_rounds_plan` 里的语义是**下限不是预算**（`源码:9898-9910`），写错方向会把 "至少跑 2 圈" 变成 "就跑 2 圈"。

### 3.2 成本档：`cost_profile`

`源码:2823` `_profile_plan` —— **五个维度一把抓**：

| 维度 | quality | balanced（默认） | economy |
|---|---|---|---|
| ① 阴阳展开合并成一次 | ✗ | ✗ | ✓ |
| ② 探针回归按角色跳过 | ✗ | ✗ | 仅「收束/复裁」圈 |
| ③ 候选截断条数 | 不截断（0） | **8** | **6** |
| ④ shape 缩放 | 1.0 | **0.72** | **0.55** |
| ⑤ 低频项惰性化（`every_n` +1） | ✗ | ✓ | ✓ |

**实测**：2 圈 ×4 层 → quality 81 次 / balanced 80 次 / economy 69 次调用。`self_check` 降频**刻意不在任何档里** —— 作者的原话是「它是质量的核心来源」。

⚠️ **三条必须知道的副作用：**

1. **档位在 `__init__` 就地改写 `memory.shape_chars / shape_items`**（`源码:8374-8380`）。多处 config 覆盖都会被它覆盖。想自定义 → 只能把 `cost_profile` 设为 `quality` 再自己写 shape，或者改代码。
2. **②③ 会实质改变产出结构**，而且有量化数据：economy 的「按圈号跳探针」版本实测 **探针 −36%、`&` +21%、线头 +29%** —— 资源从「问方向」挪到了「沉淀内容」，答得更落地但**覆盖率下降、此处未生变多**。改版后才变成"只在收束/复裁圈跳"。
3. **`expand_yin` / `expand_yang` 只关一个 = 最亏的组合**（`源码:5342-5353`）：关掉一侧会让 `len(jobs)==1`，于是 economy 的①合并展开**不触发**，省不掉那次调用，只省了单边内容。**要么两侧都开，要么两侧都关。**

### 3.3 并行：`parallel_mode` / `parallel_warmup_rounds` / `pipeline_gate_timeout` / `parallel_expand`

| 参数 | 默认 | 作用点 | 影响面 |
|---|---|---|---|
| `actions.parallel_mode` | `auto` | `源码:14527` | serial / A~H / auto。auto 走 LLM 九选一 |
| `actions.parallel_warmup_rounds` | 1 | `源码:11041` | B/C 模式下 0 层先跑几圈预热。`0`=不预热，`≥0层hard_max`=整层先行 |
| `actions.pipeline_gate_timeout` | 900 | `源码:11443,11641` | C 模式层间放行最长等待（秒），防上游崩掉把下游吊死 |
| `actions.parallel_expand` | true | `源码:5367` | 阴/阳两次展开并行发出。**只压时延，不省调用次数** |

**并行相关的三个不可配常量**（见 §7）：`_PARALLEL_CONF_MIN = 0.5`（低于它一律退回 serial）、`_ENTRY_MIN_UPSTREAM = {"all": 2}`（元层至少要吃完上游几分逐个或多个产物）、`_MODE_GRAPH`（D~H 的依赖拓扑）。

**实测教训（`_auto_plan` 注释，源码:10300-10312）**：
> 调度只给了 修行4/研究4，对撞和元漏了 → 那两层走 `hard_max`(12/13) → 元层跑满 13 圈被截断，整轮 **20.7 min**；而给全四层的 a61F 只要 **9.7 min**。

→ **`_auto_plan` 漏层时不要用 `hard_max` 兜底**,它已经改成"已给合法值的中位数"补齐。**这条对配置的含义：`per_entry` 一定要把四层全写**，漏一层就滑向全局 `hard_max`。

---

## 4. B 类 · 机制与判据（决定停不停、池怎么长）

### 4.1 停止 / 收敛判据

| 参数 | 默认 | 作用点 | 语义 | 敏感度 |
|---|---|---|---|---|
| `spiral.stop_similarity` | 0.8 | `源码:10451` | 本圈产物与上一圈的相似度超过它 → 判「复述」 | ★★★★☆ |
| `spiral.stable_need` | 2 | `源码:10452` | 需要连续几圈满足判据才停 | ★★★★☆ |
| `spiral.idle_limit` | 2 | `源码:10453` | 「无新增 & / 无线头 / 停滞」连续几圈 → 出停止理由 | ★★★★★ |
| `spiral.round_idle_limit` | 2 | `源码:10531` | 层级空闲容忍（对应上下文中 round-level idle） | ★★★☆☆ |
| `spiral.convergence_window` | 2 | `源码:9502` | 双通道 tracker 的收敛窗口 | ★★★☆☆ |
| `spiral.stall_streak_limit` | 2 | `源码:11103` | ChannelTracker：连续几圈无改善算停滞。**只读 `per_entry."1"`** | ★★★★☆ |
| `spiral.min_distance_improvement` | 0.03 | `源码:11104` | distance 至少改善多少才算进展。同上，**只读 per_entry."1"** | ★★★★☆ |
| `spiral.round_window` | 2 | `源码:10536` | 「新增性」比对回看几圈 | ★★★★☆ |
| `spiral.round_stall_limit` | 2 | `源码:10537` | 窗口内停滞几次触发 | ★★★☆☆ |
| `spiral.rehash_similarity` | 0.6 | `源码:3135` | 候选是否是上一圈的改写版本 | ★★★☆☆ |
| `spiral.all_extra_rounds` | 1 | 见 §3.1 | | |

⚠️ **`stall_streak_limit` / `min_distance_improvement` 的读取方式特殊**：构造 `ChannelTracker` 时用 `_spiral_for(self.config, "1")`（`源码:11101-11108`、`11218-11225`），**恒定读研究层的 per_entry**，写全局值只在"没设 per_entry.1"时生效。这是历史设计，改之前知道它。

**knobs 的可用性分布（§12.1，5 份真跑日志）：**

| 计数器 | 观测分布 | 结论 |
|---|---|---|
| `idle_new_amp` | 0×57, 1×7, **2×1** | 阈值可达，但稀有 |
| `idle_new_thread` | 0×43, 1×17, **2×4, 3×1** | 最活跃的一条 |
| `idle_stall` | 0×51, 1×13, **2×1** | 稀有 |

→ **`idle_limit` 调到 3 等于基本关闭这条判据**（没有一篇样本到过 3）。默认值 2 已经是"能触发但要靠运气"，动它之前先确认自己想要什么。

### 4.2 结构：`structure_saturation_*` / `re_eval_*` / `stable_layers`

| 参数 | 默认 | 作用点 | 说明 |
|---|---|---|---|
| `spiral.structure_saturation_enabled` | true | `源码:10794,12237` | 结构饱和度检查开关。判据**只在研究层与元层跑**（入口条件是 `entry in ("1","all")`） |
| `spiral.structure_saturation_every_n` | 3 | `源码:10795,12238` | 检查间隔。**v1.21.60 从过期值 2 对齐到 3**。v1.21.49 的教训：间隔 2 会让研究层 2 圈就停，可判定覆盖率仅 33% |
| `spiral.re_eval_every_n` | 1 | `源码:10713,11842` | 池极性重估间隔。`0` 表示关闭（`_lazy_every_n` 见 n<=0 直接返回） |
| `spiral.re_eval_recent_k` | 10 | `源码:9583` | 重估时回看池里最近几条。Jmeter **构造的是 2k 条 Prompt**，直接线性影响 token |
| `spiral.stable_layers` | 3 | `源码:3193,3226,3916` | 悬置条目转 `stable` 需要连续几圈确认。v1.21.59 从 2 →3，§13.3 实测**本轮无可见影响** |
| `spiral.batch_similarity` | 0.6 | `源码:3194` | 判定「这几圈的悬置批次是同一批」的相似度 |
| `spiral.meta_cover_similarity` | 0.6 | `源码:9709` | 元层清算：未交代的张力与 intersects 的命中阈值 |

**成本档会偷偷改写这两个 every_n**（`_lazy_every_n`，`源码:8583-8593`）：

```python
return n + 1 if _plan["lazy_lowfreq"] else n     # balanced/economy: every_n += 1
```

→ 也就是说 `structure_saturation_every_n: 3` 在 **balanced 下实际是 4**，quality 下才是 3。**这是把 epoch/间隔写进报告时最容易报错数的地方。**
→ 想锁定实际间隔：设 `cost_profile: quality`，或把值减 1 补偿。

### 4.3 记忆：`memory.*`

| 参数 | 默认 | 作用点 | 影响面 |
|---|---|---|---|
| `memory.channels` | `content/context/self` | `源码:4824` | 三通道。删 `self` = 无自我记忆，层间角色趋同 |
| `memory.self_layers` | 4 | `源码:4415,8465` | self_text 保留条数上限。**是永久丢历史**（超出被 `blocks[-cap:]` 丢掉） |
| `memory.self_layers_per_entry` | 2 | `源码:8457` | 每层各保留几条再交错合并（[P0-1] 修「跑最久的 all 层把前几层全挤出」） |
| `memory.carry_feedback` | true | `源码:8726` | self-check 结论回流成下一圈的约束探针。**质量核心，别关** |
| `memory.shape_items` | 6 | `源码:4391,4940,8379` | 池摘要每类喂几条。`_pool_text` / `context_of` 直接乘 token |
| `memory.shape_chars` | 900 | `源码:4392,4414,5224,8377` | 每条摘要截断多少字符 |

**重要**: `self_layers` 与 `shape_*` 的代价性质完全不同 ——
> v1.21.56 修过一个 bug 并记录在 `源码:8363-8372`：原先档位把三个一起缩，`balanced` 下 `self_layers` 从 4 掉到 2 → 四层自我记忆只剩一半。**那是机制层面的损失，不是成本优化。** 现在代码已经只缩 `shape_*`。**但你手写配置时别犯同样的错。**

---

## 5. C 类 · 质量与输出（决定产物像不像样）

### 5.1 `actions` —— 17 个开关，全生效，没有一个免费

| 开关 | 关掉后失去什么 | 读数位置 |
|---|---|---|
| `re_anchor` | 锚点重述。both/all 层会退化成直接用 root_question | `源码:5005` |
| `expand_yin` / `expand_yang` | 单侧视角。见 §3.2 陷阱 3 | `源码:5343` |
| `dual_judge` | 极性裁决 → 候选无极性，`both_quota` / `both_tighten_ratio` 全线失效 | `源码:5045` |
| `ing` | 「摄取」步。丢下游圈的素材整合 | `源码:5060` |
| `he` | 合并步 | `源码:5109` |
| `phase_probe` | 阶段探针。`select_n` / `min_gain` 一并失效 | `源码:5150` |
| `manifest` | 清单步 | `源码:5182` |
| `self_check` | **自省。`carry_feedback` 的空源，质量标记的主要来源** | `源码:5199` |
| `assess_decidability` | 可判定性评估 → 研究层无法分解出 decidable 子问题 | `源码:9354` |
| `decompose_question` | 研究层子问题分解 → 后面十几圈没有子问题可追 | `源码:10468,11901` |
| `parallel_expand` | 只影响时延，不影响内容 | `源码:5367` |
| `input_sanity` | [P1-6] 输入健全性自检（P=PN 这类废题会被拦下） | `源码:12726` |
| `re_evaluate_pool` | 极性重估 → `re_eval_*` 失效 | `源码:10712,11841` |
| `settle_research` | 研究层清账 → 债务留到元层 | `源码:12525` |
| `decidability_source` / `decompose_source` | `pool` / 外部评估。改成非 `pool` 会让"读 0 层产物"这条路径永不生效 | `源码:9355,10471` |

**注意 `output.self_check` 和 `actions.self_check` 是两个不同的键**（`_ACTION_ALIASES` 把它们别名到同一条，`源码:3166-3168`）。写到 `actions` 段优先。

### 5.2 去重 / 改判 —— 改这里就是在「误杀 vs 灌水」上挪游标

| 参数 | 默认 | 作用点 | 方向直觉 |
|---|---|---|---|
| `spiral.dedup_candidate_overlap` | 0.65 | `源码:8568` | ↑ 更容易判重复 → 候选变少但更精 |
| `spiral.dedup_candidate_similarity` | 0.70 | `源码:8569` | 同上（候选更怕误杀，所以阈值比 amp 高） |
| `spiral.dedup_amp_overlap` | 0.60 | `源码:8570` | `&` 与线头 |
| `spiral.dedup_amp_similarity` | 0.62 | `源码:8571` | 线头更容易近义改写，所以比候选松 |
| `spiral.both_tighten_ratio` | 0.3 | `源码:6024` | **改判**：both 占比超它就改回 0/1 |
| `spiral.both_quota.max_ratio` | 0.7 | `源码:7833` | **追问**：both 占比超它就追问「缺什么」（前提 min_items 条以上） |
| `spiral.both_quota.min_items` | 2 | `源码:7834` | 兜底：少于这么多条不问 both 占比的问题 |
| `spiral.alignment_similarity` | 0.7 | `源码:3801` | 四象限对齐：关键词相似度（分母取两侧最大值） |
| `spiral.alignment_containment` | 0.6 | `源码:3802` | 四象限对齐：短侧关键词落在长侧的比例。**只有这条能配上**「修行 target 短 vs 研究 sub_question 长」 |

⚠️ **`both_quota.max_ratio` 与 `both_tighten_ratio` 不是一回事**（`dgtf_config.yaml:7-12` 显式警告过）：
- `both_quota.max_ratio` (0.7) → 触发**追问**
- `both_tighten_ratio` (0.3) → 触发**改判极性**

两者差着顺序与性质：**先改判后追问**，阈值却是改判更严（0.3 < 0.7）。所以在 steady state 下 **`both_quota` 几乎不可能触发** —— 因为 both 占比在到 0.7 之前早已被 0.3 的改判压下去。可以回看 v1.21.59 的日志验证：**如果两者都要生效，`both_tighten_ratio` 必须 > `both_quota.max_ratio`**（比如 0.75）。这是一个**结构性的未验证点**，我没有真跑数据，标「待验证」。

### 5.3 质量线索阈值

| 参数 | 默认 | 作用点 | 说明 |
|---|---|---|---|
| `spiral.qc_rephrase_ratio` | 0.5 | `源码:7596`（`_spiral_num`） | ing 复述率超过它 → `ing_rephrased_direct` |
| `spiral.qc_both_ratio` | 0.6 | `源码:7632` | 候选极性 both 占比超过它 → `judge_mostly_both` |
| `spiral.all_drift_threshold` | 0.5 | `源码:8545,8819` | 元层候选漂移触发线。**只加标记不改产物** |
| `spiral.all_selfref_threshold` | 0.4 | `源码:8546,8821` | 元层候选自指标记触发线。同上 |
| `spiral.unsaid_escape_limit` | 3 | `源码:7872,8848` | 一圈里「此处未生」超过几处算逃避。**唯一支持 per_entry 覆盖的质量参数** |

**质量线索是给自己看的，不是给模型判的**（§12.3 血的教训）：
> 同一个orean方法 distinction：代码实算的「质量线索」条数随预算**减半**（1.20 vs 2.10 / 0.83 vs 1.83 两天独立复现），但**模型自报**的「综合距离」方向是**反的**（大预算 0.62 vs 小预算 0.51）。
> → **跨运行排序、打分、验收，一律用代码实算指标；自报指标只能作为辅助。**

### 5.4 探针

| 参数 | 默认 | 作用点 | 说明 |
|---|---|---|---|
| `probe.min_gain` | 0.3 | `源码:6773,7032,7178,7320` | 预期收益低于它不选为探针（`expected_gain` 是模型自报） |
| `probe.select_n` | 3 | `源码:4429` | 每圈选几条探针焦点 |

`probe.*` 与 `phase_probe` 联动；economy 下另会按角色跳过（§3.2 ②）。

### 5.5 `output.*` —— 只影响看得到的东西，不影响逻辑

`save_dir` / `verbose` / `show_dual_judge` / `show_ing` / `show_manifest` / `self_check` / `show_probe_diag`。
唯一提醒：`output.verbose` 在并行模式下**会让四层日志交错**，看不出谁是谁。调试时用 `show_probe_diag` 比用 verbose 更聚焦。

---

## 6. 隐式旋钮（不在 `DEFAULT_CONFIG`，但真生效）

| 键 | 读取点 | 默认值 | 影响面 | 建议 |
|---|---|---|---|---|
| `config.max_calls` | `源码:8388` | `0` | 总调用预算。**唯一会诚实留痕的"提前停"** | **建议每个 always-on 方案都设** |
| `spiral.max_uncovered_pushes` | `源码:10096` | `1` | fix-88b：有未深入方向时允许推迟停止几次。`0`=一次都不推迟 | §11 的 A/B 实测：**1 vs 0 两臂结构完全相同，这个旋钮没机会起作用**。补进配置无害，但别指望它改变什么 |
| `spiral.per_entry.<层>.<键>` | `源码:3186` (`_spiral_for`) | — | 逐层覆盖。**这是整套配置里唯一的 per-entry 通道**，且只对 `spiral` 段有效 —— `memory` / `actions` / `probe` 段都不支持。层取值 `0` / `1` / `both` / `all` | **四层全写**，漏一层就滑向全局 `hard_max`（§3.3） |

★ **注意 `per_entry` 只对「走 `_spiral_for` 的键」生效**，而且有两个键是例外，它们**恒定读 `per_entry."1"`**（`源码:11101-11108`、`11218-11225`）：

| 键 | 实际读哪一层 | 后果 |
|---|---|---|
| `spiral.stall_streak_limit` | `per_entry."1"` | 写全局值只在未设 `per_entry."1"` 时生效 |
| `spiral.min_distance_improvement` | `per_entry."1"` | 同上 |

**为什么这三个应该写进 `DEFAULT_CONFIG`：**
> 现在它们只能靠"有人在 yaml 里手打一个不存在的键"来生效 —— `_deep_merge` 会默默接受任何键，**拼错了不会报错**。这是最容易积灰的一类：写了以为生效，实际是 `sp.get(key, default)` 拿默认值。体检脚本 §10 会做未知键检查。

**建议一起纳入的另外三项（当前硬编码）：**

```yaml
# 以下三项当前不可配（硬编码），但它们是质量的主力旋钮
llm_temperature_map:    # 见 §7.1
llm_max_tokens_map:     # 见 §7.1
max_cont_rounds: 2      # 源码:4967 _call_long 长输出续跑次数
```

---

## 7. 硬编码常量 —— 不能配，但影响最大

### 7.1 ★ 全部 LLM 调用的 temperature / max_tokens 写死在调用点（38 处）

这是**本次扫描最大的发现**。所有 38 个 LLM 调用点的两个参数都是字面量：

| 用途 | 温度 | max_tokens | 行号 |
|---|---|---|---|
| 自动调度 `_auto_plan` | 0.2 | 500 | `源码:10294` |
| 并行模式决策 | 0.2 | 400 | `源码:10210` |
| 外部 `auto_plan` | 0.2 | 600 | `源码:13234` |
| **阴阳展开** | **0.9** | 1500 | `源码:5383,5464` |
| 展开合并（economy） | 0.9 | 2600 | `源码:5441` |
| 锚点重述 | 0.3 | 400 | `源码:5253` |
| 极性裁决 both | — | — | `源码:7804` |
| self_check / 自省 | 0.3 | 1500 | `源码:7964` |
|ING 摄取 | 0.3 | — | |
| 问题分解 | 0.3 | 3000 | `源码:5914,5932,5949` |
| 外部评估 | 0.3 | 2500 | `源码:6291` |
| 圆形/归纳 multiple | 0.3 | 1300 | `源码:6443,6463` |
| 探针相关 ×4 | 0.5 | 1900 | `源码:6866,7070,7214,7380` |
| 处/结构 | 0.3 | 1200 | `源码:9132` |
| all 层候选生成 | 0.2 | 500 | `源码:9479` |
| 极性重估 | 0.3 | 900 | `源码:9608` |
| reasoner 强推理 ×2 | **0.7** | 4000 / 2500 | `源码:6125,8165` |
| `LLM.call` 方法签名兜底 | 0.6 | 3000 | `源码:4721` |

**这为什么是问题：**

- 内容输出质量的直接旋钮 = **多样性（temperature）× 容量（max_tokens）**。当前**没有任何合法途径从外部调整** —— 要么改代码，要么接受。
- 阴阳展开用 **0.9（最高）**，:'-  Konsum jitter 最高的地方也是 `&`（相差临床最实在的贡献）。这也解释了为什么容易灌水、要写 `NO_FILL_RULE`。
- reasoner 模型用 **0.7 并且 max_tokens 强制 ≥32000**（`源码:4747`）—— 这是成本炸弹：**任何走 reasoner 的调用，成本是普通调用的 1~2 个数量级**。当前只有 2 个调用点走 reasoner（`源码:6125` 结构化解决、`源码:8165` 元层），但**这两个在每个 ikwembu lemini 都会被调到吗** —— 取决于 Tier circuit。这是最值得先量化的成本点。

**优化建议（按性价比排序）：**

1. **把 38 处收拢成一张 `llm_profile` 表**（一级往事，新增 `config.llm.temperature/<max_tokens>` 按"用途"分组：`expand / judge / probe / synthesize / meta / plan`）。改完立即获得：美菩调优 directive + 分 *-profile 隔离。
2. **先把 economy 落在 temperature/max_tokens 上而不是档位上** —— 现在的 balanced/economy 减的是内容（shape 0.72/0.55、候选截断 8/6），本质是"少喂信息"，而鮑 llm token profile 属于"少生成"，两者并不是同一回事。
3. **给 reasoner 加开关**（`actions.use_reasoner`）与预算上限。所有 query-level 的成本股虺都在那两个调用点上。

### 7.2 其余 24 个不可配常量（`源码:2748-2789`、`源码:2984`）

| 常量 | 值 | 管哪条线 | 备注 |
|---|---|---|---|
| `_DUP_SIM` | 0.85 | 去重通用「同一件事」 | 使用最频繁（>8 处） |
| `_REPHRASE_SIM` / `_REPHRASE_OVERLAP` | 0.75 / 0.62 | ing 复述判定 | **作者刻意不做配置项：样本 n=1，调它=过拟合** |
| `_BAN_SIM` / `_BAN_OVERLAP` | 0.85 / 0.70 | 禁用词/被封意图命中 | |
| `_CARRY_REPEAT_SIM` / `_CARRY_REPEAT_OVERLAP` | 0.70 / 0.50 | 自省 carry 是否重复点名 | |
| `_KW_TOP_N` | 8 | 关键词提取条数 → 所有相似度计算的分母 | 影响面极广 |
| `_QC_BACKFILL_RATIO` | 0.5 | 可疑候选占比 → `candidates_backfilled` | |
| `_QC_DIVERSITY_RATIO` | 0.4 | 结构多样性 → `*_all_same_structural` | |
| `_QC_OVERLAP_POOL_RATIO` | 0.7 | 候选与池重合 → `candidates_overlap_pool` | |
| `_TRACKER_COVERAGE` / `_TRACKER_CLARITY` | 0.7 / 0.6 | ChannelTracker 的收敛门 | |
| `_ALIGN_MATCH_LO` / `_ALIGN_MATCH_OK` | 0.1 / 0.3 | 四象限对齐的分档 | |
| `_PARALLEL_CONF_MIN` | 0.5 | **低于它一律退回 serial** | 调度合法性收据 |
| `_SUSP_SAME_SIM` | 0.8 | 悬置更新「同一件事」 | |
| `_TAKE_SIM` | 0.75 | 探针取件 | |
| `_QC_POOL_SIM` / `_QC_DUP_SIM` | 0.60 / 0.70 | 质量检查 | |
| `_MERGE_SIM` | 0.70 | 合并可判定性通道去重 | |
| `UNSAID_ESCAPE_LIMIT` | 3 | 「此处未生」逃避上限（兜底，配置优先） | |
| `_ENTRY_MIN_UPSTREAM` | `{"all": 2}` | 元层要吃完上游几分 | 并行正确性 |
| `_call_long(max_cont)` | 2 | 长输出被掐断后续跑几次 | 时延 vs 完整性的直接旋钮 |
| reasoner `max_tokens` floor | 32000 | 见 §7.1 | 成本炸弹 |

---

## 8. 陷阱组合清单（配置互斥 / 会静默失效的搭配）

| # | 组合 | 后果 | 检查 |
|---|---|---|---|
| 1 | `per_entry.both.soft_max >= hard_max` | 「自然安住」判据**永远不可能触发**（历史踩过：soft 5 vs 预算 3） | `soft_max < hard_max` |
| 2 | 手写 `memory.shape_chars` + `cost_profile != quality` | **写了白写**，被 `__init__` 的档位缩放覆盖 | shape_* 只在 quality 下可信 |
| 3 | `expand_yin` / `expand_yang` 只关一个 | economy 的合并展开不触发；只省内容不省调用 | 要么都开要么都关 |
| 4 | `cost_profile != quality` 且写了 `structure_saturation_every_n: 3` | 实际是 **4**（`_lazy_every_n` +1） | 要锁定就设 quality 或减 1 |
| 5 | `parallel_mode: auto` 且模型置信低 | 静默退回 serial（`_PARALLEL_CONF_MIN=0.5`），日志里有说明但容易忽略 | 看「调度」那一行的 confidence |
| 6 | `per_entry` 只写了部分层 | 未写的层落到全局 `hard_max`，cost 失控（实测 20.7 min vs 9.7 min） | 四层全写 |
| 7 | `min_rounds` 写值当预算用 | 语义是**下限不是预算**；写成 2 ≠ "就跑 2 圈" | 现在全 0，别动 |
| 8 | `actions.decidability_source` / `decompose_source` 设为非 `pool` | "读 0 层产物"这条路**永不生效**（v1.21.60⑩ 修的那批 bug 就在这条路上） | 保持 `pool` |
| 9 | 用模型自报指标（coverage 自评 / distance）跨运行比大小 | §12.3 实证：**方向与代码实算相反** | 只用代码实算排序 |
| 10 | 关掉 `self_check` 还想靠 `carry_feedback` 提质量 | carry 的**源头**就是 self_check | 同开关绑 |
| 11 | yaml 里写了不存在的键（如 `max_uncovered_pushes` 拼错） | `_deep_merge` 默默接受，**不报错** | 体检脚本会报未知键 |
| 12 | `both_tighten_ratio` < `both_quota.max_ratio`（默认即如此：0.3 < 0.7） | both 占比在到 0.7 前已被 0.3 改判压下去 → `both_quota` 几乎不可能触发 | 待验证（见 §5.2） |

---

## 9. 优化建议清单

### P0 · 能省大钱 / 堵大洞

| # | 建议 | 类型 | 依据 |
|---|---|---|---|
| 1 | **每个方案都设 `max_calls`** | 只改配置 | 它是唯一会诚实留痕的提前停止（`源码:10431-10436`）；`hard_max` 用满时和自然停止长得一样 |
| 2 | **`per_entry` 四层全写，别漏** | 只改配置 | §3.3 实测 20.7 min vs 9.7 min |
| 3 | **给 reasoner 调用加开关 +预算上限** | 需改代码 | 2 个调用点，`max_tokens` 强制 ≥32000，是单点最大成本风险 |
| 4 | **`temperature` / `max_tokens` 收敛成 `llm.<用途>` 表** | 需改代码 | 38 处写死，质量主旋钮不可配 |

### P1 · 提升可 Auditable（分辨得出"配了没配"）

| # | 建议 | 类型 |
|---|---|---|
| 5 | 把 `max_calls` / `max_uncovered_pushes` / `per_entry` 写进 `DEFAULT_CONFIG`（空值占位即可） | 改代码 5 行 |
| 6 | `load_config` 增加**未知键告警**（现在是默默接受） | 改代码 ~8 行 |
| 7 | 运行头部打印**一次"实际生效摘要"**：档位 + 每层预算 + 实际 every_n（含 `+1` 惰性化后的值）+ max_calls | 改代码 ~20 行 |
| 8 | `_call_long` 的 `max_cont` 配置化，或按 `max_tokens` 自适应 | 改代码 ~6 行 |

### P2 · 值得做，但先't 单 entry，要对照实验

| # | 建议 | 备注 |
|---|---|---|
| 9 | 验证 `both_tighten_ratio` > `both_quota.max_ratio` 时能否真的检出 both 占比失衡（§5.2 待验证点） | 需要两臂 A/B 对照 |
| 10 | `re_eval_recent_k` 从 10 试 6 / 14 看成本收益曲线 | 它是直接乘 token 的系数（`源码:9583`，一次喂 2k 条） |
| 11 | `_REPHRASE_*` **别动** | 作者已写「样本 n=1，调它=过拟合」。这条纪律要守住 |

---

## 10. 五套配置方案

配套文件在 `configs/` 下。预计成本的估算模型（**估算，不是实测**，锚点见下）：

```
预计调用数 ≈ Σ(各层 hard_max [+ all_extra_rounds]) × 9.6 × η(档)
    η: quality 1.0 / balanced 1.0 / economy 0.86
预计 token ≈ 调用数 × 4800
预计墙钟 ≈ 调用数 × 8.7 s（serial 实测锚点）
```
> 锚点：balanced 13 圈 → 125 次调用 / 548 108 token / 1069 s（§12.8 省档）
> balanced 23 圈 → 220 次调用 / 1 058 585 token / 1924 s（§12.8 宽档）
> 两条算出来都是 ≈9.6 次调用/层圈、≈4812 token/调用、≈8.7 s/调用。
> 并行模式 **省墙钟不省调用数**。

**这个模型受过一次独立验证：**
> 用它算「方案 C 深覆盖」（6/4/7/5+1 = 23 圈，balanced）→ **221 次调用 / 1.06 M token**
> §12.8 真跑实测的宽档，同样配置 → **220 次调用 / 1 058 585 token**
> 误差 < 1%。
> → 结论：**在 23 圈以内**这个线性模型可信；超过它仍然只有两个测点，别当预算承诺。

**先体检再跑**（下表的数字都是 `_config_lint.py` 实算出来的）：

| 方案 | 预算（0/1/both/all） | 总圈数 | 预计调用 | 预计 token | 预计墙钟 | 定位 |
|---|---|---|---|---|---|---|
| **A 省快** | 3/3/3/3+1 | 13 | ~107 | ~0.52 M | ~16 min | 探索性、可重跑、要快速筛选 |
| **B 标准** | 4/4/6/4+1 | 19 | ~182 | ~0.88 M | ~26 min | **默认推荐**，产量/成本平衡点 |
| **C 深覆盖** | 6/4/7/5+1 | 23 | ~221 | ~1.06 M | ~32 min | 要最大覆盖面。**这组预算有真跑实测背书**（§12.8） |
| **D 高质量** | 5/4/6/4+1 | 20 | ~192 | ~0.92 M | ~28 min | 不改预算，改"喂得更足 + 去重更松" |
| **E 压时延** | 4/4/6/4+1 | 19 | ~182 | ~0.88 M | ~13-16 min（F 模式） | 成本同 B，靠并行压墙钟 |

### 方案选择决策树

```
要不要尽快要结果？
├─ 是 → A（省快），并且 per_entry 全写死
└─ 否 ↓
这是探索还是交付？
├─ 探索 / 可重跑 → A 或 B
└─ 交付 ↓
瓶颈是覆盖还是精度？
├─ 覆盖面不够（这里没答到）→ C（深覆盖）
├─ 精度/自洽不够（答得浅、自相矛盾）→ D（高质量）
└─ 墙钟不够 → E（压时延）
```

**两条跨方案的硬纪律：**
1. 无论哪套，`max_calls` 都设上（P0-1）。它同时是**安全绳**和**诚实性保障**。
2. 跨方案比质量，**一律用代码实算指标**（§5.3）。自报的 distance/coverage 会给出反方向结论 —— 这件事实测发生过一次。

**跑之前先体检：**

```bash
python _config_lint.py configs/方案B-标准.yaml     # 或 configs/*.yaml
```

它会查出 12 条已知陷阱、拼错的键（现在是静默忽略的），并打印**实际生效值**
（被 `cost_profile` 缩放后的 shape、被 `+1` 后的 every_n）—— 这两个数最容易报错。

---

## 11. 关于 `max_uncovered_pushes` 的既有结论（免得重复做实验）

§11 的 A/B 实测（v1.21.58）：**1 vs 0 两臂结构完全相同**。
原因：`uncovered_streak` 要在「有未深入方向 + 非最后一圈 + 方向数在减少」三个条件同时成立时才推迟停止，而预算给 3 时，**推迟永远落在最后一圈**（被 `is_last_round` 判掉）。

→ 所以：**别花力气调这个旋钮，除非先把预算拉长到「推迟」有机会落在非末圈。**
这条值得单独记住 —— 它是一条可复用的排查经验：**很多旋钮调不动，是因为另一个旋钮把它锁死了。**

---

*生成：2026-10-01 · 扫描 `元DGTF-V1.21.61.py` · 实证引自 `元DGTF-真跑验证报告.md`*
