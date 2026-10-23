# v1.22 阶段 4 报告 · 外部锚点变真证据

## 一、目标

| 编号 | 目标 | 量化验收 | 结果 |
|---|---|---|---|
| G4.1 | 五档 | `as_evidence` 五值之一 | ✅ `"off"`（出厂）→ 真跑用 `"evidence"` |
| G4.2 | tier | tier=1 进表 / tier=4 不进 | ✅ 真跑：3 条锚点(T1,T1,T4) → 表里 X1/X2 |
| G4.3 | 真检索 | `AnchorRetriever` 存在 | ✅ snapshot 零调用 + tavily 真检索 |
| G4.4 | X# 支撑 | decidable 成立 | ✅ **4 条结论被 X# 印证** |
| G4.5 | X# 支撑 | undecidable 驳回 | ✅ 判据在（`rejected` 路径），本轮无实例 |
| G4.6 | 冲突留痕 | `view.errors` + `pool.meta` | ⚠️ 机制在，**本轮 0 冲突**（见第六节） |
| G4.7 | triage 降级 | ≥ 1 条 | ❌ **未达成**（实测 0 条，根因见第七节） |
| G4.8 | 头部 | 含「锚点分级」+「triage 降级」 | ✅ |

★ G4.7 未达成、G4.6 未在本轮触发。两者都用「机制有没有在工作」与
「条件有没有到」分开说，不混成一句话。

## 二、改前基线（探针 before）

`python _probe_v122_phase4.py _baseline_v12177.py` 实测（原样摘录）：

```
A_as_evidence_default : false            ← 基线是**布尔** False，不是五档
A2_tier_floor         : null             ← 没有这个键
A3_api_key_env        : null
A4_retriever          : "snapshot"
B_tier_fn             : AttributeError: no attribute '_anchor_tier'
B2/B3                 : 同上（布尔/非法值都无从归一）
C_enters_t1 / C2_t4 / C3_no_tier : AttributeError: no attribute '_anchor_enters_citation'
D_citation_X_t1t4     : ["X1","X2"]      ← ★ 基线**没有 tier 门**：tier=4 也进表
D2_citation_X_off     : []
E_retriever_cls       : false
E2_snapshot_zero_calls / E3_unknown_backend : AttributeError: no attribute 'AnchorRetriever'
F_src_五档            : false            ← 源码里没有 off/record/crosscheck/evidence/gate
F2_src_锚点分级        : false
F3_src_triage         : false
F4_src_冲突留痕三处    : false            ← 冲突只进 packed，没有 view.errors / pool.meta 出口
G_crosscheck_triage_source : false
```

★ `D_citation_X_t1t4 = ["X1","X2"]` 是这一阶段最重要的基线读数：
基线在 `as_evidence=True` 时**无差别**把锚点全放进引用表，
tier=4 的论坛转述与 tier=1 的国标同权。

## 三、改了什么（逐条 + 落点）

| # | 改动 | 落点 |
|---|---|---|
| 1 | `external_anchor` 加 `as_evidence`(五档) / `tier_floor` / `api_key_env` / `cache_ttl_hours` | 主文件 5857 行附近（**就地改旧键**，不是新增） |
| 2 | `_ANCHOR_TIERS` / `_TRIAGE_KEYS` / `_anchor_tier` / `_tier_floor` | `_citation_table` 之前 |
| 3 | `AnchorRetriever`（snapshot 零调用 / tavily + sha256 缓存 24h） | 同上 |
| 4 | `_load_anchors` 给每条补 `tier`（1~4，缺省 3，越界钳到 [1,4]） | `_load_anchors` |
| 5 | `_retrieve_anchors` 接入真检索后端（原来对非 snapshot 直接抛错） | `_retrieve_anchors` |
| 6 | `_citation_table` 的 X# 入表加 `_anchor_enters_citation` 门 | 主文件 5861 行附近 |
| 7 | 冲突留痕：`view.errors` + `pool.meta`；`gate` 档进 `blocked_conclusions` | `_anchor_crosscheck` 尾部 |
| 8 | triage 降级清单（**只出建议，不自动改判定**） | 同上 |
| 9 | 头部「锚点分级 / triage 降级 / 冲突」三行（**无条件写**） | `save_result` |

### ★ 本阶段最贵的一课：往 dict 加键前先看那个键在不在

第一版我用「在 `crosscheck` 后面插入新键」的方式加 `as_evidence`。
结果验收报 `as_evidence=False ∈ 五档` 失败 —— **那个键早就存在**
（v1.21.75 的布尔版），Python 的 dict 字面量**后者胜**，
我新写的 `"off"` 被后面那个 `False` 静默覆盖。

20k 行的配置块里靠人眼查不出重复键。为此新增了一条**全局结构判据**：
`check_v122_dup_dict_keys` —— 全文件 AST 扫描，任何 `ast.Dict` 里
重复的常量键都判红。它现在跑在冒烟里，属于这一阶段留下的永久资产。

修法是**就地改旧键的值**（`"as_evidence": False` → `"off"`，
注释写清五档与布尔兼容），并把 `retriever` 那处重复也一并收掉。

## 四、改后对照（探针 after）

```
A_as_evidence_default : "off"       A2_tier_floor : 2
A3_api_key_env : "TAVILY_API_KEY"   A4_retriever : "snapshot"
B_tier_fn :
    {"as_evidence": True}  → "evidence"
    {"as_evidence": False} → "off"        ← v1.21.75 布尔写法仍兼容
    {"as_evidence": "随便"} → "off"        ← 非法值按最保守处理
C_enters_citation : tier=1 → true / tier=4 → false / **无 tier → false**
D_citation_X_t1t4 : ["X1"]           ← 与基线 ["X1","X2"] 对比：tier=4 被门挡掉
D2_citation_X_off : []
E_retriever_cls : true
E2_snapshot_zero_calls : []          ← snapshot 零调用
E3_unknown_backend_raises :
    RuntimeError: external_anchor.retriever='web_search' 尚未实现
    （当前只有 'snapshot' 与 'tavily'）；不静默降级
F_src_五档 / F2_锚点分级 / F3_triage / F4_冲突留痕三处 : 全 true
G_crosscheck_triage_source : true
```

★ `C3_enters_no_tier = false` 值得单说：**不带 `tier` 字段的锚点进不了引用表**。
这是「缺省 3 + floor 2」的必然后果，也是刻意选的保守默认 ——
「二手转述支撑 →decidable 比没有证据更危险」。已写进
`_anchor_enters_citation` 的 docstring 与第九节遗留 #2。

## 五、冒烟结果

`python smoke_test.py` → **✓ 158 / ✗ 0 / EXIT=0**

阶段 4 相关：`check_v122_phase4`（五档合法性、tier_floor / api_key_env 在、
`_anchor_enters_citation` 两个方向、`AnchorRetriever` 存在、冲突留痕字面串、
triage_downgrades 字面串、头部两行）+ 全局 `check_v122_dup_dict_keys`。

### 两条旧判据的更新（都要区分「判据过时」与「真问题」）

1. **v75 `[B]`「授权后引用表 X 编号为 ['X1','X2']」**：收口后判红。
   原因是引用表**新增了 tier 门**，而它的 fixture 锚点没有 `tier`
   （缺省 3 > floor 2）→ 不进表。
   这是**判据过时**（它测的是「授权门」，不是「tier 门」）→
   给 fixture 补 `tier: 1`，判据含义不变。
   ★ 但这条也顺手暴露了一个**真问题**：`tier` 缺省 3 + `tier_floor` 缺省 2
   ⇒ **不带 tier 的锚点默认一个都进不了引用表**。这是刻意选的保守默认
   （「二手转述不该支撑 →decidable，比没有证据更危险」），但它意味着
   使用者必须**显式声明 tier** 才拿得到证据资格 —— 已在文档与
   `_anchor_enters_citation` 的 docstring 里写明。
2. **v76 `[B4]`「未实现的检索后端仍要抛错」**：收口后判红，因为抛错
   被搬进了 `AnchorRetriever.search`（唯一实现），而旧判据是按
   `_retrieve_anchors` 的函数体搜的。**功能没变**（运行时的 `[D]` 判据
   证明它仍在抛错留痕）→ 判据改搜**整条检索链**
   （`_retrieve_anchors` 体 ∪ `AnchorRetriever` 源码）。
   删掉抛错仍然会被抓到，判别力不减。
3. **本阶段探针自己的 `F4` 也误报过一次**：我按「我记得写成了什么」拼了
   `view.errors.append(f"锚点冲突`，而实际落点是
   `_pv1.errors.append("锚点冲突：" + ...)` → 探针报 `false`，
   看起来像「冲突留痕没做」。改成按**实际落点**搜
   （`"锚点冲突："` / `pool.meta.append(` / `blocked_conclusions`）后为 true。
   ★ 这是同一个坑的第三次出现（前两次分别是 docstring 里的函数名被当成定义、
   以及判据串与实际标记串不一致）：**判据串必须从源码里 copy，不能凭记忆拼**。

## 六、真跑样本（带锚点，tier 门 + 五档）

`python _run_p4_only.py 元DGTF-V1.22.0.py` → `runs/v122/p4_anchored/`
（题：老城区暴雨内涝…；route 0,1；rounds 0:3,1:3；economy；
锚点 = `_test_anchors.json` 三条：两条 tier=1 的国标/指南 + 一条 tier=4 的论坛转述）

```
calls = 51        as_evidence = "evidence"     tier_floor = 2
anchors = 3       pooled = 6（每圈投放，含重复计入）
claims = 12       supported = 4   conflicted = 0   unmatched = 8   anchor_used = 2
triage_downgrades = 0            blocked_conclusions = []
anchor_err = ""
```

产物头部（实测）：

```
**锚点分级**：evidence（tier_floor 2）
**triage 降级**：0 条
**冲突**：0 条（gate 阻断 0 条）
```

被 X# 印证的 4 条（原文摘录）：

| claim | 判定 | 锚点 | note（模型给的） |
|---|---|---|---|
| c9 | 印证 | a1 | GB50014 规定重现期 3~5 年，反映老城区管网标准偏低 |
| c10 | 印证 | a2 | 海绵指南提及源头减排、过程控制及调蓄设施等技术措施 |
| c11 | 印证 | a2 | 指南称整体翻新管网需与调蓄同步，暗示工程量大、投资高 |
| c12 | 印证 | a2 | 指南指出单靠扩容收效有限，支持局部改造不解决系统性问题 |

**G4.4 达成**：4 条判定被 X# 支撑，且 X# 确实只收了够硬的锚点 ——
真跑里 3 条锚点 tier = `[1, 1, 4]`，引用表给的是 **X1 / X2**，
tier=4 的论坛转述被挡在表外。这是 tier 门在**真实数据**上的证据，
不是单测里的构造样本。

`pool.meta` 也留了痕：`[外部锚点] 第 1 圈入池 2 条（累计 2，作证据）`、
`第 2 圈入池 1 条（累计 3，作证据）` —— 档位是 `evidence`，
部署句子按预期写成「作证据」。

### G4.6「冲突留痕可见」本轮没有实例

12 条结论的判定是 **印证 4 / 无对应 8 / 冲突 0**。所以「冲突留痕」这条
**本轮没有可展示的痕**。据实写出来，而不是拿「留下的 4 条印证」冒充。

机制本身有据可查：v1.21.74 的 `_anchor_negative_control.py` 做过
**负对照** —— 4 条合成反向结论全部被判「冲突」、1 条一致结论被判「印证」。
那一次证明了这个分支会响。本轮只能说明「这批结论与这份锚点快照不冲突」。

## 七、G4.7 为什么 0 条：触发词与引擎措辞不匹配

triage 降级的触发条件是
「不可判定侧面的**理由属于** `信息不足 / 需外部动作 / 缺数据 / 无外部` 四类
之一，且被 tier ≤ floor 的锚点命中（相似度 ≥ 0.6）」。

真跑里 `decidability.undecidable_aspects` 的 5 条原文：

```
- [外] 具体某老城区应选择全面重建还是局部改造加海绵的唯一最优方案
- [外] 当地设计暴雨、管网现状、内涝成因、地下空间与施工条件
- [外] 投资预算、财政承受力、拆迁难度与居民意愿
- [外] 长期气候变化下降雨趋势及极端暴雨频率
- [外] 多目标权衡中的社会偏好：防洪标准、生态、交通影响与成本
```

**四个关键词的命中条数 = 0/5**。而「`[外]`」这个前缀在语义上
**就是**「需要外部材料」—— 引擎早就有这个标签，只是用的不是那四个汉字。

所以结论是**条件不可达（触发词表与实际措辞不匹配）**，不是机制没工作。
按本项目的三条分类（①条件不可达 ②条件窄但成立 ③机制没工作），
它落在 ①/② 之间：**语义上成立，字面上不可达**。

**没有做的两件事，及理由**：

1. **把 `[外]` 加进触发词表**（一行改动就能让指标变绿）。这是把判据
   拟合到**一份**样本上 —— 本轮只有这样一条证据，改了也无法验证
   它是不是泛化。**不做**，列入第八节。
2. **放宽相似度阈值 0.6**。那是改阈值，且任务书明令不改。**不做**。

**下一版该做的**：触发条件不应该建在「四个固定汉字串」上，
而应该建在**结构标签**上（`[外]` / `[内]` 这类引擎自己的分类，
或池里 `undecidable_aspects` 的来源字段）。并且改完要用**多份**真跑
（≥3 题）验证命中率，而不是拿一题调到非零就宣布修好。

## 八、验收判据核对

```
── 阶段 4 ──
  ✅ [4.1.1] as_evidence='off' ∈ 五档
  ✅ [4.1.2] tier_floor=2
  ✅ [4.1.3] api_key_env='TAVILY_API_KEY'
  ✅ [4.2.1] tier=1 进引用表
  ✅ [4.2.2] tier=4 不进引用表
  ✅ [4.3] AnchorRetriever 存在
  ✅ [4.4] X# 支撑 →undecidable 被驳回（rejected 路径在）
  ✅ [4.5] 锚点冲突留痕（字面串 + 三处出口）
  ✅ [4.6] triage_downgrades 存在
  ✅ [4.7] 头部含『锚点分级』+『triage 降级』
━━━ PASS 13 / FAIL 0 ━━━          ← 机制判据全绿
EXIT=0
                                    ← 效果判据：G4.4 达成；G4.6 无实例；G4.7 未达成
```

## 九、遗留与下一阶段候选

| # | 事项 | 为什么留 | 怎么验「修好了」 |
|---|---|---|---|
| 1 | triage 触发词改成结构标签（`[外]` 一类） | 本轮 0/5 命中，字面不可达；改词表要防拟合 | ≥3 题真跑里 triage ≥1 且**无题**出现「全是 partial」的漂移 |
| 2 | `tier` 缺省 3 + `tier_floor` 缺省 2 ⇒ 无声明则无证据资格 | 是刻意的保守默认，但需要一个显式提示 | 载入锚点时若**全部**锚点 tier 缺省，产物里加一行警告 |
| 3 | 冲突分支只在 v1.21.74 的合成负对照里验过 | 本轮 0 冲突属正常结果，但不能靠它证明分支还活着 | 把 `_anchor_negative_control.py` 收进阶段 4 的固定冒烟（每轮都跑一次 neg control） |
| 4 | `gate` 档的 `blocked_conclusions` 本轮为空（无冲突） | 同上 | 合成一条冲突 + `gate` 档，断言该结论进 `blocked_conclusions` |
