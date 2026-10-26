# 已知边界清单（2026-10-26，Round 87）

> 原则：**只变好不变坏**；门禁不放宽；失败记录不删除；边界如实冻结。

## 1. 已闭环

| 边界 | 闭环方式 | 证据 |
|---|---|---|
| 成年年龄（8 vs 18 周岁） | 成年 sanity：<18 改取成年人条款，无则拒答 | 0.9575/verified，display=十八周岁（Round 85） |
| 选择题官方源缺失 | 选项题（A./B./C./D.≥2）豁免 no_official_source | **0.9387/verified/ready**（choice auto3，Round 86–87） |
| 全长/分段口径（港珠澳 42 vs 55） | _whole/_tot/_mag 偏好 + display 取总长 | 0.92/verified，display=55公里（Round 48） |
| 双值/范围/列举/地点/命名展示 | display 收窄十法 | A54/A57/A60/A61 等判据 |
| 年份错配/比较年份/历史旧规 | 硬拒答 + 年度口径 + 现行性守卫 | 判据 A24–A43 |

## 2. 阻塞（需改引擎；当前工作树被并发会话占用，不强行编辑）

| 边界 | 具体阻塞 | 记录 |
|---|---|---|
| **dual_judge local 档** | 引擎 `--dual-judge-mode` choices=["llm","cache","auto"]，无 local；引擎文件 git status: M（并发会话） | Round 50/86/87；App 层已防护回退 llm；cache 档已真跑验证（0.9464/verified） |

## 3. 待优化（门禁内）

| 边界 | 现状 | 下一步 |
|---|---|---|
| `probe_no_target_covered` | 「海水为什么咸」auto 0.2435/unverified：答案实质但未覆盖探针目标（引擎侧 flags） | 需引擎探针目标生成/覆盖判定（同被占用）；先冻结 |
| 检索源依赖 | 缺目标年份/现行法/官方页时拒答（宁缺毋假） | 继续 query 扩展与证据优先级（离线可做） |
| 旧 pack 严格拒答 | 124 packs 中 34 条 answered→unknown（旧低质答案被严格门拒） | 有意收紧；如需保留需补官方源 |
| local self_check opt-in | token −12~20%、墙钟 +31~57%、质量噪声级 | 维持 opt-in；v8b 为默认 |

## 4. 并发与成本口径（已治理）

- ab_bench：`cost_window_cny / cost_attribution / cost_note`；`cost_cny` 仅兼容保留；
- `dgtf_memory/real_run.lock`（pid/tag/start/est/ttl=1800s）：活跃锁默认拒绝真跑
  （exit 3），`--force-concurrent` 显式覆盖；
- 单日真跑 ≤3（本日已用尽，暂停）；余额保留 ≥50 CNY。

## 5. Round 90 新增闭环/量化

| 项 | 内容 |
|---|---|
| 地点/排序问句分类 | 已闭环：哪个/哪座/哪里/位于/设在/最大/最高/最长/最小 → fact；App 事实档强制 web on；App 地点 e2e 0.9288/verified/display=纽约市 |
| probe_no_target_covered | 已量化：267 packs 30.3%；verified 中 30.7%（答案正确也扣分）；引擎侧待优化（冻结） |
| App e2e 矩阵 | 9 行（新增 UNHQ 地点行） |

## 6. Round 91 新增闭环

| 项 | 内容 |
|---|---|
| 选项题 App 链路 | 已闭环：选项标记→choice + App 强制 web + uncovered 豁免；App e2e 0.9516/verified |
| 多值/单位展示 | 已闭环：出生人口 App e2e 0.9842/verified，display=954万人 |
| App e2e 矩阵 | 11 行；fast 覆盖 reasoning/fact/choice |

## 7. Round 92 新增闭环

| 项 | 内容 |
|---|---|
| 万亿元单位 | 已闭环：43.85万亿元 fast+web 0.97/verified，display=43.85万亿元 |
| 年限展示 | 已闭环（引擎层）：租赁 20年 display（A68）；App 同题缓存命中，未复跑 |
| 进出口整体量 | 已闭环：「进出口」不再被 pen 当子项（A70） |
| App e2e 端口 | 已支持自动空闲端口（并发会话不冲突） |

## 8. Round 93 新增

| 项 | 内容 |
|---|---|
| 命名题数值劫持 | 已闭环：命名问句不走数值答案（A71/A72）；最高高原 0.9776/verified |
| App 精确缓存 | 同题复跑会命中缓存（tok=0）⇒ App e2e 需新题；缓存不自动失效（已知限制） |
| 本地 v8b self_check | A/B：出生人口 0.99/＋2.27pp/−5.3% tokens；光速 tokens +5% ⇒ 默认 llm、local opt-in；v9 训练中 |
| App e2e 端口 | 自动空闲端口（8800+），并发会话安全 |

## 9. Round 95 更新

| 项 | 内容 |
|---|---|
| dual_judge local | **已实现（worktree 分支，可控）**：失败回退 llm 真跑 verified；超时调参中；主引擎待合并 |
| v9 训练 | 暂停（为双判本地验证让位 GPU）；之后重启 |

## 10. Round 99–100 维护态

| 项 | 内容 |
|---|---|
| 本地服务 | 训练期间暂停（8772/8771），训练后重启；App 自检 444/0（fail-open 已验证） |
| v9 训练 | ep1 step 20/460，ETA ~5.8h；完成即 held-out 对比 |
| 真实跑次 | 暂停（余额 50.76 近保留线） |
| dual_judge local | 补丁就绪（docs/patches），等待主引擎干净合并 |

## 11. Round 110–111 维护态

| 项 | 内容 |
|---|---|
| 真实跑次 | **停止**（余额 ¥9.48 < 10；保留硬底线） |
| v9 训练 | 运行中（step ~120/460，外部并发使 ETA 拉长；GPU 满载） |
| dual_judge local | 补丁就绪（0001–0003，T1–T8 8/8），等主引擎合并窗口 |
| 验收 | 无服务 **8/8 PASS**；探针复审 29.3% flagged |

## 12. Round 113 更新

| 项 | 内容 |
|---|---|
| v9 训练 | 外部 GPU 长时竞争 → **中止归档**（partial adapter 保留）；GPU 空闲可重启 |
| 最终综合报告 | docs/最终综合报告-20261026.md（Round 1–113） |

## 13. Round 114 更新

| 项 | 内容 |
|---|---|
| 本地服务 | 已恢复（8771/8772，v8b ready）；一键验收 --with-service **9/9 PASS** |
| v9 | 归档不变：GPU 6GB 卡无法同时容纳训练(5.8GB)+服务(2GB)，需专用窗口 |

## 14. Round 116 更新

| 项 | 内容 |
|---|---|
| v9 归档原因（更正） | 命令漏传 --model → 用了默认 1.5B base；adapter 不可用于 0.5B 服务 |
| 防错训守卫 | out 名含 05b 但模型非 0.5B ⇒ 拒绝训练（已实测 reject/allow） |
| 正确重训命令 | 见 `llm_sft/adapter_dgtf_selfcheck_05b_v9_aborted_ep1step120/ABORTED.md` |

## 15. Round 117 更新

| 项 | 内容 |
|---|---|
| v9b 重训 | 条件：专用 GPU 窗口（0.5B 训练峰值 ~4.9GB + 本地服务 ~1.9GB > 6GB 卡）；当前 8771/8772 服务由并发会话持有，不宜强停 → 等待窗口 |
| 防错训守卫 | 已验证（reject/allow 两路径）；正确命令见 ABORTED.md |
| 本地模型结论 | 当前 **v8b 为可验证最优**（质量=v6、p50/p95 更快；self_check local opt-in 收益 0.99/+2.27pp 于出生人口题） |

## 16. Round 121 阻塞快照（最终）

| 阻塞项 | 具体条件 | 已持续 |
|---|---|---|
| 真实跑次预算 | 余额 ¥6.26 < 真跑最低门槛（10；硬底线 4） | Round 110 起 |
| dual_judge local 合并 | 主引擎工作树 M（并发会话未提交）；合并器与补丁已全量校验（T1–T8） | Round 49 起 |
| v9b 重训 | GPU 6GB 卡：0.5B 训练 ~4.9GB + 本地服务 ~1.9GB（并发会话持有）超容 | Round 113 起 |
| 剩余可做 | 仅零成本文档/验收维护；机制层已到可验证最优（矩阵 57、V2 835 checks、验收 10/10） | — |
