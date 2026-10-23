# v1.22.1 · P2b 收尾任务提示词 · triage 端到端打通

> 来源：https://chat.deepseek.com/share/e3uqm2wh5a7jzpuzlr
> 性质：单点续做，不是新档。归属第一档。
> 前置：P2a（触发条件改挂结构标签）已完成。
> 目标：把 P2 从「机制通过、效果未达标」推到「端到端通过」。
> 手段：**改匹配对象**，不改阈值、不改触发条件。

---

## 0. 角色与全局约束

### 0.1 角色

P2b 的唯一执行者。P2a 已落地（触发条件 14/14 命中）。现在卡在**第二道门**：
`_similar(und_aspect, anchor.claim, 0.6)` 中位数 0.000。
任务：在不改阈值、不改触发条件、不改宪法级原则的前提下，把第二道门打开。

### 0.2 宪法级约束（继承 + 追加四条）

1. **不动 `0.6`**：claim 路径阈值一个字不许改。
2. **不塞 `[外]` 进 `_TRIAGE_KEYS`**：触发条件本版不动。
3. **answer 路径复用既有常量**：`_overlap_coef` + `_UNTRACED_OVERLAP`（=0.6），不新造阈值。
4. **向后兼容**：`answers` 缺失的锚点走原 claim 路径；缺字段不许崩。

### 0.3 文件命名

| 用途 | 命名 |
|---|---|
| 主文件（改前） | `元DGTF-V1.22.1-rc1.py` |
| 主文件（改后） | `元DGTF-V1.22.1-rc1b.py` |
| 补丁脚本 | `_mk_v1221_p2b.py` |
| 探针 | `_probe_v1221_p2b.py` |
| 真跑脚本 | `_run_v1221_p2b.py` |
| 报告 | `v1221_p2b_报告.md` |
| 验收 | `_v122_verify.py --phase p2b` |

命令：`python _v122_verify.py --phase p2b --src 元DGTF-V1.22.1-rc1b.py` → 期望 PASS N / FAIL 0 / EXIT=0。

---

## 2. 数据结构设计

### 2.1 锚点新增 `answers`（可选 list[str]，每条 ≤40 字，单锚点 0~5 条）
- 未声明 `answers` → 回落 claim 路径。
- `answers` 不参与 tier 判定，只参与匹配。

### 2.2 匹配双路径（OR）
```
hit = (_hit_by_answers(und_aspect, anchor.answers)
       or _hit_by_claim(und_aspect, anchor.claim)) and (anchor.tier <= tier_floor)
```

### 2.3 匹配函数
```python
def _hit_by_answers(aspect, answers) -> bool:
    """用 _overlap_coef（分母取 min）而非 _similar（分母取 max）；
       阈值复用 _UNTRACED_OVERLAP（0.6），不新造。双向各查一次。"""
def _hit_by_claim(aspect, claim) -> bool:
    return _similar(aspect, claim, 0.6)     # P2a 一字不动
```

### 2.4 `_load_anchors` 读 answers
```python
"answers": [str(x)[:60] for x in (a.get("answers") or [])][:5],
```

### 2.5 `_anchor_crosscheck` 的 `_hit` 改双路径（§2.5 原文）。

### 2.6 未填 answers 时的留痕（推荐，不阻断）：`self._anchor_answers_warning`。

---

## 3. Step 清单

- **P2b.1** 锚点快照加 answers。判据：≥2 条锚点有非空 answers 且单条 ≤5 条。
- **P2b.2** 加 `_hit_by_answers` / `_hit_by_claim`（位置：`_UNTRACED_OVERLAP` 之后、`_citation_table` 之前）。
  断言：P2b.2.a 函数存在；.b claim 体内是 `_similar(..., 0.6)` 字面未改；.c 用 `_overlap_coef`+`_UNTRACED_OVERLAP`。
- **P2b.3** `_load_anchors` 读 answers。断言 `_anchors[0]["answers"] == [...]`。
- **P2b.4** `_anchor_crosscheck` 改 `_hit` 双路径。断言：两处字面串在；负对照（无 answers / answers 空 list）走 claim 路径。
- **P2b.5** 探针 `_probe_v1221_p2b.py`（A1~A2 / B1~B5 / C1~C2 / D1~D2 / E1）+ before/after diff。
- **P2b.6** 冒烟 `check_v1221_p2b`（9 条断言）。
- **P2b.7** 真跑 3 题（沿用 P2a 三题；route 0,1 / rounds 0:3,1:3）。
  **主判据 P2b.7.a：≥1 题 triage ≥ 1 条**；全 0 → 判未通过，不许改词表救。
- **P2b.8** 漂移观察项（**不判 pass/fail**）：排除 triage 引起的 und→partial 后，其余条数记录；
  ≤50% 标 ✅，>50% 如实报但不判失败。（理由：triage_downgrades 与 decidability_log 是两套记录。）
- **P2b.9** 端到端验收。
  □P2b.1 □P2b.2 □P2b.3 □P2b.4 □P2b.5 □P2b.6 □P2b.7（主判据） □P2b.8
  □`count_del_lines`=0 □`mechanism_removed`=0

**未通过就停在这里。** 不许改词表、不许改阈值、不许硬凑。

---

## 7. 明确不做

1. 不改 `0.6`。 2. 不塞 `[外]` 进 `_TRIAGE_KEYS`。 3. 不新造阈值。
4. 不删 claim 路径。 5. 不做 P2.4.b 漂移判据（降为观察项）。
6. 不硬凑 triage 数（3 题全 0 就判未通过）。 7. 不动 P2a 的成果。

## 8. 执行顺序
P2b.1 → .2 → .3 → .4 → .5 → .6 → .7（主判据）→ .8 → .9

**P2b 通过后，第一档整体重判，进入第二档。**
