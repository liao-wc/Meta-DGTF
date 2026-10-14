# -*- coding: utf-8 -*-
"""追加今日记忆第十二节：候选产出率的**时序缺陷**（真实入口探针逮到）。"""
import io, os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".workbuddy", "memory", "2026-10-14.md")
ADD = u"""
---

## 十二、★ 候选产出率的**时序缺陷**（真实入口探针逮到；第 3 类失败形态再现）

### 怎么发现的
收尾时按铁律补「真实入口产出」验证 —— 写 `_probe_v12333_candyield.py`：
复用 smoke_test 的全局 mock（`mod.LLM.call = fake_call`）⇒ **零花费**但走
**真实引擎路径** `MetaDGTF.run(...)`，猴补丁包一层 `candidate_yield` 计数。

**四问结果**：
- Q1 `candidate_yield` 被调 **2 次**（接线上，看着没问题）
- Q2 两次返回 `verdict` 都是 **`''`**（缺输入不表态）
- Q3 `quant_readings` 里**没有**这个键 ⇒ **读数永不落盘**

⇒ 调用点可达、纯函数正确、判据 ㉜ 全绿 —— **但真实跑下来一条读数都没有**。

### 根因（本项目第 3 类失败：**时序颠倒**）
`MetaDGTF` 圈循环里每圈
```python
for r in range(_total_rounds):
    ...
    dg = DGTF(entry, self.llm, self.config)   # ← 每圈**新建实例**
    view = dg.run(inp)                        # ← 每圈**新建 view**
```
⇒ 我把「上一圈候选」写在 `view._prev_cand_descs` 上 ⇒ **下一圈必然读不到**
⇒ 恒 `None` ⇒ 永久「缺输入不表态」。

### 修法（不动任何签名）
`inp.pool` = `self.pools[entry]` —— **每层一个、跨圈复用**（`pool = self.pools[entry]`
在 `for r` **之外**），是天然的历史载体 ⇒ `_prev_cand_descs` 改挂 `inp.pool`。
补丁 `_patch_v12333_candyield_ts.py`。

★ 修后探针：第 1 圈 `verdict=''`（无历史，正确）/ 第 2 圈
`n=2 n_new=0 new_ratio=0.0 max_sim=1.0 verdict='collapsed'`（mock 两圈候选相同，
正确）⇒ `quant_readings` 有键。

### ★ 顺带查了「两条通道」漂移（本项目高频事故）
`_probe_v12333_candyield_par.py`：serial / B / C **三通道**各跑一遍，
落盘层都是 `['0','1']`，值**逐字相同** ⇒ 无漂移（接线在 `DGTF.run` 内部，
两通道共用）。

### 新判据 ㉞（真实入口产出）+ 新变异体 M54
- **㉞**：跑一次 `MetaDGTF.run`（等价 mock 路径），断言
  `views["0"].quant_readings` 里**真的有** `candidate_yield` 键、
  形态含 `verdict`、mock 下两圈相同**必须判 collapsed**。
  另加一条源码守卫：`view._prev_cand_descs` **不许出现**（挂回每圈重建的对象）。
- **M54**：把历史挂回 `view` ⇒ 判红。
- ★ 同期修掉 ㉜ 的**锚过脆**：原判据钉了
  `candidate_yield([getattr(c, "desc", "")` 这一整行字面 —— 参数一折行就失配
  （干净基线当场判红）。改成**压掉全部空白后查语义**
  （`candidate_yield( [getattr(c, "desc", "") for c in candidates]`）。
  ⇒ 通则：**锚不能钉在会变的东西上**（换行格式也算「会变的东西」）。

### 续记通则（本日第三次同族）
> 本项目三类「走不到」：① 结构性不可达 ② 有值但零信息量 ③ **时序颠倒**。
> ③ 的特征是「代码全对、接线全在」—— **只有跑真实入口才看得见**。
> 判据必须落**产出**（`quant_readings` 有键），不能落**调用点存在**。
"""


def main():
    if "## 十二、★ 候选产出率的**时序缺陷**" in io.open(P, encoding="utf-8").read():
        print("已存在第十二节"); return
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "记忆应为 LF-only"
    s = raw.decode("utf-8").rstrip("\n") + "\n" + ADD
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK 第十二节已追加，行数 %d" % s.count("\n"))


main()
