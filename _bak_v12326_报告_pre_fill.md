# v1.23.26 报告 · 五机制算法重构（第一期：换尺子）

> 主文件 `元DGTF-V1.23.26.py` — __LINES__ 行 / __BYTES__ bytes / 纯 CRLF
> 基线 `元DGTF-V1.23.25.py`（18593 行 / 896053 bytes）
> 设计依据 [`_设计_五机制算法重构_v12326.md`](./_设计_五机制算法重构_v12326.md)
> 诊断依据 [`_分析_锚点重述与探针设计_v12325.md`](./_分析_锚点重述与探针设计_v12325.md)

---

## 0. 一句话

> 上一轮诊断的根因是**尺子失真** + **模型自报量空转**。本版只修**尺子**那一半，
> **不动任何 LLM 接口** ⇒ 喂进模型的内容一字未增，可零成本独立验证。

---

## 1. 本版改了什么（四处）

| # | 改动 | 触及函数/常量 | 是否动 LLM 接口 |
|---|---|---|---|
| 1 | 新增 `_sim3` 三级尺子（对称 Jaccard + BM25 + 结构编号） | `_bm25_corpus` / `_bm25_best` / `_jaccard` / `_sim3` / `_sim3_pair`（新） | ❌ 否 |
| 2 | 复述检测切到 `_sim3` | `_sent_is_rephrase` / `_detect_ing_rephrase` / `_REPHRASE_SIM3`（新） | ❌ 否 |
| 3 | 池内去重阈值可配 | `Pool.merge` 签名 + 体内 4 处；`_DEDUP_SIM` / `_DEDUP_SUSP_SIM`（新）；`DEFAULT_CONFIG.sim`（新） | ❌ 否 |
| 4 | covers 数字编号分支补语义校验 | `_quality_check` 内嵌判据；`_COV_OVERLAP_MIN`（新） | ❌ 否 |

**不在本版**（需真跑验证，见设计报告 §4.2）：`expected_gain` 改引擎算 EIG、
子模批选、`link` 反查、空探针判据双向化、`AspectUnit` 结构化、`BeliefItem` 四态机。

---

## 2. 基线量化（改前，`_probe_v12326_sim.py` → `_baseline_v12326.json`）

### 2.1 根因：`_overlap_coef` 短句高估

| A | B | `_overlap_coef` | `_similar(0.75)` | `_sim_ratio` |
|---|---|---|---|---|
| 人工智能 模型 部署 | 人工智能 模型 训练 | **0.667** | **0** | 0.667 |
| 神经网络 优化 | 神经网络 训练 | **0.500** | **0** | 0.000 |
| 模型 部署 | 模型 训练 | **0.500** | **0** | 0.000 |
| 长句（8 词） | 长句（5 词，被包含） | **1.000** | 0 | 0.625 |
| 无空格长串 | 无空格长串（被包含） | **1.000** | 0 | 0.700 |

**两把尺子在同一对上结论完全相反**（`_overlap_coef` 0.5 vs `_similar` 0）。
根因链：`_kw` 内 `most_common(top_n*2)` ⇒ 实取 16 词；短句取不满 ⇒ `len(ka)=3`；
分母 `min` 被最短侧钉死 ⇒ 共享 1 个名词即 0.33，共享 2 个即 0.67。

而 `_overlap_coef` 被 **19 处**调用，跨四种语义场景 ⇒ **一把尺子量五件事**。

### 2.2 其余基线

| 项 | 实测 |
|---|---|
| `_kw("长句", 8)` 实取词数 | **14** ⇒ 确认 `top_n*2` 语义 |
| `Pool.merge` 阈值字面量 | **4 处**（`0.9` ×3 + `0.85` ×1），**不读配置** |
| 探针过滤门 `gain < min_gain` | **4 处**（L6567/6767/6941/7127，四层各一） |
| `select_probe_focus` 全不相干 4 候选(n=3) | **只选出 1 个** ⇒ ★ 修正设计报告原判断（非「必然塞满」） |
| `probe_no_target_covered` 数字分支 | **无语义比较** ⇒ 乱指 T1 不报红 |
| 非数字分支 / 无 covers fallback | 均有 `_similar` 校验 |
| `_classify_unsaid({"covers":["T1"]})` | `real`（只看有无，不看对错） |

### 2.3 ★ 基线阶段修正了设计报告的两处判断

| 项 | 设计报告原判断 | 实测 | 处置 |
|---|---|---|---|
| `select_probe_focus` 批选 | 「fallback 必然塞满 n」 | 全不相干 ⇒ **只选出 1** | **不改**（子模批选降级为 v1.23.27 的可选项） |
| `covers` 校验 | 「只查编号，不校验语义」 | 数字分支确实无；**非数字 + fallback 都有** | 收窄为**只修数字分支** |
| 探针过滤门 | 1 处 | **4 处** | 改动面 ×4（本版未改，留下版） |

> 教训：**设计阶段的推断必须用基线探针复核再用**。两处推断被实测推翻，
> 若直接照设计动手会白改（`select_probe_focus` 的「塞满」并不存在）。

---

## 3. 改动细节

### 3.1 `_sim3` 三级尺子

```python
_sim3(a, b, corpus=None, top_n=_KW_TOP_N) -> float
  ├─ L4 结构层：a,b 都是 "T3" 式编号且相等 → 1.0（符号必然命中）
  ├─ L1 字面层：_jaccard(a,b) = |A∩B| / |A∪B|    ← 分母是**并集**（非 min）
  └─ L2 稀疏层：BM25（需 corpus 且 N >= 4）
       _bm25_best 归一化：raw / (raw + _BM25_K1)   ∈ [0,1)
       BM25 原式：Σ idf(t)·(tf·(k1+1)) / (tf + k1·(1-b+b·|d|/avgdl))
       idf(t) = ln(1 + (N - df(t) + 0.5)/(df(t) + 0.5))
       合并：0.4·jac + 0.6·bm
```

**为什么选 BM25 而不是 embedding**：
① 零新依赖（纯 Python），可进主路径；
② 语料 = 本圈池内条目，**无需外部服务/训练**；
③ 修的是「平权词袋」→「TF-IDF 加权」，这是 `_overlap_coef` 最缺的一半；
④ 语义那一半（同义词）留给 v1.23.27 的可选稠密通道（降级矩阵见设计报告 §6.2）。

**降级设计（关键）**：语料 < 4 篇 ⇒ BM25 通道**自动关闭**，退回纯 Jaccard。
降级路径与主路径是**同一个函数**（只是 `corpus=None`），因此：
- 不同圈（语料大小不同）的读数**仍可比**；
- 冒烟可对同一条数据构造「有/无语料」两臂对照。

### 3.2 复述检测切换

```python
_sent_is_rephrase(s, u, corpus=None):
    if _similar(s, u, _REPHRASE_SIM):            return True   # 原有
    if _sim3(s, u, corpus=corpus) >= _REPHRASE_SIM3:  return True  # ★ 新主判据
    return _overlap_coef(s, u, _KW_TOP_N) >= _REPHRASE_OVERLAP     # 包住形状保底
```

★ `_overlap_coef` 那一条**保留**：它管「s 的关键词几乎全在 u 里」这个**特定几何**
（短句整段落在长句里），是 sim3 抓不到的一类。两条判据**各管各的形状**，
不是「同一件事两条实现」。

`_detect_ing_rephrase` 内部**只编一次语料**再传给每句 —— 否则 IDF 随调用次序变，
同一对句子在同一圈内会得到不同的分。

### 3.3 池内阈值可配

```python
_DEDUP_SIM = 0.90        # = 原 Pool.merge 字面量
_DEDUP_SUSP_SIM = 0.85   # = 原 Pool.merge 字面量

Pool.merge(..., thr=None, susp_thr=None):
    _t  = _DEDUP_SIM if thr is None else float(thr)
    _st = _DEDUP_SUSP_SIM if susp_thr is None else float(susp_thr)
```

调用点从 `self.config["sim"]` 读。**不配置 ⇒ 与 v1.23.25 行为逐位相同。**

### 3.4 covers 数字分支

```python
# 旧：编号在范围内即通过
if 0 <= idx < len(untouched_items):
    has_touch = True; break

# 新：编号合法只是**必要条件**，还要语义对得上
if 0 <= idx < len(untouched_items):
    if (_similar(_pq, untouched_items[idx], _QC_DUP_SIM)
            or _overlap_coef(_pq, untouched_items[idx]) >= _COV_OVERLAP_MIN):
        has_touch = True; break
```

比较对象是**探针的 question vs 该项**（不是两个 untouched 项互比 ——
那是清单内部一致性，不是「覆盖」）。

---

## 4. 验收

### 4.1 判据（`smoke_test.py` 新增 `check_v12326_sim3`）

| 组 | 判据 | 负对照 |
|---|---|---|
| A | `sim3` 显著低于 `_overlap_coef`（短句高估修好）；`_overlap_coef` 基线仍是 0.5（否则夹具失去意义）；**对称性**逐对验证 | 若 `_overlap_coef` 不再虚高 ⇒ 报「夹具失去意义」 |
| B | 语料 ≥ 4 时 BM25 启用；**不相干对不因 BM25 被抬高**；相关对不降分；语料不足**自动降级**（返回 0.0） | 不相干对被抬高 > 0.2 ⇒ 报红 |
| C | 常量默认值 = 旧字面量；`DEFAULT_CONFIG.sim` 对；`merge` 签名含 `thr`/`susp_thr`；**改 thr 真的改行为**；不传参 = 传 0.9 | 阈值改了但结论没变 ⇒ 「阈值没接上」 |
| D | 源码层：数字分支含语义比较；**行为层**：covers 乱指 T1 必报红；正指向不报红；越界仍报红 | 乱指不报红 ⇒ 「语义校验没接上」 |

### 4.2 负对照脚本（`_nv_v12326_covers.py`）—— 改前/改后对照

驱动**真实方法** `DGTF._quality_check(view, pool, 1, write_diag=False)`：

| 案例 | v1.23.25（改前） | v1.23.26（改后） | 期望 |
|---|---|---|---|
| A `covers=["T1"]` 但问题语义无关 | **不报红** ★缺陷 | **报红** | 报红 ✅ |
| B `covers=["T1"]` 且语义相关 | 不报红 | 不报红 | 不报红 ✅ |
| C `covers=["T5"]` 越界 | 报红 | 报红 | 报红 ✅ |
| D covers 空 + 问题全无关 | 报红 | 报红 | 报红 ✅ |
| E covers 空 + 问题相关（fallback） | 不报红 | 不报红 | 不报红 ✅ |

★ 改前 A **不报红**是一切的前提：若无此读数，就无法区分「修好了」与「夹具本就报红」。

### 4.3 本轮实测数字

| 项 | 结果 |
|---|---|
| 冒烟 `smoke_test.py` | ✓=__SMOKE_OK__ / ✗=0（exit 0） |
| 变异体 `_mut_v12326.py` | **__MUT_OK__ / 8 判红** + 正对照判绿 |
| 负对照 `_nv_v12326_covers.py` | 5/5 符合（改前 A 不报红 ⇒ 改后报红） |
| 配置同步 | 166 键 / **load_config 逐字差异 0 项** |
| 主文件 CRLF | `CRLF=__CRLF__ / 裸 LF=0 / lone CR=0 / \r\r\n=0` |

### 4.4 `sim3` 实测值（改前 vs 改后）

| 对 | `_overlap_coef`（旧） | `_sim3` 无 corpus | `_sim3` 有 corpus |
|---|---|---|---|
| 模型 部署 / 模型 训练 | 0.500 | **0.333** | 0.422 |
| 神经网络 优化 / 神经网络 训练 | 0.500 | 0.333 | 0.540 |
| 长句（8 词）/ 长句（5 词，被包含） | **1.000** | 0.625 | 0.745 |
| `T3` / `T3` | — | **1.000** | 1.000 |
| `T3` / `T4` | — | 0.000 | 0.000 |

---

## 5. 变异体（`_mut_v12326.py`，8 个）

| # | 变异体 | 打在 | 期望 |
|---|---|---|---|
| M1 | `_sim3` 阈值抬到 0.99 | 复述判据的比较 | 判红 |
| M2 | Jaccard 分母换回 `min` | A 组分母来源（退回短句高估） | 判红 |
| M3 | 结构层短路返回 0.0 | L4 编号相等的短路 | 判红 |
| M4 | `_BM25_MIN_CORPUS` 降到 0 | B 组降级条件 | 判红 |
| M5 | BM25 归一化去掉 | B 组值域 | 判红 |
| M6 | `_DEDUP_SIM` 默认改 0.5 | C 组默认值 | 判红 |
| M7 | `merge` 忽略 `thr` 参数 | C 组「阈值接上了吗」 | 判红 |
| M8 | covers 数字分支退回裸 `True` | D 组语义校验 | 判红 |

★ 沿用 v1.23.25 的两条防呆：**SRC 换绝对路径**（否则畸形体因路径错冒充判红）；
**加载/执行抛错不算判红**（那只说明判据没跑）。

---

## 6. 未做 / 风险 / 下一步

### 6.1 未做

- **真跑（full run）**：本版改的是引擎侧尺子与阈值来源，**喂进模型的内容一字未增**
  （`_sim3` 不进 prompt），故以零成本判据 + 变异体 + 负对照替代真跑。
- `expected_gain` / `link` / 空探针判据 / 子模批选 / `AspectUnit` / `BeliefItem`
  —— 全部留 v1.23.27 / v1.23.28（需真跑）。

### 6.2 已知风险

| 风险 | 处置 |
|---|---|
| `sim3` 只是**加权词袋**，抓不到同义词（「AI」vs「人工智能」） | 设计取舍：语义那一半留给可选稠密通道（v1.23.27，`bge-small-zh-v1.5` 24M/CPU 10ms，走 user yaml，不进出厂配置） |
| BM25 在小语料（N≈5）上 IDF 不稳 | `_BM25_MIN_CORPUS=4` 以下整个通道关闭；且归一化 `raw/(raw+k1)` 压制极端值 |
| 复述判据两条并存，可能**任一条**误报 | 两条各管不同几何（Jaccard=全局对称；overlap=包住形状），已在 docstring 写明；判据 D 的负对照守住语义那一侧 |
| `_overlap_coef` 其余 16 处调用**未动**（仍有短句高估） | 有意为之：改动面可控。修它们需要逐处确认「那个场景的 min 分母是否有意义」，留下版 |

### 6.3 下一步建议

1. **v1.23.27（接口层，需真跑）**：`expected_gain` 取消自报 → 引擎算 $G$；
   `link` 反查；空探针判据双向化（honest/lazy 区分）；`AspectUnit` 结构化。
   **成败判据**：新 $G$ 与旧 `expected_gain` 在同一批候选上的排序相关性
   —— 高度相关 ⇒ 白改；弱相关且 $G$ 与实际兑现率更相关 ⇒ 成立（同条件重复 ≥3）。
2. **v1.23.28（信念层）**：`BeliefItem` 四态机 + 语义熵 + 异质化双臂。

---

## 7. 附：本版新增/修改符号清单

**新增模块级函数**
- `_bm25_corpus(items) -> (doc_tfs, dfs, avgdl, N)`
- `_bm25_best(query, corpus) -> float`
- `_jaccard(a, b, top_n) -> float`
- `_sim3(a, b, corpus=None, top_n) -> float`
- `_sim3_pair(a, b, corpus=None, top_n) -> (float, dict)`

**新增模块级常量**
- `_BM25_K1 = 1.5` / `_BM25_B = 0.75` / `_BM25_MIN_CORPUS = 4`
- `_REPHRASE_SIM3 = 0.62`
- `_DEDUP_SIM = 0.90` / `_DEDUP_SUSP_SIM = 0.85`
- `_COV_OVERLAP_MIN = 0.50`

**签名变更**
- `_sent_is_rephrase(s, u)` → `_sent_is_rephrase(s, u, corpus=None)`
- `Pool.merge(amps, threads, meta, probes=None, suspensions=None)`
  → `+ thr=None, susp_thr=None`

**新增配置键（`DEFAULT_CONFIG["sim"]`）**
- `sim.dedup = 0.9` / `sim.dedup_susp = 0.85`

**未动（有意）**
- `_overlap_coef`（19 处调用中只改复述 1 处）
- `_similar` / `_sim_ratio` / `_kw` / `_tokenize`
- 全部 LLM 提示词
- `select_probe_focus`（基线证明「必然塞满」不存在，无需改）
