#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step9：补 smoke 判据（结构层短路 + BM25 pair 方向）并修 M4 词。

变异体暴露的三条漏洞（M1/M3/M4），其中 M1/M4 是判据选样问题、M3 是判据缺口。
配合 Step8（实现修正）一起，让 8 个变异体全部可判红。

具体：
  · A 组补「结构层短路」判据：`T3/T3 == 1.0`、`T3/T4 == 0.0`
    —— M3（去掉结构层）必须判红；
  · B 组补「BM25 方向」判据：两条**各自与语料相关但彼此无关**的句子，
    在带语料时 sim3 必须仍为 0（不是 0.4+）—— M1'（用回 _bm25_best）判红；
  · B 组「语料不足降级」判据把查询词换成**语料里真实存在的词**
    —— 原判据用「测试」（不在语料里 ⇒ 本就 0）抓不到 M4。
"""
from pathlib import Path
import ast

SMOKE = Path(__file__).resolve().parent / "smoke_test.py"
b = SMOKE.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

# ---------- A 组：补结构层短路判据 ----------
A_OLD = '''    # 对称性：sim3 必须是对称的
    _pairs = [(_a, _b), ("人工智能 模型 部署 管线", "人工智能 模型 部署"),
              ("量子纠缠实验需要极低温", "量子纠缠实验需要低温环境")]
    for _x, _y in _pairs:
        if abs(mod._sim3(_x, _y) - mod._sim3(_y, _x)) > 1e-9:
            bad.append(f"[A] _sim3 不对称：{_x} / {_y}")
'''
A_NEW = '''    # 对称性：sim3 必须是对称的
    _pairs = [(_a, _b), ("人工智能 模型 部署 管线", "人工智能 模型 部署"),
              ("量子纠缠实验需要极低温", "量子纠缠实验需要低温环境")]
    for _x, _y in _pairs:
        if abs(mod._sim3(_x, _y) - mod._sim3(_y, _x)) > 1e-9:
            bad.append(f"[A] _sim3 不对称：{_x} / {_y}")
    # ★ 结构层（L4）短路：同编号必须 1.0、异编号必须 0.0
    #   —— 变异体 M3（去掉 L4）就打在**这条判据读的东西**上。
    if mod._sim3("T3", "T3") != 1.0:
        bad.append(f"[A] 同编号未短路为 1.0（{mod._sim3('T3', 'T3')}）"
                   f"⇒ 结构层失效")
    if mod._sim3("T3", "T4") != 0.0:
        bad.append(f"[A] 异编号未短路为 0.0（{mod._sim3('T3', 'T4')}）"
                   f"⇒ 结构层失效")
    # 负数对照：结构层必须**先于**字面层（T3/T4 无字面交集仍须 0.0）
    if mod._sim3("T3", "T4") >= mod._sim3("T3", "T3"):
        bad.append("[A] 异编号分不低于同编号分 ⇒ 结构层没前置")
'''
c = txt.count(A_OLD)
assert c == 1, f"A 组锚点命中 {c} 次"
txt = txt.replace(A_OLD, A_NEW, 1)

# ---------- B 组：换 M4 查询词 + 补 BM25 方向判据 ----------
B_OLD = '''    # 语料不足时自动降级（N < _BM25_MIN_CORPUS）
    _tiny = mod._bm25_corpus(["只有一个句子"])
    if mod._bm25_best("测试", _tiny) != 0.0:
        bad.append("[B] 语料不足时 BM25 未降级（应返回 0.0）")
'''
B_NEW = '''    # ★ BM25 必须是**两篇之间**的分（pair），不能是「各自对语料」的 best。
    #   反例（改前的真 bug）：两条各自与语料相关、但彼此**毫不相干**的句子，
    #   用 best 均值会被抬到 0.78；用 pair 必为 0.0。
    #   变异体 M1'（把 _bm25_pair 换回 _bm25_best）就打在**这条判据读的东西**上。
    _far_a, _far_b = "量子纠缠实验需要极低温", "人工智能模型部署管线优化"
    if mod._jaccard(_far_a, _far_b) != 0.0:
        bad.append(f"[B] 负对照对本身有字面重叠"
                   f"（{mod._jaccard(_far_a, _far_b)}）⇒ 请换样本")
    _far_s3 = mod._sim3(_far_a, _far_b, _corpus)
    if _far_s3 > 1e-9:
        bad.append(f"[B] 两条**无关**句子因 BM25 被抬高（{_far_s3}）⇒ "
                   f"BM25 通道用的是「各自对语料」而非「两篇之间」")
    # 正对照：真相关的对必须保住高分（避免「一律归零」蒙混过关）
    _near_s3 = mod._sim3("量子纠缠实验", "量子纠缠实验需要极低温环境",
                         _corpus)
    if _near_s3 <= 0.5:
        bad.append(f"[B] 相关对在 BM25 pair 下分数过低（{_near_s3}）⇒ "
                   f"通道被改坏（过度收缩）")
    # pair 必须对称
    if abs(mod._bm25_pair(_far_a, _far_b, _corpus)
           - mod._bm25_pair(_far_b, _far_a, _corpus)) > 1e-9:
        bad.append("[B] _bm25_pair 不对称")
    # 语料不足时自动降级（N < _BM25_MIN_CORPUS）
    # ★ 查询词必须是**语料里真实存在的词**：原来用「测试」（不在语料里
    #   ⇒ 本来就 0）⇒ 抓不到 M4（下限降到 0 也不报）。
    _tiny = mod._bm25_corpus(["只有一个句子"])
    _tiny_q = "只有一个句子"
    if mod._bm25_best(_tiny_q, _tiny) != 0.0:
        bad.append(f"[B] 语料不足时 BM25 未降级"
                   f"（应返回 0.0，实得 {mod._bm25_best(_tiny_q, _tiny)}）")
    if mod._bm25_pair(_tiny_q, "只有一个句子", _tiny) != 0.0:
        bad.append("[B] 语料不足时 _bm25_pair 未降级（应返回 0.0）")
'''
c = txt.count(B_OLD)
assert c == 1, f"B 组锚点命中 {c} 次"
txt = txt.replace(B_OLD, B_NEW, 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
SMOKE.write_bytes(out)
ast.parse(out.decode("utf-8"))
print("OK Step9: A 组补结构层判据 + B 组换词并补 BM25 方向判据")
print("lines =", out.count(b"\n"), "bytes =", len(out))
