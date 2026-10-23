# 元DGTF · 停止与收敛条件参考（v1.21.58）

> 回答两个问题：**各层的停止条件是什么？各模式下有没有区别？**
> 一句话结论：**9 个模式的停止理由集完全一致**，只有 2 条代码路径；
> 差异只在"谁驱动圈循环"，不在"什么时候该停"。

---

## 一、9 个模式 → 2 条代码路径

| 模式 | 入口 | 圈循环函数 | 驱动方式 |
|---|---|---|---|
| **serial** | `_run_serial` | `_run_layer` | 四层严格串行，每层跑完自己的圈 |
| **A** | `_run_parallel_A` | `_run_layer` | 四层**线程并行**（`ThreadPoolExecutor`）+ 跑完后一个**汇流圈** |
| **B** | `_run_parallel_B` | `_run_one_round_B` | 波次/barrier：所有层每圈对齐一次（Jacobi） |
| **C** | `_run_parallel_C` | `_run_one_round_B` | 流水线（`_run_layer_C` 包一层），0 层先预热 N 圈 |
| **D–H** | `_run_parallel_stage` | `_run_one_round_B` | 阶段式 DAG（`_run_layer_stage` 按 `_MODE_GRAPH` 走 wait/gate 闸门） |

两条路径的**停止理由列表逐条相同**（已逐条比对过）。所以下文的停止条件
对 9 个模式**一并成立**，不必分模式记。

三个模式特有、但不属于"停止条件"的东西：

- **A 的汇流圈**：四层跑完后，若 `0/1/both` 里至少 2 份 view 可用，
  额外让 all 层**跑一圈**（`round_role="收束"`）读它们，结果入池。
  这一圈是**单圈、不走螺旋**，因此**没有任何停止判据**——它要么跑，要么跳过。
- **C / D–H 的预热**：`actions.parallel_warmup_rounds`（默认 1）——
  0 层先单独跑 N 圈，让下游一出发就有上游可读。设 0 = 字面"同时出发"。
- **D/E**：0 层预热后与 1 层并行出发，下游等待方式不同（见 `_MODE_GRAPH`）。

---

## 二、停止理由总表（9 条）

在**两条路径里都**按这个顺序生成 `stop_reasons`，非空即停。

| # | 理由文本 | 触发条件 | 累计门槛 | 适用层 | 额外门 |
|---|---|---|---|---|---|
| 1a | `ing 连续 N 圈复述（层内空转）` | `max(meta_idle_streak, view._meta_idle_streak) >= 2` | ≥2 圈 | **仅 both / all** | `layer_no >= soft_max` |
| 1b | `自省连续 N 圈点名同一批问题未消化（层内空转）` | `carry_streak >= 2`（**同一批** banned 集合重复才 +1） | ≥2 圈 | **仅 both / all** | `layer_no >= soft_max` |
| 2 | `结构饱和度判定连续无新维度` | `sat_verdict is False` 且 `sat_override` | — | **仅 1 / all**（检查本身只在这两层跑） | 替代 3 |
| 3 | `连续 N 轮无新 &（沉淀完了）` | `idle_new_amp >= round_idle_limit`（默认 2） | ≥2 圈 | **除 0 之外**（`entry != "0"`） | `_total_rounds > 1` |
| 4 | `连续 N 轮无线头新增（方向走完了）` | `idle_new_thread >= round_idle_limit` | ≥2 圈 | **全部** | `_total_rounds > 1` |
| 5 | `连续 N 轮有新增但无推进（…）` | `idle_stall >= round_stall_limit`（默认 2） | ≥2 圈 | **全部** | `rounds_n > 1` |
| 6 | `研究层双通道均收敛` | `dec_tracker.converged and und_tracker.converged and idle_new_amp >= 2` | — | **仅 1** | — |
| 7 | `双通道均停滞（qdist 无改善）` | 两个 tracker 都 `is_stalled()`、未都收敛、`idle_new_amp >= 2` | — | **仅 1** | — |
| 8a | `产物相似度高，自然安住` | `_similar(上一圈 manifest, 本圈 manifest, stop_similarity=0.8)` | 连续两圈 | **全部** | `rounds_n > 1 且 layer_no >= soft_max` |
| 8b | `悬置决定稳定，自然安住` | `len(stable) >= stable_layers`（默认 3；both 用 `duel_suspensions`） | — | **全部** | 同上 |
| 9a | `无新张力（材料耗尽）` | `not stop_reasons and view.idle` 连续 `idle_limit`（默认 2）圈 | ≥2 圈 | **仅 both** | 同上 |
| 9b | `无新元决策（元决策耗尽）` | 同上 | ≥2 圈 | **仅 all** | 同上 |
| 9c | `连续空转` | 同上 | ≥2 圈 | **其他（0 / 1）** | 同上 |

**层 × 理由可达矩阵**

| 理由 \ 层 | 0 修行 | 1 研究 | both 对撞 | all 元 |
|---|---|---|---|---|
| 1a/1b 复述 / 自省点名 | — | — | ✓ | ✓ |
| 2 结构饱和度 | — | ✓ | — | ✓ |
| 3 无新 & | — | ✓ | ✓ | ✓ |
| 4 无线头 | ✓ | ✓ | ✓ | ✓ |
| 5 有新增无推进 | ✓ | ✓ | ✓ | ✓ |
| 6/7 双通道收敛 / 停滞 | — | ✓ | — | — |
| 8 自然安住 | ✓ | ✓ | ✓ | ✓ |
| 9 空转（措辞按层） | ✓ | ✓ | ✓ | ✓ |

> ★ **读法**：注意 `soft_max` 是「自然安住」与 1a/1b/9 的**圈号下限**
> （`layer_no >= soft_max`）。理由 3/4/5 不看 soft_max，但它们自身要
> 累计 ≥2 圈。所以**第 1 圈在任何层都不可能产生停止理由**（v1.21.57 复查结论）。

---

## 三、理由生成之后的 4 道闸门（会"拦住"已触发的理由）

即使 `stop_reasons` 非空，下面 4 条任一命中都会把停止**拦下**：

| # | 闸门 | 条件 | 后果 |
|---|---|---|---|
| 1 | **`_uncovered_gate`（fix-88b）** | 还有「未深入方向」≥1 且方向数在减少 且 未超 `max_uncovered_pushes`(1) 且 **不是最后一圈** | 清空理由、推迟一圈；理由原文进 `deferred_notes` |
| 2 | **`min_rounds`** | `layer_no < min_rounds[层]` | 清空理由。**v1.21.58 起全层 0** |
| 3 | **元层语义下限** | `entry=="all"` 且 `layer_no < _total_rounds` 且 `_settle_meta()` 报「未交代 >0」且未连续不降 | 清空理由、推迟。**不看圈号** |
| 4 | **走满预算** | 循环正常结束（没 break） | 写 `体力耗尽（…）`；若有被闸门 1 推迟过的理由，**如实写出来** |

`_uncovered_gate` 的三条放行理由（都不再推迟）：已达上限 / 方向数未减少 /
**已是最后一圈没有下一圈可推**。

---

## 四、收敛（两个 tracker，只研究层更新）

| 通道 | 收敛条件 | 标记 |
|---|---|---|
| 可判定 | `effective_cov >= _TRACKER_COVERAGE(0.7)` 连续 `convergence_window(2)` 圈 | `dec_tracker.mark_converged` |
| 不可判定 | `len(structural_amps) >= 2` 且 `clarity >= _TRACKER_CLARITY(0.6)` 连续 2 圈 | `und_tracker.mark_converged` |
| 停滞 | `qdist = 1 - cov/clarity`，改善 `< min_distance_improvement(0.03)` 连续 `stall_streak_limit(2)` 圈 | `is_stalled()` |

收敛/停滞**只用于研究层**的理由 6/7；其他层不读 tracker。

---

## 五、三个已知的坑

1. **预算必须 > `soft_max`**，否则「自然安住」（理由 8）永远触发不了——
   它是 `layer_no >= soft_max` 且有预算上限的，`预算 3 < soft_max 5` 时
   第 5 圈根本不存在。旧默认就是这样（对撞层 `soft_max: 5` + 预算 3）。
2. **预算就是决定量，不是"等它自然停"**。当前版本实测：给 6/4/7/5 的预算，
   四层跑到 6/4/7/6 **全部顶到上限**，且每圈仍有真·新增 &（`idle_new_amp`
   一直是 0）。所以"连续 N 轮无新 &"这类理由**在还能产出时就永远不触发**。
   详见真跑验证报告第十二节。
3. **`min_rounds` 是"下限"不是"预算"**（v1.21.58 修了这个混用）。
   旧代码把 `min_rounds: 2` 当成"预算就是 2"，正好撞上配置注释里那条教训
   （研究层 2 圈 → 可判定覆盖率仅 33%）。

---

## 六、怎么调（三条路，都是运行时）

```bash
# 1) 命令行（只管预算）
python 元DGTF-V1.21.58.py "问题" --rounds 3
python 元DGTF-V1.21.58.py "问题" --rounds "0:4,both:6"   # 只改想改的层

# 2) 交互式（不给参数时会问）
#    圈数 [0=用 hard_max]> 0:2,1:2,both:3,all:3

# 3) 配置文件（要改的不只是预算时，临时加这一段）
#    spiral:
#      per_entry:
#        "both": { soft_max: 5, hard_max: 6 }
```

**出厂默认**（`dgtf_config.yaml`，v1.21.58 起）：全层统一
`soft_max: 3` / `hard_max: 12` / `stable_layers: 3` /
`structure_saturation_every_n: 3` / `min_rounds` 全 0，**没有 `per_entry`**。
