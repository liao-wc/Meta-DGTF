# v1.22 阶段 3 报告 · decision 模式强制行动闭环

## 一、目标

| 编号 | 目标 | 量化验收 | 结果 |
|---|---|---|---|
| G3.1 | 开关 | `landing_decision` 存在 | ✅ |
| G3.2 | 分流 | 两个 render 函数都在 | ✅ 三分支实测 |
| G3.3 | 抽取 | ≥ 1 条 action | ✅ 1 条（构造样本） |
| G3.4 | 六字段 | 每条都有 | ✅ |
| G3.5 | 硬约束 | `action_incomplete` + `not_do_missing` | ✅ 真跑里都触发过 |
| G3.6 | rubric | 存在 | ✅ `score_actions` / `score_decision_rubric` |
| G3.7 | decision 题 | **100% ≥ 3 action** | ❌ **未达成**（实测 0/2/0/2 条） |
| G3.8 | rubric | 平均 ≥ 2/3 | ❌ **未达成**（见第六节） |

★ G3.7 / G3.8 未达成，**不是「大致完成」，是没做到**。第六节给数字、
第七节给根因与下一版怎么改。机制本身（分流 / 抽取 / 硬约束 / rubric）
全部落地并被真跑触发过。

## 二、改前基线（探针 before）

`python _probe_v122_phase3.py _baseline_v12177.py`：

```
A_switch                   : AttributeError（DEFAULT_CONFIG.actions 无 landing_decision）
B_render_boundary_exists   : False
B2_render_decision_exists  : False
C_extract                  : AttributeError: no attribute '_extract_actions'
C2_extract_empty           : AttributeError
D_not_do                   : AttributeError
E_dispatch.boundary        : {decision_template: false, has_action_section: false, len: 500}
E_dispatch.decision        : 同上（基线里根本没有 decision 模板）
F_src_action_incomplete    : False
F2_src_not_do_missing      : False
F3_src_orientation_field   : False
H_boundary_template_unchanged : False
```

## 三、改了什么（逐条 + 落点）

| # | 改动 | 落点 |
|---|---|---|
| 1 | `DEFAULT_CONFIG["actions"]["landing_decision"] = True` | 主文件 19329 行附近 |
| 2 | `run()` 记 `self._orientation`（给收尾环节用） | `run()` 内 |
| 3 | `_render_landing_boundary`（原 `render_landing` 整体改名，一行没删） | 主文件 17655 行 |
| 4 | `render_landing` 退成分流壳（3 行判断，无渲染逻辑） | 同上 |
| 5 | `_render_landing_decision`（六段模板） | 同上 |
| 6 | `_extract_actions` + `_guess_{role,deadline,acceptance,fallback}` + `_extract_not_do` + `_act_text` / `_und_text` | `_classify_unsaid` 之前 |
| 7 | 硬约束 `action_incomplete` / `not_do_missing` | `_finalize_layer_common` |
| 8 | `_pack_result` 挂 `orientation` / `_config` / `views.1._actions` / `views.1._not_do` | 主文件 16690 行附近 |
| 9 | `bench_score.score_actions`（结构化 rubric） | `bench/` |

## 四、改后对照（探针 after）

```
A_switch : True          B/B2 : True / True
C_extract : {n: 3, ids: [A1,A2,A3], verbs: [指派,申请,清淤],
             fields_complete: true, roles: [排水公司,信息科,项目组],
             deadlines: [汛期前,本月内,本季度]}
C2_extract_empty : 0                 ← 负对照：空结论 0 条
C3_extract_cached: [{id: A1}]        ← 已抽过的不再抽一遍
D_not_do : ["不要整体翻新"]           D2_not_do_none : []
E_dispatch.boundary      : {decision_template: false, len: 500}   ← 老五块模板
E_dispatch.decision      : {decision_template: true,  has_action_section: true,
                            has_not_do_section: true, len: 708}
E_dispatch.decision_off  : {decision_template: false, len: 500}   ← 关开关回老模板
E_dispatch.auto          : {decision_template: true, len: 708}    ← auto 按 decision
F/F2/F3 : True / True / True
```

★ `verbs: [指派,申请,清淤]` 里第 3 条落在「清淤」而不是「委托」——
`next(v for v in WHITELIST if v in s)` 按白名单顺序取第一个命中的词，
同一句里有两个动词时会取靠前的那个。字段齐备性不受影响，
但**动词归属可能与人的直觉不同**。这是白名单式抽取的固有粗糙处，
已列入下一版候选（第七节）。

## 五、真跑里被触发过的机制（含一个真 bug）

### 5.1 硬约束真的会响

`runs/v122/p2_consistency_1/packed.json` 实测：

```
views.1.errors        = ['decision 模式行动清单不足（0 < 3），需补 A1~A3',
                         'decision 模式未交代「不做什么」，需补该清单']
views.1.quality_flags = []      ← ★ 空的！
```

### 5.2 真 bug：硬约束 flag 被 `quality_flags` 重算冲掉

`errors` 留下了、`quality_flags` 空了 —— 说明 flag 被**后写覆盖**。

根因：`_finalize_layer_common` 里我的硬约束块在 16012~16026 行写完 flag，
**19 行之后**（16072）有：

```python
view.quality_flags = _keep_selfcheck_flags(
    view, _dg._quality_check(view, self.pools[entry], r_actual, ...))
```

`_quality_check` 是**整体重算**，而 `_keep_selfcheck_flags` 只保住自省派生的
两个线索。本项目在 P2-8 就记录过同类事故（「合并后重算 quality_flags 时
必须保住」），这次是第三个家族：**硬约束 flag**。

修法（加性）：新增 `_V122_HARD_FLAGS = ("action_incomplete", "not_do_missing")`
并合成 `_PRESERVED_FLAGS = _SELFCHECK_FLAGS + _V122_HARD_FLAGS`，
`_keep_selfcheck_flags` 按它保留。冒烟里加了**两向**判据：
硬约束 flag 必须存活（正），不在保留集合里的线索必须被丢掉（负对照，
否则等于「全都保留」）。

★ 这条**是读真跑的 packed 才发现的**，不是读代码发现的 ——
单看源代码，19 行的距离不会引起注意；只有「errors 有、flags 没有」
这种**同一次运行内的不一致**才能把它逼出来。

### 5.3 另一处口径修正：校准队列

见阶段 2 报告第六节（`calibration_queue` 原来把全部条目都塞进去）。

## 六、真跑样本与 G3.7 / G3.8 的实测

用的是**已有的 decision 取向真跑产物**（不是另起一轮）：

| 产物 | 来源 | 取向 | 层 | 行动清单段 | A 条目 | 不做什么条目 |
|---|---|---|---|---|---|---|
| `_v122_phase6_before.md` | rc1 · route 0,1 · 3:3 圈 | decision | 0,1 | ✅ | **0** | 0 |
| `_v122_phase6_after.md` | 定稿 · 同上 | decision | 0,1 | ✅ | **2** | 1 |
| `_v122_ctrl1.md` | 定稿 · 同上（负对照 1） | decision | 0,1 | ✅ | **0** | 0 |
| `_v122_ctrl2.md` | 定稿 · 同上（负对照 2） | decision | 0,1 | ✅ | **2** | 1 |
| `bench/runs/p1v2/eng_001` 等 3 份 | rc1 · 四层 · 5~6 圈 | decision | 0,1,both,all | ❌ 无 | — | — |

- 四份有行动段里，`A 条目` = **0 / 2 / 0 / 2** → **没有一份达到 3 条**。
  所以 **G3.7「decision 题 100% ≥ 3 action」未达成**。
- G3.8 的 rubric（三项各 1 分：①≥3 条 ②每条带回退 ③有「不做什么」）：
  四份的得分逐个算出来是 **0 / 2 / 0 / 2**（0 条那两份三项全不满足 → 0 分；
  2 条那两份满足②③、不满足① → 2 分）。**平均 1.0/3 ≈ 0.33 < 2/3**
  → **G3.8 未达成**。
- ★ `p1v2` 那三份没有行动段 —— 因为它们**在阶段 3 落地之前就启动了**
  （bench_run 启动时把模块读进内存，之后再改磁盘上的文件不影响它）。
  这也是「产物记得标注它由哪一版生成」的原因；本条如实写出来，
  免得被误读成「四层模式下行动段会消失」。

## 七、根因与下一版怎么做

**根因不是抽取器的 bug，是输出形态不匹配。**

引擎的研究层产出的是**结论段落**，例如（实测原文，CAP 那题）：

> 在CAP中，网络分区时订单系统通常选择CP（强一致+分区容忍），牺牲可用性，
> 因为超卖不可逆。不超卖方案：数据库唯一约束+条件插入（键含幂等键）、
> Redis原子操作（Lua脚本）、分布式锁（Redlock）、乐观锁（版本号）。
> 降卡顿：缓存、异步、限流、分片、队列削峰。…

这段话里有**方案名**，但没有「谁、在什么时候、做到什么算完成、不成立时怎么退」。
而 `_extract_actions` 是「按 `。；` 切句 + 动词白名单命中」的**词法**抽取，
它拿到的句子天然缺 `owner_role` / `deadline_hint` / `acceptance` /
`fallback` 四格 —— 只能靠 `_guess_*` 猜，猜不到就填「（未指定）」。
于是「≥3 条且六字段齐备」这个目标**在数据上不可达**。

**没有采用的两种「把指标做绿」的办法，及理由**：

1. **扩充动词白名单**（把 选择/采用/降级/缓存/限流… 加进去）。
   这会让条目数好看，但四格仍然是「（未指定）」—— 指标绿了、能力没变，
   属于把判据拟合到数据上。**不做**。
2. **放宽 `min_actions`**。那是改判据阈值，且任务书明令「不改阈值」。**不做**。

**下一版该做的**（真修）：

- 让**研究层直接产出结构化行动清单**（在拆解/收束的 schema 里加一个
  `actions: [{verb, object, owner_role, deadline_hint, acceptance, fallback}]`
  段），而不是从结论文本里事后正则抽。这样六字段是**产出的**，不是**猜的**。
- 抽取器保留（对旧产物仍有用），但明确定位成**兜底**；
  `action_incomplete` 的语义随之变成「模型没按 schema 产出」。
- 判据也要跟着改：从「抽出来 ≥3 条」变成「schema 段存在且 ≥3 条
  六字段齐备」。**判据得随实现走**——但这次不是「判据过时」，
  是「实现还没做到判据要求的事」。

## 八、验收判据核对

```
── 阶段 3 ──
  ✅ [3.1] landing_decision 开关存在
  ✅ [3.2.1] _render_landing_boundary 存在
  ✅ [3.2.2] _render_landing_decision 存在
  ✅ [3.2.3] boundary→老模板 / decision→新模板 / 关开关→老模板
  ✅ [3.3.1] _extract_actions 存在
  ✅ [3.3.2] 抽出 3 条（≥1）
  ✅ [3.4] 六字段齐备（缺 []）
  ✅ [3.7] 负对照 空/无动词 answer → []/[]/[]

  ✅ [3.7b] 带 _actions 的 dict 直接复用（不重复抽）
  ✅ [3.8] not_do 抽取 + 负对照（无标记 → 空）
  ✅ [3.5.1] action_incomplete 硬约束
  ✅ [3.5.2] not_do_missing 硬约束
  ✅ [3.6] bench_score.score_decision_rubric / score_actions 存在
━━━ PASS 16 / FAIL 0 ━━━      ← 这 16 条是**机制**判据，全绿
EXIT=0
                               ← G3.7 / G3.8 是**效果**判据，未达成（第六节）
```

★ 这张表要连起来读：**机制全绿 ≠ 效果达标**。机制判据（开关在不在、
抽取器有没有、硬约束响不响、负对照动不动）全绿；效果判据（真跑里行动
够不够 3 条、rubric 够不够 2/3）没过。把两者分开写，是为了不让
「16/0」看起来像阶段通过。

## 九、遗留与下一阶段候选

- **研究层结构化行动清单**：见第七节，这是让 G3.7/G3.8 达标的正路。
- **`landing_decision` 与 `orientation` 的关系**：现在 `auto` 默认走
  decision 模板（任务书的口径）。但 `auto` 的实际取向是 `plan_orientation`
  判的，产物里没有把它回填到 `_config`，所以「auto 判成 boundary 却渲染
  decision 模板」这种错配**看不出来**。下一版应把 `plan_orientation`
  的结果写进产物头部。
- **`_guess_*` 的角色**：目前只覆盖 8 个角色名与 5 个时限词，实测命中率低。
  若继续用抽取路线，需要按领域配置化（而不是在代码里硬编码一张短名单）。
