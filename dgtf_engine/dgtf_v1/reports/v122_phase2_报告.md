# v1.22 阶段 2 报告 · 三态多票化 + 冻结 + 人工校准

## 一、目标

| 编号 | 目标 | 量化验收 | 结果 |
|---|---|---|---|
| G2.1 | 三票 prompt | 长度 = 3 且互异 | ✅ 3/3 |
| G2.2 | 多票方法 | 新增 + 旧保留 | ✅ 两个都在 |
| G2.3 | 冻结 | signature 非空 + 篡改抛错 | ✅ 64 位 + 三类篡改全红 |
| G2.4 | coverage 用冻结 | 改判后分母不变 | ✅ 1→1（不冻结 1→0） |
| G2.5 | 头部渲染 | 含「三态多票」+「冻结」 | ✅ |
| G2.6 | 校准脚本 | export / import 都有 | ✅ 端到端跑通 |
| G2.7 | packed | 含 `freeze` + `calibration_queue` | ✅ |
| G2.8 | 一致率 | high+medium ≥ 50% | ✅ 100% / 100% / 80% |

## 二、改前基线（探针 before）

`python _probe_v122_phase2.py _baseline_v12177.py` 实测：

```
A_tri_vote_prompts            : AttributeError: no attribute '_TRI_VOTE_PROMPTS'
A2_tri_vote_prompts_distinct  : AttributeError
B_multi_method                : False
B2_single_method_still_there  : True
C_freeze                      : AttributeError: no attribute 'DecidabilityFreeze'
D_cov_frozen                  : （同上，取不到）
E_calib_roundtrip             : {export_rc: 0, rows: 12, import_rc: 0, verdicts_n: 1}
F_header_src_三态多票          : False
F2_header_src_冻结             : False
G_action_switch               : None
```

★ `E_calib_roundtrip` 在基线上就「能跑」——因为基线的 `bench_calibrate.py`
（我方 harness）本来就认不了新格式的队列，于是回落到 `pools.1` 分支。
这一格在基线上**看起来正常**恰恰说明它没有判别力：它测的是脚本自己的
回落分支。所以验收里把校准改成**端到端**（export → 人工填表 → import →
读回 `verdicts.json` 的条数），而不是只看退出码。

## 三、改了什么（逐条 + 落点）

| # | 改动 | 落点 |
|---|---|---|
| 1 | `_TRI_VOTE_PROMPTS` 三票（严格 / 宽松 / 中立），互不可见、各自独立一次调用 | `_DEC_ANSWERABLE` 附近 |
| 2 | `_adjudicate_sub_tristate_multi`（多数票 → 标签） | `_adjudicate_sub_tristate` 之后 |
| 3 | 单票方法保留，开关打开时**派发**到多票 | `_adjudicate_sub_tristate` 头部 |
| 4 | `DecidabilityFreeze`（冻结 + 签名 + 校验） | `_normalize_decidability` 附近 |
| 5 | 逐条写 `votes` / `agreement` / `stability`（任务书口径键名） | 多票方法内 |
| 6 | `_pack_result` 挂 `freeze` + `calibration_queue` | 主文件 16662 行附近 |
| 7 | 头部「三态多票」+「冻结」两行 | `save_result` |
| 8 | `bench_calibrate.py`（export / import） | `bench/` |

### 两处口径回正（第一轮只拿到残篇，做错过）

- **键名**：我原来写的是私有名 `_tri_votes` / `_tri_level` / `_tri_final`，
  而任务书 Step 2.2 用的是 `votes` / `agreement` / `stability`。
  不改名的话，任务书自带的 `bench_calibrate.py`（读
  `it["votes"][i]["label"]`）会在另一边**静默拿到空表**。现在的做法是
  **加别名不删旧名**：两套键并存，各自有明确读者。
- **头部统计源**：原来按 `tri_consensus` 渲染，任务书 Step 2.5 是按逐条
  `stability` 统计。改成后者（两者数值同源，但口径以后者为准）。

### 冻结签名的口径（本阶段最贵的一课）

签名的第一版记的是 `[id, 当前标签, 由标签现推的可答性]`。
于是「**只把 `_frozen_answerable` 翻过来、标签不动**」改不动签名 ——
被冻结的那个布尔**根本没进签名**，它只是个没人读的副本。
任务书 Step 3.3 的冒烟标的正是这一刀；探针实测返回「未判红（漏洞）」。

现在是五元组：`id / 当前标签 / 当前可答性 / 冻结布尔 / 冻结标签`，
并且 `freeze()` 必须**先写冻结键、再算签名**（顺序反了会「刚冻结就验不过」，
那症状极难往顺序上想）。

## 四、改后对照（探针 after）

```
A_tri_vote_prompts            : 3
A2_tri_vote_prompts_distinct  : 3
B_multi_method                : True
B2_single_method_still_there  : True
C_freeze : {sig_len: 64, has_frozen_keys: true, clean_verify: true,
            tamper: {"decidable→partial":    "RuntimeError",
                     "decidable→undecidable": "RuntimeError",
                     "signature 手改":         "RuntimeError"}}
D_cov_frozen : {frozen_denominator: [1, 1], unfrozen_denominator: [1, 0]}
E_calib_roundtrip : {export_rc: 0, import_rc: 0, verdicts_n: 1}
F_header_src_三态多票 : True      F2_header_src_冻结 : True
G_action_switch : True            G2_pack_keys : ["calibration_queue","freeze"]
```

`D_cov_frozen` 是 G2.4 的核心：**冻结后改判分母不动（1→1）；不冻结时
改判分母会动（1→0）**。第二格是负对照 —— 没有它，「冻住了」这句话
无法与「压根没变」区分。

## 五、冒烟结果

`python smoke_test.py` → **✓ 158 / ✗ 0 / EXIT=0**

`check_v122_phase2` 的负对照共 5 条，全部实测判红：
1. `decidable → partial`（分母没变、判定变了）；
2. `decidable → undecidable`（真翻分母）；
3. 换了池子（条数变了）；
4. **只翻 `_frozen_answerable`**（探针发现、后收进冒烟）；
5. **只改 `_frozen_decidability`**。

另有**反向负对照**：不冻结时改判分母**必须**变（`1 → 0`）——
否则第 1~5 条全都没有判别力。

## 六、真跑样本（一致率核对）

`python _run_v122_evidence.py` → `runs/v122/p2_consistency_{1,2,3}/`
（同题 `订单系统要保证不超卖又要不卡顿。CAP 约束下，下单链路怎么设计？`，
`--route 1 --rounds 1:4`，profile=economy）

| 跑次 | calls | 子问题数 | high | medium | low | 一致率 (high+medium)/n | 冻结签名 |
|---|---|---|---|---|---|---|---|
| 1 | 42 | 6 | 6 | 0 | 0 | **100%** | 64 位 |
| 2 | 41 | 5 | 5 | 0 | 0 | **100%** | 64 位 |
| 3 | 40 | 5 | 3 | 1 | 1 | **80%** | 64 位 |

**G2.8 通过**：三次都 ≥ 50%（100% / 100% / 80%）。

★ 对照历史：**单票**时代同一指标实测落在 17~67%（本项目 §7.13 已定性
那是三态标签本身的可定义性边界，不是工程质量）。本轮多票把它推到
80~100%，方向与预期一致。但**样本只有 3 次**，按本项目测量学纪律，
这只能说明「多票没有把一致率做坏」，不足以宣称「多票把一致率提高了」——
要宣称后者需要同条件重复 ≥3 次以上的对照实验。

### 一个被真跑抓出来的口径问题

三次真跑的 `calibration_queue` 分别是 6 / 5 / 5 条 —— **等于全部子问题数**。
原因：`_pack_result` 当时把 `_tri_multi_items`（每一条都带 level）整批塞进队列，
而队列的语义应该是「**无多数票**的那些条才要人工核」。
后果很具体：产物显示「校准队列 6 条」，读起来像「每条都要人工看」，
人工校准这件事就会被放弃。

已修（阶段 3c）：`calibration_queue` 只收 `level == "low"` 的条目；
`bench_calibrate` 的回落分支同步改成只取 `_tri_level == "low"`
（原来写的是 `or s.get("first_label")`，而 `first_label` 每一条都有 →
「队列为空」时导出表反而是满的，把「没有分歧」读成了「全都要核」）。

**修完之后的真实读数**（F.1 那一批是修后跑的）：`biz_003` 6 个子问题里
`low` 4 条 → `calibration_queue` = **4**（不是 6），`eng_002` 4、`eng_004` 2。
导出的表长这样（`bench/calib/batch1.md`，真数据）：

```
| # | 子问题 | 三票 | 最终 | 人工 verdict | 备注 |
| 1 | 异常编号的生成权若在原供应商…是否具备触发多源化决策的资格？ | undecidable / partial / decidable | partial |  |  |
```

三票互异 → 无多数票 → `partial` + `unstable` + 进队列，正是设计的样子。
回填也跑通了真数据：填第 1 行为 `partial` 后
`bench/calib/verdicts.json` 记下 **1 条**（`illegal: []`）。

## 七、验收判据核对

```
── 阶段 2 ──
  ✅ [2.1] 三票 prompt 长度 3 且互异
  ✅ [2.2] 新旧方法都在
  ✅ [2.3.1] 签名 64 位
  ✅ [2.3.2] 未篡改不判红（负对照）
  ✅ [2.3.3] decidable→partial 判红
  ✅ [2.3.4] decidable→undecidable 判红
  ✅ [2.3.5] 池条数变了判红
  ✅ [2.4] 冻结后分母不变（+ 不冻结时必变，反向负对照）
  ✅ [2.5] 头部含「三态多票」+「冻结」
  ✅ [2.6] bench_calibrate 端到端 export→填表→import（verdicts 1 条）
  ✅ [2.7] packed 含 freeze + calibration_queue 渲染点
  ✅ [2.8] 一致率 100% / 100% / 80%（≥50%）
━━━ PASS 14 / FAIL 0 ━━━
EXIT=0
```

## 八、遗留与下一阶段候选

- **一致率的样本量**：3 次，远不够支撑「多票更好」的结论。下一版应做
  「同题同模型、多票 ON/OFF 各 3 次以上」的对照，并注意本项目已记录的
  塌陷：counts 类判据单次涨落可达 ±10 calls，单跑对照不可信。
- **`low` 条目落 `partial` 的口径**：这是刻意选择（落 `undecidable` 会把
  分母砍一截，正是 v1.21.62 修过的形态）。但 `partial` 会让覆盖率偏高。
  下一版可以考虑给「因分裂而 partial」单独一个标记维度，而不是复用
  `partial` 这个语义。
- `_TRI_VOTE_PROMPTS` 的三套判据目前是「严格/宽松/中立」，实测三次的
  `low` 只出现 1 次 —— 分裂率偏低也可能是三票**相关度过高**（同一个
  模型、同一个 user 段）。要做的是换更正交的判据（比如一票只看
  「有没有 0/1 候选答案」，另一票只看「位置有没有长出来」），
  而不是继续加票数。
