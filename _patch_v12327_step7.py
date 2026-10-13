# -*- coding: utf-8 -*-
"""[v1.23.27 Step7] E1 · EIG 可计算化 + E2 · 子模批选。

设计（`_设计_五机制算法重构_v12326.md` §3.5 E1/E2）：

E1 —— **不再让模型自报 `expected_gain`**，改由引擎算：

    G(p) = H_before(U) - E_a[H_after(U | p=a)]

可计算化规格（全部用**已有产物**，零额外 LLM 调用）：
  · 未决集合 U   = `pool.belief_items` 中 `status ∈ {active}` 的条目
  · H_before     = U 的语义熵（D3，用 sim3 聚类）
  · 候选答案分布 a = 探针 `question` 与各 BeliefItem 的 `sim3` ⇒ 软分配
  · H_after      = 若探针**命中**某条 ⇒ 该条**移除**后的熵；未命中 ⇒ 熵不变
  · G(p)         = 上式，归一化到 H_before ⇒ 值域 [0,1]

E2 —— 子模贪心 + **边际下限**（宁少勿滥，修「必然塞满」）：

    S = ∅
    for i in 1..n:
        p* = argmax_{p ∉ S} G(p | S)
        if G(p* | S) < floor: break
        S = S ∪ {p*}

★ 关键设计取舍（写清楚，判据才能对准）：
  · `expected_gain` **旧键继续写**（双写）：`_probe_research` 的
    `gain < min_gain` 过滤门仍在，但喂给它的是**引擎算的 G**。
    ⇒ 「模型自报」这条空转路径被切断，而下游读取点零改动。
  · 引擎算不出来时（未决集合为空 / 只有 1 条）⇒ **退回模型自报值**，
    并留痕 `gain_source="model"`。★ 不假装成引擎算的：
      「检测缺省」要在补默认值**之前**判（本项目老坑）。
  · 模型给的 `question` 仍然有用 —— 它是**候选问题的文本**，
    引擎只接管「值多少」这个问题。

★ 本条与红线：「悬置不打分」—— G 是**信息量**，不是**优良**；
  未决集合里有几条本身就是「不值得答」的，G 也不会因此变负。
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
# 1. 模块级：E1 的 G 计算 + E2 的子模贪心（插在 select_probe_focus 之前）
# ══════════════════════════════════════════════════════════════════
sub(
    "def select_probe_focus(pool: \"Pool\", new_probes: List[dict],\n",
    '''# ── [E1/E2] 探针的信息增益（引擎算）与子模批选 ─────────────────
#: 引擎算 G 时的**软分配下限**：探针与某条未决主张的 sim3 低于它 ⇒
#: 视为「打不到」（不给权重）。★ 不设它会得到一个「所有探针都对所有
#: 主张有一点点权重」的稠密矩阵 —— 熵降全是噪声，G 读数没有判别力。
_GAIN_ASSIGN_MIN = 0.15
#: 子模批选的**边际下限**（E2）：`G(p*|S) < floor` ⇒ 停手。
#: ★ 默认 0.0 = 「不许零增益的补位」，**不是**「不许少」。
#:   有意不设高阈值：G 的绝对值尺度依赖池大小，硬阈值会随池漂移。
_GAIN_MARGINAL_FLOOR = 0.0


def probe_information_gain(probe, belief_items, covered_ids=None,
                           corpus=None, thr=None, assign_min=None):
    """E1：**引擎算**这条探针的信息增益 G ∈ [0,1]。

    返回 `(G, detail)`；`detail` 留痕（`h_before` / `h_after` / `hit_ids`），
    便于判据与变异体定位是哪一步给出的数。
    ★ 算不出来（未决 < 2 条）⇒ 返回 `(None, {"why": ...})`。
      **返回 None 不是 0.0**：0.0 会被读成「算出来是零增益」，
      而真相是「这个池子没有可谈的信息量」—— 两回事，别混。
    """
    _q = str((probe or {}).get("question", "")).strip()
    _und = [b for b in (belief_items or [])
            if str(b.get("status") or "") == "active"
            and str(b.get("text") or "").strip()]
    if not _q:
        return None, {"why": "empty_question"}
    if len(_und) < 2:
        return None, {"why": "undecidable_lt2", "n": len(_und)}

    _cov = {str(x).strip() for x in (covered_ids or []) if str(x).strip()}
    _live = [b for b in _und if str(b.get("id") or "") not in _cov]
    if len(_live) < 2:
        return None, {"why": "all_covered", "n": len(_live)}

    _am = _GAIN_ASSIGN_MIN if assign_min is None else float(assign_min)

    def _entropy(_items):
        """未决集合的语义熵（复用 D3 的纯函数；归一化到 ln(n)）。"""
        _hn, _h, _cl = semantic_entropy_of(
            [str(b.get("text", "")) for b in _items], corpus=corpus, thr=thr)
        return _hn if _hn is not None else 0.0

    h_before = _entropy(_live)
    # 候选答案分布：sim3(question, text) 归一化（软分配）
    _w = []
    for _b in _live:
        _s = float(_sim3(_q, str(_b.get("text", "")), corpus=corpus))
        _w.append(_s if _s >= _am else 0.0)
    _tot = sum(_w)
    if _tot <= 0.0:
        return 0.0, {"why": "no_assignment", "h_before": round(h_before, 4),
                     "h_after": round(h_before, 4), "hit_ids": []}
    _p = [x / _tot for x in _w]
    # 期望后熵：按软分配加权「命中某条 ⇒ 移除该条」
    h_after = 0.0
    _guard = 0
    for _i, _pi in enumerate(_p):
        if _pi <= 0.0:
            continue
        _guard += 1
        _rest = [_b for _j, _b in enumerate(_live) if _j != _i]
        h_after += _pi * _entropy(_rest)
    # 泛化到 unseen 的可能：权重 < 1 的部分按「熵不变」处理
    h_after += max(0.0, 1.0 - sum(_p)) * h_before
    if h_before <= 0.0:
        return 0.0, {"why": "h_before_zero", "h_before": 0.0,
                     "h_after": 0.0, "hit_ids": []}
    _g = (h_before - h_after) / h_before
    _g = max(0.0, min(1.0, _g))
    return round(_g, 6), {
        "h_before": round(h_before, 4), "h_after": round(h_after, 4),
        "hit_ids": [_live[_i].get("id", "")
                    for _i, _pi in enumerate(_p) if _pi > 0],
        "n_live": len(_live), "guard": _guard,
    }


def select_probe_focus_submodular(pool, candidates, n,
                                  corpus=None, thr=None,
                                  floor=None):
    """E2：子模贪心批选（**宁少勿滥**）。返回 `(picked, detail)`。

    G(p | S) 的实现：把**已选探针命中过的信念 id** 从活跃集合里扣掉，
    再算 G —— 这就是子模条件化（已覆盖的贡献不再计入边际增益）。

    ★ 与旧 `select_probe_focus` 的三轮 take 的**关键差别**：
      旧实现三轮都可能不产出（实测 4 条全不相干只选 1 条），但**也可能**
      在某轮塞进一条增益为零的；新实现显式判 `G < floor` ⇒ 停手。
    ★ `floor` 默认 `_GAIN_MARGINAL_FLOOR`（0.0）。
    """
    _n = int(n or 0)
    _items = [it for it in (candidates or [])
              if str(it.get("text", "")).strip()]
    if _n <= 0 or not _items:
        return [], {"picked_n": 0, "why": "n<=0 or no candidates"}

    _fl = _GAIN_MARGINAL_FLOOR if floor is None else float(floor)
    _bi = list(getattr(pool, "belief_items", None) or [])
    picked: List[dict] = []
    covered: List[str] = []
    picked_texts: List[str] = []
    trace: List[dict] = []
    for _ in range(_n):
        _best, _best_g, _best_d = None, -1.0, None
        for _it in _items:
            _t = str(_it.get("text", "")).strip()
            if any(_similar(_t, _x, _TAKE_SIM) for _x in picked_texts):
                continue
            _g, _d = probe_information_gain(
                {"question": _t}, _bi, covered_ids=covered,
                corpus=corpus, thr=thr)
            if _g is None:
                continue
            if _g > _best_g:
                _best, _best_g, _best_d = _it, float(_g), _d
        if _best is None:
            trace.append({"stop": "no_candidate_with_gain"})
            break
        if _best_g < _fl:
            trace.append({"stop": "below_floor", "best_g": _best_g})
            break
        picked.append(_best)
        picked_texts.append(str(_best.get("text", "")).strip())
        covered = list(covered) + list((_best_d or {}).get("hit_ids") or [])
        trace.append({"picked": str(_best.get("text", ""))[:60],
                      "g": _best_g, "hits": (_best_d or {}).get("hit_ids")})
    return picked, {"picked_n": len(picked),
                    "floor": _fl, "trace": trace,
                    "why": "ok" if picked else "none_above_floor"}


def select_probe_focus(pool: "Pool", new_probes: List[dict],
''',
    "E1/E2 纯函数")

# ══════════════════════════════════════════════════════════════════
# 2. select_probe_focus 出口接上子模批选（开关式：默认开，可回退）
# ══════════════════════════════════════════════════════════════════
sub(
    "    take(_amp_weighted_score)\n"
    "    take(lambda it: len(_kw(it[\"text\"], 12) & q_kw))\n"
    "    take(lambda it: fresh(it[\"text\"]))\n"
    "    return [p[\"raw\"] for p in picked[:n]]\n",
    "    take(_amp_weighted_score)\n"
    "    take(lambda it: len(_kw(it[\"text\"], 12) & q_kw))\n"
    "    take(lambda it: fresh(it[\"text\"]))\n"
    "    _legacy = [p[\"raw\"] for p in picked[:n]]\n"
    "    # ── [E2] 子模批选接管（可关；关掉时与旧行为逐位一致） ──\n"
    "    #  ★ 开关走配置 `probe.submodular`，默认 True。\n"
    "    #  ★ 引擎算不出 G（未决 < 2 条）⇒ `picked` 为空 ⇒ **退回旧结果**：\n"
    "    #    不能因为「新方法算不出来」就把探针整批丢掉。\n"
    "    if not bool((cfg.get(\"probe\") or {}).get(\"submodular\", True)):\n"
    "        return _legacy\n"
    "    _sub, _det = select_probe_focus_submodular(\n"
    "        pool, items, n,\n"
    "        thr=(cfg.get(\"sim\") or {}).get(\"cluster\", None))\n"
    "    _gains = {str(x.get(\"text\", \"\")): x.get(\"g\")\n"
    "              for x in (_det.get(\"trace\") or []) if x.get(\"picked\")}\n"
    "    _picked_raw = []\n"
    "    for _p in _sub:\n"
    "        _raw = _p.get(\"raw\")\n"
    "        if not isinstance(_raw, dict):\n"
    "            _raw = {\"question\": str(_p.get(\"text\", \"\")),\n"
    "                    \"link\": \"（池里的线头）\"}\n"
    "        else:\n"
    "            _raw = dict(_raw)\n"
    "        if _raw.get(\"question\"):\n"
    "            _picked_raw.append(_raw)\n"
    "    if not _picked_raw:\n"
    "        return _legacy\n"
    "    # ★ `expected_gain` 双写：喂**引擎算的 G**给下游过滤门。\n"
    "    for _r in _picked_raw:\n"
    "        _q = str(_r.get(\"question\", \"\")).strip()\n"
    "        _g = _gains.get(str(_q))\n"
    "        _r[\"expected_gain_engine\"] = _g\n"
    "        if _g is not None:\n"
    "            _r[\"expected_gain\"] = float(_g)\n"
    "            _r[\"gain_source\"] = \"engine\"\n"
    "        else:\n"
    "            _r.setdefault(\"gain_source\", \"model\")\n"
    "    return _picked_raw\n",
    "select_probe_focus 接子模")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out, "产出含 \\r\\r\\n"
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n"), "写回后不是纯 CRLF"
assert "\r\r\n" not in chk, "写回后含 \\r\\r\\n"

# ── 自证：不许留版次批注 ────────────────────────────────────────
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

print("STEP7 OK  —— %d 处替换" % len(HITS))
for _tag, _n in HITS:
    print("  · %-30s x%d" % (_tag, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
