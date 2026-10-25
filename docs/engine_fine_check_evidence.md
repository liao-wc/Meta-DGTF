# 引擎机制层离线回放证据（V2.2.3）

> 目的：在**零 API 成本**下回答两个问题——
> ① 确定性自省核（fine_check）单独能不能替代 LLM 自省的各字段？
> ② 若不能，V2.2.3 应当交付哪几档、默认与回退怎么定？
> 所有数字可复现：`python scripts/eval_self_check_replay.py`（177 packs / 577 views，
> 实测约 40s）。本文件同时收录 **Lead 独立复核**的另一套口径数字（见 §3），
> 两个口径的差异在 §4 解释。

---

## 1. 回放设置

| 项 | 值 |
|---|---|
| 数据 | `outputs/*.packed.json` 共 **177** 份（全部有 `views.*.self_check` LLM 标签） |
| 带自省标签 view | **577** 个（4 层合计） |
| 单圈 view（`rounds_run==1`） | **121** 个 —— 只有这里 `candidates` 与末圈标签**索引对齐** |
| 标签来源 | 引擎 V2.2.2 真跑时 `self_check` 的 LLM 输出（不是人评） |
| 确定性核 | `dgtf_engine/dgtf_v2/fine_check.py`，阈值默认（见 registry §1） |
| 脚本 | `scripts/eval_self_check_replay.py`（`--write-prior` 另生成结构先验表） |

**口径说明（必读）**：packed 的 `views.*.candidates` 是**跨圈合并**后的列表，
而 `self_check` 是**末圈一次调用**的标签 ⇒ 索引级 P/R 只在单圈子集（121 views）
严格成立；全量只用「标签级（布尔）/决策触发级」口径。回放态没有逐圈展开
provenance（`expanded_descs` 不在 packed 里），故 `new_candidates` 触发器不可回放，
只能给上下界（§2.4）。

---

## 2. 我方回放结果（确定性核 vs LLM 标签）

### 2.1 索引级（单圈 121 views，`rounds_run==1`）

| 字段 | Precision | Recall | F1 | TP/FP/FN | 判读 |
|---|---|---|---|---|---|
| `suspicious_candidates` | 0.3075 | 0.3569 | 0.3304 | 111 / 250 / 200 | **召回不足**，不接管决策字段 |
| `suspicious_amps` | 0.0000 | 0.0000 | 0.0000 | 0 / 1 / 101 | 词面证据与 LLM「凑数」判断不相关，不接管 |

### 2.2 标签级（全量 577 views）

| 字段 | 指标 | 值 | 判读 |
|---|---|---|---|
| `ing_rephrased` | P / R / F1 | 1.0000 / 0.0345 / 0.0667（TP=1, FN=28） | 字符 n-gram 只能抓逐字复述；语义复述抓不到 ⇒ **不接管**（auto_narr 仍由 LLM 判） |
| `honest_about_empty` | 一致率 | 0.9912（n=569） | 无决策消费者，可本地化 |
| `unsaid_count` | 精确一致 | 0.8284 | 计数本地化可用 |
| `unsaid_count` | ±1 一致 | 0.9185 | 同上 |
| `unsaid_count` | det ≥ LLM | 0.8614 | 偏保守方向（多报） |
| `unsaid_overused` 旗 | 判定相同 | **0.9480** | 双源闸行为基本保持 |
| `unsaid_overused` 旗 | 更保守（多挂旗/留痕） | 0.0000 | — |
| `unsaid_overused` 旗 | **漏挂（LLM 挂而核不挂）** | **0.0520** | 有 5.2% 漏报 ⇒ 旗不交给核，仍由 LLM/双源闸 |

### 2.3 决策触发级（全量 577 views）

| 决策 | P | R | F1 | TP/FP/FN/TN | 方向判读 |
|---|---|---|---|---|---|
| 回填旗（`candidates_backfilled`，对 packed 最终旗） | 0.2598 | 0.6543 | 0.3719 | 53/151/28/345 | 因「空展开⇒全可疑」等保守规则**过度挂旗**（FP 151 > FN 28）——方向保守但等价率低 ⇒ 不接管 |
| carry 种类（candidate/ing/any/dual） | 0.9181 | 0.8567 | 0.8863 | 538/48/90 | 接近可用；**auto 跳过时**才由核给出，auto_narr/local 仍以 LLM 判定为准 |

LLM 标签派生 carry 种类分布：candidate 525、any 72、ing 29、dual 2（views）。

### 2.4 触发器与跳过率

| 口径 | 值 | 说明 |
|---|---|---|
| 触发理由分布（回放态） | structural 133、candidates_suspect 421、amps_suspect 6、silent 4、rephrase 1（views，可多重） | `new_candidates` 不可回放 |
| 回放态静态跳过率（无 provenance） | **0.2374** | 即「仅结构性可疑才值得复核」的圈占比 |
| 模拟运行时最好情况（expanded_descs=全部候选） | **0.2374** | `new_candidates` 只增不减 ⇒ 这是 auto 档跳过率**上界** |
| 模拟运行时最坏情况（全部候选都"新"） | 0.0000 | 全触发 |
| Lead 独立复核（更早版本核） | 581/581 = 100% 触发 | 该版把无 provenance 的 `new_candidates` 也算触发；本版已修：**没有 `expanded_descs` 不按新候选触发** |

**结论**：auto 实验档的跳过率上界 23.7% < Lead 定的 50% 线 ⇒ **auto 不进默认、
标记实验档**；它只在「无可疑/无复述/无静默」的圈跳过 LLM。

### 2.5 auto_narr 的 token 经济（离线静态测量，121 单圈 views）

| 项 | full（llm 档） | narrow（auto_narr） | 变化 |
|---|---|---|---|
| 平均 prompt 字符（system+user） | 5414 | 3794 | **-29.9%** |
| 平均 user 字符 | 4570 | 3404 | -25.5% |
| multi-turn assistant 历史 | 1969 字符/次 | 移除 | 全部省掉 |
| 输出 schema 上限 | 1500 tokens | 600 tokens | -60% |
| 调用次数 | 1 次/圈 | 1 次/圈 | 不变 |
| 估算 prompt tokens（chars/1.7） | ~3185 | ~2232 | 约 -950 tokens/次 |

> 推理 token 是这两个阶段的成本大头（Lead 真跑探针：self_check
> reasoning/completion ≈ 92%），收窄输出 schema 与去掉历史对 reasoning 的影响
> **无法离线量化**，留待 Lead 谷时真跑 A/B（本轮不做真跑）。

### 2.6 运行时调用次数证据（单测，非回放）

`tests_fine_check.py` 用 stub LLM 断言实际调用次数（这是「运行时触发率」的
机器可复现证据）：

- `auto` + 干净圈（候选都有展开出处、无结构旗、无复述、无未生）⇒ **0 次调用**，
  `self_check_calls["skipped"] += 1`，决策字段由确定性核给出；
- `auto_narr` ⇒ **1 次收窄调用**（payload 只含 4 个决策字段），叙述字段本地化；
- `local` 端点不可达 ⇒ **0 次云调用成功路径失败后 1 次收窄 LLM**，
  `local_llm_errors=1` + `view.meta` 留痕；
- 收窄调用再失败 ⇒ 回退原全量自省（1 次 full）。

---

## 3. Lead 独立复核（不同口径，原文收录）

Lead 用独立脚本（未复用本回放器）读 178 packs / 581 views / 577 有标签：

| 指标 | Lead 结果 | 当时的验收线 |
|---|---|---|
| auto 触发 `llm_needed` | 581/581 = 100%（new_candidates 577、candidates_suspect 423、structural 134、amps_suspect 6、silent 4、rephrase 1） | 跳过率 ≥50% |
| backfill 旗 P/R/F1 | 0.257 / 0.654 / 0.369 | 决策等价率 ≥95% |
| unsaid 旗 P/R/F1 | 1.000 / 0.016 / 0.032 | 召回接近 LLM 版 |
| ing_rephrased P/R/F1 | 1.000 / 0.035 / 0.067 | 召回 ≥0.9 或明确不接管 |
| carry 种类 P/R/F1 | 0.925 / 0.854 / 0.888 | 可接受 |
| suspicious 索引 P/R/F1（单圈） | 0.308 / 0.357 / 0.330 | 召回 ≥0.9（若接管） |
| audit 耗时 | 35.3 ms/view | <50ms 可接受 |

**两边一致的结论**：`backfill`（P≈0.26）、`unsaid 旗`（召回≈0~0.02）、
`ing_rephrased`（召回≈0.035）、`suspicious_candidates`（召回≈0.36）都**达不到
接管决策字段的验收线**；`carry 种类`尚可（F1≈0.89）。

**两边数字的差异**来自：
1. **版本时点**：Lead 跑的是「无 provenance 也按 `new_candidates` 触发」的早期核
   （100% 触发）；本报告是修正后版本（无 `expanded_descs` 不触发）⇒ 23.7% 跳过。
2. **标签口径**：Lead 的 unsaid 旗/ backfill 分母构造与本人脚本不同（独立实现），
   P/R 会因「LLM 派生期望」的构造方式（是否含 packed 最终旗、是否含 dual 等）浮动。
3. **分母**：Lead 581 views vs 本脚本 577 views（4 个无标签/形状异常的 view 被本脚本
   过滤）；单圈子集 121 两边一致。

---

## 4. 双判（dual_judge）的离线统计（决定是否值得做缓存/先验）

| 指标 | 值 | 判读 |
|---|---|---|
| 候选总数（577 views） | 17,233 | — |
| 去重后唯一 (entry, 归一化文本) | 17,123（99.36%） | 普通问题几乎无重复 |
| 跨跑重复率 | **0.64%** | 判定缓存对「新问题」近零收益；同题复跑/续跑/修复有效 |
| 重复文本的 position 一致率 | 1.0000（全部一致） | 命中时缓存**零风险** |
| position 分布 | 0：9,878（57.3%）/ 1：6,902（40.0%）/ both：453（2.6%） | 全局多数类基线 57.3% |
| 结构先验分组数 | 92 | (entry,source,kind,attribute) |
| 先验高置信覆盖（n≥20 且占比≥0.75） | **23.03%** | 只够 opt-in |
| 高置信先验准确率 | **86.97%** | 替代 LLM 有 ~13% 风险 ⇒ 默认不用 |

**结论**：`dual_judge_mode` 默认 `llm` 不变；`cache` 当「零风险附加项」，
`auto`（缓存+先验）仅实验 opt-in，硬门控 `min_support=20 / min_confidence=0.75`，
且结构复采样强制走 LLM。先验表写入 `dgtf_engine/dgtf_v2/engine/dual_judge_prior.json`
（由本脚本 `--write-prior` 生成；缺失时 auto 退化为 cache）。

---

## 5. 最终交付判断（据此定档）

| 字段/决策 | 确定性核能否接管 | 交付方式 |
|---|---|---|
| `unsaid_count` / `unsaid_where` | 可（精确 82.8%，±1 91.9%） | auto_narr/local 本地化计数；**旗不接管**（有 5.2% 漏挂） |
| `ing 复述比`（字符 n-gram） | 只能算读数（召回 0.035） | 读数本地化；`ing_rephrased` 布尔仍由 LLM/本地模型判 |
| `suspicious_candidates` / `suspicious_amps` | 否（召回 0.36 / 0） | 仍由 LLM/本地模型判；核只给「线索」提示 |
| `honest_about_empty` / 叙述三字段 / notes | 可（一致率 0.99） | 本地化 |
| 回填旗 | 否（P 0.26） | 仍走引擎原双源闸 + LLM 判定 |
| carry 种类 | 尚可（F1 0.89） | auto 跳过时才由核给 |
| `new_candidates` 触发 | 不可回放（需运行时 provenance） | 运行时用 `view._expanded_descs`；单测证明可跳过 |
| dual_judge cache/auto | 缓存零风险但低收益；先验 23% 覆盖/87% 准确 | `cache` 附加；`auto` 实验 opt-in |

⇒ **上线档位：`llm`（默认，零行为差）+ `auto_narr`（建议）+ `local`（待端点）；
`auto` 实验档不进默认。** 与 Lead 决策一致。

---

## 6. 复现命令

```powershell
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
$env:PYTHONPATH="$PWD;$PWD/dgtf_engine"
python scripts/eval_self_check_replay.py --write-prior   # 本文档全部数字
python dgtf_engine/dgtf_v2/tests_fine_check.py            # 运行时调用次数证据（48 checks）
```

机器可读报告可用 `--out docs/engine_fine_check_replay.json` 落一份；默认不写盘。
