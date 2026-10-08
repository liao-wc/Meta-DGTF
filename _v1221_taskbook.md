# 元 DGTF v1.22.0 → v1.22.1 · 三档收尾任务提示词

> 来源：https://chat.deepseek.com/share/ly234s1gqarlphvm6p（用户指定，2026-10-05 落盘）
> **用途**：直接喂给 AI 编程助手。整段可用。
> **执行方式**：**档内串行、档间严格串行**。前一档验收未通过，不许开下一档。
> **版本号**：`v1.22.1`（v1.22.0 的收尾版本，不是新六大阶段）。
> **输出方式**：每 Step 输出 `[P N][Step N.M] 完成：<证据>`；每档结束输出 `[档 N] 验收：通过 / 未通过`。

---

## 0. 角色与全局约束

### 0.1 你的角色

你是本次收尾任务的**唯一执行者**。目标：把 v1.22.0 六阶段留下的**三条效果未达标、三条待补**做完。**不加新机制、不拆模块、不删代码、不动阈值**。

### 0.2 三档与执行顺序

```
第一档（立刻做、必须做）
  P1：研究层直接产出结构化 actions 段
  P2：triage 触发条件改挂结构标签
  P3：仅源码机制做负对照
第二档（需要前置）
  P4：一致率 ON/OFF 对照
  P5：auto 取向回填
  P6：tier 缺省时的显式提示
第三档（明确不做）
  —— 只出说明，不动代码
```

### 0.3 宪法级约束（违反即任务失败）

继承 v1.22 全部约束，并**追加**三条：

01. **加性优先**：新键、新参数默认值、新方法，不删旧行、不改旧键语义。
02. **失败必须留痕**：任何路径失败都进 `view.errors` / `pool.meta` / 日志。
03. **先量后改**：每 Step 先跑探针拿 before，改后跑同一支探针出 after。
04. **不改阈值 / 常量**：本版**一个新阈值都不加**；需要新判据走配置键 + 默认值。
05. **不动模型配置**：`DEFAULT_CONFIG["api"]` / thinking stages 一律不碰。
06. **不动宪法级原则**。
07. **CRLF 一致**：改后逐次核对行尾。
08. **docstring 里零反斜杠**。
09. **每档必须出**：探针 before/after + 冒烟 `check_v1221_pN` + 报告 `v1221_pN_报告.md`。
10. **不许跨档**：前一档未通过，不许开下一档。
11. **本版一行 `del` 都不许有**：`count_del_lines` 必须 = 0；`mechanism_removed` 必须 = 0 项。
12. **不许把"拟合数据"当修好**：扩动词白名单 / 放宽 `min_actions` / 把 `[外]` 塞进旧词表 —— **一律禁止**。

### 0.4 文件命名

| 用途 | 命名 |
|---|---|
| 主文件（改前） | `元DGTF-V1.22.0.py`（= 基线副本 `_baseline_v1220.py`） |
| 主文件（中间态） | `元DGTF-V1.22.1-rc<N>.py` |
| 主文件（定稿） | `元DGTF-V1.22.1.py` |
| 探针 | `_probe_v1221_p<N>.py` |
| 探针输出 | `_probe_v1221_p<N>_before.txt` / `_after.txt` |
| 冒烟 | 追加进 `smoke_test.py`，`check_v1221_p<N>` |
| 报告 | `v1221_p<N>_报告.md` |
| 总报告 | `v1221_报告.md` |
| 验收脚本（扩展） | `_v122_verify.py`（加 `--phase p1..p6`） |

### 0.5 命令格式

```bash
python _v122_verify.py --phase p<N> --src 元DGTF-V1.22.1-rc<N>.py
```

**期望**：`PASS N / FAIL 0` + `EXIT=0`。

---

# 第一档：立刻做、必须做

## P1 · 研究层直接产出结构化 actions 段

### P1.1 目标

| 编号 | 目标 | 量化验收 |
|---|---|---|
| P1-a | 研究层 schema 加 `actions` 段 | `decidable_product.actions` 键存在 |
| P1-b | 每条 action 六字段齐全 | `verb / object / owner_role / deadline_hint / acceptance / fallback` |
| P1-c | `_extract_actions` 优先读 schema，兜底走词法 | 有 schema 时不再猜 |
| P1-d | `action_incomplete` 语义改为「模型没按 schema 产出」 | 报告与代码注释同步 |
| P1-e | decision 题 ≥ 3 条 action | **≥ 3 题真跑上验：100% ≥ 3** |
| P1-f | rubric 平均 ≥ 2/3 | **≥ 3 题真跑上验** |

### P1.2 Step 清单

#### Step P1.1 研究层 `_he` 的 schema 加 `actions`

**文件**：`元DGTF-V1.22.1-rc1.py`，`DGTF._he` 的 `is_research` 分支。

**改 prompt 的 system**（在 `decidable_product` 的 JSON 骨架里加）：

```json
"decidable_product": {
  "answer": "...",
  "answered_sub_ids": [1],
  "evidence": ["..."],
  "distance": 0.0-1.0,
  "actions": [
    {
      "id": "A1",
      "verb": "指派|核查|测量|提交|申请|封堵|清淤|试点|备案|签发|复核|排查|改造|扩容|委托|报审|谈判|调取",
      "object": "≤40字，动作对象",
      "owner_role": "≤20字，具名角色或部门",
      "deadline_hint": "≤20字，具体时限或触发条件",
      "acceptance": "≤40字，怎么算完成",
      "fallback": "≤40字，失败时的退路"
    }
  ]
}
```

**加 prompt 约束段**：

```
【★ actions 段 · decision 取向必须产出】
- 研究层的回答若落在"该做什么"，必须同时给 actions 段，而不是只给结论段落。
- 每条 action 六字段**全部必填**，缺一格视为无效条目。
- owner_role 必须是一个**具体的角色 / 部门 / 岗位**，不许写"相关部门""有关方面"。
- deadline_hint 必须是**可指认的时限或触发条件**（如"汛期前 30 天""下一次暴雨后 24h"），
  不许写"尽早""适时"。
- acceptance 必须能**被第三方核对**（如"出具签字人清单""泵站流量记录入档"）。
- fallback 必须写**失败时的退路**，不许写"重新评估"这类空动作。
- 若确实给不出 actions（纯事实题 / 边界题），给空数组并在 answer 里说明，
  不要硬凑。
```

**验收命令**：

```bash
python _v122_verify.py --phase p1 --src 元DGTF-V1.22.1-rc1.py 2>&1 | grep "P1.1"
```

**期望**：`P1.1.a`（schema 键在）/ `P1.1.b`（六字段字符串在 prompt 里）/ `P1.1.c`（约束段字面串在）全 ✅。

#### Step P1.2 `_extract_actions` 优先读 schema

**文件**：同上，`_extract_actions` 函数。

**改后逻辑**：

```python
def _extract_actions(view) -> list:
    """优先读 schema 产出的 actions；schema 缺失时才回退词法抽取。

    [v1.22.1 P1] 语义变更：从"从结论段落里猜动作"变成"读研究层已产出的
    结构化 actions"。词法路径保留，仅作兜底（老产物 / 未升级 schema 的跑批）。
    """
    dp = getattr(view, "decidable_product", None) or {}
    _schema_actions = dp.get("actions")
    if isinstance(_schema_actions, list) and _schema_actions:
        out = []
        for a in _schema_actions:
            if not isinstance(a, dict):
                continue
            _act = {
                "id": str(a.get("id") or f"A{len(out)+1}"),
                "verb": str(a.get("verb", "")).strip(),
                "object": str(a.get("object", "")).strip(),
                "owner_role": str(a.get("owner_role", "")).strip(),
                "deadline_hint": str(a.get("deadline_hint", "")).strip(),
                "acceptance": str(a.get("acceptance", "")).strip(),
                "fallback": str(a.get("fallback", "")).strip(),
            }
            # 六字段全空视为无效；留一条空字段也收，但标 incomplete
            if not any(_act[k] for k in ("verb", "object")):
                continue
            _act["_source"] = "schema"
            _act["_missing"] = [k for k in
                ("verb", "object", "owner_role", "deadline_hint",
                 "acceptance", "fallback") if not _act[k]]
            out.append(_act)
        if out:
            return out
    # 兜底：词法（老路径，一字不动）
    return _extract_actions_lexical(view)
```

**动作**：把原 `_extract_actions` 整体改名 `_extract_actions_lexical`，保留所有正文；新函数瘦壳 + 兜底。

**验收命令**：

```bash
python _v122_verify.py --phase p1 --src 元DGTF-V1.22.1-rc1.py 2>&1 | grep "P1.2"
```

**期望**：

- `P1.2.a`：schema 有 actions → 返回的 action 带 `_source = "schema"`
- `P1.2.b`：schema 无 actions → 走词法，返回的 action 带 `_source = "lexical"`
- `P1.2.c`：空 answer → 返回 `[]`（负对照）

#### Step P1.3 `action_incomplete` 语义改写

**文件**：`_finalize_layer_common`。

**改后逻辑**：

```python
_orientation = getattr(self, "_orientation", "auto")
if entry == "1" and _orientation == "decision":
    _acts = _extract_actions(view)
    _schema_acts = [a for a in _acts if a.get("_source") == "schema"]
    if len(_schema_acts) < 3:
        view.errors.append(
            f"decision 取向 actions 段不足：schema 产出 {len(_schema_acts)} 条"
            f"（< 3）。请在 _he 的 decidable_product 里补 schema actions。")
        view.quality_flags.append("action_incomplete")
    # 六字段齐全性检查（仅对 schema 来源的）
    for a in _schema_acts:
        if a.get("_missing"):
            view.errors.append(
                f"action {a.get('id')} 缺字段：{a['_missing']}")
            view.quality_flags.append("action_fields_missing")
            break
    _dp = getattr(view, "decidable_product", None) or {}
    _ans = str(_dp.get("answer") or "")
    if any(k in _ans for k in ("缺主体", "无主体", "无承接者", "缺承接者")):
        if not _schema_acts:
            view.errors.append(
                "结论落在'缺 X'但 schema 未给 actions，需补 A1~A3")
```

**注释同步**：`# [v1.22.1 P1] 本 flag 语义 = 模型没按 schema 产出 actions，不是词法没抽到`。

**验收命令**：

```bash
python _v122_verify.py --phase p1 --src 元DGTF-V1.22.1-rc1.py 2>&1 | grep "P1.3"
```

**期望**：

- `P1.3.a`：源码有「模型没按 schema 产出 actions」
- `P1.3.b`：`action_fields_missing` 字面串在
- `P1.3.c`：负对照 — 造一个 schema 3 条全字段齐全的 view，不应触发 `action_incomplete`

#### Step P1.4 ≥ 3 题真跑

**命令**：

```bash
for q in \
  "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？" \
  "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？" \
  "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？"; do
  python 元DGTF-V1.22.1-rc1.py "$q" \
    --route 0,1,both,all --rounds "0:4,1:4,both:4,all:5" \
    --parallel serial --orientation decision --quiet
done
```

**核对**：

```bash
python - <<'EOF'
import glob, re, json, sys
from pathlib import Path
bad = []
for f in sorted(glob.glob("outputs/*.md"))[-3:]:
    text = Path(f).read_text(encoding="utf-8")
    m = re.search(r"### 二、行动清单(.*?)### 三、", text, re.S)
    if not m:
        bad.append((f, "无行动清单段")); continue
    actions = re.findall(r"- \*\*(A\d+)\*\*", m.group(1))
    if len(actions) < 3:
        bad.append((f, f"action 数 {len(actions)} < 3"))
print("BAD:", bad)
sys.exit(1 if bad else 0)
EOF
```

**期望**：`BAD: []`（3 题全部 ≥ 3 条）。

**rubric 核对**：

```bash
python bench/bench_score.py <每份产物目录> bench/gold/<id>.yaml | grep decision
```

**期望**：3 题 rubric 平均 ≥ 2/3。

#### Step P1.5 冒烟 `check_v1221_p1`

```python
def check_v1221_p1(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    # 1 schema 优先
    v = m.View(entry="1")
    v.decidable_product = {
        "answer": "x",
        "actions": [
            {"id": "A1", "verb": "指派", "object": "核查",
             "owner_role": "区防汛办", "deadline_hint": "汛期前 30 天",
             "acceptance": "出具签字人清单", "fallback": "向上级申请"},
            {"id": "A2", "verb": "提交", "object": "排水图",
             "owner_role": "排水公司", "deadline_hint": "本月内",
             "acceptance": "管网档案归档", "fallback": "委托第三方"},
            {"id": "A3", "verb": "试点", "object": "透水铺装",
             "owner_role": "项目组", "deadline_hint": "本季度",
             "acceptance": "验收报告出具", "fallback": "缩减试点范围"},
        ],
    }
    acts = m._extract_actions(v)
    assert len(acts) == 3
    assert all(a["_source"] == "schema" for a in acts)
    assert all(not a["_missing"] for a in acts)
    # 2 兜底词法
    v2 = m.View(entry="1")
    v2.decidable_product = {"answer": "先指派区防汛办核查。否则回退上级。"}
    acts2 = m._extract_actions(v2)
    assert acts2 and all(a["_source"] == "lexical" for a in acts2)
    # 3 负对照：空 answer 无 schema → []
    v3 = m.View(entry="1")
    v3.decidable_product = {"answer": ""}
    assert m._extract_actions(v3) == []
    # 4 负对照：schema 缺字段 → _missing 标出
    v4 = m.View(entry="1")
    v4.decidable_product = {"answer": "x",
        "actions": [{"id": "A1", "verb": "指派", "object": "核查"}]}
    acts4 = m._extract_actions(v4)
    assert acts4 and acts4[0]["_missing"], acts4
    # 5 源码断言
    src = open(SRC, encoding="utf-8").read()
    assert "decidable_product" in src and '"actions"' in src
    assert "模型没按 schema 产出 actions" in src
    assert "action_fields_missing" in src
    return True
```

#### Step P1.6 验收

```bash
python _v122_verify.py --phase p1 --src 元DGTF-V1.22.1-rc1.py
echo "EXIT=$?"
```

**期望**：`PASS N / FAIL 0` + `EXIT=0`。

**通过判据**：

- □ P1.1 / P1.2 / P1.3 全绿
- □ 3 题真跑 action ≥ 3
- □ 3 题 rubric 平均 ≥ 2/3
- □ 3 题 `action_incomplete` 均为 0
- □ `count_del_lines` = 0

**报告**：`v1221_p1_报告.md`，必须含：

- 探针 before / after
- 3 题产物路径 + action 数 + rubric
- 改前 / 改后 `action_incomplete` 触发次数

---

## P2 · triage 触发条件改挂结构标签

### P2.1 目标

| 编号 | 目标 | 量化验收 |
|---|---|---|
| P2-a | 触发条件改挂结构标签 | `[外]` 前缀被识别 |
| P2-b | 真·自指不被误降级 | 负对照：自指型 und 不降级 |
| P2-c | triage 降级 ≥ 1 条 | **≥ 3 题真跑上验** |
| P2-d | 降级留痕 | `triage_downgrades` 非空 |

### P2.2 Step 清单

#### Step P2.1 `_TRIAGE_KEYS` 改结构标签

**文件**：`_anchor_crosscheck` 附近的 `_TRIAGE_KEYS`。

**改后逻辑**：

```python
# [v1.22.1 P2] 触发条件从"四个固定汉字串"改成"结构标签或语义关键词"。
# 依据：v1.22.0 阶段 4 实测 —— 真跑里 5 条 undecidable_aspects
# **全部以 `[外]` 开头**（引擎自己的结构标签），而旧词表 0/5 命中。
# ★ 不许把 `[外]` 塞进旧词表（那是拟合一题样本），
#   而是把"结构标签"本身立为第一类触发条件。
_TRIAGE_STRUCTURAL_PREFIXES = ("[外]",)   # 引擎自己的标签，可加 [内] 等

_TRIAGE_SEMANTIC_KEYS = (                  # 语义关键词，第二类
    "信息不足", "需外部动作", "缺数据", "无外部",
    "需要外部", "取决于外部", "依赖外部",
)

def _is_triage_candidate(aspect: str) -> bool:
    s = str(aspect or "").strip()
    if not s:
        return False
    # 第一类：结构标签
    if any(s.startswith(p) for p in _TRIAGE_STRUCTURAL_PREFIXES):
        return True
    # 第二类：语义关键词
    if any(k in s for k in _TRIAGE_SEMANTIC_KEYS):
        return True
    return False
```

**在 `_anchor_crosscheck` 里**：`if not any(k in str(a) for k in _TRIAGE_KEYS):` 改 `if not _is_triage_candidate(a):`。

#### Step P2.2 结构标签不该被误降级的负对照

**新增判据**：`_TRIAGE_NEVER_DOWNGRADE = ("自指", "自证", "本体论", "无共同参照系")`。

```python
def _is_never_downgrade(aspect: str) -> bool:
    """这些是 v1.21.59 定义的真正"原则判不出"，锚点无关，不许降级。"""
    s = str(aspect or "")
    return any(k in s for k in _TRIAGE_NEVER_DOWNGRADE)
```

**在 `_anchor_crosscheck` 里**：triage 前先过滤：

```python
for a in (dec.get("undecidable_aspects") or []):
    if _is_never_downgrade(a):
        continue
    if not _is_triage_candidate(a):
        continue
    ...
```

#### Step P2.3 ≥ 3 题真跑验证命中率

**命令**：

```bash
python - <<'EOF'
import importlib.util, json
spec = importlib.util.spec_from_file_location("dgtf", "元DGTF-V1.22.1-rc1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cfg = m.DEFAULT_CONFIG.copy()
cfg["external_anchor"] = dict(cfg["external_anchor"])
cfg["external_anchor"].update({
    "enabled": True, "path": "_test_anchors.json",
    "as_evidence": "evidence", "tier_floor": 2,
})
Q = [
  "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？",
  "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？",
  "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？",
]
for i, q in enumerate(Q, 1):
    meta = m.MetaDGTF(cfg)
    res = meta.run(q, route=["0","1"], rounds="0:3,1:3")
    m.save_result(res, f"outputs/p2_run{i}")
    print(f"run{i}: triage =", res.get("external_anchor", {}).get("triage_downgrades"))
EOF
```

**核对**：

```bash
for i in 1 2 3; do
  echo "--- run$i"
  grep -E "triage 降级" outputs/p2_run$i/*.md | head -1
done
```

**期望**：≥ 1 题 triage ≥ 1 条（**不是**要求 3/3，因为取决于题面）。

**通过判据**：

- 3 题里 ≥ 1 题 triage ≥ 1 条 → **P2-c 达成**
- 若 3 题全 0，**该档验收失败**——需要重新审视触发条件
- **不许**为了达标去改词表拟合这 3 题

#### Step P2.4 冒烟 `check_v1221_p2`

```python
def check_v1221_p2(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    # 1 结构标签命中
    assert m._is_triage_candidate("[外] 具体某老城区的最优方案")
    # 2 语义关键词命中
    assert m._is_triage_candidate("信息不足，无法判断")
    # 3 负对照①：真·自指不许降级
    assert not m._is_never_downgrade("[外] 具体某老城区的最优方案")
    assert m._is_never_downgrade("该判定自指，无共同参照系")
    # 4 负对照②：无标签无语义词
    assert not m._is_triage_candidate("现场取证难度大")
    # 5 源码断言
    src = open(SRC, encoding="utf-8").read()
    assert "_TRIAGE_STRUCTURAL_PREFIXES" in src
    assert "_TRIAGE_NEVER_DOWNGRADE" in src
    assert "_is_triage_candidate" in src
    assert "_is_never_downgrade" in src
    return True
```

#### Step P2.5 验收

```bash
python _v122_verify.py --phase p2 --src 元DGTF-V1.22.1-rc1.py
echo "EXIT=$?"
```

**期望**：`PASS N / FAIL 0` + `EXIT=0`。

**通过判据**：

- □ P2.1 / P2.2 / P2.3 全绿
- □ 3 题真跑 ≥ 1 题 triage ≥ 1 条
- □ 负对照：真·自指不降级
- □ 无题出现「全是 partial」漂移（`decidability_log` 里 `undecidable → partial` 条数 ≤ 50%）
- □ `count_del_lines` = 0

**报告**：`v1221_p2_报告.md`，必须含：

- 3 题 triage 条数
- 每一条 triage 的 `from / to / anchor_id / aspect`
- 「为什么这 3 题的命中率是 X」的解释

---

## P3 · 仅源码机制做负对照

### P3.1 目标

把 v1.22.0 阶段 5 里判「仅源码」的机制，**每一条**喂一个该触发的输入，看它触不触发。判定三分类：`条件不可达 / 条件窄但成立 / 机制没工作`。

**清单以 `audit_v122_dead_mechanisms.md` 的「仅源码」判定为准**（v1.22.0 报告里是 5~6 项，两处口径不一致时以审计报告为准，并在任务书里注明）。

### P3.2 Step 清单

#### Step P3.1 建负对照脚本 `_negctl_v1221_p3.py`

对每条机制，一个函数：

```python
def negctl_escalate_starve_rounds() -> dict:
    """喂一个"连续 N 圈无进展 + 名下有账"的输入，看它触发不触发。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    pool = m.Pool()
    pool.sub_questions = [
        {"id": 1, "question": "Q", "decidability": "decidable",
         "status": "open", "_starve_rounds": 2},
    ]
    pool.deferrals = [
        {"id": "d_001", "sub_id": 1, "status": "deferred",
         "revisit_condition": "当 X 出现后"},
    ]
    view = m.View(entry="1")
    stats = {"reclassified": 0, "escalated": 0, "rejected": 0, "_transitions": []}
    m._starve_escalation(pool, view, {1: pool.sub_questions[0]},
                          layer=3, cfg=m.DEFAULT_CONFIG, stats=stats)
    return {
        "mechanism": "escalate_starve_rounds",
        "triggered": stats["escalated"] > 0,
        "stats": stats,
        "pool_log": pool.decidability_log,
    }
```

对每条机制各写一个：

- `negctl_escalate_starve_rounds`：连续 N 圈 + 有账
- `negctl_no_push_when_idle`：空转类判据 + 有未深入方向
- `negctl_reopen_closed_debt`：分类被推翻 + 曾有 escalated
- `negctl_both_tighten_ratio`：both 占比超阈值
- `negctl_all_settle_streak`：元层清算未下降
- `negctl_<其余>`：按审计报告清单补

**注意**：若审计报告「仅源码」是 5 项，就写 5 个；不硬凑 6 项。

#### Step P3.2 每条机制给判定

脚本输出 `_negctl_v1221_p3.json`：

```json
{
  "escalate_starve_rounds": {
    "triggered": true,
    "verdict": "条件窄但成立",
    "evidence": "stats.escalated = 1, pool.decidability_log[0].status = applied"
  },
  "no_push_when_idle": {
    "triggered": false,
    "verdict": "条件不可达",
    "evidence": "构造输入命中 stop_reasons 但 _uncovered_gate 未清空 reasons"
  }
}
```

判定规则：

- `triggered = true`：**条件窄但成立**（不删，保留）
- `triggered = false` 且构造输入**语义正确**（确实该触发）：**机制没工作**（进 `pending_fix`）
- `triggered = false` 且构造输入**在源码里根本走不到**：**条件不可达**（进 `pending_fix`，考虑删；但**本版不删**）

#### Step P3.3 输出 `docs/机制负对照-v1221.md`

每条机制写清：

- 触发条件
- 构造输入
- 实测结果
- 判定
- 下一步（`保留 / 修 / 归档`）

#### Step P3.4 冒烟 `check_v1221_p3`

```python
def check_v1221_p3(SRC):
    import json
    from pathlib import Path
    assert Path("_negctl_v1221_p3.py").exists()
    assert Path("_negctl_v1221_p3.json").exists()
    assert Path("docs/机制负对照-v1221.md").exists()
    data = json.loads(Path("_negctl_v1221_p3.json").read_text(encoding="utf-8"))
    assert len(data) >= 5, f"负对照条数 {len(data)} < 5"
    for name, it in data.items():
        assert it["verdict"] in ("条件不可达", "条件窄但成立", "机制没工作"), \
            f"{name} verdict 非法：{it['verdict']}"
    return True
```

#### Step P3.5 验收

```bash
python _negctl_v1221_p3.py
python _v122_verify.py --phase p3 --src 元DGTF-V1.22.1-rc1.py
echo "EXIT=$?"
```

**通过判据**：

- □ 每条「仅源码」机制都有负对照结果
- □ 每条判定合法（三分类之一）
- □ `docs/机制负对照-v1221.md` 生成
- □ **本版不删任何机制**（`count_del_lines` = 0）
- □ 判「机制没工作」的条目进 `pending_fix`

**报告**：`v1221_p3_报告.md`。

---

## 第一档验收

```bash
python _v122_verify.py --phase p1 --src 元DGTF-V1.22.1-rc1.py && \
python _v122_verify.py --phase p2 --src 元DGTF-V1.22.1-rc1.py && \
python _v122_verify.py --phase p3 --src 元DGTF-V1.22.1-rc1.py
echo "EXIT=$?"
```

**通过判据**：三档全绿 + 三份报告齐 + 三档真跑齐。

**未通过就停在这里，不许开第二档。**

---

# 第二档：需要前置

## P4 · 一致率 ON/OFF 对照

### P4.1 目标

同题同配置跑多票 **ON** 和 **OFF** 各 ≥ 3 次，比较一致率。

### P4.2 Step 清单

#### Step P4.1 加运行时开关

**`DEFAULT_CONFIG["actions"]` 加**：

```python
"tri_multi_vote": True,   # [v1.22.1 P4] ON/OFF 对照用；默认 ON
```

**`_run_layer` / `_b_pre_layer` 调用点**：

```python
if _action_on(self.config, "tri_multi_vote"):
    self._tri_agree, self._tri_total, self._calibration_queue = \
        self._adjudicate_sub_tristate_multi(subs, question, n=3)
else:
    self._tri_agree, self._tri_total = \
        self._adjudicate_sub_tristate(subs, question)
    self._calibration_queue = []
```

#### Step P4.2 建对照脚本 `_run_v1221_p4.py`

```python
import subprocess, sys, os, json
from pathlib import Path

Q = "订单系统要保证不超卖又要不卡顿。CAP 约束下，下单链路怎么设计？"

for arm in ("ON", "OFF"):
    os.environ["DGTF_TRI_MULTI_VOTE"] = "1" if arm == "ON" else "0"
    for i in range(1, 4):
        out = Path(f"runs/v1221/p4_{arm}_{i}")
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            sys.executable, "元DGTF-V1.22.1-rc2.py", Q,
            "--route", "1", "--rounds", "1:4",
            "--parallel", "serial", "--quiet",
            "--actions-off", "self_check" if arm == "OFF" else "",
        ], env=os.environ)
```

**注意**：`--actions-off` 不是本脚本要用的；ON/OFF 靠 `tri_multi_vote` 开关。上面骨架里的 `--actions-off` 是错的，**实际脚本要传的是 `tri_multi_vote` 的环境变量或配置覆盖**。任务书此处给出原则，实现时以 `tri_multi_vote` 开关为准。

#### Step P4.3 汇总

```bash
python - <<'EOF'
import glob, re, json
from pathlib import Path

def parse_consistency(md):
    text = Path(md).read_text(encoding="utf-8")
    m = re.search(r"三态多票.*?high (\d+).*?medium (\d+).*?low (\d+).*?共 (\d+)", text)
    if not m:
        return None
    high, med, low, tot = map(int, m.groups())
    return {"high": high, "medium": med, "low": low, "total": tot,
            "consistency": (high + med) / tot}

out = {}
for arm in ("ON", "OFF"):
    vals = []
    for f in sorted(glob.glob(f"outputs/*.md"))[-6:]:
        r = parse_consistency(f)
        if r: vals.append(r)
    out[arm] = vals

json.dump(out, open("_v1221_p4_consistency.json", "w"),
          ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
EOF
```

**核对**：

```bash
python - <<'EOF'
import json
d = json.load(open("_v1221_p4_consistency.json"))
on = [x["consistency"] for x in d["ON"]]
off = [x["consistency"] for x in d["OFF"]]
print(f"ON  平均 = {sum(on)/len(on):.2%}  n={len(on)}")
print(f"OFF 平均 = {sum(off)/len(off):.2%}  n={len(off)}")
print(f"差值 = {(sum(on)/len(on)) - (sum(off)/len(off)):+.2%}")
EOF
```

#### Step P4.4 判定规则

- 若 `ON 平均 - OFF 平均 ≥ +10%`：**多票更好**
- 若 `|ON - OFF| < 5%`：**多票没做坏，也没做出改善**
- 若 `ON - OFF ≤ -5%`：**多票拖后腿**
- 判据**两向**：不仅要看差值，还要看组内极差（ON 组内、OFF 组内的最大-最小），若组内极差 ≥ 组间差，则**无结论**（本项目纪律）

#### Step P4.5 验收

```bash
python _v122_verify.py --phase p4 --src 元DGTF-V1.22.1-rc2.py
echo "EXIT=$?"
```

**通过判据**：

- □ ON / OFF 各 ≥ 3 次跑完
- □ `_v1221_p4_consistency.json` 生成
- □ 组内极差与组间差都写进报告
- □ 结论按 P4.4 四档之一给出

**报告**：`v1221_p4_报告.md`。

---

## P5 · auto 取向回填

### P5.1 目标

`plan_orientation` 的真实判定结果写进产物头部；`auto` 判成 boundary 却渲染 decision 模板这种错配**可查**。

### P5.2 Step 清单

#### Step P5.1 `run()` 记 `self._auto_plan_used`

**`MetaDGTF.run` 里**，`_auto_plan` 调用后：

```python
if parallel_mode == "auto" and not rounds:
    plan = self._auto_plan(question)
    self._auto_plan_used = plan
    ...
```

**`_auto_plan` 内**：把 `plan_orientation` 的真实结果带出（如果它走了那一段）：

```python
def _auto_plan(self, question):
    result = auto_plan(question, self.config, llm=self.llm)
    return result
```

`auto_plan` 已经带 `orientation` 字段（v1.22.0 阶段 1 加的），把它带出来即可。

#### Step P5.2 头部渲染「取向判定」

**`save_result` 里，orientation 行之后**：

```python
_ap = result.get("_auto_plan_used") or {}
if _ap.get("orientation"):
    f.write(f"**取向判定（plan_orientation）**："
            f"{_ap['orientation']}"
            f"（{_ap.get('_orientation_reason', '')[:60]}）\n\n")
```

#### Step P5.3 错配告警

**在 `save_result` 里**：

```python
_actual = (_ap.get("orientation") or "").strip()
_declared = (result.get("orientation") or "auto").strip()
if _actual and _declared == "auto" and _actual != "decision":
    f.write(f"⚠️ **取向错配**：plan_orientation 判为 "
            f"`{_actual}`，但 orientation 未指定（按 decision 渲染）。"
            f"如想用 boundary 模板，请显式传 `--orientation boundary`。\n\n")
```

#### Step P5.4 `_pack_result` 挂 `_auto_plan_used`

```python
"_auto_plan_used": dict(getattr(self, "_auto_plan_used", None) or {}),
```

#### Step P5.5 冒烟 `check_v1221_p5`

```python
def check_v1221_p5(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    src = open(SRC, encoding="utf-8").read()
    assert "_auto_plan_used" in src
    assert "取向判定（plan_orientation）" in src
    assert "取向错配" in src
    return True
```

#### Step P5.6 验收

**命令**：

```bash
python 元DGTF-V1.22.1-rc3.py "地铁运营效率该怎么衡量？" \
  --route 0,1,both,all --rounds "0:4,1:4,both:4,all:5" \
  --parallel auto --quiet
LATEST=$(ls -t outputs/*.md | head -1)
grep -E "取向判定|取向错配" $LATEST
```

**期望**：至少命中一行。

**通过判据**：

- □ 产物头部含「取向判定（plan_orientation）」
- □ auto 且判 boundary 时含「取向错配」告警
- □ 显式传 `--orientation boundary` 时**不含**告警（负对照）

**报告**：`v1221_p5_报告.md`。

---

## P6 · tier 缺省时的显式提示

### P6.1 目标

若**全部**锚点 tier 缺省（1 条显式都没有），产物加一行警告。

### P6.2 Step 清单

#### Step P6.1 `_load_anchors` 检测

**在 `_load_anchors` 尾部**：

```python
_n_explicit = sum(1 for a in out if "tier" in a and a["tier"] is not None)
if out and _n_explicit == 0:
    self._anchor_err = (self._anchor_err + ";" if self._anchor_err else "") + \
        f"全部 {len(out)} 条锚点未显式声明 tier（缺省 3 > tier_floor 2），" \
        f"引用表将收不到任何锚点"
    logger.warning("锚点 tier 全部缺省：%s", self._anchor_err)
```

**新增实例字段**：`self._anchor_tier_warning: str = ""`，承载这条警告。

#### Step P6.2 头部渲染

**`save_result` 锚点行之后**：

```python
if result.get("_anchor_tier_warning"):
    f.write(f"⚠️ **锚点 tier 警告**：{result['_anchor_tier_warning']}\n\n")
```

#### Step P6.3 `_pack_result` 挂字段

```python
"_anchor_tier_warning": getattr(self, "_anchor_tier_warning", ""),
```

#### Step P6.4 冒烟 `check_v1221_p6`

```python
def check_v1221_p6(SRC):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    src = open(SRC, encoding="utf-8").read()
    assert "_anchor_tier_warning" in src
    assert "锚点 tier 警告" in src
    # 逻辑测试：全缺省 → 警告；有一条显式 → 无警告
    pool = m.Pool()
    pool.anchors = [{"id": "a1", "claim": "X"}]
    pool.anchor_as_evidence = True
    tbl = m._citation_table(None, pool)
    assert not any(c.startswith("X") for c, _ in tbl)  # 无 tier → 不进表
    pool2 = m.Pool()
    pool2.anchors = [{"id": "a2", "claim": "Y", "tier": 1}]
    pool2.anchor_as_evidence = True
    tbl2 = m._citation_table(None, pool2)
    assert any(c.startswith("X") for c, _ in tbl2)
    return True
```

#### Step P6.5 验收

**命令**：

```bash
# 造一个所有锚点都没 tier 的 JSON，跑一次
cat > _test_anchors_notier.json <<'JSON'
{"anchors": [{"id": "a1", "claim": "x"}, {"id": "a2", "claim": "y"}]}
JSON
python - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("dgtf", "元DGTF-V1.22.1-rc3.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cfg = m.DEFAULT_CONFIG.copy()
cfg["external_anchor"] = dict(cfg["external_anchor"])
cfg["external_anchor"].update({
    "enabled": True, "path": "_test_anchors_notier.json",
    "as_evidence": "evidence", "tier_floor": 2,
})
meta = m.MetaDGTF(cfg)
res = meta.run("测试", route=["0"], rounds="0:1")
m.save_result(res, "outputs")
EOF
LATEST=$(ls -t outputs/*.md | head -1)
grep "锚点 tier 警告" $LATEST
```

**期望**：1 行命中。

**通过判据**：

- □ 全缺省时产物含「锚点 tier 警告」
- □ 有任一条显式 tier 时**不含**（负对照）
- □ `_citation_table` 对无 tier 锚点仍拒绝入表（红线保留）

**报告**：`v1221_p6_报告.md`。

---

## 第二档验收

```bash
python _v122_verify.py --phase p4 --src 元DGTF-V1.22.1-rc3.py && \
python _v122_verify.py --phase p5 --src 元DGTF-V1.22.1-rc3.py && \
python _v122_verify.py --phase p6 --src 元DGTF-V1.22.1-rc3.py
echo "EXIT=$?"
```

**通过判据**：三档全绿 + 三份报告齐 + P4 组内/组间差都写进报告。

**未通过就停在这里。**

---

# 第三档：明确不做（只出说明）

## P7 · 只出说明，不动代码

### P7.1 目标

把「明确不做」的三件事，**以决策记录的形式写进产物**，保证下一版看到时不会重开。

### P7.2 Step 清单

#### Step P7.1 写 `docs/不做什么-v1221.md`

三条：

```markdown
# v1.22.1 · 明确不做的三件事

## 1. 不拆模块

依据：`docs/拆模块方案-v122.md` 实测 —— 顶层符号 201、依赖边 384、
双向边 10 对、跨候选模块边 48%。

前置条件（未完成前不拆）：
- 12 处字面串判据要改成按模块 glob
- 2 处单文件比对要改成多文件口径
- `other` 里 136 个符号要先立命名法

## 2. 不扩动词白名单 / 不放宽 min_actions

依据：v1.22.0 阶段 3 报告第七节 —— 扩白名单是"把判据拟合到数据"，
放宽 `min_actions` 是"改阈值"。任务书明令禁止。

正路：P1 已做（研究层 schema 直接产 actions），不再走词法拟合。

## 3. 不删任何机制

依据：v1.22 六阶段 + 本收尾，累计 3 次红线判定，全部要求 `count_del_lines = 0`。
即使 P3 判「条件不可达」的机制，**本版也不删** —— 归档到 `pending_fix`，
由下一版在拿到 ≥3 题负对照后再决定。
```

#### Step P7.2 `save_result` 头部不提这三件事

**理由**：这三件事是**决策记录**，不是产物级告警。不进头部，避免噪音。

#### Step P7.3 冒烟 `check_v1221_p7`

```python
def check_v1221_p7():
    from pathlib import Path
    assert Path("docs/不做什么-v1221.md").exists()
    text = Path("docs/不做什么-v1221.md").read_text(encoding="utf-8")
    assert "不拆模块" in text
    assert "不扩动词白名单" in text
    assert "不删任何机制" in text
    return True
```

#### Step P7.4 验收

```bash
python _v122_verify.py --phase p7 --src 元DGTF-V1.22.1.py
echo "EXIT=$?"
```

**通过判据**：

- □ `docs/不做什么-v1221.md` 存在
- □ 三条都在
- □ 引擎一行未动（`diff 元DGTF-V1.22.1-rc3.py 元DGTF-V1.22.1.py` 只含版本号与 changelog 差异）

---

# 全局收尾

## Step F.1 全量重跑

```bash
python bench/bench_run.py --src 元DGTF-V1.22.1.py --jobs 5 \
  --profile economy --rounds "0:2,1:2,both:2,all:3" --tag v1221_full
python bench/bench_report.py bench/runs/v1221_full > bench/reports/v1221_full.md
```

**通过判据**：

- 20 / 20 产物
- rubric 平均 ≥ 2/3（P1 的直接效果）
- 一致率 ≥ 50% 的题数 ≥ 16/20（P4 的间接效果，若 ON）

## Step F.2 版本定稿

- `__version__ = "1.22.1"`
- changelog 加 `v1.22.1 相对 v1.22.0`，三档分段

## Step F.3 `v1221_报告.md`

```
一、总览：三档目标、判据、结论
二、P1：研究层结构化 actions（重点）
三、P2：triage 挂结构标签
四、P3：仅源码机制负对照
五、P4：一致率 ON/OFF
六、P5：auto 取向回填
七、P6：tier 缺省提示
八、P7：明确不做（只记录）
九、全量回归
十、遗留与下一版候选
```

## Step F.4 交付物清单核对

```bash
python - <<'EOF'
import sys
from pathlib import Path
req = [
    "元DGTF-V1.22.1.py",
    "smoke_test.py",
    "_v122_verify.py",
    "_probe_v1221_p1.py", "_probe_v1221_p2.py", "_probe_v1221_p3.py",
    "_probe_v1221_p4.py", "_probe_v1221_p5.py", "_probe_v1221_p6.py",
    "_negctl_v1221_p3.py", "_negctl_v1221_p3.json",
    "_run_v1221_p4.py", "_v1221_p4_consistency.json",
    "docs/机制负对照-v1221.md",
    "docs/不做什么-v1221.md",
    "v1221_p1_报告.md", "v1221_p2_报告.md", "v1221_p3_报告.md",
    "v1221_p4_报告.md", "v1221_p5_报告.md", "v1221_p6_报告.md",
    "v1221_报告.md",
    "bench/reports/v1221_full.md",
]
missing = [r for r in req if not Path(r).exists()]
print(f"缺失: {missing}")
sys.exit(1 if missing else 0)
EOF
```

**期望**：`缺失: []`。

---

# 附录 · 每档验收脚本扩展

`_v122_verify.py` 加：

```python
def phase_p1(src): ...
def phase_p2(src): ...
def phase_p3(src): ...
def phase_p4(src): ...
def phase_p5(src): ...
def phase_p6(src): ...
def phase_p7(src): ...   # 只查 docs/不做什么-v1221.md

# main 里注册
fns = {
    "p1": phase_p1, "p2": phase_p2, "p3": phase_p3,
    "p4": phase_p4, "p5": phase_p5, "p6": phase_p6, "p7": phase_p7,
    "all": ...,  # 保持六阶段
}
```

**追加运行**：

```bash
python _v122_verify.py --phase p1 --src 元DGTF-V1.22.1-rc1.py
```

---

# 执行顺序与禁令

## 执行顺序

```
第一档
  P1 → 验收
  P2 → 验收
  P3 → 验收
  第一档整体验收
     ↓ 未通过停在这里
第二档
  P4 → 验收
  P5 → 验收
  P6 → 验收
  第二档整体验收
     ↓ 未通过停在这里
第三档
  P7 → 出说明（不动代码）
全局收尾
```

## 禁令

- 不许跳过任何一档的验收
- 不许一次改两个 P
- 不许改已有阈值 / 常量
- 不许删旧键、旧方法（本版 `count_del_lines` 必须 = 0）
- 不许把"拟合数据"当修好（扩动词白名单 / 放宽 min_actions / 把 `[外]` 塞进旧词表 —— 一律禁止）
- 不许把失败写进日志了事
- 不许在没有探针对照的情况下宣称"修好了"
- 不许在报告里写"大致完成""基本可用"
- 不许在 P3 里删机制 —— 判「条件不可达」也只能进 `pending_fix`
- 不许在 P4 里因单次读数就下"多票更好"结论 —— 必须比组内极差与组间差

---

## 附：v1.22.1 相对 v1.22.0 的预期 changelog 骨架

```
v1.22.1 ── 三档收尾（研究层结构化 actions + triage 挂标签 + 仅源码机制负对照）

  【P1】研究层直接产出结构化 actions 段
    · decidable_product schema 加 actions[]
    · _extract_actions 改"schema 优先、词法兜底"
    · action_incomplete 语义改为"模型没按 schema 产出"
    · 3 题真跑：action ≥ 3 条 / rubric ≥ 2/3

  【P2】triage 触发条件改挂结构标签
    · _is_triage_candidate（结构标签 + 语义关键词）
    · _is_never_downgrade（真·自指不许降级）
    · 3 题真跑：≥ 1 题 triage ≥ 1 条

  【P3】仅源码机制负对照
    · 每条"仅源码"机制给负对照输入
    · 判定三分类：条件不可达 / 条件窄但成立 / 机制没工作
    · 本版不删任何机制

  【P4】一致率 ON/OFF 对照
    · tri_multi_vote 运行时开关
    · ON / OFF 各 ≥ 3 次，比组内极差与组间差

  【P5】auto 取向回填
    · plan_orientation 结果写进产物头部
    · auto 判 boundary 但渲染 decision 时给出错配告警

  【P6】tier 缺省显式提示
    · 全部锚点 tier 缺省时，产物加一行警告

  【P7】明确不做（只记录）
    · 不拆模块 / 不扩白名单 / 不删机制
    · docs/不做什么-v1221.md
```

---

## 用户追加要求（2026-10-05，非任务书原文）

- `TAVILY_API_KEY` 已放进 `.env`，要求**一并验收**锚点真检索链路。
  实测（本会话已完成）：引擎顶部 `load_dotenv()` 在导入时生效 →
  `os.environ["TAVILY_API_KEY"]` 存在（58 字符）→
  `AnchorRetriever("tavily", key, 24).search([...])` 返回 3 条真实结果。
