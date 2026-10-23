# -*- coding: utf-8 -*-
"""修正 `_ab_v1255_对表.md` §七 第 3 条：`rephrase_ratio` 在 0/1 层是**无定义**，不是漏出口。

★ 我原来写「要判修行层，得先补这个读数」—— 查了实现后这是错的：
  `rephrase_ratio` 的定义是 `_detect_ing_rephrase(view.collision, _upstream_texts)`，
  **分子分母都在"与上游的重合"上**。修行层没有上游、研究层的碰撞对象不是 view，
  所以这两层那个数**结构上不存在**，补不出来。
  要判这两层"裁没裁过头"，得用**层内**的读数（候选重复度/新颖度）。
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_ab_v1255_对表.md"
s = p.read_text(encoding="utf-8")

OLD = """3. ★ 注意：`rephrase_ratio` 只在对撞层/元层有值（修行/研究层为 null），
   所以"过裁"的判断**只能在这两层做**；如果要判修行层，得先补这个读数。"""

NEW = """3. ★ 注意：`rephrase_ratio` **只在对撞层/元层有值**，修行/研究层是 `null`。
   查了实现才明白这不是"漏出口"，而是**结构上无定义** ——
   它的定义是「与**上游**的重合度」（`_detect_ing_rephrase(view.collision, _upstream_texts)`），
   而修行层没有上游、研究层的碰撞对象不是上游 view。**这两层补不出这个数。**
   ⇒ 要判这两层"裁没裁过头"，得另找**层内**读数（候选重复度 / 新颖度），
     不能拿"复述率缺失"当缺陷去修。"""

assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
p.write_text(s.replace(OLD, NEW), encoding="utf-8")
print("已修正 §七 第 3 条")
