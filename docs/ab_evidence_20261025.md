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
