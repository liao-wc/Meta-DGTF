# W 系列任务书（v1.23.0）· 已按 v1.22.2 阶段 0 核验结果**回写修正**

> 原始方案来自外部共享链接（《核心引擎 · 外部联网功能设计与实施方案（v1.23.0 · W 系列）》）。
> 本文件是**核验后回写的执行版**：原方案的 3 处卡点已在此修正，标 `[修正 B1/B2/B3]`。
> 执行前提：v1.22.2 已定稿（`元DGTF-V1.22.2.py`）。
> 核验记录见 `docs/W系列启动检查清单-v1222.md` §B。

---

## 零、卡点修正（本文件相对原方案的唯一差别）

| # | 原方案 | 修正后 | 为什么 |
|---|---|---|---|
| **B1** | 「`_citation_table` 含 W#」排在 **W4**；但 **W2** 的验收判据是 `apply_decidability_change(evidence=["W1"], to="partial") → applied` | **`[修正 B1]` 把「W# 进 `_citation_table`（带授权门）」提到 W2 前置**；W4 只保留「三票正交化」。判据与交付物同阶段 | 实测 `_resolve_citation`（`元DGTF-V1.22.2.py` 6373）只认 `_citation_table`（6322）里的编号。W# 不进表 ⇒ W2 的判据恒 `rejected` ⇒ **判据不可达** |
| **B2** | `logger_web = logging.getLogger("dgtf.websearch")`；声称「所有 web 日志**只**进这个 logger」 | **`[修正 B2]` 必须加 `logger_web.propagate = False`**，并加冒烟断言「主 logger `dgtf` 的输出里 grep 不到 `[W-`」 | 主 logger 是 `logging.getLogger("dgtf")`（4544）；`dgtf.websearch` 是它的**子 logger**，`propagate` 默认 True ⇒ 日志会同时进父 logger，**违反方案自己的红线** |
| **B3** | §6.3 声明「连续 3 次失败 → `disabled = True`」 | **`[修正 B3]` `note_failure()` 里显式 `self.disabled = True` 并留痕 `[W-DISABLED]`**；`allow()` 的 reason 与 `disabled` 状态必须一致 | 原代码片段里**没有任何一处**给 `self.disabled` 赋值（`allow()` 只返回 False）⇒ 产物里读不到「本跑已降级」这个**状态** |

**另有一处自纠**：v1.22.2 的清单 §C 写「四条宪法级判据 W1 需补」—— 这是**判据与阶段不匹配**。
W1 不接入任何环节，那时写出的四条判据只能靠 `enabled=False` 通过 ⇒ **恒真的装饰判据**。
修正：**W1 只测「默认关 → 零调用」这条骨架判据；四条宪法级判据各自在对应接入 Phase 补，
且必须配变异体**（把 W 调用塞进 `settle_deferrals` / 塞进候选 / 塞进 `_ing` prompt → 判据必须判红）。

---

## 一、设计原则（红线，违反即方案作废）

1. **按环节授权**，不是全局 ON/OFF。
2. **检索结果不是内容，是参照**：W# 一律不进 `view.candidates` / 不进 `_ing` / 不进对撞第三者。
3. **配额三层**：每环节每圈 / 每环节全程 / 每跑总。
4. **默认全关**：`web_search.enabled = False` ⇒ 零调用。
5. **失败必须留痕且有独立通道**：`dgtf.websearch`，`propagate=False`。
6. **与四条宪法级特性兼容**（见 §六）。

---

## 二、架构

```
WebSearchGate（授权 + 配额 + 降级）
   ↓
WebSearchClient（HTTP + 重试 + 退避 + 失败分类）
   ↓
WebSearchCache（sha256 + TTL，cache/websearch/）
   ↓
EvidencePool / ArbitrationPool / CleanCheckPool（三池分离，W1/W2/… 统一编号）
   ↓
CitationResolver（_citation_table 收 W#，只允许 →partial）
```

**与 `AnchorRetriever` 的关系**：不合并。锚点是**事先落盘**的冻结事实
（`AnchorRetriever`，`snapshot` 零调用 / `tavily` + `cache/anchors/`）；
联网是**运行时**发起的活检索（`WebSearchClient`，`cache/websearch/`）。
两套编号 `X#` / `W#` **不互换**。

---

## 三、配置（`DEFAULT_CONFIG["web_search"]`，加性）

```python
"web_search": {
    "enabled": False,                      # 全局总闸（默认关）
    "backend": "tavily",
    "api_key_env": "TAVILY_API_KEY",
    "timeout_seconds": 30,
    "max_retries": 2,
    "backoff_seconds": 1.8,
    "cache_ttl_hours": 24,
    "quota": {"per_stage_round": 2, "per_stage_total": 8, "per_run_total": 30},
    "stages": {
        "practice_term_calibration": False,   # 修行层默认关
        "research_decompose": True,
        "research_evidence": True,
        "research_precedent": True,
        "duel_arbitration": True,
        "meta_clean_check": True,
        "stop_criteria": False,
    },
    "as_evidence": "crosscheck",
    "tier_floor": 2,
    "auto_disable_after_failures": 3,
},
```

---

## 四、Phase W1 · 骨架 + 客户端 + 缓存（**本阶段只建基础设施，不接入任何环节**）

### 交付

| # | 组件 | 关键点 |
|---|---|---|
| W1.1 | `DEFAULT_CONFIG["web_search"]` | 加性；不动 `external_anchor` 任何键 |
| W1.2 | `logger_web = logging.getLogger("dgtf.websearch")` | **`propagate = False`** `[修正 B2]` |
| W1.3 | `WebSearchCache` | `cache/websearch/<sha256[:24]>.json` + TTL；**不复用** `cache/anchors/` |
| W1.4 | `WebSearchClient` | `timeout` / 重试 / 退避；**失败分类五档**（timeout / rate_limit / empty / dirty / api_error），每档返回 `(results, fail_kind)`，不抛裸异常 |
| W1.5 | `WebSearchGate` | `allow(stage, round_no) -> (bool, reason)`；三层配额 + 授权 + 连续失败降级；**`note_failure()` 显式置 `disabled`** `[修正 B3]` |

### 验收判据

- [ ] `DEFAULT_CONFIG["web_search"]["enabled"] is False`，且 `external_anchor` 键集**逐字未变**
- [ ] 三个 quota 键都在
- [ ] `allow()` 三个方向（超配额 / 未授权 / 连续失败）都判 `False`
- [ ] 连续第 3 次失败后 `gate.disabled is True`（`[修正 B3]` 的正面证据）
- [ ] `logger_web.propagate is False`，且**主 logger 的 handler 收不到** `[W-` 开头的记录（`[修正 B2]` 的正面证据）
- [ ] 缓存：同 query 第二次调用**不增** `client.calls`
- [ ] **负对照**：`enabled=False` 时 `allow()` 恒 `False`、`client.calls == 0`
- [ ] **负对照**：`cache/websearch/` 与 `cache/anchors/` 是两个目录（`AnchorRetriever._cache_path` 未动）
- [ ] 探针 `_probe_v123_w1.py`：对 v1.22.2 全 `AttributeError`/`None`，对本版全有值

### 不做

任何环节接入（`research_decompose` 等全部**只配不接**）。本 Phase 结束即成 W1 门。

---

## 五、Phase W2 ~ W5（本轮不执行，列此以固定依赖顺序）

| Phase | 交付 | 相对原方案的修正 |
|---|---|---|
| W2 | `research_decompose` / `research_evidence` / `research_precedent` 接入；`EvidencePool` + `W#` 编号；**`_citation_table` 收 W#（带授权门）**；`apply_decidability_change` 加「W# 不许支撑 →undecidable」特例 | **`[修正 B1]`**：`_citation_table` 一项移到此阶段（原排在 W4） |
| W3 | `duel_arbitration` / `meta_clean_check`；`ArbitrationPool` / `CleanCheckPool` | 无 |
| W4 | 三票正交化（一票改为「外部证据裁判」） | 去掉 `_citation_table` 一项（已在 W2） |
| W5 | 20 题全量回归 + `v123_报告.md` | 无 |

**门控纪律**：每一 Phase 验收未通过**不许进入下一 Phase**。

---

## 六、四条宪法级特性（各自在对应 Phase 补**带变异体**的判据）

| 特性 | 保护 | 判据落在哪一 Phase | 变异体（判据必须判红） |
|---|---|---|---|
| 输入是形状不是数据 | 联网结果不进 `view.candidates` | W2 | mock 返回 10 条 W# → 候选数若变化 ⇒ 红 |
| 悬置不打分 | W# 不许支撑 `→undecidable` | W2 | `apply_decidability_change(evidence=["W1"], to="undecidable")` ⇒ 必须 `rejected` |
| 未对齐合法 | W# 不进 `_ing` prompt | W3 | 把 W# 注入 `_ing` prompt ⇒ 输出若变 ⇒ 红 |
| 停止与清算分开 | `settle_deferrals` 里 web 调用 = 0 | W3 | 在 `settle_deferrals` 里插一次 web 调用 ⇒ 计数若 > 0 ⇒ 红 |

---

## 七、明确不做

1. 不做全局 ON（出厂 `enabled=False`）。
2. 不做修行层默认开。
3. 不做 W# 支撑 `→undecidable`。
4. 不做检索结果直接当候选。
5. 不做清算阶段发起新检索。
6. 不合并 `AnchorRetriever` 与 `WebSearchClient`。
7. 不做联网结果自动 tier 判定（首次出现新域名进 `pool.meta` 待审）。
8. 不做联网改阈值（`_UNTRACED_OVERLAP` / `_overlap_coef` 一律不动）。
