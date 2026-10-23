# -*- coding: utf-8 -*-
"""[v1.23.27 Step4] A2 · 覆盖对账（符号化） + A3 · 双读数分离。

设计（`_设计_五机制算法重构_v12326.md` §3.1 A2 / A3）：

A2 —— 现状 `_und_self_touch_texts()` 用**文本包含 / `_overlap_coef`** 判
「后续圈有没有再呼应这条结构 &」，受尺子失真影响。新设计改成**符号对账**：
编号是离散符号，不受相似度尺子影响。

A3 —— 红线「未对齐合法」要求「未触达 ≠ 失败」，所以读数拆两个、**永不合成
一个分**：
  · `touch_rate`（能力读数）= touched 非空圈数 / 总圈数
  · `carry_rate`（延续读数）= 被后续圈 carry 的 AspectUnit 数 / 总 AspectUnit 数

本步只做**加法**，不动任何既有读数：
  1. `Pool._aspect_symbols_v12327()` —— 新增：把池内所有**可被符号引用的
     靶子**收成一个 id 集合（AspectUnit.id / amp id / thread id / probe id /
     covered_unders 的 A#）。
  2. `Pool._und_self_touch_symbols()` —— 新增：符号版的自触及凭据。
  3. `Pool.add_undecidable` 尾部**追加** `last_carry_rate` 一族键
     （旧键 `last_sc_ratio` 一字不动）。
  4. `View` 新增 `touch_rate` 只读属性 + `aspect_carry_rate` 只读属性。
  5. `DGTF._finalize_layer_common` 里给 `view.touch_rate` 落一个值。

★ 判据「落点」说明：`carry_rate` 的分母是 **aspect_units 条数**，
  分子是「被后续圈产物按 **id** 命中」的条数 —— 用的是**符号**，
  不是 `_overlap_coef` 与 `_similar`（那两者是本轮要绕开的东西）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "源文件不是纯 CRLF"
assert "\r\r\n" not in txt, "源文件已有 \\r\\r\\n 污染"

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
# 1. Pool 新增两个符号函数（插在 _und_self_touch_texts 之前）
# ══════════════════════════════════════════════════════════════════
sub(
    "    def _und_self_touch_texts(self) -> List[str]:\n",
    '''    # ── [v1.23.27 A2] 覆盖对账的**符号侧**：用 id 对账，不用尺子 ──
    def aspect_targets_v12327(self) -> dict:
        """池内所有**可被符号引用的靶子**：{id: {"kind","text"}}。

        ★ 为什么要有它：`covers` / `carry_rate` 要判「这条编号指向谁」，
          没有登记表就只能靠文本相似度猜 —— 那正是本轮要绕开的尺子。
        ★ 只收**真有条目**的 id，不收空串（空 id 会让对账假通过）。
        """
        out: dict = {}
        def _put(_i, _kind, _t):
            _i = str(_i).strip()
            if not _i:
                return
            out.setdefault(_i, {"kind": _kind, "text": str(_t or "")[:200]})
        for _i, _a in enumerate(self.amps or [], 1):
            _put(_a.get("id") or ("amp#%d" % _i), "amp", _a.get("desc", ""))
        for _i, _t in enumerate(self.threads or [], 1):
            _put(_t.get("id") or ("th#%d" % _i), "thread", _t.get("desc", ""))
        for _i, _p in enumerate(self.probes or [], 1):
            _put(_p.get("id") or ("probe#%d" % _i), "probe",
                 _p.get("question", ""))
        for _i, _s in enumerate(self.covered_unders or [], 1):
            _put("A%d" % _i, "covered_under", _s)
        return out

    def _und_self_touch_symbols(self) -> dict:
        """符号版自触及凭据：{id: 来源标签}——哪些靶子被**后续产物**按 id 引用。

        ★ 与 `_und_self_touch_texts()` 的关系：那些是**文本**凭据（旧口径，
          继续保留供旧读数用）；这里是**符号**凭据（新口径）。
          两者并存不互相替代 —— 旧读数要继续可读，新读数要不受尺子影响。
        ★ 空池返回空 dict（调用点据此记 None，不印 0.00 冒充读数）。
        """
        out: dict = {}
        _targets = self.aspect_targets_v12327()
        _pat = re.compile(r"(?:amp|th|probe|A|B|T)#?(\\d+)")
        _all_ids = set(_targets.keys())

        def _scan(_text, _tag):
            _s = str(_text or "").strip()
            if not _s:
                return
            # ① 直接出现真实 id 字面量（如 "amp#3" / "A2"）
            for _tid in _all_ids:
                if _tid and re.search(
                        r"(?<![\\w#])" + re.escape(_tid) + r"(?![\\w#])", _s):
                    out.setdefault(_tid, _tag)
            # ② 出现带前缀的形态（amp#3 / th#2 / probe#1 / A2 / B7）
            for _m in _pat.finditer(_s):
                _full = _m.group(0).replace("#", "#")
                if _full in _all_ids:
                    out.setdefault(_full, _tag)
                _bare = _m.group(1)
                for _prefix in ("amp#", "th#", "probe#", "A", "B", "T"):
                    _cand = _prefix + _bare
                    if _cand in _all_ids:
                        out.setdefault(_cand, _tag)

        for _t in (self.threads or []):
            _scan(_t.get("desc", ""), "thread")
            _scan(_t.get("polarity_why", ""), "thread")
        for _p in (self.probes or []):
            _scan(_p.get("question", ""), "probe")
            for _c in (_p.get("covers") or []):
                _scan(_c, "covers")
            _scan(_p.get("link", ""), "link")
        for _e in (self.engagements or []):
            _scan(_e.get("target", ""), "engagement")
        for _s in (self.suspensions or []):
            _scan(_s.get("target", ""), "suspension")
        for _d in (self.deferrals or []):
            _scan(_d.get("target", ""), "deferral")
        return out

    def _und_self_touch_texts(self) -> List[str]:
''',
    "Pool 符号函数")

# ══════════════════════════════════════════════════════════════════
# 2. add_undecidable 尾部追加 carry_rate 一族键（旧键一字不动）
# ══════════════════════════════════════════════════════════════════
sub(
    "        _append_trace(self.undecidable_channel[\"structural_amps\"],\n"
    "                      hit_aspects, \"struct_trace\", \"aspect_first_hit\")\n",
    '''        # ── [v1.23.27 A3] carry_rate（延续读数，**符号口径**） ──
        #  ★ 与 last_sc_ratio 的关键区别：
        #    last_sc_ratio 的凭据是**文本**（_overlap_coef ≥ 0.3，受尺子失真）；
        #    carry_rate 的凭据是**符号**（id 命中，不受尺子影响）。
        #  ★ 两者**永远分开报**、不合成一个分（红线「未对齐合法」）。
        _sym_targets = self.aspect_targets_v12327()
        _sym_hits = self._und_self_touch_symbols()
        _sym_hit_ids = [i for i in _sym_hits if i in _sym_targets]
        self.undecidable_channel["last_carry_rate"] = (
            len(_sym_hit_ids) / len(_sym_targets) if _sym_targets else None)
        self.undecidable_channel["last_carry_pool"] = len(_sym_targets)
        self.undecidable_channel["last_carry_hits"] = len(_sym_hit_ids)
        self.undecidable_channel["carry_touched_ids"] = sorted(_sym_hit_ids)
        self.undecidable_channel.setdefault("carry_history", []).append(
            self.undecidable_channel["last_carry_rate"])

        _append_trace(self.undecidable_channel["structural_amps"],
                      hit_aspects, "struct_trace", "aspect_first_hit")
''',
    "add_undecidable carry_rate")

# ══════════════════════════════════════════════════════════════════
# 3. to_dict 出口（不出口 = 静默丢产物）
# ══════════════════════════════════════════════════════════════════
sub(
    "                \"decidable_channel\": self.decidable_channel,\n"
    "                \"undecidable_channel\": self.undecidable_channel}\n"
    "        if self.covered_unders:\n",
    "                \"decidable_channel\": self.decidable_channel,\n"
    "                \"undecidable_channel\": self.undecidable_channel}\n"
    "        # [v1.23.27 A2/A3] 符号对账的登记表：出口才能被下游读。\n"
    "        # ★ to_dict 是**手工白名单**，新键不同步 = 静默丢产物。\n"
    "        if self.undecidable_channel:\n"
    "            _at = self.aspect_targets_v12327()\n"
    "            if _at:\n"
    "                d[\"aspect_targets\"] = _at\n"
    "        if self.covered_unders:\n",
    "Pool.to_dict aspect_targets")

# ══════════════════════════════════════════════════════════════════
# 4. View 新增两个只读读数（永不合成一个分）
# ══════════════════════════════════════════════════════════════════
sub(
    "    def add_aspect_unit(self, desc, source=\"anchor\", polarity=\"阴\",\n",
    '''    # ── [v1.23.27 A3] 双读数：**永不合成一个分**（红线「未对齐合法」）──
    @property
    def touch_rate(self) -> Optional[float]:
        """能力读数：本层有「触及」的圈数 / 实际跑的圈数。

        ★ 这不是「分数」，是**覆盖率观测**：未触达 ≠ 失败（红线）。
        ★ 兜底口径写清楚：`round_log` 有就用它按圈判；没有就退回
          「anchor_touched 非空 ⇒ 1.0」这个**一次性**观测。
          ★ 兜底分支**不假装**是逐圈读数（它只答「有没有发生过」）。
        """
        _rl = getattr(self, "round_log", None) or []
        if _rl:
            _hit = 0
            for _r in _rl:
                try:
                    if int(_r.get("anchor_touched_n", 0) or 0) > 0:
                        _hit += 1
                except (TypeError, ValueError):
                    continue
            return _hit / len(_rl) if _rl else None
        _n = len(self.anchor_touched or [])
        return 1.0 if _n > 0 else 0.0

    @property
    def aspect_carry_rate(self) -> Optional[float]:
        """延续读数：被后续圈**按 id** 引用的方面数 / 方面总数。

        ★ 与 `touch_rate` 分开报（一个是「碰没碰过」，一个是「后来还追不追」）。
        ★ 空池返回 None —— 不印 0.00 冒充读数（本项目老坑）。
        """
        _units = self.aspect_units or []
        if not _units:
            return None
        _hit_ids = set(getattr(self, "_carried_aspect_ids", []) or [])
        if not _hit_ids:
            _ch = getattr(self, "_layer_und_channel", None) or {}
            _hit_ids = set(_ch.get("carry_touched_ids") or [])
        if not _hit_ids:
            return 0.0
        return len([u for u in _units
                    if str(u.get("id", "")) in _hit_ids]) / len(_units)

    def add_aspect_unit(self, desc, source="anchor", polarity="阴",
''',
    "View 双读数")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out, "产出含 \\r\\r\\n"
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n"), "写回后不是纯 CRLF"
assert "\r\r\n" not in chk, "写回后含 \\r\\r\\n"

print("STEP4 OK  —— %d 处替换" % len(HITS))
for _t, _n in HITS:
    print("  · %-30s x%d" % (_t, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
