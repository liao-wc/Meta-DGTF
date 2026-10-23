# -*- coding: utf-8 -*-
"""[v1.23.27 Step6] D3 · 语义熵（semantic entropy）—— 用 sim3 聚类。

设计（`_设计_五机制算法重构_v12326.md` §3.4 D3）：

    H_sem(B) = -Σ_c  p(c) · ln p(c)
    其中 c 为语义簇（用 sim3 聚类，阈值 cluster_thr）

  · `H_sem ≈ 0` ⇒ 所有出现语义一致 ⇒ `stable`
  · `H_sem` 高   ⇒ 语义发散 ⇒ **保持 active**（不是判「错」，是判「还不稳」）

★ 这是红线「悬置不打分」的**算法化**：语义熵是**可观测量**，不是给主张
  打的分；它决定的是**状态**，不是**优良**。

★ 判据要点（可负对照）：
  · 全部出现语义一致 ⇒ H ≈ 0（且 `stable`）
  · 全部出现两两不相关 ⇒ H = ln(n)（最大熵，保持 active）
  · **归一化**：H_norm = H / ln(n) ∈ [0,1]，n=1 时 **返回 None**
    （单样本无法谈「发散」；印 0.00 会让「只出现过一次」冒充「很稳定」）

本步是**纯新增**：新增一个模块级函数 + 给 BeliefItem 填 `semantic_entropy`。
不改任何既有读数的口径。

★ 聚类阈值走配置 `sim.cluster`，默认 0.70 —— **按默认值补写**，
  不传参时行为与显式传 0.70 逐位一致（配置键可达性判据要求）。
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
        tag, n, count, anchor[:240])
    lf = lf.replace(anchor, new)
    HITS.append((tag, n))


# ══════════════════════════════════════════════════════════════════
# 1. 模块级：语义熵纯函数（紧跟 D1/D2 之后）
# ══════════════════════════════════════════════════════════════════
sub(
    "def make_aspect_unit(desc, source=\"anchor\", polarity=\"阴\",\n",
    '''#: 语义熵聚类阈值（D3）。★ 与 `dgtf_config.yaml` 的 `sim.cluster`
#:   **同值**（0.70）—— 这里给的是「函数默认值」，配置侧由
#:   `semantic_entropy_of(..., thr=cfg)` 覆盖。默认值 = 出厂值 ⇒ 零行为差。
_SEM_CLUSTER_THR = 0.70


def semantic_entropy_of(texts, corpus=None, thr=None, top_n=None):
    """D3 语义熵：对**同一主张的多次独立出现**做 sim3 聚类，返回三元组。

    返回 `(h_norm, h_raw, clusters)`：
      · `h_norm` 归一化熵 ∈ [0,1]（除以 ln(n)）；**n < 2 时返回 None**
      · `h_raw`  原始熵 -Σ p·ln p（自然对数）
      · `clusters` 每簇成员下标（按首次出现顺序）

    ★ 为什么 n < 2 返回 None 而不是 0.0：单样本谈「发散」是无意义的，
      而 0.0 会被下游读成「很稳定」—— 那是**自欺**（本项目老坑：
      「检测缺省」要在补默认值之前判）。

    ★ 为什么聚类用「与簇代表的最大相似度」而不是两两平均：平均会被
      链式传递（A~B、B~C 但 A≁C）拉成大簇，把发散读成一致。
      用**单链到代表**（第一次进簇的那条）⇒ 同义反复的文本稳定聚在一起，
      真正发散的进不去。这是**保守**选择：宁可高估发散，不高估稳定
      （高估发散只是不判 stable，不改变任何主张的优劣）。

    ★ corpus 透传给 `_sim3`：语料 < 4 篇时 `_sim3` 自动降级到字面层，
      同一批调用共享同一降级路径 ⇒ 簇间可比。
    """
    _t = [str(x).strip() for x in (texts or []) if str(x).strip()]
    n = len(_t)
    if n < 2:
        return None, 0.0, ([list(range(n))] if n else [])
    _thr = float(_SEM_CLUSTER_THR if thr is None else thr)
    _kw = {}
    clusters: list = []
    for _i, _s in enumerate(_t):
        _placed = False
        for _c in clusters:
            _rep = _t[_c[0]]
            try:
                _sim = _sim3(_s, _rep, corpus=corpus) if top_n is None \\
                    else _sim3(_s, _rep, corpus=corpus, top_n=top_n)
            except TypeError:
                _sim = _sim3(_s, _rep, corpus=corpus)
            if float(_sim) >= _thr:
                _c.append(_i)
                _placed = True
                break
        if not _placed:
            clusters.append([_i])
    _kw = None
    import math as _math
    h = 0.0
    for _c in clusters:
        _p = len(_c) / n
        if _p > 0:
            h -= _p * _math.log(_p)
    _hmax = _math.log(n)
    _hn = (h / _hmax) if _hmax > 0 else None
    return _hn, round(h, 6), clusters


def make_aspect_unit(desc, source="anchor", polarity="阴",
''',
    "D3 semantic_entropy_of")

# ══════════════════════════════════════════════════════════════════
# 2. BeliefItem 里补 semantic_entropy 的**计算入口**
#    （Pool 侧：把同一主张的历次文本收齐 → 算熵 → 落到条目上）
# ══════════════════════════════════════════════════════════════════
sub(
    "    def belief_status_counts(self) -> dict:\n",
    '''    def refresh_belief_entropy(self, corpus=None, thr=None):
        """D3：给所有信念条目刷新 `semantic_entropy`（可观测量，非评分）。

        ★ 出现文本从哪来：`structural_amps`（历次独立提炼的原话）+ 条目
          自身的 `text`。**去重后**再算 —— 同一句话重复登记两次不是
          「两次独立出现」（那是本项目的「重复面」老坑）。
        ★ `thr=None` ⇒ 用模块默认（0.70）；外部传配置值时逐位一致。
        ★ 只对 `status == "active"` 的条目算发散度？**不。**
          全部条目都算 —— 「稳不稳」是观测，不是只对某类条目生效的规则；
          只在**迁移**时用 active 的身份去读它（见 D2）。
        """
        _out = {}
        for _it in self.belief_items:
            _txt = [str(_it.get("text", "")).strip()]
            for _sa in (self.undecidable_channel.get("structural_amps") or []):
                _sa = str(_sa).strip()
                if _sa:
                    _txt.append(_sa)
            # 去重（保序）
            _seen = set()
            _uniq = []
            for _s in _txt:
                if _s and _s not in _seen:
                    _seen.add(_s)
                    _uniq.append(_s)
            _hn, _h, _cl = semantic_entropy_of(_uniq, corpus=corpus,
                                               thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _out[_it.get("id", "")] = _hn
        return _out

    def belief_status_counts(self) -> dict:
''',
    "Pool refresh_belief_entropy")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out, "产出含 \\r\\r\\n"
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n"), "写回后不是纯 CRLF"
assert "\r\r\n" not in chk, "写回后含 \\r\\r\\n"

# ── 自证：剥掉本轮标记后不许有版次批注 ─────────────────────────
import re as _re
import ast as _ast
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

print("STEP6 OK  —— %d 处替换" % len(HITS))
for _tag, _n in HITS:
    print("  · %-30s x%d" % (_tag, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
