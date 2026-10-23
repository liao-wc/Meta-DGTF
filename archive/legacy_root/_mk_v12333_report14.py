# -*- coding: utf-8 -*-
"""追加报告第十四节：候选产出率的时序缺陷（真实入口探针逮到）。"""
import io, os, sys

P = "v12333_报告.md"
ADD = u"""
---

## 十四、★ 候选产出率的**时序缺陷**：读数永不落盘（真实入口探针逮到）

### 14.1 怎么发现的 —— 按铁律主动补验证

本轮新增 `candidate_yield` 后，判据 ㉜ 是**纯函数 + 字面存在 + 位置**形态，
全绿。但本项目已经栽过两次同族问题：

| 次数 | 事由 | 形态 |
|---|---|---|
| v1.23.27 | 三条信念迁移在真实入口结构性不可达 | 第 1 类 |
| 本轮 | `_quant_note` 定义在 `MetaDGTF`、调用点在 `DGTF`（无继承） | 第 1 类 |
| 本轮 | **候选历史挂在每圈重建的 `view` 上** | **第 3 类（时序颠倒）** |

于是写了 `_probe_v12333_candyield.py`：**复用冒烟 mock**（`mod.LLM.call = fake_call`）
⇒ **零 API 花费**，但走的是**真实引擎路径** `MetaDGTF.run(...)`。
猴补丁包一层 `candidate_yield` 计数（不改主文件）。

### 14.2 四问结果（打点读数，不是「看代码」）

```
Q1 candidate_yield 调用次数 = 2
     第 1 次返回：n=3 n_new=None new_ratio=None max_sim=None verdict=''
     第 2 次返回：n=2 n_new=None new_ratio=None max_sim=None verdict=''
Q3 quant_readings 键 = ['ing_density', 'restate_fidelity']
     candidate_yield 值 = None
```

⇒ **调用点可达（2 次）、纯函数正确（`n` 有值）、判据全绿 —— 但读数一条都没有。**

### 14.3 根因：`view` 与 `DGTF` 实例**每圈新建**

```python
for r in range(_total_rounds):          # ← MetaDGTF 的圈循环
    pool = self.pools[entry]            # ← 跨圈存活（在 for 之外）
    ...
    dg = DGTF(entry, self.llm, self.config)   # ← 每圈**新建实例**
    view = dg.run(inp)                        # ← 每圈**新建 view**
```

我把「上一圈候选」写在 `view._prev_cand_descs` 上 ⇒ **下一圈必然读不到**
⇒ 恒 `None` ⇒ `candidate_yield` 永久走「缺输入不表态」分支 ⇒ `verdict=''`
⇒ `_quant_note` 的前置条件 `if _cy.get("verdict")` 不成立 ⇒ **不落盘**。

### 14.4 修法（不动任何签名）

`inp.pool` = `self.pools[entry]` —— **每层一个、跨圈复用**，是天然的历史载体。
把 `_prev_cand_descs` 从「每圈重建的 `view`」改挂「跨圈复用的 `pool`」。

★ 为什么**不**复用已有的 `view._expanded_descs`：它每圈被本圈候选覆盖
（`DGTF.run` 内），且语义是**「累积」**（累积由 `MetaDGTF.all_expanded_descs`
在圈末完成）—— 不是「上一圈」。硬套会引入第二处语义。
★ 也**不**新造第三份机制：只换**历史载体**，语义不变。

### 14.5 验收

· 修复后探针：第 1 圈 `verdict=''`（无历史，**正确**）/ 第 2 圈
  `n=2 n_new=0 new_ratio=0.0 max_sim=1.0 verdict='collapsed'`
  （mock 两圈候选完全相同 ⇒ 判 collapsed，**正确**）⇒ `quant_readings` 有键。
· **两条通道漂移检查**（本项目高频事故）：`_probe_v12333_candyield_par.py`
  跑 serial / B / C 三通道，落盘层都是 `['0','1']`、值**逐字相同** ⇒ **无漂移**。

### 14.6 新判据 ㉞ + 新变异体 M54

· **㉞ 真实入口产出**：跑一次 `MetaDGTF.run`（等价 mock 路径，零花费），断言
  ① `views["0"].quant_readings` 里**真有** `candidate_yield` 键；
  ② 落盘值含 `verdict`；
  ③ mock 下两圈候选相同**必须**判 `collapsed`；
  ④ 源码守卫：`view._prev_cand_descs` **不许出现**（挂回每圈重建的对象即判红）。
· **M54**：把历史挂回 `view` ⇒ 判红（干净基线先绿）。

### 14.7 ★ 同步修掉 ㉜ 的「锚过脆」

原判据钉的是**整行字面**：

```python
if 'candidate_yield([getattr(c, "desc", "")' not in src:   # ✗
```

本轮把参数一折行（
`candidate_yield(` 换行后接 `[getattr(...)]`），这条**立刻失配**
⇒ 干净基线当场判红。改成**压掉全部空白后查语义**：

```python
_flat_src = " ".join(src.replace(CRLF, LF).split())
if 'candidate_yield( [getattr(c, "desc", "") for c in candidates]' not in _flat_src:
```

⇒ 通则：**锚不能钉在会变的东西上** —— **换行格式也算「会变的东西」**。

### 14.8 本项目「走不到」三类形态（本轮补全第三类）

| 类型 | 特征 | 判据要求 |
|---|---|---|
| ① 结构性不可达 | 调用点被守卫/去重/默认值挡死 | 断言**产出**，非「有调用点」 |
| ② 有值但零信息量 | 能力可达、读数恒定 | 看**值的分布**，非「有没有值」 |
| ③ **时序颠倒** | 代码全对、接线全在，只是**读在写之前** | 跑**真实入口**、断言**产出落盘** |

③ 最隐蔽：判据查「调用点存在」会绿、查「纯函数正确」也会绿 ——
**只有跑一次真实入口、读出口，才看得见。**
"""

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), P)
raw = io.open(p, "rb").read()
assert raw.count(b"\r\n") == 0, "报告应为 LF-only"
s = raw.decode("utf-8")
if "## 十四、★ 候选产出率的**时序缺陷**" in s:
    print("已存在第十四节"); sys.exit(0)
s = s.rstrip("\n") + "\n" + ADD
io.open(p, "wb").write(s.encode("utf-8"))
print("OK 第十四节已追加，行数 %d" % s.count("\n"))
