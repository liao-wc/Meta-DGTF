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


## 11. 前缀缓存 prompt 重排：机制已实现，但无收益（Round 6 负结果）

动机：DeepSeek cache hit/miss 单价差约 50 倍（$0.003 vs $0.15/M）。研究 Top5 提出
「静态段前置、变量段后置」以扩大可缓存前缀。本轮实现 opt-in 机制后做局部对照：

实现（V2.2.3，默认关=零行为差）：
- 新配置 `output.prompt_stable_first`（默认 False）与 CLI `--prompt-stable-first`；
- 开启时把 `dual_judge` 的 carry 约束块 / `self_check` 的 self_block
  （每圈变化的变量块）从 system 末尾移到 user 末尾；
- 纯函数 `_move_var_to_user()` + 14 项判据（tests_prompt_cache.py）。

局部实测（route 0 / 1 圈 / web off / behavior-fusion off，同题）：

| 指标 | 基线（off） | 变体（--prompt-stable-first） |
|---|---|---|
| prompt cache hit ratio | **0.4279** | 0.3970 |
| cache hit / miss tokens | 46,592 / 62,283 | 44,544 / 67,657 |
| tokens / calls / wall | 159,740 / 29 / 462.1s | 168,633 / 29 / 487.3s |
| self_check tokens（3 calls） | 22,648 | 23,292 |
| dual_judge tokens（3 calls） | 17,596 | 19,427 |

判读：
1. 变体**没有提升缓存命中**（−3.1pp），tokens/墙钟略升；差异在单跑噪声量级内。
2. 原因：当前 prompt 本来就「system 静态在前」——self_check 的 self_block 已在 system
   末尾（静态前缀已是 system 的绝大部分）；dual_judge 的 carry 块虽在中间，但
   schema 等静态段较短，可扩展空间有限，且缓存按 64 token 块对齐，位移后仍需重算。
3. **结论：不采纳为默认**（机制保留为 opt-in/可回退），并把「前缀缓存已接近上限」
   写入结论：局部跑缓存命中率已达 **42.8%**（此前全量跑 11~18% 是跨阶段/间隔更长
   导致的缓存失效，不代表布局问题）。下一步省钱重点回到「轮数/档位/本地模型」。


## 12. 实测矩阵回灌管线（learning loop，Round 6）

问题：`mode_fusion.MEASURED_SCENARIOS` 是人工锚点，每轮 A/B 新数据不会自动进来。
新增 `scripts/update_scenario_matrix.py`：
- 扫描 `docs/ab_results.jsonl` 的**有效真跑**（valid=true），按
  「题型场景（kind_of_question）× 引擎模式（auto/fast/serial × web on/off）」聚合；
- **质量锚点只用 verified 真跑**（负结果机制实验如 B1 auto_narr / D1 thinking off
  虽然 valid=true，但不能进入场景质量锚点——首版脚本因此把 reasoning auto 拉低到
  0.726，已修正为 verified-only）；
- 输出 `docs/scenario_matrix_live.json`（每格含 n/verified 比例/均值/latest/样本），
  并与人工锚点逐项对照打印 Δ，供人工/CI 决定是否更新代码锚点（不自动改代码，
  避免悄悄改变选档行为与测试基准）。

本轮实测一致性（人工锚点 vs 真跑汇总）：

| 场景 | 模式 | 人工 | 实测 | Δ |
|---|---|---|---|---|
| reasoning | auto | 0.947 | 0.959（n=6，verified 4） | +0.012 |
| reasoning | fast | 0.937 | 0.945（n=2） | +0.008 |
| reasoning | serial | 0.946 | 0.946（n=1） | 0 |
| choice | auto / fast | 0.949 / 0.948 | 0.949 / 0.948 | 0 |
| fact | web_on_auto / web_on_fast / web_off_auto | 0.958 / 0.474 / 0.444 | 同 | 0 |

结论：人工锚点与真跑数据一致（Δ≤0.012），矩阵可信；回灌管线可在后续轮次把新跑次
自动纳入并提示更新，形成「跑→汇总→校准锚点→再选档」的闭环。


## 13. App 道生 fast 成本档真实任务端到端（Round 7）

目的：验证「App plan → 引擎参数 → 真实跑次」链路上，新场景规则（fast 成本档）
能正确落到引擎并产出 verified 质量。此前只做过 mock 与 CLI 直跑。

执行：起 App server（8768 真实非 mock）→ `POST /api/tasks`
`{mode:"daosheng_fast", question:"为什么在高原上煮饭更容易夹生？"}` → 轮询到 done。

plan 实际生效（响应回显）：
```
tier=fast | engine_mode=fast | parallel=serial | thinking=off | web=off
rounds=0:2,1:3,both:2,all:2 | scenario=reasoning → 推荐 fast_domain2
```

真实跑次（packed 读数，非缓存）：
| 指标 | 值 |
|---|---|
| question | 为什么在高原上煮饭更容易夹生？（跨领域推理，全新题） |
| **quality / answer_quality / answer_ready** | **0.9588 / verified / True** |
| tokens / calls | **698,602 / 107** |
| rounds | {0:2, 1:3, both:2, all:2}（与 plan 完全一致） |
| 任务墙钟（App 计时） | 573.3s |

判读：
- 场景规则在真实 App 任务中生效：reasoning → fast 档（thinking off + 低圈），
  以 **69.9 万 tokens / 9.5 分钟** 拿到 **verified + answer_ready=True**；
- 与 CLI fast 档实测（481K~579K tokens / 188~283s）同向；App 侧多出的时间是
  任务编排/归档/内容落盘与并发环境差异，量级合理；
- 首次尝试同一题（热岛）时命中 App 答案缓存（11.2s done），说明缓存路径正常；
  换全新题后触发真实跑次，故本次为真实引擎证据。
- 证据：`llm_sft/_round7_evidence/app_fast_e2e.json`、
  `outputs/20261025_143654_为什么在高原上煮饭更容易夹生.packed.json`。


## 14. 事实门「官方源优先」冲突消解 + 证据去重官方优先（Round 8）

真实反例（App 事实题 real e2e「珠穆朗玛峰的海拔是多少米？」）：
- 修复前：web on + 全四层 → quality 0.4273 / **unverified**（gaps=conflict_unresolved），
  1,257,791 tokens 白跑；
- 根因：证据间冲突项是**年份**（1852 vs 1856，辅助信息），不是题面目标值；
  官方源 E8 已给出海拔，但现逻辑「有冲突就 conflict」直接卡死事实门。
- 另一根因：同一文本先被非官方镜像召回时，`dedup_evidence` 保留首个出现，
  后到的官方源被当重复丢弃 → 假性 `no_official_source`。

两个机制（`dgtf_v2/fact_flow.py` + `dgtf_v2/evidence.py`，默认生效）：
1. **官方源优先消解**：当冲突**全部是日期类辅助冲突**（单位/锚点含年/月/日/date，
   或数值全在 1000~2100 像年份）且官方源能给出题面相关答案时 → status=answered、
   答案取官方原文（清洗掉行首 [日期]/### 等）、原冲突存 `resolved_conflicts`、
   gaps 记 `conflict_resolved_official:official_precedence`（非硬缺口）。
   负对照：目标量冲突（GDP 5.2 vs 6.8，单位 %）**不会被消解**；官方源参与冲突、
   无官方源、官方源答不出 → 保持 conflict。
2. **去重官方优先**：同 URL/文本多渠道时，若保留者非官方而后到者官方 → 用官方源
   顶替（旧项记 `dedup_prefer_official`），避免官方证据被当重复丢掉。

判据：`tests_fact_official_precedence.py` **14 项**（7 正/负对照 + 边界 + 确定性）、
`tests_fact_flow.py` 15 项、`tests_evidence.py` 21 项全 PASS；全量 V2 45 文件绿。

真实端到端验证（本轮运行）：
| 场景 | 结果 |
|---|---|
| App 事实题（珠峰）修复前 | 0.4273 / unverified / ready=False / 1,257,791 tok |
| App 事实题（珠峰）修复后 | **answer_quality=verified**（conflict 消解为 1 条辅助冲突），
  gaps 仅 `conflict_resolved_official`；ready=False 原因是**过程门**（元层 all 产物 400 字
  未达标），非事实门 —— 下一轮修过程门 |
| CLI 长江长度（web on，对照） | 0.9746 / verified / ready=True / 1,120,972 tok / 108 calls / 1070s |

## 15. 上下文压缩（self_memory ≤N 字，opt-in，默认关）（Round 8）

机制：V2.2.3 `output.self_memory_max_chars`（默认 0=不压缩）+ CLI
`--self-memory-max-chars`：self_check 的「上一次是谁」记忆只保留最近 N 字并加压缩标记，
降低跨圈/跨层重复计费；`tests_memory_compact.py` 13 项判据。

局部 A/B（route 0 / 5 圈 / web off，同题）：
| 指标 | 基线（cap=0） | 变体（cap=1200） |
|---|---|---|
| 总 tokens / calls | 211,762 / 39 | 132,388 / 29 |
| self_check | 4 calls / 29,251 tok（7.3K/次） | 3 calls / 20,159 tok（6.7K/次） |
| dual_judge | 4 calls / 21,992 tok | 3 calls / 19,566 tok |

判读：self_check 单次 prompt tokens −8.3%；总 tokens 差异主要来自**轮次/停止点不同**
（非纯压缩），不能当压缩收益。self_check 只占全量 ~10-15%，故总收益约 1% 量级 ⇒
**保留 opt-in，不设默认**；上下文压缩的真正大头在层 prompt（manifest/collision），
需质量 A/B 预算，留待后续。


### 14.1 真实跑次明细与收尾说明（Round 8 末尾）

| 跑次 | 关键读数 |
|---|---|
| 珠峰 App e2e（修复前，web on，全四层） | 0.4273 / unverified / ready=False / 1,257,791 tok / 111 calls |
| 珠峰 App e2e（官方源优先后，pre-clean 版本） | **0.37 / verified / ready=False** / 1,114,650 tok / 101 calls；fact_card=answered，resolved_conflicts=1，gaps 仅 `conflict_resolved_official:official_precedence`；ready=False 仍由**过程门**（元层 all 产物 400 字未达标）阻断，非事实门 |
| 长江长度 CLI（web on，对照） | **0.9746 / verified / ready=True** / 1,120,972 tok / 108 calls / 1070s；fact_card=answered 无冲突 |

两个遗留观察（下一轮处理）：
1. **过程门**：珠峰跑次元层 all 产物仅 400 字、无引用 ⇒ `process_ledger.standard_all=False`
   ⇒ answer_ready 仍 False。事实门与过程门是两套合同，需分别优化（过程门属元层收束问题）。
2. **答案抽取**：`answer_from_evidence` 曾把 `[2018-09-20] ### 关于珠峰高度…8844.43米`
   这类带日期/标题/旧值的网页片段当答案（官方源是 2005 年公布值）。本轮已给
   official-precedence 路径加 `_clean_card_answer` 清洗（去行首 [日期]/###、压 200 字），
   并把同一清洗用于**普通 answered 路径**；更进一步的「最新值优先」需要按证据日期
   排序与语义过滤，作为下一轮机制候选。
3. 预算状态：Round 8 末尾账户余额约 **¥3.3**，不足以再跑完整引擎跑次（单次 ¥2.5+）；
   后续轮次转入零/低 API 成本工作（代码、判据、文档、离线分析），直到预算耗尽。


## 16. 事实答案「展示分离」：answer_display 数值紧凑（Round 9，零 API 成本）

问题（来自已存真实 pack）：verified 事实答案字段混入网页噪声——
- 长江长度：「[2020-12-28] 6280千米与0.88千米的对话——记长江局与…（整段网页文本）」
- 珠峰海拔：「…我看2005年公布的高程是8844.43米」（日期/标题前缀）

第一版把 `card.answer` 直接收窄成「值+单位」→ **真实回归**：consistency 校验按
`card.answer` 做检索 vs 推理比对，收窄后相似度 0.17 判 mismatch
（tests_fact_flow 两处失败）。故改为**展示分离**：
- `card.answer` 保持完整短文本（逻辑/一致性用，零改动）；
- `FactCard.to_dict()` 新增 **`answer_display`** = 数值紧凑版
  （`_compact_numeric_answer`：题面含数值信号时抽「值+单位」，单位命中题面优先、
  再按原文位置；抽不到则回退清洗文本）；
- 引擎 `answer_summary.answer` 优先取 `answer_display`（Show/App/契约统一）。

判据：tests_fact_official_precedence 增至 **19 项**（新增 4 项展示分离：字段存在、
answer 完整、数值题收窄 ≤20 字、非数值题两者相同）；tests_fact_flow 15 项回归通过
（一致性路径不受影响）。全量 V2 45 文件、fast_gate 12/12 绿。

说明：紧凑答案的「最新值优先」（珠峰 8844.43 vs 最新 8848.86）需要按证据日期排序 +
语义过滤，属下一轮候选；本轮余额约 ¥3，无法再跑真实 e2e 验证，故先落机制与离线判据。


## 17. 事实答案「时效优先」（prefer_recent，Round 11，零 API 成本）

问题（遗留 #2，来自真实 pack）：珠峰事实题答案可能取 2005 年公布的 8844.43 米，
而证据里同时存在 2020 年联合公布的 8848.86 米。

实现（`dgtf_v2/evidence.py` + `fact_flow.py`）：
- `answer_from_evidence(..., prefer_recent=False)`：**默认 False = 零行为差**；
- 仅当题面含「最新/当前/现在/目前/截至/如今/现行/latest/current」时效词时启用：
  从证据文本解析日期（**年份只认 1800–2099 且前面不能是数字**，避免把 8844.43
  这类小数当成年份——第一版因此误判，已修正），日期最新者 +0.5 分（可反超
  非最新官方源的 0.15 官方加权）；
- `fact_flow` 两处答案抽取透传 `prefer_recent=True`（题面无时效词时内部自动不启用）。

判据：新增 `tests_recency_preference.py` **7 项**（默认关闭=旧行为 / 时效题取最新 /
非时效题不启用 / 无日期回退 / fact_flow 双向集成）；回归 tests_evidence 21、
tests_fact_flow 15、tests_fact_official_precedence 19 全 PASS；
全量 V2 **46/46（686 checks）**、fast_gate **12/12** 绿。

边界：若多来源给出不同数值（如 8844.43 vs 8848.86 同上下文），会先走冲突判定
（conflict 分支），时效优先只在「非冲突的多个答案候选」之间生效；这也符合
「冲突必须显式消解」的红线。


## 18. 离线 pack 审计：212 个真实产物的机制覆盖与剩余问题（Round 12，零 API）

预算受限后改为审计已存 `outputs/*.packed.json`（**212 个真实产物，其中 64 条事实题**），
脚本 `scripts/lead_offline_pack_audit.py`，结果 `docs/offline_pack_audit_20261025.json`。

### 18.1 分布

- 事实题 answer_quality：verified **44** / unverified 33 / needs_evidence 8；
- fact_card 状态：answered **50** / conflict 8 / 无卡 6；
- fact gaps 频次：conflict_unresolved 8、no_official_source **7**、uncovered:* 8、
  conflict_resolved_official:official_precedence 1（本轮新机制已生效 1 次）；
- 冲突覆盖：8 个跑次有冲突，其中仅 **2 个**是日期类辅助冲突（可被官方源优先消解），
  本轮新机制真实命中 1 次（珠峰）；其余 6 个是目标量/官方互冲（按设计保持 conflict）；
- 过程门：`standard_all=False` **41** 跑次、`meta_clean=False` **19** 跑次、
  meta_closure 未交代张力合计 **53** ⇒ ready=False 的最大来源是**过程门**而非事实门。

### 18.2 关键发现（下一轮候选，均需小额 A/B 验证）

1. **官方证据捕获可靠性**：7 个 `no_official_source` 跑次的原始检索池里其实**存在
   官方域名**（如 developer.mozilla.org / iana / rfc-editor / cas.cn），但进入
   evidence 层的 8 条里 official=0 ⇒ 官方证据在「检索→归一化→预算保留」链路被
   丢弃或未识别。修复方向：核对 `from_search_hits` 的 url/link 字段映射与
   budget 保留顺序；若确认是字段映射问题，可显著提升 verified 率（零成本修复，
   但需一轮真实跑验证）。
2. **过程门是 readiness 主瓶颈**：41/64 事实跑次 standard_all=False；
   meta_closure 未交代张力 53 处。候选：短事实题的探针纪律（不引入与答案无关的
   张力）+ 元层收束提示词；需质量 A/B。
3. **答案展示机制待真跑验证**：212 个产物均早于 Round 9 的 `answer_display` 变更
   ⇒ 实跑中暂未出现展示分离；离线判据（19+7 项）已覆盖逻辑。

### 18.3 方法学价值

该审计给出**零 API 成本的回归检查面**：每次机制改动后，用已存 packs 重算
gaps/status/显示字段即可发现「机制命中率、真实瓶颈、回归」；后续可作为
`scripts/lead_offline_pack_audit.py` 纳入例行检查（docs 账本 + git 留档）。


## 19. 事实门两处真实跑次驱动的修复：uncovered 片段覆盖 + 整体量语义（Round 12）

### 19.1 真实反例

黄河长度真跑（web on，官方源 hnb.yrcc.gov.cn 已捕获）终态 `aq=needs_evidence`：
- `gaps=['uncovered:黄河的长度']`：题面整短语「黄河的长度」不在原文（原文是
  「黄河…全长约5464公里」）⇒ 硬 gap 把 answered 事实卡挡在 verified 外；
- 答案取了官方 E3「河段长3472千米」（上游分段值），而多源非官方证据给出
  「黄河全长约5464公里」⇒ 官方 +0.15 压过了目标量语义。

### 19.2 修复 A：词项片段级覆盖（含近义）

`detect_gaps` 的 `uncovered:<term>` 判定改为 `_term_covered`：
- 整短语命中 ⇒ 覆盖；
- 否则按语气词（的/是/多少/什么/几/了/吗/？/，/空格）切片段，要求**全部 ≥2 字
  片段**命中；片段允许近义覆盖（长度←全长/总长，高度←高程/海拔，千米←公里/km，
  大小←规模…）；
- 真缺目标项（如问「面积」而证据无面积/占地）仍报 uncovered（负对照保留）。

### 19.3 修复 B：整体量目标语义加权

`answer_from_evidence` 评分新增 `_overall_quantity_bonus`：题面问整体量
（长度/多长/全长/高度/海拔/宽度/深度/距离/速度/面积/重量…）时，
含整体量标记（全长/总长/总长度/最高/海拔/最大/总计/面积…）的证据 **+1.0**。
权重取 1.0 是为了压过「官方 0.15 + 相关度 0.8」（黄河真实分数 0.95）。

### 19.4 判据与验证

`tests_evidence_coverage.py` **11 项**（片段覆盖 7 + 整体量语义 5）：
- 片段覆盖：整短语/片段全命中/缺片段/近义覆盖/真缺目标项负对照/unit 近义；
- 整体量：问长+全长加分、非整体量题不加分、「河段长」不加分、
  官方分段值 vs 非官方全长值 → 取 5464（反超官方加权）。
回归：tests_evidence 21、tests_fact_flow 15、tests_fact_official_precedence 19 全 PASS。

> 真实复验说明：计划中「fact-gapfix-huanghe」复验跑次因 harness 重启丢失（无
> ab_results 记录），机制当前仅由 12 项离线判据 + 历史真实 pack 反例验证；
> 复验需在预算允许时补跑一次（约 ¥2.5）。

### 19.5 同期发现（下一轮）

HTTP 404 事实跑（17:01）终态 `needs_evidence` 的 gaps 是 `no_official_source`：
检索池里出现过 MDN/RFC/IANA，但进入 evidence 层的 8 条（docs.oracle.com 等）
不含官方源；且答案字段混入工具调用文本（「工具 search_web(...) 返回：…」）。
⇒ 下一轮：核对检索记录（used_as=record 的官方页）是否该纳入证据层 +
事实答案过滤工具调用噪声。


### 19.6 离线重放验证 + 机制 C（数值句优先）

用黄河真实 pack 离线重放（pools→from_search_hits→dedup→budget→build_fact_card，
零 API）对比修复前后：
- 修复前：status=answered、gaps=['uncovered:黄河的长度']、official=['E3']、
  answer=「河段长3472千米」；
- 修复后：status=answered、**gaps=[]**、official=['E3'] —— uncovered 误报已消除、
  官方源保留 ✓；
- 但 answer 仍取到「黄河，我国第二大河……哺育了灿烂的中华文明」这类**无数值首句**
  ⇒ 新增机制 C：_short_answer 面对数值型问句时**优先返回含数值+单位的句子**
  （须早于「日期句优先」分支，否则带日期的无数值首句会抢先返回）。
- 复跑重放：answer 仍为首句（该 pack 的 evidence 片段中数值句不在同一切分段内），
  说明「答案句选择」还依赖证据片段质量/切分，下一轮需要针对数值题做
  **claim 级抽取**（从数值主张上下文出答案，而非从长 snippet 首句）。
- 机制 C 回归：tests_evidence 21、tests_evidence_coverage 12、tests_fact_flow 15、
  tests_fact_official_precedence 19、全量 V2 47/47（701 checks）、fast_gate 12/12 全绿。


## 20. 离线事实重放工具 + claim 级答案抽取尝试（Round 14，零 API；负结果留档）

### 20.1 工具：`scripts/lead_offline_fact_replay.py`

用已存 pack 的检索池**离线重算 FactCard**（与引擎 finalize 同口径：
pools.web_results → from_search_hits → dedup → budget → build_fact_card），
对比存储卡与新卡（status/gaps/official/answer/display），统计数值答案覆盖率。
输出 `docs/fact_replay_20261025.json`。零 API，可作为机制改动的**回归检查面**。

当天（2026-10-25）14 个 fact 跑次重放：answered 11、gaps 清除 1；
数值答案（含「值+单位」）before 3 / after 1。差异来自：
- 旧存储答案含日期前缀（`[2024-07-14] …14` 之类），"before 数值" 含噪声；
- 部分跑次（珠峰）重放证据集与当轮不同（引擎当轮还用了 fetch/records 层），
  重放卡 status 与存储卡不一致 ⇒ 重放只对「当前引擎同口径」跑次可信。

### 20.2 尝试：claim 级数值答案抽取（**回退，未采纳**）

设计：数值题从 `extract_numeric_claims` 抽「数值+单位」主张，按「单位量纲类命中
（千米/公里同属长度）> 整体量标记（全长/总长/海拔）> raw 长度」排序取答案。

离线重放暴露两个无法接受的问题：
1. **日期噪声**：`[2024-07-14]` 的 14 被当成答案（光速题重放 answer="14"）；
2. **回归**：数值答案覆盖率 after 反而下降（7/3 波动），且单位字段在
   `extract_numeric_claims` 里不稳定（raw 自带单位、unit 为空等边界多）。

处置：**按「只变好不变坏」原则回退**（`git checkout -- evidence.py`），保留
Round 13 的「句子级数值优先」修复；claim 级抽取仅在加日期剥离+量纲类匹配+
多轮真实跑验证后才考虑重新引入。工具与负结果留档，避免重复踩坑。


## 21. 数值答案句「口语量词」修复 + 展示弱量词过滤（Round 15，零 API）

### 21.1 根因（离线重放定位）

黄河 pack 离线重放后发现 answer 仍是「黄河，我国第二大河……哺育了灿烂的中华文明」
（无数值）。逐层调试定位：
- `_short_answer` 的数值句正则只认「数字+单位」紧邻，**不认「5400多公里 / 约5464
  公里 / 5400余公里」**这类中文口语量词 ⇒ 数值句匹配失败，回退整段文本；
- `_compact_numeric_answer`（展示层）把「9个省」的 `9个` 当成「值+单位」⇒ display
  可能给出无意义数字。

### 21.2 修复

1. `_short_answer` 数值句正则允许 `多|余|约|近` 等量词插入（`\d+多?/约?/余?\s*单位`）；
2. `_compact_numeric_answer` 增加**弱量词过滤**（个/条/处/项/次/种/位/名/份/家/所/岁
   在非对应量题中不作答案），并要求强单位（千米/公里/米/%/℃/吨/kg/元/万）才可作为
   紧凑展示；无合格 claim 时回退清洗后的原文。

### 21.3 离线重放验证（零 API，黄河/长江真实 pack）

| 题 | 修复前 answer | 修复后 answer | display |
|---|---|---|---|
| 黄河长度 | 「河段长3472千米」（分段值） | 「黄河流经我国9个省（区），**全长5400多公里**」 | 回退全文（含数值） |
| 长江长度 | 整段网页文本（含 6280千米） | 保持含 6280千米 | **6280千米** |

判据：tests_evidence_coverage 增至 **16 项**（新增口语量词数值句 3 项 + 展示弱量词
过滤 2 项）；回归 tests_evidence 21、tests_fact_flow 15、tests_fact_official_precedence
19 全 PASS；全量 V2 47/47、fast_gate 12/12。

### 21.4 说明

本轮为纯离线修复（¥0 API）；真实验证需一次 web on 跑次（约 ¥2.5），余额约 ¥3.2
仅够 1 次 ⇒ 留待预算恢复后补验，当前以「真实 pack 离线重放」作为证据。


## 22. 状态码官方站内检索修复 + 两题真实验证（Round 16）

### 22.1 根因与修复

HTTP 404 事实题连续两次 `no_official_source`（检索池 34 条、官方 URL 0 条）。
根因：`extract_queries` 的官方站内检索条件用 `\b([1-5]\d\d)\b` 匹配状态码，
但**中文是 word 字符**——「HTTP 404状态码」里 404 后紧跟「状」，`\b` 不成立
⇒ `site:developer.mozilla.org HTTP 404` / `site:rfc-editor.org RFC 9110 404`
官方检索从未注入。修复：改用数字前后断言 `(?<!\d)([1-5]\d\d)(?!\d)`。
判据 `tests_fact_queries.py` 7 项（404/500 注入、HTTP 协议不误注入、1404 年份不误注入、
确定性、limit 约束）。

### 22.2 真实验证（同题 web on，脚本化复跑）

| 题 | 修复前 | 修复后 |
|---|---|---|
| 黄河长度（Round 12 修复复验） | 0.4325 / needs_evidence / ready=False / gaps=['uncovered:黄河的长度'] | **0.9633 / verified / ready=True**；gaps=[]；official E3；answer=「全长约5464千米」；**display=5464千米** |
| HTTP 404 状态码 | 0.4033 / needs_evidence / ready=False / official=0 | **aq=verified**；official **E1,E2,E3**（MDN 等官方源已捕获）；gaps=[]；answer=「404 Not Found…服务器无法找到所请求的资源」；ready=False 仍为**过程门**（standard_all=False，3/4 层达标） |

### 22.3 判读

- 「uncovered 片段覆盖 + 整体量语义 + 口语量词数值句 + 展示分离」四层修复在**真实跑次**
  全部生效：黄河从 needs_evidence → **verified/ready/0.9633**，display 直接给「5464千米」；
- 状态码官方检索修复让 404 题从 `no_official_source` → **官方源 3 条 + verified**；
- 两题质量门（quality 0.43 / 0.96）差异主要来自**过程门**（层产物标准/元层收束），
  与事实门解耦；下一步聚焦过程门（HTTP404 为 3/4 层达标，定位失败层）。
- 门禁：V2 **48/48（713 checks）**、fast_gate 12/12。


## 23. 过程门修复：通用词不冒充证据命中（Round 17）

### 23.1 根因

HTTP 404 题（Round 16）事实门已 verified，但 ready=False：`process_ledger` 显示
**layer 1 standard False**（decidability_audit status=mixed、bad=1）。
审计明细行：子问题 4「对确实存在的资源故意回 404 时，Not Found 是语义漂移还是
语用借用」被判 `undecidable_but_evidence_exists` ⇒ bad。
但证据命中来源只是通用词 **not / found**（MDN 文本必然出现），并非该子问题的
命题落点 ⇒ **审计误判**，被修复成「将不可判定降级为 partial 并记 bad」，进而层不达标。

### 23.2 修复

`decidability_audit._terms()` 增加**通用英文/技术高频词过滤**（not/found/http/
status/code/response/server/page/url/the/and/…共 40 余词）：这些词在证据里几乎
必然出现，不能当「命题落点」；真术语（GDP/RFC/MDN…）仍照常命中。
判据 `tests_decidability_audit.py` 增至 **17 项**（新增：通用词不误判、真术语
（RFC）仍判 overclaim、混合问题真术语仍判 overclaim）。

### 23.3 真实验证（HTTP 404，web on 三次跑次轨迹）

| 阶段 | quality | answer_quality | ready | 说明 |
|---|---|---|---|---|
| 修复前（Round 15 前） | 0.4033 | needs_evidence | False | 检索池无官方源 |
| Round 16（官方站内检索修复） | 0.4269 | **verified** | False | 官方源 E1,E2,E3 已捕获；卡在过程门 |
| **Round 17（通用词审计修复）** | **0.9062** | **verified** | **True** | standard_all=True，四层全达标 |

结论：三个独立机制（状态码官方检索、事实门官方源优先/去重、审计通用词过滤）
串起来把该题从「未证不可用」推到 **0.9062/verified/ready**；质量跃升主要来自
过程门放行（四层标准全达标）与事实答案确定性。

### 23.4 门禁

全量 V2 **48/48（716 checks）**、fast_gate 12/12。
