#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3] 主文件补丁 C：子问题 `id` 规范化成 1..n（不再由模型决定）。

发现路径：审计探针新增的 L 类（「读模型返回的 id 必须归一化」）报出
`_parse_subs`(11051) 与 `_decompose_from_pool`(11192) 两处 —— 这两处不是
「票错位」，是**子问题 id 直接来自模型**：

    sid = int(sq.get("id", len(out) + 1))

模型有时给 0 起、有时漏给（回落 `len(out)+1`）、有时重复 ⇒ 同一份 `subs`
里 id 可能是 0..n-1、可能有洞，而下游（三票 prompt 的编号、`sub_id` 留痕、
`sub_by_id` 查找、`answered_sub_ids` 的显示）都默认它是 **1..n**。

修法：新增 `_canonical_sub_ids(items)`（就地按位置重编号 1..n），
在两个解析器的出口调用。★ 子问题 id 是**本地的行号**，没有任何理由
由模型决定；规范化后三票 prompt 的编号与 `sub["id"]` 第一次真正一致。
"""
from pathlib import Path
import ast

P = Path(__file__).resolve().parent / "元DGTF-V1.23.3.py"
raw = P.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "主文件不是纯 CRLF"
s = raw.replace("\r\n", "\n")


def sub_once(old, new, tag):
    global s
    assert s.count(old) == 1, "%s：锚点命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new)
    print("  · %s" % tag)


# S3c 纯函数：放在 `_normalize_judgment_ids` 之后
sub_once('''def _thinking_stage(cfg, name):''',
         '''def _canonical_sub_ids(items):
    """[v1.23.3] 把子问题的 `id` 按**当前位置**重编号成 1..n（就地）。

    【为什么必须做】`_parse_subs` / `_decompose_from_pool` 的 id 直接来自
      模型（`int(sq.get("id", len(out) + 1))`）—— 模型有时给 0 起、有时漏给
      （回落成位置）、有时重复。于是同一份 `subs` 里 id 可能是 0..n-1、
      可能带洞，而下游一律默认它是 1..n：
        · 三票 prompt 用 `enumerate(subs, 1)` 编号；
        · `sub_id` 留痕 / `sub_by_id` 查找 / `answered_sub_ids` 的展示。
      id 是**本地的行号**，由模型决定没有任何好处，只有风险。
    【加性】条数、顺序、其他字段一律不动，只改 `id`。
    """
    for _i, _s in enumerate(items or [], 1):
        if isinstance(_s, dict):
            _s["id"] = _i
    return items


def _thinking_stage(cfg, name):''', "C1 _canonical_sub_ids")

# C2 _parse_subs 出口
sub_once('''            if len(out) >= 7:
                break
        return out''',
         '''            if len(out) >= 7:
                break
        # [v1.23.3] id 规范化：模型给的 id 不作为最终 id（见
        #   `_canonical_sub_ids` 的 docstring）。
        return _canonical_sub_ids(out)''', "C2 _parse_subs 出口")

# C3 _decompose_from_pool：解析循环之后、展示循环之前
sub_once('''            if len(out) >= 7:
                break

        for s in out:
            self.vp(f"      · [{s['decidability']}] {s['question'][:50]}"''',
         '''            if len(out) >= 7:
                break

        # [v1.23.3] id 规范化（与 `_parse_subs` 同源处理）。
        _canonical_sub_ids(out)

        for s in out:
            self.vp(f"      · [{s['decidability']}] {s['question'][:50]}"''',
         "C3 _decompose_from_pool")

# C4 changelog
sub_once("""      改为记**真票号**（无弃票时与改前逐字相同，只有弃票时才不同 ——
      而那时改前的值是错的）。
""",
         """      改为记**真票号**（无弃票时与改前逐字相同，只有弃票时才不同 ——
      而那时改前的值是错的）。
    ★ 审计探针新增的 L 类（「读模型返回的 id 必须归一化」）又报出两处
      **同类但不同点**的问题：`_parse_subs` / `_decompose_from_pool` 的
      子问题 id 直接取自模型（`int(sq.get("id", len(out) + 1))`）⇒ 可能是
      0 起 / 带洞 / 重复，而下游一律按 1..n 用。新增 `_canonical_sub_ids()`
      在出口处按位置重编号（加性：只改 id）。
""", "C4 changelog")

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
ast.parse(s)
P.write_bytes(out)
print("  · 已写 %s" % P.name)
