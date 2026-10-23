# -*- coding: utf-8 -*-
"""按真实结果改写 `v12359_报告.md` §五（原计划段 → 实测段）。

★ 为什么用脚本文件而不是 `python -c`：这段文字里有反引号，shell 会把它当命令替换
  （本次又踩了一次，报 `unterminated triple-quoted string`）。
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "v12359_报告.md"
s = p.read_text(encoding="utf-8")

OLD = """## 五、还差一步：真实跑一次（≈¥0.5）

判据证的是**函数**能触发；但「引擎里这个键真的会在某一圈停下」还需要一次真跑。
计划：修行层、`gain_floor=0.01`、6 圈、上限 80 calls / 15 min，
看 `stop_reason` 里是否出现「增益趋零」，以及 `goal_trace` 里的 `n_aspects` 序列。

不跑的话，这一版只能说"信号通了"，不能说"这个键活了"。
"""

NEW = """## 五、真实跑的结果（¥0.3）—— 它没被 gain_floor 停，被**层目标停因**抢了

真跑：修行层、`gain_floor=0.01`、6 圈上限，实花 **31 calls / 123,546 tokens ≈ ¥0.3 / 7.5 min**：

```
完成 7.5 min | 圈=3 | goal_trace 条数=3
n_aspects 序列: [10, 14, 9]
停因: 修行目标已达成（层面边际新增率 0.000 < 0.10，Heaps 饱和 ⇒ 挖到不能再挖）
```

**信号确实活了**（三圈三条、`n_aspects` 有值，之前全是 None），但它停在第 3 圈，
停因是**「修行目标已达成」** —— 不是 `gain_floor`。

原因：`_goal_stop_signal` **先问层目标，命中就返回**；而**四层各自都有目标停因**
（修行 `excavate<0.10` / 研究 `settle` 不涨 / 对撞 `fuse` 不涨 / 元 `crystallize≥1`）。
这些与 `gain_floor` 语义高度重叠，但**触发更宽**（达标即停 vs 连续 2 圈都低）。

> ⇒ **`gain_floor` 不是"信号稀疏"单靠换信号就能救的 —— 它是「层目标停因」的重复实现。**
> 换信号让它原理上可达，真实跑里仍是**冗余兜底**。详见 `_ab_v1255_对表.md` §十一。

**所以这一版的真实价值**不是"让 gain_floor 活过来"，而是：
1. 把读数恒 None 的通道修成有值（必要前提）；
2. **暴露了"重复实现"这件事** —— 这比修好一个冗余键值钱。
"""

assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
p.write_text(s.replace(OLD, NEW), encoding="utf-8")
print("报告 §五 已按真实结果改写")
