# -*- coding: utf-8 -*-
"""v1.23.28 补丁脚本 —— 机制效果修复 + 复审优化。

单一真相源：全部编辑在 `lines` 行表上做，最后 join 一次、转一次 CRLF、写一次盘。
（本项目教训：文本级 + 行级混用会静默丢替换。）

九项改动：
  F1  D1/D2 接线：`upsert_belief` 挪出「新条目」守卫（复现必须能登记）
  F2  D1/D2 语义：`layer` 实参改**层名**（不再错传圈号）
  F3  D1/D2 迁移驱动：把 attack / resolved 两类信号接进调用点
  F4  D3 接线：`refresh_belief_entropy` 在每层入库后刷新 + `belief_status_counts` 留痕
  F5  A3 出口：`touch_rate` / `aspect_carry_rate` 进 `Pool.to_dict`（可观测化）
  F6  A1 编号统一：`untouched` 写入带 `id`（渲染前缀 + covers 靶子同物）
  F7  A1 编号对齐：`aspect_targets_v12327` 优先用 `aspect_units` 的 id
  F8  E2 floor：默认值改 0.02（与 stop_floor 同量级，让 below_floor 可达）
  F9  E1 落盘：探针 dict 补 `gain_source` / `expected_gain_engine`
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.28.py"

raw_bytes = SRC.read_bytes()
txt = raw_bytes.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "源文件不是纯 CRLF！"
txt = txt.replace("\r\n", "\n")
lines = txt.split("\n")

_applied = []


def find_row(anchor, expect=1):
    """按整行相等找行号（避免前导空格子串坑）。"""
    hits = [i for i, ln in enumerate(lines) if ln == anchor]
    assert len(hits) == expect, \
        "锚点命中 %d 次（要求 %d）：%r" % (len(hits), expect, anchor[:70])
    return hits[0]


def find_idx(anchor, expect=1):
    """按整行**包含**找行号（用于带变量的行）。"""
    hits = [i for i, ln in enumerate(lines) if anchor in ln]
    assert len(hits) == expect, \
        "片段命中 %d 次（要求 %d）：%r" % (len(hits), expect, anchor[:70])
    return hits[0]


def repl(old, new, what, expect=1):
    """整块替换：按行列表比对。"""
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1)
            if lines[i:i + len(o)] == o]
    assert len(hits) == expect, \
        "%s：块命中 %d 次（要求 %d）\n%s" % (what, len(hits), expect, old[:200])
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    _applied.append(what)


# ══════════════════════════════════════════════════════════════════
# F1 + F2 + F3：D1/D2 接线修复
# ══════════════════════════════════════════════════════════════════
# 改前：
#   for sa in (product.get("structural_amps") or []):
#       s = str(sa).strip()
#       if s and not any(_similar(s, x, _DUP_SIM)
#                        for x in self.undecidable_channel["structural_amps"]):
#           self.undecidable_channel["structural_amps"].append(s[:200])
#           # [D1 信念条目] 双写：同一条主张**同时**进信念条目。
#           # ★ 来源 = 本层标签，独立复现的凭据（D2 的 ≥2 来源）。
#           self.upsert_belief(s[:200], ground="layer%s" % layer,
#                              round_no=int(layer or 0),
#                              sources=["layer%s" % layer])
_F1_OLD = '''        for sa in (product.get("structural_amps") or []):
            s = str(sa).strip()
            if s and not any(_similar(s, x, _DUP_SIM)
                             for x in self.undecidable_channel["structural_amps"]):
                self.undecidable_channel["structural_amps"].append(s[:200])
                # [D1 信念条目] 双写：同一条主张**同时**进信念条目。
                # ★ 来源 = 本层标签，独立复现的凭据（D2 的 ≥2 来源）。
                self.upsert_belief(s[:200], ground="layer%s" % layer,
                                   round_no=int(layer or 0),
                                   sources=["layer%s" % layer])'''

# 改后：**登记与去重解耦** ——
#   · 去重仍按旧口径（同一个结构名不重复进 structural_amps）；
#   · 但 **信念登记**每圈都做（复现是 D2 的前提，被去重挡掉就永远凑不齐来源）。
#   · `layer` 改传**层名**（`layer_name`），圈号单独传（`round_no`）。
#   · `attack` / `resolved_by` 两类迁移驱动接进来。
_F1_NEW = '''        _bl = str(product.get("_layer_name") or layer or "")
        _br = product.get("_round_no", 0)
        try:
            _br = int(_br or 0)
        except (TypeError, ValueError):
            _br = 0
        # [D1 信念条目] **登记与去重解耦**：
        #   · `structural_amps` 仍按旧口径去重（同一个结构名不重复入列）；
        #   · 但信念登记**每圈都做** —— 复现是 D2「连续 k 圈被 ≥2 来源
        #     独立复现」的前提，被去重挡在外面就永远凑不齐来源。
        #   · `sources` 用**层名**（0/1/both/all）：同一主张被不同层独立
        #     提炼才算「独立复现」；用圈号会让「同一层反复说」冒充独立。
        for sa in (product.get("structural_amps") or []):
            s = str(sa).strip()
            if not s:
                continue
            _is_new = not any(_similar(s, x, _DUP_SIM)
                              for x in self.undecidable_channel["structural_amps"])
            if _is_new:
                self.undecidable_channel["structural_amps"].append(s[:200])
            _atk = []
            _why_atk = str(product.get("_belief_attack") or "").strip()
            if _why_atk:
                _atk = [_why_atk[:40]]
            _res = str(product.get("_belief_resolved") or "").strip()
            self.upsert_belief(s[:200], ground=("layer" + _bl) if _bl else "",
                               round_no=_br,
                               sources=[("layer" + _bl) if _bl else "unknown"],
                               attack=(_atk or None),
                               resolved_by=(_res or None))'''

repl(_F1_OLD, _F1_NEW, "F1/F2/F3 D1-D2 登记与去重解耦 + 层名 + 迁移驱动")

# ══════════════════════════════════════════════════════════════════
# F4：D3 接线 —— 每层入库后刷新语义熵
# ══════════════════════════════════════════════════════════════════
# 挂在 add_undecidable 的**出口**（登记完所有条目之后）
_F4_ANCHOR = '''        aspects = self.undecidable_channel.get("und_aspects", [])'''
_F4_NEW = '''        # [D3 语义熵] 每层入库后刷新一次（**唯一调用点**）：
        #   产物里的 `semantic_entropy` 由此有值，不再恒为 null。
        #   ★ 失败不拦（观测失败不该改变主路径结果）。
        try:
            self.refresh_belief_entropy()
        except Exception:
            pass
        aspects = self.undecidable_channel.get("und_aspects", [])'''
repl(_F4_ANCHOR, _F4_NEW, "F4 D3 语义熵接线（唯一调用点）")

# ══════════════════════════════════════════════════════════════════
# F5：A3 出口 —— 双读数进 View.to_dict（层/圈级，语义正确）
# ══════════════════════════════════════════════════════════════════
# `View.to_dict` 原来是 `asdict(self)`，而 `asdict` **不收集 property**
# ⇒ `touch_rate` / `aspect_carry_rate` 永远进不了产物。
# ★ 只补出口，**不改两个 property 的语义**（口径不动）。
_F5_OLD = '''    def to_dict(self) -> dict:
        return asdict(self)


CHANNELS = ("content", "context", "self")'''
_F5_NEW = '''    def to_dict(self) -> dict:
        d = asdict(self)
        # [A3 双读数出口] `asdict` **不收集 property** ⇒ 两个读数原本
        #   永远进不了产物（能力在、看不见）。这里显式补出口：
        #   ★ 两个读数**各占一个键**，永不合成一个分（红线「未对齐合法」）；
        #   ★ 算不出（空池）就**不写这个键** —— 不印 0.00 冒充读数。
        try:
            _tr = self.touch_rate
            if _tr is not None:
                d["touch_rate"] = round(float(_tr), 4)
        except Exception:
            pass
        try:
            _acr = self.aspect_carry_rate
            if _acr is not None:
                d["aspect_carry_rate"] = round(float(_acr), 4)
        except Exception:
            pass
        return d


CHANNELS = ("content", "context", "self")'''
repl(_F5_OLD, _F5_NEW, "F5 A3 双读数进 View.to_dict")

# ══════════════════════════════════════════════════════════════════
# F5c：D1 四态统计出口（Pool.to_dict 补 belief_status_counts）
# ══════════════════════════════════════════════════════════════════
_F5C_OLD = '''        if self.probe_stop_history:
            d["probe_stop_history"] = self.probe_stop_history'''
_F5C_NEW = '''        if self.probe_stop_history:
            d["probe_stop_history"] = self.probe_stop_history
        # [D1 四态统计] 信念状态计数（可观测量）：给「稳不稳」一个读数出口。
        #   `belief_status_counts()` 原本零调用点 ⇒ 能力在、产物读不到。
        if self.belief_items:
            d["belief_status_counts"] = self.belief_status_counts()'''
repl(_F5C_OLD, _F5C_NEW, "F5c D1 四态统计出口")

# ══════════════════════════════════════════════════════════════════
# F6：A1 编号统一 —— untouched 写入带 id
# ══════════════════════════════════════════════════════════════════
_F6A_OLD = '''        for t in _anchor_touched:
            view.anchor_touched.append({"desc": t, "source": "anchor"})
            view.add_aspect_unit(t, source="anchor", polarity="阳",
                                 ground="anchor")
        for u in anchor_untouched:
            view.untouched.append({"desc": u, "source": "anchor"})
            view.add_aspect_unit(u, source="anchor", polarity="阴",
                                 ground="anchor")'''
_F6A_NEW = '''        for t in _anchor_touched:
            _u_t = view.add_aspect_unit(t, source="anchor", polarity="阳",
                                        ground="anchor")
            view.anchor_touched.append({"desc": t, "source": "anchor",
                                        "id": (_u_t or {}).get("id", "")})
        for u in anchor_untouched:
            _u_u = view.add_aspect_unit(u, source="anchor", polarity="阴",
                                        ground="anchor")
            # [A1 编号统一] `untouched` 必须带 `id` —— 渲染前缀与
            #   covers 靶子共用同一个编号，否则「A1」在两处指向不同物。
            view.untouched.append({"desc": u, "source": "anchor",
                                   "id": (_u_u or {}).get("id", "")})'''
repl(_F6A_OLD, _F6A_NEW, "F6a 锚点侧 untouched/anchor_touched 带 id")

# 第二处 untouched 写入（judge 侧）
_F6B_ANCHOR = '''                    view.untouched.append({"desc": c.desc, "source": "judge"})'''
_F6B_NEW = '''                    _u_j = view.add_aspect_unit(c.desc, source="judge",
                                                polarity="阴", ground="anchor")
                    view.untouched.append({"desc": c.desc, "source": "judge",
                                           "id": (_u_j or {}).get("id", "")})'''
repl(_F6B_ANCHOR, _F6B_NEW, "F6b judge 侧 untouched 带 id")

# ══════════════════════════════════════════════════════════════════
# F7：A1 编号对齐 —— aspect_targets 优先用 aspect_units 的 id
# ══════════════════════════════════════════════════════════════════
_F7_OLD = '''        for _i, _s in enumerate(self.covered_unders or [], 1):
            _put("A%d" % _i, "covered_under", _s)
        return out'''
_F7_NEW = '''        # ★ [A1 编号统一] 方面单元优先用 `aspect_units` **已分配**的 id
        #   （与渲染前缀同一套编号）；只有对不上时才按位置临时编号。
        _aunit_by_desc = {}
        for _u in (self.aspect_units or []):
            _d = str(_u.get("desc") or "").strip()
            _uid = str(_u.get("id") or "").strip()
            if _d and _uid:
                _aunit_by_desc.setdefault(_d, _uid)
        for _i, _s in enumerate(self.covered_unders or [], 1):
            _sid = _aunit_by_desc.get(str(_s or "").strip()) or ("A%d" % _i)
            _put(_sid, "covered_under", _s)
        return out'''
repl(_F7_OLD, _F7_NEW, "F7 A1 编号对齐（aspect_targets 用真 id）")

# ══════════════════════════════════════════════════════════════════
# F8：E2 floor 默认值 0.0 → 0.02
# ══════════════════════════════════════════════════════════════════
_F8_ANCHOR = "_GAIN_MARGINAL_FLOOR = 0.0"
_F8_NEW = ("_GAIN_MARGINAL_FLOOR = 0.02   # G ∈ [0,1]；默认须 > 0，"
           "否则 below_floor 分支恒不触发")
_r8 = find_row(_F8_ANCHOR)
lines[_r8] = _F8_NEW
_applied.append("F8 E2 marginal floor 0.0 -> 0.02")

# ══════════════════════════════════════════════════════════════════
# F9：E1 落盘 —— 探针 dict 补 gain_source
# ══════════════════════════════════════════════════════════════════
_F9_OLD = '''            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2),
                        "covers": covers})'''
_F9_NEW = '''            # [E1 双写落盘] 引擎算的 G 与它的**来源**必须落在**同一份**
            #   dict 上 —— 只写进「喂下一轮」的副本 = 产物里读不到来源。
            _eng = p.get("expected_gain_engine", None)
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2),
                        "expected_gain_engine": (
                            round(float(_eng), 4) if _eng is not None else None),
                        "gain_source": str(p.get("gain_source") or "model"),
                        "covers": covers})'''
repl(_F9_OLD, _F9_NEW, "F9 探针落盘带 gain_source / expected_gain_engine")

# ══════════════════════════════════════════════════════════════════
# F10：给 add_undecidable 的 product 注入「层名 + 圈号 + 迁移驱动」
#      —— F1/F2/F3 依赖这些键（单一注入点，避免多处各写一份）
# ══════════════════════════════════════════════════════════════════
_F10_OLD = '''            pool.add_undecidable(
                view.undecidable_product,
                und_aspects=und_aspects, layer=layer,
                covered_aspects=list(
                    getattr(view, "covered_aspects", None) or []))'''
_F10_NEW = '''            # [D1/D2 元数据注入] 层名 / 圈号 / 迁移驱动**由这里统一注入**
            #   —— `layer` 实参在本仓库常指**圈号**（见 `layer_no = r + 1`），
            #   层名另走 `view.entry`；两者的语义差正是「独立复现」能否成立的关键。
            _und_prod = view.undecidable_product
            try:
                _und_prod["_layer_name"] = str(getattr(view, "entry", "") or "")
                _und_prod["_round_no"] = int(layer or 0)
                # 攻击证据：不可判定通道里被点名的冲突（非空即「被质疑」）
                _atk = getattr(view, "collision", "") or ""
                if not _atk:
                    _atk = str(getattr(view, "duel_conflict", "") or "")
                if _atk:
                    _und_prod["_belief_attack"] = str(_atk)[:80]
                # 已清偿：本层可判定通道答出的条 ⇒ resolved
                _res = ""
                _dc = getattr(view, "decidable_product", None) or {}
                if _dc:
                    _ans = _dc.get("answered") or _dc.get("resolutions") or []
                    if _ans:
                        _res = "decidable_channel"
                if _res:
                    _und_prod["_belief_resolved"] = _res
            except Exception:
                pass
            pool.add_undecidable(
                _und_prod,
                und_aspects=und_aspects, layer=layer,
                covered_aspects=list(
                    getattr(view, "covered_aspects", None) or []))'''
repl(_F10_OLD, _F10_NEW, "F10 D1/D2 元数据统一注入")

# ══════════════════════════════════════════════════════════════════
# F11：Pool 加 `aspect_units` 字段（A1 编号体系在池级可用）
#      + `merge` 同步（View→Pool 时把单元带过来）
# ══════════════════════════════════════════════════════════════════
_F11A_OLD = '''    covered_unders: List[str] = field(default_factory=list)
    anchors: List[dict] = field(default_factory=list)'''
_F11A_NEW = '''    covered_unders: List[str] = field(default_factory=list)
    #  [A1 方面单元] 池级镜像 —— `aspect_targets_v12327` 要按**真 id**
    #    对账，而 id 是 View 分配的 ⇒ 必须同步过来（否则两套编号又分叉）。
    aspect_units: List[dict] = field(default_factory=list)
    anchors: List[dict] = field(default_factory=list)'''
repl(_F11A_OLD, _F11A_NEW, "F11a Pool.aspect_units 字段")

# merge 里同步（按 id 去重并入）
_F11B_OLD = '''        for m in meta:
            if m and m not in self.meta:
                self.meta.append(m)'''
_F11B_NEW = '''        for m in meta:
            if m and m not in self.meta:
                self.meta.append(m)
        # [A1 方面单元] 池级同步：按 **id** 去重并入（同 id 只留一条）。
        for _u in (aspect_units or []):
            if not isinstance(_u, dict):
                continue
            _uid = str(_u.get("id") or "").strip()
            if not _uid:
                continue
            if not any(str(x.get("id") or "") == _uid
                       for x in self.aspect_units):
                self.aspect_units.append(_u)'''
repl(_F11B_OLD, _F11B_NEW, "F11b merge 同步 aspect_units")

# merge 签名加 aspect_units
_F11C_OLD = '''    def merge(self, amps, threads, meta, probes=None, suspensions=None,
              thr=None, susp_thr=None):'''
_F11C_NEW = '''    def merge(self, amps, threads, meta, probes=None, suspensions=None,
              thr=None, susp_thr=None, aspect_units=None):'''
repl(_F11C_OLD, _F11C_NEW, "F11c merge 签名加 aspect_units")

# Pool.to_dict 出口
_F11D_OLD = '''        # [D1 四态统计] 信念状态计数（可观测量）：给「稳不稳」一个读数出口。
        #   `belief_status_counts()` 原本零调用点 ⇒ 能力在、产物读不到。
        if self.belief_items:
            d["belief_status_counts"] = self.belief_status_counts()'''
_F11D_NEW = '''        # [D1 四态统计] 信念状态计数（可观测量）：给「稳不稳」一个读数出口。
        #   `belief_status_counts()` 原本零调用点 ⇒ 能力在、产物读不到。
        if self.belief_items:
            d["belief_status_counts"] = self.belief_status_counts()
        # [A1 方面单元] 池级镜像出口（A1~An 编号可在产物里审计）。
        if self.aspect_units:
            d["aspect_units"] = self.aspect_units'''
repl(_F11D_OLD, _F11D_NEW, "F11d Pool.to_dict 出口 aspect_units")

# 调用点把 view.aspect_units 传进 merge
_F11E_OLD = '''        pool.merge(view.amps, view.threads, view.meta, view.probes,
                   thr=_sim_cfg.get("dedup", _DEDUP_SIM),
                   susp_thr=_sim_cfg.get("dedup_susp", _DEDUP_SUSP_SIM))'''
_F11E_NEW = '''        pool.merge(view.amps, view.threads, view.meta, view.probes,
                   thr=_sim_cfg.get("dedup", _DEDUP_SIM),
                   susp_thr=_sim_cfg.get("dedup_susp", _DEDUP_SUSP_SIM),
                   aspect_units=list(getattr(view, "aspect_units", None) or []))'''
repl(_F11E_OLD, _F11E_NEW, "F11e 调用点同步 aspect_units")

# ══════════════════════════════════════════════════════════════════
# 版本号两处
# ══════════════════════════════════════════════════════════════════
_r = find_row('__version__ = "1.23.27"')
lines[_r] = '__version__ = "1.23.28"'
_applied.append("版本号 __version__ -> 1.23.28")

# docstring 标题
for i, ln in enumerate(lines[:200]):
    if "元 DGTF · v1.23.27" in ln:
        lines[i] = ln.replace("v1.23.27", "v1.23.28")
        _applied.append("docstring 标题 -> v1.23.28")
        break
else:
    raise AssertionError("未找到 docstring 标题")

# ══════════════════════════════════════════════════════════════════
out = "\n".join(lines)
assert out.count("\r\n") == 0
out_crlf = out.replace("\n", "\r\n")
SRC.write_bytes(out_crlf.encode("utf-8"))

# ── 落盘校验（换一条命令独立复核之前先自检）──
b = SRC.read_bytes()
assert b.count(b"\r\r\n") == 0, "CRCRLF 出现！"
assert b.count(b"\n") == b.count(b"\r\n"), "不是纯 CRLF！"

print("已应用 %d 项：" % len(_applied))
for x in _applied:
    print("  · " + x)
print()
print("主文件：%d 行 / %d bytes / CRCRLF=%d"
      % (len(lines), len(b), b.count(b"\r\r\n")))
