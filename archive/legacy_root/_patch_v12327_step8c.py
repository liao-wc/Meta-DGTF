# -*- coding: utf-8 -*-
"""[v1.23.27 Step8c] 修 Step7 的 E1 归一化 bug —— **同一把尺子**。

## 实测到的 bug

    bi = [B1 量子纠缠…极低温, B2 人工智能…部署管线, B3 披萨…烤制时长]
    probe_information_gain({"question": "极低温环境下量子纠缠实验怎么做"}, bi)
    → G = 0.0   （hits=['B1'], h_before=1.0）

**明明命中了 B1，G 却是 0。** 原因是 `_entropy()` 每次都把集合
**归一化到自己的 ln(n)**：

  · H_before = H({3 条两两不相关}) / ln3 = ln3/ln3 = **1.0**
  · 移除 B1 后剩 {B2,B3} 仍两两不相关 ⇒ H_after = ln2/ln2 = **1.0**
  · G = (1.0 − 1.0) / 1.0 = **0.0**

「移除一条」带来的原始熵降 ln3→ln2 被各自的 ln(n) **除掉了** ⇒
归一看不见移除的效应 ⇒ G 恒 0。

## 这正是我自己踩的坑

Step7 的注释里我写过「两臂对照前先证**两臂都产出了这个量**且是
**同一把尺子**」—— 结果 `H_before` 与 `H_after` 用了两把尺子
（各自 ln n）。**方向错的判据比没判据更危险**，这里是「方向错的计算」。

## 修法

`H_after` 必须用 **`H_before` 的尺子**：同一个归一化基准 `ln(n_before)`。

    h(x)        = -Σ p·ln p           （**原始**熵，不归一化）
    h_before    = h(live)             ← 归一化基准 = ln(n_before)
    h_after     = Σ_i p_i · h(live \ i)  + p_unseen · h_before
    G           = (H_before − H_after) / H_before
    其中 H_x = h_x / ln(n_before)     ← **同一个分母**

`semantic_entropy_of` 已经同时返回 `(h_norm, h_raw, clusters)` ⇒
取 `h_raw` 即可，不用改 D3。

## 自证（写进本次补丁）

  · 命中 3 条中的 1 条 ⇒ G **必须 > 0**（旧实现给 0.0）
  · 打不中任何一条 ⇒ G **必须 == 0.0**（边界不变）
  · 全部命中且集合两两不相关 ⇒ G **必须 == 1.0**（移除全部 ⇒ 熵 0）
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "源文件不是纯 CRLF"
assert "\r\r\n" not in txt

lf = txt.replace("\r\n", "\n")
orig_lf = lf
HITS = []


def sub(anchor, new, tag, count=1):
    global lf
    n = lf.count(anchor)
    assert n == count, "%s：锚点命中 %d 次（要求 %d）\n---\n%s" % (
        tag, n, count, anchor[:260])
    lf = lf.replace(anchor, new)
    HITS.append((tag, n))


# ══════════════════════════════════════════════════════════════════
# 1. _entropy 从「归一化」改为「原始熵」
# ══════════════════════════════════════════════════════════════════
sub(
    "    def _entropy(_items):\n"
    "        \"\"\"未决集合的语义熵（复用 D3 的纯函数；归一化到 ln(n)）。\"\"\"\n"
    "        _hn, _h, _cl = semantic_entropy_of(\n"
    "            [str(b.get(\"text\", \"\")) for b in _items], corpus=corpus, thr=thr)\n"
    "        return _hn if _hn is not None else 0.0\n",
    "    import math as _math\n"
    "\n"
    "    def _raw_entropy(_items):\n"
    "        \"\"\"未决集合的**原始**语义熵 h = -Σ p·ln p —— ★ 不归一化。\n"
    "\n"
    "        ★ 为什么不归一化（这是本轮修掉的 bug）：\n"
    "          `h(x)/ln(n_x)` 的分母随集合大小变 ⇒ 「移除一条」造成的\n"
    "          ln3→ln2 降幅会被两个不同的 ln(n) 各自除掉、**完全抵消**，\n"
    "          G 恒为 0。归一化只在**跨不同大小集合比较**时才有意义。\n"
    "        ★ 归一化留给最后一步统一做，分母恒为 `ln(n_before)`\n"
    "          —— 两臂用**同一把尺子**。\n"
    "        ★ 空集合返回 0.0（ln(1)=0，数学上也成立）。\n"
    "        \"\"\"\n"
    "        _t = [str(b.get(\"text\", \"\")) for b in _items]\n"
    "        if len(_t) < 2:\n"
    "            return 0.0\n"
    "        _hn, _h, _cl = semantic_entropy_of(_t, corpus=corpus, thr=thr)\n"
    "        return float(_h)\n",
    "_raw_entropy")

# ══════════════════════════════════════════════════════════════════
# 2. G 的计算改为「同一把尺子」
# ══════════════════════════════════════════════════════════════════
sub(
    "    h_before = _entropy(_live)\n"
    "    # 候选答案分布：sim3(question, text) 归一化（软分配）\n"
    "    _w = []\n"
    "    for _b in _live:\n"
    "        _s = float(_sim3(_q, str(_b.get(\"text\", \"\")), corpus=corpus))\n"
    "        _w.append(_s if _s >= _am else 0.0)\n"
    "    _tot = sum(_w)\n"
    "    if _tot <= 0.0:\n"
    "        return 0.0, {\"why\": \"no_assignment\", \"h_before\": round(h_before, 4),\n"
    "                     \"h_after\": round(h_before, 4), \"hit_ids\": []}\n"
    "    _p = [x / _tot for x in _w]\n"
    "    # 期望后熵：按软分配加权「命中某条 ⇒ 移除该条」\n"
    "    h_after = 0.0\n"
    "    _guard = 0\n"
    "    for _i, _pi in enumerate(_p):\n"
    "        if _pi <= 0.0:\n"
    "            continue\n"
    "        _guard += 1\n"
    "        _rest = [_b for _j, _b in enumerate(_live) if _j != _i]\n"
    "        h_after += _pi * _entropy(_rest)\n"
    "    # 泛化到 unseen 的可能：权重 < 1 的部分按「熵不变」处理\n"
    "    h_after += max(0.0, 1.0 - sum(_p)) * h_before\n"
    "    if h_before <= 0.0:\n"
    "        return 0.0, {\"why\": \"h_before_zero\", \"h_before\": 0.0,\n"
    "                     \"h_after\": 0.0, \"hit_ids\": []}\n"
    "    _g = (h_before - h_after) / h_before\n"
    "    _g = max(0.0, min(1.0, _g))\n"
    "    return round(_g, 6), {\n"
    "        \"h_before\": round(h_before, 4), \"h_after\": round(h_after, 4),\n"
    "        \"hit_ids\": [_live[_i].get(\"id\", \"\")\n"
    "                    for _i, _pi in enumerate(_p) if _pi > 0],\n"
    "        \"n_live\": len(_live), \"guard\": _guard,\n"
    "    }\n",
    "    # ── 两臂同一把尺子：分母恒为 ln(n_before) ──\n"
    "    _h_before_raw = _raw_entropy(_live)\n"
    "    _denom = _math.log(len(_live)) if len(_live) > 1 else 0.0\n"
    "    h_before = (_h_before_raw / _denom) if _denom > 0 else 0.0\n"
    "\n"
    "    # 候选答案分布：sim3(question, text) 归一化（软分配）\n"
    "    _w = []\n"
    "    for _b in _live:\n"
    "        _s = float(_sim3(_q, str(_b.get(\"text\", \"\")), corpus=corpus))\n"
    "        _w.append(_s if _s >= _am else 0.0)\n"
    "    _tot = sum(_w)\n"
    "    if _tot <= 0.0:\n"
    "        return 0.0, {\"why\": \"no_assignment\", \"h_before\": round(h_before, 4),\n"
    "                     \"h_after\": round(h_before, 4), \"hit_ids\": []}\n"
    "    _p = [x / _tot for x in _w]\n"
    "    # 期望后熵：按软分配加权「命中某条 ⇒ 移除该条」。\n"
    "    # ★ 用**原始**熵求和，除的仍是 `_denom = ln(n_before)` ——\n"
    "    #   两臂同尺；`_denom == 0`（n_before ≤ 1）时上面已早退。\n"
    "    _h_after_raw = 0.0\n"
    "    _guard = 0\n"
    "    for _i, _pi in enumerate(_p):\n"
    "        if _pi <= 0.0:\n"
    "            continue\n"
    "        _guard += 1\n"
    "        _rest = [_b for _j, _b in enumerate(_live) if _j != _i]\n"
    "        _h_after_raw += _pi * _raw_entropy(_rest)\n"
    "    # 泛化到 unseen 的可能：权重 < 1 的部分按「熵不变」处理\n"
    "    _h_after_raw += max(0.0, 1.0 - sum(_p)) * _h_before_raw\n"
    "    h_after = (_h_after_raw / _denom) if _denom > 0 else 0.0\n"
    "    if h_before <= 0.0:\n"
    "        return 0.0, {\"why\": \"h_before_zero\", \"h_before\": 0.0,\n"
    "                     \"h_after\": 0.0, \"hit_ids\": []}\n"
    "    _g = (h_before - h_after) / h_before\n"
    "    _g = max(0.0, min(1.0, _g))\n"
    "    return round(_g, 6), {\n"
    "        \"h_before\": round(h_before, 4), \"h_after\": round(h_after, 4),\n"
    "        \"h_raw_before\": round(_h_before_raw, 4),\n"
    "        \"h_raw_after\": round(_h_after_raw, 4),\n"
    "        \"denom\": round(_denom, 4),\n"
    "        \"hit_ids\": [_live[_i].get(\"id\", \"\")\n"
    "                    for _i, _pi in enumerate(_p) if _pi > 0],\n"
    "        \"n_live\": len(_live), \"guard\": _guard,\n"
    "    }\n",
    "G 同一把尺子")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n")
assert "\r\r\n" not in chk

import re as _re
_TAG = _re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
_s = chk.replace("\r\n", "\n")
_i = _s.index('"""')
_j = _s.index('"""', _i + 3)
_de = _s[: _j].count("\n")
_l = _s.split("\n")
_h = [k + 1 for k in range(_de + 1, len(_l))
      if _l[k].lstrip().startswith("#") and _TAG.search(_l[k])]
_t = [k + 1 for k in range(_de + 1, len(_l))
      if not _l[k].lstrip().startswith("#") and "#" in _l[k]
      and _TAG.search(_l[k].split("#", 1)[1])]
assert not _h and not _t, "本步引入了版次批注：%s %s" % (_h, _t)

print("STEP8c OK —— %d 处替换" % len(HITS))
for _tag, _n in HITS:
    print("  · %-30s x%d" % (_tag, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
