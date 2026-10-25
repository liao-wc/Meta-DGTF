# 全量 A/B 证据：细粒度自省替换（2026-10-25）

> 目的：回答「auto_narr / self_check thinking off 能不能上线」——用**同题、同配置、
> 只改机制的配对真跑**给出可复现数字，并据此决定生产默认值。
> 原始记录：`docs/ab_results.jsonl`（每跑一行，含 probe 用量与 packed 指标）；
> 复现命令见每节；对比工具：`python scripts/ab_bench.py pair --a <tag> --b <tag>`。

## 0. 设计

| 项 | 值 |
|---|---|
| 问题 | 「为什么城市热岛效应在夜间比白天更明显？」（项目历史标准对照题） |
| 配置 | `configs/方案B-标准.yaml`（方案B 标准档），`--parallel B --web off --behavior-fusion off` |
| 引擎 | Meta-DGTF-V2.2.3（默认档与 V2.2.2 逐字零行为差，tests_fine_check 判据） |
| 变量 | 仅 `--self-check-mode` 与 `--stage-thinking` |
| 有效性 | `valid=true` 要求：引擎 exit 0 + 有 packed + `budget.hard_hit=false` |

## 1. 结果（写稿时的有效跑）

| tag | 变体 | quality | answer_quality | answer_ready | tokens | calls | self_check tokens/calls | self_check ms | wall |
|---|---|---|---|---|---|---|---|---|---|
| b0-presetB-baseline | 基线：self_check=llm | **0.9615** | verified | **True** | 1,788,798 | 177 | 176,912 / 17 | 35,815 | 1275.6s* |
| b1-presetB-auto-narr-thinkoff | auto_narr + self_check thinking off | **0.2632** | unverified | **False** | 1,457,052 | 159 | 113,907 / 15 | 15,061 | 922.6s* |
| b2-presetB-thinkoff-only | 仅 self_check thinking off（对照复跑） | 0.9860 | verified | True | 1,846,074 | 182 | 179,520 / 17 | 38,030 | 1131.8s（单跑） |

\* B0/B1 为**并行执行**：两跑互为背景负载，绝对墙钟不能直接比较（同一方向偏大）；
tokens/calls 不受影响。B2 为**单跑**，墙钟可直接与后续单跑对照。

**关键归因（B2 后修正）**：对照 B0 的 `_runtime.thinking_stages_enabled` 可见，`self_check` 在基线里**本来就未开 thinking**（`--thinking auto` + `api.thinking.stages.self_check=disabled`），因此 `--stage-thinking self_check=disabled` 是 no-op：B2 实际等于 B0 的复跑，两者差异（quality 0.9615→0.9860、tokens 1.79M→1.85M、calls 177→182）就是**单跑方差**。
⇒ B1 的落差（quality 0.2632、self_check token -27%、ms -52%）可以**干净归因到 auto_narr**（收窄 prompt + 去掉 multi-turn 历史），而不是 thinking 开关。

无效跑（留档，不进对照）：
- `r1-baseline-default`（route/rounds 手工指定的早期尝试）：rounds 被引擎计划放大到
  {0:4,1:8,both:5,all:6} 并触发 2M token 预算硬顶（`hard_hit=true`、`lazy_empty`），
  质量 0.2605 属截断产物 ⇒ `valid=false`，不作为基线。

## 2. 判读

1. **auto_narr + thinking off 组合显著降质**：quality 0.9615 → 0.2632，verified → unverified，
   answer_ready True → False（四层 duty_short）。同一配置下 rounds 计划一致
   （{0:4,1:4,both:4,all:5}），差异只能来自自省机制。
2. **经济性是真的**：self_check 单跑 token -27%、墙钟 -52%（35.8s→15.1s 总耗时），
   总 tokens -18.5%（1.79M→1.46M）。但质量损失远大于收益（与 V2.2.2 时期
   「B-no-self_check quality 0.94」的负结果同向且更重）。
3. **根因假设**：auto_narr 的收窄 prompt 去掉了 manifest/collision/上游历史，
   self_check 对「复述/可疑候选/未生」的判断失准 → carry 约束与回填动作被带偏 →
   四层交付面（duty）不达标 → 答案门不过。thinking off 是否单独有份，看 B2 隔离结果。
4. **决策**：本组合**不采纳、不进生产默认**；`output.self_check_mode` 保持 `llm`。
   道生专属模式预设已固定 `llm`（configs/道生专属模式.yaml）。实验档只允许在
   显式 opt-in 的预算实验里用，不得出现在默认链路。

## 3. 成本与缓存读数（probe）

| tag | prompt_cache_hit_ratio | cache hit / miss tokens | dup prompts |
|---|---|---|---|
| b0（基线） | **13.9%** | 201,088 / 1,245,165 | 0 |
| b1（变体） | **16.8%** | 194,176 / 961,506 | 1 |

- 真实全量跑的**前缀缓存命中率约 14%~17%**（此前 route-0 探针为 0%，说明 full-run
  里同层/同 stage 重复前缀确实被缓存）；按官方 cache hit $0.003/M vs miss $0.15/M，
  当前已自动省下约 ¥0.2~0.25/跑。
- 机制侧（`scripts/lead_prefix_cache_test.py`）实测：同 system + 不同 user 第二次
  命中 1024/1269 tokens、TTL > 8min；把变化段放到 system 头部则 0 命中
  ⇒ **prompt 静态段前置**是下一轮可验证的省钱项（需质量 A/B，因为会改 prompt）。

## 4. 复现

```bash
# 基线
python scripts/ab_bench.py run --tag b0-presetB-baseline --question "为什么城市热岛效应在夜间比白天更明显？" \
  --config configs/方案B-标准.yaml --parallel B --web off --behavior-fusion off

# 变体（auto_narr + self_check thinking off）
python scripts/ab_bench.py run --tag b1-presetB-auto-narr-thinkoff --question "为什么城市热岛效应在夜间比白天更明显？" \
  --config configs/方案B-标准.yaml --parallel B --web off --behavior-fusion off \
  --extra=--self-check-mode --extra=auto_narr --extra=--stage-thinking --extra=self_check=disabled

# 差
python scripts/ab_bench.py pair --a b0-presetB-baseline --b b1-presetB-auto-narr-thinkoff
```

## 5. local 模式集成验证（partial，真端点）

命令：lead_probe_run.py --route 0 --rounds 1 --self-check-mode local --local-llm-url http://127.0.0.1:8772
（route 0 / 1 圈 / web off / behavior-fusion off；成本约 ¥0.29、23 calls / 169,402 tokens / 470.2s）。

结果与判读：
- 引擎**确实走了本地端点**：view.meta 留痕
  [SC-local] 本地模型失败（累计 1 次：URLError WinError 10061 连接被拒）⇒ 回退 llm；
  原因是同一时间 local-smith 为「截断修复版重训」停掉 8772（计划内），本地调用落空。
- **失败回退契约实测通过**：503/连接失败 → error 计数 + view.meta 留痕 + 自动回退云端 llm，
  没有崩、没有丢 self_check（3 次云调用，13,219 prompt / 5,074 completion）。
- 成功路径（本地直判、0 云调用、低置信/不一致升云）仍由 	ests_fine_check（fake endpoint）
  判据覆盖；真实成功路径待 8772 新适配器就绪后再验（下一轮）。
- 结论：**local 通道的接线与回退是通的**；当前不启用（0.5B 适配器质量未过 go/no-go）。
