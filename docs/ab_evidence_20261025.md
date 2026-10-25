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

## 5. local 模式集成验证（partial 真跑，三种失败模式全链路）

命令：lead_probe_run.py --route 0 --rounds 1 --self-check-mode local --local-llm-url http://127.0.0.1:8772/generate
（route 0 / 1 圈 / web off / behavior-fusion off；每次约 ¥0.3、6~9 分钟）。

| # | 端到端状态 | 实测结果（view.meta / 服务日志） | 判定 |
|---|---|---|---|
| v1 | 端点不可达（服务未起/被回收） | URLError [WinError 10061] 拒绝连接 ⇒ 回退 llm | 失败回退 ✅ |
| v2 | 请求到达服务，但生成超时 | 服务日志 3×503 TIMEOUT、TimeoutError: 生成超时；引擎 TimeoutError ⇒ 回退 llm | 失败回退 ✅ |
| v3 | **服务 200 返回本地 JSON，但置信度不足** | RuntimeError: 置信度 0.48 < 0.60 ⇒ 回退 llm；云 self_check 照常 | **质量门回退 ✅（按设计）** |
| v4 | 同 v3（第二次） | 置信度 0.24 < 0.60 ⇒ 回退 llm | 质量门回退 ✅ |
| v5 | 200 返回、门槛降到 0.2 后继续过闸 | 	ext 解析不出 JSON ⇒ 回退 llm（0.5B 在引擎窄 prompt 上 JSON 合法率不足） | JSON 门回退 ✅ |

关键工程修正（v3 前）：pi.local_llm / output.local_llm 增加
max_new_tokens=160、	imeout=45s。原因：0.5B 本地模型实测 ~6 tok/s，
旧值 600 tokens / 30s 必然超时；min schema 160 tokens 足够。修正后服务连续返回
200（服务日志 2×200），证实「引擎 → 本地端点 → JSON → 置信度门」全链路已通。

结论：
- **local 通道接线与三级回退（不可达 / 超时 / 低置信）全部实测通过**，且三种失败
  都留痕、都不崩、都回退云端，符合「失败留痕 + 只变好不变坏」；
- 0.5B 适配器置信度 0.48 低于 0.6 门槛 → 被质量门拦下（这是**期望行为**）：
  本地模型当前只适合叙述/格式草稿，不接管决策字段；
- 成功接管路径（本地直判、0 云调用、确定性核一致性校验通过）由
  	ests_fine_check 的 fake endpoint 判据覆盖；真实接管需 1.5B + 更大数据训练后再验。


## 6. 道生专属模式 CLI e2e（首跑，2026-10-25 11:01）

命令（App 侧 daosheng 预设的引擎等价调用）：
b_bench.py run --tag daosheng-e2e-cli --config configs/道生专属模式.yaml --web off，
同题（城市热岛）。

| 指标 | 结果 | 对照（方案B preset / 同题） |
|---|---|---|
| quality | **0.9465** | 0.9615 / 0.9860（B0/B2） |
| answer_quality / ready | **verified / True** | verified / True |
| tokens | **723,064** | 1,457,052 ~ 1,846,074 |
| calls | **97** | 159 ~ 182 |
| wall | **586.2s** | 922.6 ~ 1275.6s（含并行/单跑差异） |
| rounds | {0:2,1:2,both:2,all:2}（引擎 auto 自适应） | {0:4,1:4,both:4,all:5}（preset B 硬上限路径） |
| cache hit ratio | 11.4% | 13.9%~17.9% |
| 费用（tokens 估算） | ≈ ¥1.4~1.6 | ≈ ¥2.6~3.4 |

判读：
- 道生专属预设（rounds=auto + parallel=B + self_check=llm + web off）在**同题上以约
  一半的 tokens/calls 拿到 verified + answer_ready=True，quality 只低 1.5pp**；
  这符合「rounds=auto 由引擎自然停止点决定成本」的既有结论（preset B 的 19 圈是被
  上限推着走的）。
- 质量 0.9465 与 B0 的 0.9615 差异中，rounds 不同是主因（8 圈 vs 19 圈），
  不能据此说「专属模式比 B 档差」；只能说它是**更省的成本档**，质量仍过门。
- 该结果证明「道生专属模式」预设可被引擎直接加载并跑出 verified 产物；
  App 侧 mock 验收（444/0）与本次 CLI e2e 合起来覆盖了「配置→引擎→产物」链路。


## 7. 负结果：dual_judge thinking off（2026-10-25 11:15）

动机：dual_judge 是 reasoning token 大户（B2 基线 22 calls / 286,935 tokens / 400,320ms，
其中推理占大部分）。若关掉它的 thinking 能保质量，就是一条可观的省钱/省时路径。

命令：b_bench.py run --tag d1-presetB-dj-thinkoff --config configs/方案B-标准.yaml
--parallel B --web off --behavior-fusion off --extra=--stage-thinking --extra=dual_judge=disabled
（同题；基线用 B0/B2 两次同配置跑：quality 0.9615 / 0.9860，tokens 1.79M / 1.85M，
calls 177 / 182，dual_judge 17~22 calls / 177K~287K tokens / 358K~400K ms。）

| 指标 | D1（dual_judge thinking off） | 基线 B0/B2 |
|---|---|---|
| quality | **0.2573** | 0.9615 / 0.9860 |
| answer_quality / ready | **unverified / False**（duty_short） | verified / True |
| tokens | 1,262,637 | 1,788,798 / 1,846,074 |
| calls | 148 | 177 / 182 |
| dual_judge tokens / ms | **116,078 / 36,537** | 286,935 / 400,320（B2） |
| self_check tokens / ms | 137,937 / 30,779 | 179,520 / 38,030（B2） |
| wall | 688.8s | 1131.8s（B2 单跑） |

判读：
- 经济性巨大：dual_judge 推理 token **-60%**、耗时 **-91%**，总 tokens -32%、
  wall -39%；但质量从 0.96~0.99 崩到 **0.257**（answer_ready=False、duty_short）。
- 与 B1（auto_narr）同向：一旦削弱这两个辅助阶段，四层「职责交付面」就短，
  答案门直接不过。⇒ **dual_judge 的 thinking 是质量保险，不是可裁剪开销**。
- 结论：**不采纳**；默认与所有质量档保持 dual_judge thinking=enabled，
  该 lever 关闭；成本优化只剩「前缀缓存/更优轮数/本地模型」三条路。

## 8. 道生专属模式 × 跨场景矩阵（引擎 CLI 直跑，2026-10-25 12:53）

同一预设（configs/道生专属模式.yaml）在 5 个不同题型/领域上各跑一次：

| 场景 | 题型/领域 | web | quality | answer_quality / ready | tokens | calls | wall |
|---|---|---|---|---|---|---|---|
| 城市气候 | 推理 | off | 0.9465 | verified / True | 723,064 | 97 | 586s |
| 静电成因 | 推理（跨领域） | off | 0.9400 | verified / True | 718,020 | 100 | 585s |
| 补观测 vs 统一定义 | 选择/决策 | off | 0.9487 | verified / True | 842,151 | 98 | 869s |
| 介质光速 | 事实 | **off** | **0.4440** | **unverified / False** | 1,015,910 | 111 | 980s |
| 介质光速 | 事实 | **on** | **0.9581** | **verified / True** | 1,154,024 | 108 | 966s |

判读（动态最优规则）：
1. **推理/选择类**：道生预设稳定在 0.94~0.95、verified、ready=True、72~84 万 tokens、
   585~870s；跨领域与跨题型一致 ⇒ 该档可作为推理/决策题的默认动态档。
2. **事实类必须联网**：同一题 web off → 0.444/unverified（101 万 tokens 白花）；
   web on → 0.958/verified（+13.6 万 tokens、质量 +0.51）⇒ 「事实题无 web」是
   **更高成本 + 更低质量**的双输档，必须在 App/引擎两层强制 web-retry
   （App 2.0.23 的 auto:web-retry 已覆盖；引擎直跑需显式 --web on）。
3. 事实题联网后的成本（115 万 tokens / 966s）仍高于推理题（72 万/585s）⇒
   动态调度里「题型→web」是**质量开关**而不是成本开关，应优先质量。
4. 该矩阵可作为 M4/mode_fusion 场景表的实测锚点：推理/选择→daosheng(auto rounds,
   web off)；事实→daosheng + web on（web-retry）。


## 9. 场景 × 模式矩阵（Round 4：补 fast / serial 两档实测）

同一推理题（城市热岛，道生预设 + 引擎 CLI）三种模式各跑一次：

| 模式 | 配置 | quality | verified/ready | tokens | calls | wall |
|---|---|---|---|---|---|---|
| auto（B 并行 + thinking auto + rounds auto） | 道生预设默认 | 0.9465 | ✅ / ✅ | 723,064 | 97 | 586.2s |
| serial（串行） | --parallel serial | 0.9456 | ✅ / ✅ | 644,954 | 89 | 1019.0s |
| fast（thinking off） | --thinking off | 0.9366 | ✅ / ✅ | **481,050** | 89 | **188.4s** |

事实题（光速）fast 对照：**quality 0.4741 / needs_evidence / ready=False**
（836K tokens / 316s）⇒ 事实题不能关 thinking。

判读（写进 mode_fusion.MEASURED_SCENARIOS 与 
ecommend_scenario()）：
1. **推理/选择类**：auto 质量最高（0.9465/0.9487）；**fast 是成本/墙钟档**
   （tokens −33%、墙钟 −68%，质量 −1.0pp）；serial 仅省 11% tokens 但墙钟 +74%，
   是受支配档（只在 min_quality≥0.94 且 tokens 优先时有用）。
2. **事实类**：必须 web on + thinking on；web off（0.444）与 thinking off（0.474）
   都是「成本不低、质量不达标」的双输档。
3. 
ecommend_scenario(kind, min_quality, max_wall, prefer) 已把这套规则机器化：
   按实测 verified 池筛选 → 偏好排序 → 约束不可满足时显式回退并写 reason。
   判据：tests_scenario_matrix.py 19/19 PASS。


## 10. fast 档泛化实测（Round 5：推理跨域 + 选择题）

| 场景 | 模式 | quality | verified/ready | tokens | calls | wall |
|---|---|---|---|---|---|---|
| 推理·静电（跨领域） | auto | 0.9400 | ✅/✅ | 718,020 | 100 | 585s |
| 推理·静电（跨领域） | **fast** | **0.9535** | ✅/✅ | **579,083** | 98 | **283s** |
| 选择·补观测 vs 定义 | auto | 0.9487 | ✅/✅ | 842,151 | 98 | 869s |
| 选择·补观测 vs 定义 | **fast** | **0.9481** | ✅/✅ | **593,788** | 97 | **273s** |

判读：
- **fast 在跨领域推理与选择类上与 auto 同质量（差值 ≤0.01，单跑方差内），
  tokens −19~30%、墙钟 −52~69%** ⇒ 成本档从「仅热岛单题」升级为「3 题 × 2 题型验证」。
- 事实题仍然禁止 fast（上节：0.4741/needs_evidence；thinking off 与 web 缺一不可）。
- 更新 `mode_fusion.MEASURED_SCENARIOS`（9 行实测）与规则：
  reasoning/choice 的 `cost_first=fast`；质量优先仍 `auto`（保留 thinking，方差更稳）；
  serial 被 fast/auto 支配（仅历史对照保留）。
- App 道生 plan 已把规则落到**决策**而非审计字段：
  预算档 reasoning/choice → fast；预算档/降级遇事实题 → 保 B + 强制 web on + thinking auto。
