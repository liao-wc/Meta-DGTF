#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 打补丁 Step5：covers 数字编号分支增加语义校验。

现状（v1.23.25 / 基线已量化）：
    m = re.match(r"^T?(\\d+)$", c)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(untouched_items):
            has_touch = True      # ★ 编号在范围内即通过，不校验语义
            break

改成：编号在范围内**还要**语义对得上（探针问题 vs 该未触及项）。
阈值用 `_QC_DUP_SIM`（0.70）—— 与非数字分支同一把尺子，避免出现
「两条分支用两个标准」。

★ 语义比较必须用**探针的 question** 比 **untouched 目标文本**。
  两个 `untouched_items` 之间比是错的（那是清单内部一致性，不是覆盖）。

铁律：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换（断言各命中 1 次）
-> 转回 CRLF -> 断言 -> write_bytes。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.26.py"

b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0
txt = b.decode("utf-8").replace("\r\n", "\n")

OLD = '''            has_touch = False
            covers_seen = False
            for p in view.probes:
                for c in (p.get("covers") or []):
                    c = str(c).strip()
                    if not c:
                        continue
                    covers_seen = True
                    m = re.match(r"^T?(\\d+)$", c)
                    if m:
                        idx = int(m.group(1)) - 1
                        if 0 <= idx < len(untouched_items):
                            has_touch = True
                            break
                    else:
                        if any(_similar(c, d, _QC_DUP_SIM)
                               for d in untouched_items):
                            has_touch = True
                            break
                if has_touch:
                    break
'''

NEW = '''            has_touch = False
            covers_seen = False
            for p in view.probes:
                _pq = str(p.get("question", "")).strip()
                _pc = [str(x).strip() for x in (p.get("covers") or [])
                       if str(x).strip()]
                for c in (p.get("covers") or []):
                    c = str(c).strip()
                    if not c:
                        continue
                    covers_seen = True
                    m = re.match(r"^T?(\\d+)$", c)
                    if m:
                        idx = int(m.group(1)) - 1
                        if 0 <= idx < len(untouched_items):
                            # ★ 编号合法只是**必要条件**：还要语义对得上。
                            #   原来这里直接 has_touch = True，covers 乱指
                            #   T1 也算覆盖 —— 负对照实测不报。
                            #   比较对象是**探针问题 vs 该项**（不是两项互比）。
                            if (_similar(_pq, untouched_items[idx],
                                         _QC_DUP_SIM)
                                    or _overlap_coef(_pq,
                                                     untouched_items[idx])
                                    >= _COV_OVERLAP_MIN):
                                has_touch = True
                                break
                    else:
                        if any(_similar(c, d, _QC_DUP_SIM)
                               for d in untouched_items):
                            has_touch = True
                            break
                if has_touch:
                    break
'''

assert txt.count(OLD) == 1, f"covers 判据体命中 {txt.count(OLD)} 次"
txt = txt.replace(OLD, NEW, 1)

# ---------- 新增常量 ----------
OLD_C = '''_QC_DUP_SIM = 0.70     # 质量检查：候选彼此的重叠
'''
NEW_C = '''_QC_DUP_SIM = 0.70     # 质量检查：候选彼此的重叠
_COV_OVERLAP_MIN = 0.50  # covers 语言判据：探针问题与未触及项的 overlap 下限
'''
assert txt.count(OLD_C) == 1
txt = txt.replace(OLD_C, NEW_C, 1)

# ---------- 断言 ----------
assert "_COV_OVERLAP_MIN" in txt
assert txt.count("_COV_OVERLAP_MIN") == 2
assert "if (_similar(_pq, untouched_items[idx]," in txt
assert "_pc = [str(x).strip() for x in (p.get(\"covers\") or [])" in txt
# 旧的无条件 True 已消失
_i = txt.find('            has_touch = False\n            covers_seen = False')
_j = txt.find("if not has_touch:", _i)
_body = txt[_i:_j]
assert "if 0 <= idx < len(untouched_items):\n                            has_touch = True" not in _body

out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n")
assert out.count(b"\r") == out.count(b"\r\n")
assert out.count(b"\r\r\n") == 0
SRC.write_bytes(out)

print("OK Step5: covers 数字分支加语义校验 + _COV_OVERLAP_MIN")
print("lines =", out.count(b"\n"), "bytes =", len(out))
