# -*- coding: utf-8 -*-
"""给 `_ab_v1255_对表.md` 追加 §十一：`gain_floor` 与「层目标停因」重复（真实跑证据）。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_ab_v1255_对表.md"
s = p.read_text(encoding="utf-8")

ADD = """

---

## 十一、真实跑把 B 的意义打掉了：`gain_floor` 与「层目标停因」重复

换完信号（v1.23.59）立刻真跑一次（修行层、`gain_floor=0.01`、6 圈上限，
实花 **31 calls / 123,546 tokens ≈ ¥0.3 / 7.5 min**）：

```
完成 7.5 min | calls=31 tokens=123546 | 圈=3 | goal_trace 条数=3
n_aspects 序列: [10, 14, 9]
停因: 修行目标已达成（层面边际新增率 0.000 < 0.10，Heaps 饱和 ⇒ 挖到不能再挖），螺旋停止
```

**信号确实活了** —— `goal_trace` 三圈三条、`n_aspects` 有值（之前是 None）。
但它停在第 3 圈，停因是**「修行目标已达成」**，不是 `gain_floor`。

### 为什么抢不过

`_goal_stop_signal` 的顺序是 **先问层目标，命中就返回**：

```python
_hit, _why = layer_goal_stop_signal(entry, _now, _tr)
if _hit:
    return _hit, _why          # ← 层目标先表态，直接返回
...
if _gf > 0:
    return layer_gain_stop_signal(entry, _now, _tr, _gf)
```

而**四层各自都有目标停因**（`layer_goal_stop_signal` 的 docstring 原话）：

| 层 | 层目标停因 |
|---|---|
| `0` 修行 | `excavate < _LG_STOP_MARGIN(0.10)` ⇒ 层面挖尽 |
| `1` 研究 | `settle` 连续 `N` 圈不涨 |
| `both` 对撞 | `fuse` 连续不涨 **或** `sem_stagnation` 触顶 |
| `all` 元 | `crystallize >= 1.0`（四件事齐） |

这几条与 `gain_floor` 的语义**高度重叠**（"这层没进展了就停"），但触发条件
**更宽**（达标即停，而 `gain_floor` 要连续 2 圈都低）。所以在修行层：
`excavate` 一旦算得出来且 < 0.10，**当圈就停**，`gain_floor` 永远轮不到。

### 结论（这条要改口）

> **`gain_floor` 不是"信号稀疏"这一个问题 —— 它是「层目标停因」的重复实现，
> 而后者更早、更宽。** 换信号让它在原理上可达，但在真实跑里仍是**冗余兜底**。

### 对「五个键」总账的修订

| 键 | 判决（修订后） |
|---|---|
| `spiral.shape_limit` | **赚**（−8.8% tokens，无过裁） |
| `stop.gain_floor` | **冗余**：语义被"层目标停因"覆盖，且触发更严。建议**保留代码、默认关**，不要让它在出厂配置里出现 |
| `memory.eml_adaptive` | 生效但被质量闸挡住（门槛降到 1 也没东西可升） |
| `memory.eml_semantic_merge` | 本次没机会（无近重候选），单元判据已覆盖 |
| `duty.span_tolerant` | 度量口径，不是变量 |

### 这次换信号白做了吗？

**没有，但价值要重新说**：
- 它把一个"读数恒 None"的通道修成了"有值"——这是**必要前提**，不是充分条件；
- 它让 `gain_floor` 在**没有层目标停因的场景**（将来若新增层、或某层目标读数长期缺失）
  仍能作为兜底工作；
- 更重要的是它暴露了上面那条**重复实现** —— 这个信息比修好一个冗余键值钱。

**教训**：修一个"零触发"的键之前，先问一句「**它想拦的情况，是不是已经有别的东西在拦？**」
否则修好了也还是零触发，然后你会以为"修得不对"。
"""

assert "## 十一、真实跑把 B 的意义打掉了" not in s, "已追加过（幂等）"
p.write_text(s.rstrip() + ADD, encoding="utf-8")
print("已追加 §十一（%d 字符）" % len(ADD))
