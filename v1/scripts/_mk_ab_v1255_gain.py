# -*- coding: utf-8 -*-
"""给 `_ab_v1255_对表.md` 追加 §八：`gain_floor` 是**结构性不可达**（不是阈值太严）。

★ 这条发现直接作废了"取值扫描 ¥12"的计划 —— 扫任何阈值都不会触发，
  因为判据需要的**历史长度**永远凑不够。
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_ab_v1255_对表.md"
s = p.read_text(encoding="utf-8")

ADD = """

---

## 八、追查「三个键零触发」：`gain_floor` 是**结构性不可达**

§六 说 `stop.gain_floor` 本跑未触发。当时以为是阈值太严，本来打算做取值扫描
（6/8/12 之类）。**追下去发现不是阈值问题 —— 它压根触发不了。**

### 证据链

1. `layer_gain_stop_signal(entry, goal, prev, gain_floor)` 的第一道门：

```python
_tr = list(prev or [])
if len(_tr) < int(_LG_STOP_FLAT_N) + 1:      # _LG_STOP_FLAT_N = 2 ⇒ 需要 ≥3 条历史
    return False, ""
```

2. `prev` 从哪来？`_goal_stop_signal` 里：`_tr = list(getattr(view, "goal_trace", None) or [])`
   —— **从当前 view 拿**。

3. 而引擎**每圈新建 view**（串行侧 `view = dg.run(inp)`，旁边注释原话：
   「跨圈累积 view.errors —— **每圈新建 view**、只 return 最后」）。
   `_layer_goal_now` 每圈 `view.goal_trace.append(...)` 追加到**当圈那个 view** 上
   ⇒ 下一圈换了新对象，**上一圈的记录就丢了**。

4. 产物实测印证：四个层都跑了 4~7 圈，但 `goal_trace` **每层只有 1 条**：

| 层 | `rounds_run` | `goal_trace` 条数 | 最后一条的 `round` |
|---|---:|---:|---:|
| 0 | 4 | **1** | 4 |
| 1 | 7 | **1** | 7 |
| both | 7 | **1** | 7 |
| all | 2 | **1** | 2 |

`round` 字段写的是"最后那一圈"的圈号 —— 正好说明**只剩最后一条**。

### 结论

`len(_tr)` 在停止判定那一刻**恒为 1** ⇒ `1 < 3` ⇒ **`stop.gain_floor` 在任何取值下都不会触发**。
这不是"阈值太严"，是**判据的输入通道断了**（我记忆里那三种失败形态的第 ①种：
结构性不可达 —— 调用点在、逻辑对，被数据流挡死）。

> ⇒ **取值扫描（原计划 ≈¥12）作废**：扫 6/8/12 会得到三个"零触发"，
> 然后被误读成"这个键没用"。**先证明它走得到，再谈它值多少。**

### 建议的修法（3 行，风险可控）

在每圈拿到新 view 之后、调用 `_layer_goal_now` 之前，把上一圈的 trace 接上：

```python
if last is not None and not view.goal_trace:
    view.goal_trace = list(last.goal_trace)
```

- **只搬数据，不动任何判据**；`gain_floor` 默认 0（关）⇒ 出厂行为逐字不变。
- 修好之后 `goal_trace` 会变长（每层每条）⇒ 产物体积略增、`_tr` 终于有意义。
- 需要配一条判据：**连续 3 圈 `gain < gain_floor` 必须真的停**（构造性，零成本）。

### 另外两个键（`eml_adaptive` / `eml_semantic_merge`）不是同一类问题

它们的触发条件分别是「候选快到升级阈值」与「有近重候选」，本轮条件**确实没出现**
（2 个候选、无近重、0 升级）—— 那是**条件未出现**，不是接线断了。
两者在冒烟里都有单元级判据（`check_v12344_eml_adaptive` /
`check_v12348_eml_semantic`），所以**不必**为它们造真实跑场景。
"""

assert "## 八、追查" not in s, "已追加过（幂等）"
p.write_text(s.rstrip() + ADD, encoding="utf-8")
print("已追加 §八（%d 字符）" % len(ADD))
