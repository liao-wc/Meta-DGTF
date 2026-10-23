# -*- coding: utf-8 -*-
"""[v1.23.27 Step5] D1 · 信念条目（BeliefItem）四态机 + D2 · 迁移规则。

设计（`_设计_五机制算法重构_v12326.md` §3.4 D1/D2）：

D1 —— 把 `structural_amps` 从「字符串列表」**升级为带状态的信念条目**
（**不是替换**：旧的字符串列表继续写，新的 belief_items 并行）：

    BeliefItem = {id, text, ground, status, support, attack,
                  rounds_seen, semantic_entropy}

★ `status` **复用** `SUSPENSION_STATUS` 四态 —— **不新增枚举**
  （教训：「写枚举前先在本仓库找权威来源」）。

状态转移（D2 迁移规则，Markov 三角色语义）：
    · active  → stable    连续 k 圈被 ≥2 个**不同来源**独立复现
    · active  → revoked   出现 attack 且 attack 强度 > support
    · stable  → active    新 attack 出现（信念可被推翻，非单调）
    · 任意    → resolved  被 decidable_channel 回答（停止与清算分开）

★ 红线核对：
  · 悬置不打分 —— `status` 判的是**状态**，不是优良；`semantic_entropy`
    是可观测量，不是给主张打的分（D3 才有，本步先留 `None`）。
  · 停止与清算分开 —— `resolved` 只由 decidable_channel 触发。
  · 失败留痕 —— `revoked` 条目**保留不删**。

本步是**纯新增**：不改任何既有读数的口径。`structural_amps` 一字不动。
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
# 1. 模块级：信念条目的**单一构造点** + 迁移规则纯函数
# ══════════════════════════════════════════════════════════════════
sub(
    "def make_aspect_unit(desc, source=\"anchor\", polarity=\"阴\",\n",
    '''# ── [v1.23.27 D1/D2] 信念条目（BeliefItem）与四态迁移 ──────────────
#  ★ `status` **复用** SUSPENSION_STATUS —— 不新增枚举。
#  ★ 迁移规则写成**模块级纯函数**：判据可以脱离引擎直接喂它（可负对照），
#    也避免「同一件事两条实现」（本项目老坑）。
_BELIEF_STATUS = SUSPENSION_STATUS          # ← 别名，不是新枚举

#: `active → stable` 需要的**连续圈数**（D2 的 k）。
_BELIEF_STABLE_K = 2
#: `active → stable` 需要的**不同来源数**（D2 的 ≥2 个独立来源）。
_BELIEF_STABLE_SOURCES = 2


def make_belief_item(text, ground="", status="active", item_id="",
                     support=None, attack=None, rounds_seen=None,
                     semantic_entropy=None):
    """构造一个 BeliefItem（dict）—— **全工程唯一构造点**。

    ★ `status` 不在 `_BELIEF_STATUS` 里时**归一化到 "active"**（不抛错）：
      状态越界不该让整条主张消失 —— 那是「失败留痕」的反面。
    ★ `semantic_entropy` 默认 `None`（**不是 0.0**）：D3 还没算过与
      「算出来是 0」是两回事，印 0.00 就是自欺（本项目老坑）。
    """
    s = str(text or "").strip()
    if not s:
        return {}
    st = str(status or "").strip()
    if st not in _BELIEF_STATUS:
        st = "active"
    return {
        "id": str(item_id or ""),
        "text": s[:200],
        "ground": str(ground or ""),
        "status": st,
        "support": [str(x) for x in (support or [])],
        "attack": [str(x) for x in (attack or [])],
        "rounds_seen": list(rounds_seen or []),
        "semantic_entropy": semantic_entropy,
    }


def belief_transition(item, *, round_no=0, sources=None, attack=None,
                      resolved_by=None):
    """D2 迁移规则：返回**新状态**（纯函数，不改入参）。

    参数语义：
      · `round_no`    本圈号 —— 记进 `rounds_seen`（同一圈不重复记）
      · `sources`     本圈**独立复现**这条主张的来源标签列表
                      （如 ["probe#2","th#1"]）—— 进 `support`
      · `attack`      本圈新出现的攻击证据标签列表 —— 进 `attack`
      · `resolved_by` 非空 ⇒ 被 decidable_channel 回答 ⇒ `resolved`

    ★ 优先级（写死，可负对照）：resolved > revoked > stable > 保持原状。
      为什么 resolved 最高：停止与清算分开 ⇒ 一旦被可判定通道回答，
      其余的「稳不稳 / 被不被质疑」都不再是这条主张的问题。
    """
    if not item:
        return "active"
    _cur = str(item.get("status") or "active")
    if _cur not in _BELIEF_STATUS:
        _cur = "active"

    # ① resolved：被可判定通道回答 ⇒ 直接清偿（最高优先级）
    if str(resolved_by or "").strip():
        return "resolved"

    _sup = list(item.get("support") or [])
    _atk = list(item.get("attack") or [])
    _rnd = [r for r in (item.get("rounds_seen") or [])]
    _seen = set()
    for _r in _rnd:
        try:
            _seen.add(int(_r))
        except (TypeError, ValueError):
            continue
    try:
        _rn = int(round_no or 0)
    except (TypeError, ValueError):
        _rn = 0

    # 累积本圈的复现来源与本圈的圈号
    for _s in (sources or []):
        _s = str(_s).strip()
        if _s and _s not in _sup:
            _sup.append(_s)
    for _a in (attack or []):
        _a = str(_a).strip()
        if _a and _a not in _atk:
            _atk.append(_a)
    if _rn and _rn not in _seen:
        _rnd.append(_rn)

    # ② revoked：有攻击且攻击面 ≥ 支持面（「质疑者胜出」）
    if _atk and len(_atk) >= len(_sup):
        return "revoked"

    # ③ stable：连续 k 圈被 ≥2 个**不同来源**独立复现
    if _cur in ("active", "stable"):
        _distinct_rounds = sorted(_seen | ({_rn} if _rn else set()))
        if (len(_sup) >= _BELIEF_STABLE_SOURCES
                and len(_distinct_rounds) >= _BELIEF_STABLE_K):
            return "stable"

    # ④ 有攻击但不占多数 ⇒ 从 stable 掉回 active（非单调，可被推翻）
    if _atk and _cur == "stable":
        return "active"

    return _cur


def make_aspect_unit(desc, source="anchor", polarity="阴",
''',
    "D1/D2 构造点+迁移")

# ══════════════════════════════════════════════════════════════════
# 2. View 新增 belief_items 字段
# ══════════════════════════════════════════════════════════════════
sub(
    "    aspect_units: List[dict] = field(default_factory=list)\n",
    "    aspect_units: List[dict] = field(default_factory=list)\n"
    "    # [v1.23.27 D1] 信念条目（带状态/证据/熵），与 structural_amps 双写。\n"
    "    # ★ `structural_amps`（字符串列表）**继续写**：它是历史 packed 的\n"
    "    #   口径，删了会让下游读数从「作证据」静默降级成「读不到」。\n"
    "    belief_items: List[dict] = field(default_factory=list)\n",
    "View.belief_items")

# ══════════════════════════════════════════════════════════════════
# 3. Pool 新增信念登记/迁移（紧跟符号函数之后）
# ══════════════════════════════════════════════════════════════════
sub(
    "    def _und_self_touch_symbols(self) -> dict:\n",
    '''    # ── [v1.23.27 D1/D2] 信念条目：登记 + 四态迁移 ──────────────
    def upsert_belief(self, text, *, ground="", round_no=0, sources=None,
                      attack=None, resolved_by=None):
        """登记/更新一条信念条目，返回 (item, 旧状态, 新状态)。

        ★ 认领规则：**同 id 优先，其次同 text**。同 text 认领让「模型换个
          说法重提同一主张」仍能连续 —— 这是 D2「连续 k 圈复现」的前提。
          （真正的语义聚类在 D3；这里先用精确 text，保守且可负对照。）
        ★ 迁移**一定**走 `belief_transition`（纯函数）⇒ 判据可脱离引擎测它。
        """
        items = self.belief_items
        _key = str(text or "").strip()
        if not _key:
            return {}, "active", "active"
        _tgt = None
        for _it in items:
            if str(_it.get("text", "")) == _key:
                _tgt = _it
                break
        if _tgt is None:
            _uid = "B%d" % (len(items) + 1)
            _tgt = make_belief_item(_key, ground=ground, item_id=_uid)
            if not _tgt:
                return {}, "active", "active"
            items.append(_tgt)
        _old = str(_tgt.get("status") or "active")
        _new = belief_transition(_tgt, round_no=round_no, sources=sources,
                                 attack=attack, resolved_by=resolved_by)
        # 就地更新（rounds_seen / support / attack 是累积量）
        _sup = list(_tgt.get("support") or [])
        for _s in (sources or []):
            _s = str(_s).strip()
            if _s and _s not in _sup:
                _sup.append(_s)
        _atk = list(_tgt.get("attack") or [])
        for _a in (attack or []):
            _a = str(_a).strip()
            if _a and _a not in _atk:
                _atk.append(_a)
        _rnd = list(_tgt.get("rounds_seen") or [])
        try:
            _rn = int(round_no or 0)
        except (TypeError, ValueError):
            _rn = 0
        if _rn and _rn not in _rnd:
            _rnd.append(_rn)
        _tgt["support"] = _sup
        _tgt["attack"] = _atk
        _tgt["rounds_seen"] = _rnd
        if ground and not _tgt.get("ground"):
            _tgt["ground"] = str(ground)
        _tgt["status"] = _new
        if _new != _old:
            self.belief_transitions.append({
                "id": _tgt.get("id", ""), "from": _old, "to": _new,
                "round": _rn,
                "why": ("resolved_by_decidable" if resolved_by
                        else ("attack_wins" if _new == "revoked"
                              else ("independent_recurrence" if _new == "stable"
                                    else "attack_reopened"))),
            })
        return _tgt, _old, _new

    def belief_status_counts(self) -> dict:
        """四态计数（**两向对账**用：计数之和必须 == 条目总数）。"""
        out = {s: 0 for s in _BELIEF_STATUS}
        for _it in self.belief_items:
            _s = str(_it.get("status") or "")
            if _s in out:
                out[_s] += 1
            else:
                out.setdefault("__unknown__", 0)
                out["__unknown__"] += 1
        return out

    def _und_self_touch_symbols(self) -> dict:
''',
    "Pool 信念登记")

# ══════════════════════════════════════════════════════════════════
# 4. Pool 新增字段（belief_items / belief_transitions）
# ══════════════════════════════════════════════════════════════════
sub(
    "    def add_undecidable(self, product: dict,\n",
    "    # [v1.23.27 D1] 信念条目（与 structural_amps 双写，不是替换）\n"
    "    belief_items: List[dict] = field(default_factory=list)\n"
    "    belief_transitions: List[dict] = field(default_factory=list)\n"
    "\n"
    "    def add_undecidable(self, product: dict,\n",
    "Pool 字段")

# ══════════════════════════════════════════════════════════════════
# 5. add_undecidable：把 structural_amps **同时**登记成 BeliefItem
# ══════════════════════════════════════════════════════════════════
sub(
    "        for sa in (product.get(\"structural_amps\") or []):\n"
    "            s = str(sa).strip()\n"
    "            if s and not any(_similar(s, x, _DUP_SIM)\n"
    "                             for x in self.undecidable_channel[\"structural_amps\"]):\n"
    "                self.undecidable_channel[\"structural_amps\"].append(s[:200])\n",
    "        for sa in (product.get(\"structural_amps\") or []):\n"
    "            s = str(sa).strip()\n"
    "            if s and not any(_similar(s, x, _DUP_SIM)\n"
    "                             for x in self.undecidable_channel[\"structural_amps\"]):\n"
    "                self.undecidable_channel[\"structural_amps\"].append(s[:200])\n"
    "                # [v1.23.27 D1] 双写：同一条主张**同时**进信念条目。\n"
    "                # ★ 来源 = 本层标签，独立复现的凭据（D2 的 ≥2 来源）。\n"
    "                self.upsert_belief(s[:200], ground=\"layer%s\" % layer,\n"
    "                                   round_no=int(layer or 0),\n"
    "                                   sources=[\"layer%s\" % layer])\n",
    "add_undecidable 双写 belief")

# ══════════════════════════════════════════════════════════════════
# 6b. add_decidable：可判定通道**真回答**时把对应信念置 resolved
#     （D2 规则 ④「任意 → resolved」：停止与清算分开 —— resolved 只由
#       decidable_channel 触发，不由「圈数够了」触发）
# ══════════════════════════════════════════════════════════════════
sub(
    "        ans = str(product.get(\"answer\", \"\")).strip()\n"
    "        if ans and len(ans) > 20:\n"
    "            self.decidable_channel[\"answers\"].append({\n"
    "                \"answer\": ans[:500],\n"
    "                \"answered_sub_ids\": list(product.get(\"answered_sub_ids\") or []),\n"
    "                \"evidence\": [str(e)[:200]\n"
    "                             for e in (product.get(\"evidence\") or [])][:5],\n"
    "            })\n",
    "        ans = str(product.get(\"answer\", \"\")).strip()\n"
    "        if ans and len(ans) > 20:\n"
    "            self.decidable_channel[\"answers\"].append({\n"
    "                \"answer\": ans[:500],\n"
    "                \"answered_sub_ids\": list(product.get(\"answered_sub_ids\") or []),\n"
    "                \"evidence\": [str(e)[:200]\n"
    "                             for e in (product.get(\"evidence\") or [])][:5],\n"
    "            })\n"
    "            # [v1.23.27 D2] ★ 可判定通道**真回答了** ⇒ 对应信念置 resolved。\n"
    "            #   「对应」的判定用 `answered_sub_ids` 里的 id 命中信念 id：\n"
    "            #   这是**符号**命中，不受尺子影响（与 A2 同一原则）。\n"
    "            #   ★ 命中不到就**什么都不做** —— 不猜、不按文本相似兜底：\n"
    "            #     猜错会把没被回答的主张标成 resolved（清算错账比不清算糟）。\n"
    "            _ans_ids = {str(x).strip()\n"
    "                        for x in (product.get(\"answered_sub_ids\") or [])\n"
    "                        if str(x).strip()}\n"
    "            for _it in self.belief_items:\n"
    "                _bid = str(_it.get(\"id\") or \"\").strip()\n"
    "                if _bid and _bid in _ans_ids:\n"
    "                    _old = str(_it.get(\"status\") or \"active\")\n"
    "                    if _old != \"resolved\":\n"
    "                        _it[\"status\"] = \"resolved\"\n"
    "                        self.belief_transitions.append({\n"
    "                            \"id\": _bid, \"from\": _old, \"to\": \"resolved\",\n"
    "                            \"round\": 0,\n"
    "                            \"why\": \"resolved_by_decidable\",\n"
    "                        })\n",
    "add_decidable resolved")

# ══════════════════════════════════════════════════════════════════
# 7. to_dict 出口（手工白名单，不同步 = 静默丢产物）
# ══════════════════════════════════════════════════════════════════
sub(
    "        if self.undecidable_channel:\n"
    "            _at = self.aspect_targets_v12327()\n"
    "            if _at:\n"
    "                d[\"aspect_targets\"] = _at\n",
    "        if self.undecidable_channel:\n"
    "            _at = self.aspect_targets_v12327()\n"
    "            if _at:\n"
    "                d[\"aspect_targets\"] = _at\n"
    "        # [v1.23.27 D1/D2] 信念条目与迁移轨迹：出口才能被下游读。\n"
    "        if self.belief_items:\n"
    "            d[\"belief_items\"] = self.belief_items\n"
    "        if self.belief_transitions:\n"
    "            d[\"belief_transitions\"] = self.belief_transitions\n",
    "Pool.to_dict belief")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out, "产出含 \\r\\r\\n"
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n"), "写回后不是纯 CRLF"
assert "\r\r\n" not in chk, "写回后含 \\r\\r\\n"

print("STEP5 OK  —— %d 处替换" % len(HITS))
for _t, _n in HITS:
    print("  · %-30s x%d" % (_t, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
