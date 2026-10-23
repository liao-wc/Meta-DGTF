# -*- coding: utf-8 -*-
"""给 `_ab_v1255_对表.md` 追加 §九：`gain_floor` 的**测量结果**（花 ¥0.4 实测）。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_ab_v1255_对表.md"
s = p.read_text(encoding="utf-8")

ADD = """

---

## 九、实测：`gain_floor` 依赖的读数**本身稀疏**（花 ¥0.4 得到的答案）

§八 修好了「历史不跨圈」，那只是第一层。修完立刻实测一次（只跑修行层，
`route=["0"]`、6 圈、`max_calls=80`/`max_minutes=15`，实花 **39 calls / 161,399 tokens ≈ ¥0.4**）。

### 结果

```
完成 8.8 min | calls=39 tokens=161399 | 圈=4 | goal_trace 条数=4

圈      excavate   n_aspects  增益
1      None       16         None
2      None       16         None
3      0.0        14         None
4      None       20         None
```

**跨圈携带生效了**（4 圈 → 4 条记录），但 `excavate` **4 圈里 3 圈是 None**。

### 为什么是 None

`excavate` = Heaps 边际新增率，`_lg_aspect_margin(hist, total)` 的两道门：

```python
xs = [float(x) for x in (hist or []) if x is not None]
if len(xs) >= 3:                      # ← 要 ≥3 圈历史才开算
    ...
    if early <= 1e-12:
        return 0.0 if late <= 1e-12 else None    # ← 退化增长还返回 None
```

而 `refinement_gain` 又有自己的一层：

```python
if _cur is None: return None
if _pv  is None: return None          # ← 上一圈没读数就"不表态"
```

于是要触发早停，得凑齐：**≥3 圈历史 × 相邻两圈都有非 None 的 excavate**。
4~6 圈的层里，非 None 的值本就只有 2~4 个，再要求"连续两个" —— 实际几乎凑不齐。

### 结论（这条彻底给取值扫描判死刑）

> **`stop.gain_floor` 在当前实现下不可用**。不是阈值问题（§八），
> 也不只是跨圈问题（§八修的那层），而是**它依赖的读数是稀疏的**。
> 扫 6/8/12 依然会得到三个"零触发" —— **¥12 省下来了**。

### 两条出路（要你选，别自己决定）

| 方案 | 做什么 | 代价 | 风险 |
|---|---|---|---|
| **A 承认不可用** | 把 `gain_floor` 从「可评估的新键」里摘出来，文档标注"依赖读数稀疏、当前不适用"，默认保持 0 | 0 | 少一个早停手段，但现状本来就是"没在用" |
| **B 换信号** | 增益改用 `n_aspects` 逐圈差（**永远有值**）而不是 Heaps 边际；语义仍是"新增趋零" | 一个版本 + 判据 | **改变 P-2 的语义定义**，等于重新设计这个键 |

我倾向 **A 先做、B 留作独立一版**：A 是把话说清楚（零风险），B 是改语义
（要重新论证"新增趋零"用什么度量才不跑偏，不能在半小时内拍板）。
"""

assert "## 九、实测" not in s, "已追加过（幂等）"
p.write_text(s.rstrip() + ADD, encoding="utf-8")
print("已追加 §九（%d 字符）" % len(ADD))
