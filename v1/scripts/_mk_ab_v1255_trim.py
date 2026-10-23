# -*- coding: utf-8 -*-
"""给 `_ab_v1255_对表.md` 追加 §七：`shape_limit=8` 有没有过裁（用现有产物判，不跑）。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_ab_v1255_对表.md"
s = p.read_text(encoding="utf-8")

ADD = """

---

## 七、`shape_limit=8` 是不是**过裁**？（用现有产物判，零成本）

`shape_limit` 裁的是**喂进上下文的形状**，所以它省 token 的同时最可能的副作用是：
模型看不到足够上下文 ⇒ **重复输出**、**断链**、**携带被丢**。这三样产物里都有读数：

| 指标 | 含义 | A | B | 谁好 |
|---|---|---|---|---|
| `rephrase_ratio`（对撞） | 复述比，越高越像在原地重说 | **0.176** | **0.064** | **B**（复述少了 64%） |
| `rephrase_ratio`（元） | 同上 | **0.309** | **0.108** | **B**（复述少了 65%） |
| `probe_link_dangling` 四层合计 | 探针指向不存在的线头 | 12 | **10** | **B** |
| `carry_dropped` / `carry_dropped_all` | 携带被丢 | 0 / 0 | 0 / 0 | 平 |
| `probe_skipped` | 探针被跳过 | False | False | 平 |
| `candidates_backfilled`（元） | 候选后补（内容压力信号） | sc:5 | sc:6 | A 略好 |
| `polarity_all_same_structural` | 池极性全同 | 有（研究/对撞） | 有（元） | 各有 |
| `probe_no_target_covered` | 探针没覆盖到目标 | 无 | **研究层有** | A |

### 判读

**没有「过裁」的证据，反而相反**：B 的复述比只有 A 的 **1/3**（0.064 vs 0.176、0.108 vs 0.309），
断链也少 2 条，携带一条没丢。合起来说明：

> 裁掉的是**反复喂进上下文的冗余**，不是信息。上下文短了，模型反而**更少复述**。

唯一的负面信号是两处小的：元层后补 6 vs 5、研究层多一个 `probe_no_target_covered`。
两者都不足以说明"裁过头"，但也不能忽略 —— 记在这里，等 `shape_limit` 取 6/12 的对照
时一起看。

### 对 `shape_limit` 的建议

1. **8 可以保持**（当前唯一有正收益、且无过裁证据的键）。
2. 想进一步压成本，下一步该做的是**取值扫描**（6 / 8 / 12，各一跑），看
   `tokens/call` 与 `rephrase_ratio` 的曲线在哪拐 —— 而不是再加新键。
3. ★ 注意：`rephrase_ratio` 只在对撞层/元层有值（修行/研究层为 null），
   所以"过裁"的判断**只能在这两层做**；如果要判修行层，得先补这个读数。
"""

assert "## 七、`shape_limit=8`" not in s, "已追加过（幂等）"
p.write_text(s.rstrip() + ADD, encoding="utf-8")
print("已追加 §七（%d 字符）" % len(ADD))
