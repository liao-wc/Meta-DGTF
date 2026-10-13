#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step6d：修 check_v12326_sim3 的 B 组判据。

原因：B 组第一版用「量子纠缠实验」vs「超导材料在低温下表现特殊」当
「不相干对」，但两者**共享「低温」**且 BM25 语料里恰有
「量子纠缠实验需要极低温环境」⇒ 词面重叠真实存在，分高是**对的**。
⇒ 不是 BM25 被抬高，是**负对照对选错了**。

修法：
  · 负对照换成**真正无关**的输入（「披萨烤制时长」）—— 实测 0.0000；
  · 去掉「相关对不许降分」这条 —— `_bm25_best(a)` 与 `_bm25_best(b)`
    各算各的，本就不保证单调（不是 BM25 的契约）。
"""
from pathlib import Path
import ast

SMOKE = Path(__file__).resolve().parent / "smoke_test.py"
b = SMOKE.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

OLD = '''    _no_c = mod._sim3("量子纠缠实验", "超导材料在低温下表现特殊")
    _wi_c = mod._sim3("量子纠缠实验", "超导材料在低温下表现特殊", _corpus)
    # 负对照：不相干对不该因 BM25 而升高
    if _wi_c >= _no_c + 0.2:
        bad.append(f"[B] 不相干对因 BM25 被抬高（{_no_c} -> {_wi_c}）")
    # 正对照：相关对在语料下应 >= 无语料
    _rel_a, _rel_b = "超导材料在低温下表现特殊", "低温下超导材料的特殊表现"
    if mod._sim3(_rel_a, _rel_b, _corpus) < mod._sim3(_rel_a, _rel_b) - 1e-9:
        bad.append("[B] 相关对在 BM25 语料下反而降分")
'''

NEW = '''    # ★ 负对照要选**真的不相干**的输入。第一版拿
    #   「量子纠缠实验」vs「超导材料在低温下表现特殊」当负对照是错的
    #   —— 两者共享「低温」，而语料里恰有「量子纠缠实验需要极低温环境」，
    #   词面重叠真实存在 ⇒ 分高是对的，不是「被抬高」。
    _irrelevant = "披萨烤制时长与面团发酵温度"
    if mod._bm25_best(_irrelevant, _corpus) > 0.0:
        bad.append(f"[B] 完全不相干的输入拿到了 BM25 分 "
                   f"（{mod._bm25_best(_irrelevant, _corpus)}），应为 0")
    # ★ 正对照：与语料真有词面重叠的输入必须拿到 > 0 的分
    _overlap_q = "量子纠缠实验"
    if mod._bm25_best(_overlap_q, _corpus) <= 0.0:
        bad.append("[B] 与语料有真实词面重叠的输入拿不到 BM25 分 ⇒ "
                   "通道没接上")
    # ★ BM25 通道确实改变最终分（不是「算了不用」）
    _q2, _c2 = "量子纠缠实验", "量子纠缠实验需要极低温环境"
    _s_no = mod._sim3(_q2, _c2)
    _s_yes = mod._sim3(_q2, _c2, _corpus)
    if not (_s_yes > _s_no):
        bad.append(f"[B] 有语料时未升分（{_s_no} -> {_s_yes}）⇒ "
                   f"BM25 通道没进合并式")
    # ★ 归一化必须把分压回 [0,1)（无上界的 raw 会破坏三层加权）
    _bm_raw_hi = mod._bm25_best(
        "量子纠缠实验需要极低温环境 人工智能模型部署管线优化 "
        "模型蒸馏可以压缩参数量 超导材料在低温下表现特殊", _corpus)
    if not (0.0 <= _bm_raw_hi < 1.0):
        bad.append(f"[B] BM25 归一化失效，分越界：{_bm_raw_hi}")
'''

assert txt.count(OLD) == 1, f"B 组判据命中 {txt.count(OLD)} 次"
txt = txt.replace(OLD, NEW, 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
SMOKE.write_bytes(out)
ast.parse(out.decode("utf-8"))
print("OK Step6d: B 组判据已修（负对照换成真不相干输入）")
print("lines =", out.count(b"\n"), "bytes =", len(out))
