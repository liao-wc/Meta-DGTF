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
