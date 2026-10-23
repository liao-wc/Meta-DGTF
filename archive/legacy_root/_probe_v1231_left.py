# -*- coding: utf-8 -*-
"""[v1.23.1 遗留收尾] 探针：真圈号（round_no）+ tier 提案（待审）。

覆盖三条遗留：
  · 遗留3 round_no 换真圈号（含**配额的每圈语义**这一实质后果）；
  · 遗留2 tier 提案（默认关 / 纯留痕 / 不改任何字段）；
  · 3 个变异体（M1 提案写进 item["tier"] / M2 round_no 退回拆解序号 /
    M3 证据钩子退回前置口径）—— 判据必须有判别力。

用法：python _probe_v1231_left.py [元DGTF-V1.23.1.py]
改前跑（v1.23.0）应大量报红（`_web_tier_proposal` 等符号不存在）。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.1.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

spec = importlib.util.spec_from_file_location("dgtf_l1", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_l1"] = mod
spec.loader.exec_module(mod)

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


# ---------------------------------------------------------- 0 改前兼容门
#  ★ 跑改前版本（v1.23.0）时这些符号本来就不存在 —— 直接崩在中间的
#    TypeError 会把「改前读数」变成一条 traceback（本项目反复踩）。
#    所以先做一次显式兼容检查：缺一个就整篇报红退出，读数可记录。
_COMPAT = (
    (hasattr(mod, "_web_tier_proposal"), "存在 _web_tier_proposal"),
    (hasattr(mod, "_web_domain_of"), "存在 _web_domain_of"),
    (hasattr(getattr(mod, "WebSearchCache", object), "domains_load"),
     "存在 WebSearchCache.domains_load"),
    ("tier_proposal" in (mod.DEFAULT_CONFIG.get("web_search") or {}),
     "web_search 配置含 tier_proposal"),
    ("domain_tier_rules" in (mod.DEFAULT_CONFIG.get("web_search") or {}),
     "web_search 配置含 domain_tier_rules"),
    ("web_tier_proposals" in getattr(mod.Pool, "__dataclass_fields__", {}),
     "Pool 含 web_tier_proposals"),
)
_miss = [t for ok, t in _COMPAT if not ok]
if _miss:
    for _t in _miss:
        print("  ✗ 兼容门：" + _t)
    print("\n改前版本（%s）：遗留收尾的 API 尚未具备 → 整篇判红" % SRC.name)
    print("\nPASS %d / FAIL %d" % (len(_COMPAT) - len(_miss), len(_COMPAT)))
    sys.exit(1)


class _SC:
    """桩客户端：成功档返回 1 条（url 可控），用于 tier 提案 / 圈号判据。"""

    def __init__(self, cache, url="https://www.example.gov.cn/a/b", tier=3):
        self.cache = cache
        self.calls = 0
        self.cache_hits = 0
        self.url = url
        self.tier = tier

    def search(self, q, max_n=8):
        self.calls += 1
        return [{"claim": "桩：" + str(q), "url": self.url,
                 "source": "s", "tier": self.tier}], ""


def _cfg(**over):
    c = {"web_search": dict(mod.DEFAULT_CONFIG.get("web_search") or {})}
    for k in ("quota", "stages"):
        c["web_search"][k] = dict(c["web_search"].get(k) or {})
    c["web_search"]["domain_tier_rules"] = list(
        c["web_search"].get("domain_tier_rules") or [])
    c["web_search"].update(over)
    return c


def _mkmeta(srcdir, cfg=None, url="https://www.example.gov.cn/a/b"):
    cfg = cfg or _cfg(enabled=True, as_evidence="evidence")
    ck_ = mod.WebSearchCache(24, root=str(srcdir))
    o = object.__new__(mod.MetaDGTF)
    o.config = cfg
    o.pools = {k: mod.Pool() for k in ("0", "1", "both", "all")}
    o.vp = lambda *a, **k: None
    o._web_gate = mod.WebSearchGate(cfg)
    o._web_client = _SC(ck_, url=url)
    o._web_prep_seq = 0
    o.decidability_result = {"undecidable_aspects": ["[外] 上游是否有官方标准"]}
    return o


# ============================================================ 1 round_no 语义
ck("L1.1 前置圈号 = 0",
   getattr(mod.MetaDGTF, "_research_round_no", None) is not None
   and mod.MetaDGTF._research_round_no(
       object.__new__(mod.MetaDGTF)) == 0,
   "原先返回拆解序号（每跑恒 1）")

_o = _mkmeta(Path(tempfile.mkdtemp()), _cfg(enabled=True, as_evidence="evidence"))
_d = _o._research_web_prep("问题")
_p1 = _o.pools["1"]
ck("L1.2 前置检索 round = 0 且 round_kind = pre",
   bool(_p1.web_results)
   and all(int(x.get("round", -1)) == 0 for x in _p1.web_results)
   and all(x.get("round_kind") == "pre" for x in _p1.web_results),
   repr([(x.get("round"), x.get("round_kind")) for x in _p1.web_results][:2]))
ck("L1.3 前置序号走 pre_seq（≥1，且不再是圈号）",
   all(int(x.get("pre_seq") or 0) >= 1 for x in _p1.web_results),
   repr([x.get("pre_seq") for x in _p1.web_results][:3]))

# 圈内：证据钩子用 update_deferrals 传进来的 layer
_o2 = _mkmeta(Path(tempfile.mkdtemp()))
_o2._web_evidence_hook(
    {"to": "partial", "_sq_text": "老城区管网重现期是多少"}, 3)
_w = _o2.pools["1"].web_results
ck("L1.4 证据钩子用真圈号 3（不是前置 0）",
   bool(_w) and all(int(x.get("round", -1)) == 3
                    and x.get("round_kind") == "in" for x in _w),
   repr([(x.get("round"), x.get("round_kind")) for x in _w][:2]))

_v = mod.View(entry="both")
_v.adjudications = [{"tension": "A 与 B 冲突"}]
_v.meta = []
_o3 = _mkmeta(Path(tempfile.mkdtemp()))
_o3._web_duel_arbitration(_v, 2)
_a = _o3.pools["both"].web_arbitration
ck("L1.5 对撞仲裁用真圈号 2",
   bool(_a) and all(int(x.get("round", -1)) == 2 for x in _a),
   repr([x.get("round") for x in _a][:2]))

_v2 = mod.View(entry="all")
_v2.meta = []
_o4 = _mkmeta(Path(tempfile.mkdtemp()))
_o4._web_meta_clean_check(_v2, ["未覆盖区间 X"], 5)
_c = _o4.pools["all"].web_clean_check
ck("L1.6 元层核对用真圈号 5",
   bool(_c) and all(int(x.get("round", -1)) == 5 for x in _c),
   repr([x.get("round") for x in _c][:2]))

# ★ 实质后果：per_stage_round 真的是「每圈」
_q = _cfg(enabled=True, as_evidence="evidence",
          quota={"per_stage_round": 1, "per_stage_total": 10,
                 "per_run_total": 10})
_o5 = _mkmeta(Path(tempfile.mkdtemp()), _q)
_r1 = _o5._web_search("research_evidence", ["a"], 1)
_r2 = _o5._web_search("research_evidence", ["b"], 1)
_r3 = _o5._web_search("research_evidence", ["c"], 2)
ck("L1.7 ★ 三层配额真的是「每环节每圈」（同圈拦、新圈放）",
   len(_r1) == 1 and len(_r2) == 0 and len(_r3) == 1,
   "同圈 %d/%d → 新圈 %d" % (len(_r1), len(_r2), len(_r3)))

# ============================================================ 2 tier 提案
ck("L2.1 _web_domain_of 取域名",
   mod._web_domain_of("https://www.Example.GOV.cn/a?b=1") == "example.gov.cn"
   and mod._web_domain_of("http://user@a.b.com:8080/x") == "a.b.com"
   and mod._web_domain_of("") == "",
   repr(mod._web_domain_of("https://www.Example.GOV.cn/a?b=1")))

_known = {"old.com"}
_res = [{"url": "https://www.example.gov.cn/s", "tier": 3},
        {"url": "http://blog.foo.com/p", "tier": 3},
        {"url": "https://mystery.io/x", "tier": 3},
        {"url": "https://blog.foo.com/dup", "tier": 3},
        {"url": "https://old.com/y", "tier": 3}]
_snap = json.dumps(_res, sort_keys=True)
_pr = mod._web_tier_proposal(_res, _cfg(), _known)
_pr2 = mod._web_tier_proposal(_res, _cfg()["web_search"], _known)
ck("L2.2b ★ 两种入参（完整 config / 子段）结果逐条相同",
   json.dumps(_pr, sort_keys=True) == json.dumps(_pr2, sort_keys=True), "")
_by = {x["domain"]: x for x in _pr}
ck("L2.2 提案：命中规则 / 未知保守 3 / 去重（同域名只提一次）",
   _by.get("example.gov.cn", {}).get("proposed_tier") == 1
   and _by.get("blog.foo.com", {}).get("proposed_tier") == 4
   and _by.get("mystery.io", {}).get("proposed_tier") == 3
   and len([x for x in _pr if x["domain"] == "blog.foo.com"]) == 1,
   repr({k: v["proposed_tier"] for k, v in _by.items()}))
ck("L2.3 first_seen：已知域名 False / 新域名 True",
   _by.get("old.com", {}).get("first_seen") is False
   and _by.get("mystery.io", {}).get("first_seen") is True, "")
ck("L2.4 ★ 纯函数：不改入参（输入逐字未变）",
   json.dumps(_res, sort_keys=True) == _snap, "")
ck("L2.5 提案一律 confirmed = False（待审）",
   all(x.get("confirmed") is False for x in _pr), "")

# 默认关：零副作用（不写 _domains.json、不挂提案）
_d1 = Path(tempfile.mkdtemp())
_o6 = _mkmeta(_d1)          # 默认 tier_proposal=False
_o6._web_search("research_evidence", ["a"], 1)
ck("L2.6 ★ 默认关：不挂 pool.web_tier_proposals",
   _o6.pools["1"].web_tier_proposals == [], "")
ck("L2.7 ★ 默认关：不写 cache/websearch/_domains.json",
   not (_d1 / "_domains.json").exists(), "")
ck("L2.8 默认关：无 [W-TIER?] 留痕",
   not any("[W-TIER" in str(x) for x in _o6.pools["1"].meta), "")
_t_off = [x.get("tier") for x in _o6.pools["1"].web_results]

# 开启：提案进待审队列 + 域名登记；tier 字段**逐条不变**
_d2 = Path(tempfile.mkdtemp())
_o7 = _mkmeta(_d2, _cfg(enabled=True, as_evidence="evidence",
                        tier_proposal=True))
_o7._web_search("research_evidence", ["a"], 1)
_prop = _o7.pools["1"].web_tier_proposals
_t_on = [x.get("tier") for x in _o7.pools["1"].web_results]
ck("L2.9 开启：提案进 pool.web_tier_proposals + [W-TIER?] 留痕",
   bool(_prop) and any("[W-TIER?]" in str(x) for x in _o7.pools["1"].meta),
   repr([str(x)[:60] for x in _o7.pools["1"].meta if "[W-TIER" in str(x)][:1]))
ck("L2.10 开启：域名进 cache/websearch/_domains.json",
   (_d2 / "_domains.json").is_file()
   and "example.gov.cn" in json.loads(
       (_d2 / "_domains.json").read_text(encoding="utf-8"))["domains"], "")
ck("L2.11 ★ 提案是纯留痕：flag 开/关时 item['tier'] 逐条相同",
   _t_on == _t_off, "off=%r on=%r" % (_t_off, _t_on))
ck("L2.12 提案不挂 confirmed 为真（不是生效值）",
   all(x.get("confirmed") is False for x in _prop), "")
_pa = mod.Pool()
_pa.web_results = [{"id": "W1", "claim": "c1", "tier": 3}]
_pa.web_as_evidence = True
_pb = mod.Pool()
_pb.web_results = [{"id": "W1", "claim": "c1", "tier": 3}]
_pb.web_as_evidence = True
_pb.web_tier_proposals = [{"domain": "example.gov.cn", "proposed_tier": 1,
                           "confirmed": False}]
ck("L2.13 ★ 引用表只由 web_results 决定：多挂提案不改变它（不进判定路径）",
   dict(mod._citation_table(None, _pa)) == dict(mod._citation_table(None, _pb))
   and "W1" in dict(mod._citation_table(None, _pb)),
   repr(sorted(dict(mod._citation_table(None, _pb)).keys())[:6]))

# ============================================================ 3 变异体
MUT = (
    ("M1 提案写进 item['tier']（必须判红：开/关 tier 不再相同）",
     "                    if _ck is not None:\n"
     "                        _ck.domains_save([x.get(\"domain\") for x in _pr])\n",
     "                    for _it in out:\n"
     "                        if int(_it.get('tier', 3) or 3) == 3 and _pr:\n"
     "                            _it['tier'] = int(_pr[0]['proposed_tier'])\n"
     "                    if _ck is not None:\n"
     "                        _ck.domains_save([x.get(\"domain\") for x in _pr])\n"),
    ("M2 round_no 退回拆解序号（必须判红：前置不再是 0）",
     "          圈内一律用 `layer_no`：`_web_evidence_hook` 的 `layer`、\n"
     "          `_finalize_layer_common` 的 `r_actual + 1`。\n"
     "        \"\"\"\n"
     "        return 0\n",
     "          圈内一律用 `layer_no`：`_web_evidence_hook` 的 `layer`、\n"
     "          `_finalize_layer_common` 的 `r_actual + 1`。\n"
     "        \"\"\"\n"
     "        return int(getattr(self, \"_web_prep_seq\", 0) or 0)\n"),
    ("M3 证据钩子退回前置口径（必须判红：圈号不再是 3）",
     "        _rn = int(layer or 0) or 1        # 只在圈内被调；保险起见 ≥ 1\n"
     "        return self._web_search(\"research_evidence\", _qs, _rn,\n"
     "                                used_as=\"evidence\")\n",
     "        return self._web_search(\"research_evidence\", _qs,\n"
     "                                self._research_round_no(),\n"
     "                                used_as=\"evidence\")\n"),
)

_src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
_td = Path(tempfile.mkdtemp())
for _i, (_name, _o, _n) in enumerate(MUT):
    _c = _src.count(_o)
    if _c != 1:
        ck("L3.%d %s" % (_i + 1, _name[:14] + " · 变异体可构造"), False,
           "锚点命中 %d 次（应 1）" % _c)
        continue
    _mp = _td / ("mut_l1_%d.py" % _i)
    _mp.write_bytes(_src.replace(_o, _n).replace("\n", "\r\n").encode("utf-8"))
    try:
        _spec = importlib.util.spec_from_file_location("mut_l1_%d" % _i, str(_mp))
        _mm = importlib.util.module_from_spec(_spec)
        sys.modules["mut_l1_%d" % _i] = _mm
        _spec.loader.exec_module(_mm)
    except Exception as _e:  # noqa: BLE001
        ck("L3.%d %s" % (_i + 1, _name[:24]), False, "变异体导入失败：" + str(_e))
        continue
    _red = False
    try:
        if _name.startswith("M1"):
            _dd = Path(tempfile.mkdtemp())
            _cfg1 = _cfg(enabled=True, as_evidence="evidence")
            _cfgo = _cfg(enabled=True, as_evidence="evidence",
                         tier_proposal=True)

            def _tiers(cfg, root):
                o = object.__new__(_mm.MetaDGTF)
                o.config = cfg
                o.pools = {"1": _mm.Pool()}
                o.vp = lambda *a, **k: None
                o._web_gate = _mm.WebSearchGate(cfg)
                o._web_client = _SC(_mm.WebSearchCache(24, root=str(root)))
                o._web_prep_seq = 0
                o._web_search("research_evidence", ["a"], 1)
                return [x.get("tier") for x in o.pools["1"].web_results]

            _red = _tiers(_cfgo, _dd) != _tiers(_cfg1, _dd / "off")
        elif _name.startswith("M2"):
            # ★ 必须让 `_web_prep_seq` > 0 —— 退回拆解序号的变异体在
            #   「序号为 0」时返回 0，判据会**看不出差别**（空过）。
            _mo2 = object.__new__(_mm.MetaDGTF)
            _mo2._web_prep_seq = 5
            _red = _mm.MetaDGTF._research_round_no(_mo2) != 0
        else:
            _mmo = object.__new__(_mm.MetaDGTF)
            _mmo.config = _cfg(enabled=True, as_evidence="evidence")
            _mmo.pools = {"1": _mm.Pool()}
            _mmo.vp = lambda *a, **k: None
            _mmo._web_gate = _mm.WebSearchGate(_mmo.config)
            _mmo._web_client = _SC(_mm.WebSearchCache(
                24, root=str(tempfile.mkdtemp())))
            _mmo._web_prep_seq = 7        # 退回拆解序号时会变成 7
            _mmo._web_evidence_hook({"_sq_text": "q"}, 3)
            _w = _mmo.pools["1"].web_results
            _red = (not _w) or int(_w[0].get("round", -1)) != 3
    except Exception:  # noqa: BLE001
        _red = True
    ck("L3.%d %s" % (_i + 1, _name[:40]), _red,
       "变异体下判据判红" if _red else "★ 变异体下判据**没判红**（无判别力）")

# ============================================================ 4 空票留痕
class _LLM3:
    """桩 llm：第 `empty` 票返回**合法 dict 但零条判决**。"""

    def __init__(self, empty=1):
        self.i = -1
        self.empty = empty

    def call(self, sysp, user, t, mx, json_mode=False, stage=None, **k):
        self.i += 1
        if self.i == self.empty:
            return '{"judgments": []}'
        return json.dumps({"judgments": [
            {"id": 1, "reason": "r", "decidability": "decidable"}]})

    def parse_json(self, raw):
        return json.loads(raw)


def _adj(empty, retry=0):
    # ★ [v1.23.2] 本版默认**空票重试 1 次**；要复现「空票无声」那条旧路径，
    #   必须显式把 `tri_vote_retry_empty` 置 0（= v1.23.1 行为）。
    o = object.__new__(mod.MetaDGTF)
    o.llm = _LLM3(empty)
    o.config = _cfg(enabled=False)
    o.config["actions"] = {"tri_vote_retry_empty": retry}
    o.pools = {"1": mod.Pool()}
    o.vp = lambda *a, **k: None
    o._web_gate = None
    subs = [{"id": 1, "question": "q", "decidability": "partial"}]
    o._adjudicate_sub_tristate_multi(subs, "Q")
    return o, subs


_o8, _s8 = _adj(1)
ck("L4.1 ★ 某票返回合法 dict 但零条判决 → 必须留痕（原先完全无声）",
   any("票可用" in str(x) for x in _o8.pools["1"].meta),
   repr(_o8.pools["1"].meta[:2]))
ck("L4.2 留痕必须写清「可用几票 / 空票几张」",
   any(("2/3" in str(x)) and ("空票 1" in str(x))
       for x in _o8.pools["1"].meta),
   repr(_o8.pools["1"].meta[:2]))
ck("L4.3 ★ 纯留痕：票的取值不受影响（该票等于弃权）",
   [v["label"] for v in _s8[0]["votes"]] == ["decidable", "decidable"],
   repr([v["label"] for v in _s8[0]["votes"]]))
_o9, _ = _adj(99)                      # 三票都正常
_o10, _s10 = _adj(1, retry=1)          # [v1.23.2] 默认重试 1 次
ck("L4.6 ★ 默认重试：空票重试一次就救回来 → 3 票可用、不报空票",
   len(_s10[0].get("votes") or []) == 3
   and not any("票可用" in str(x) for x in _o10.pools["1"].meta),
   repr([v["label"] for v in _s10[0].get("votes") or []]))
ck("L4.4 负对照：三票都正常 → **不**留痕",
   not any("票可用" in str(x) for x in _o9.pools["1"].meta),
   repr(_o9.pools["1"].meta[:2]))

# ★ 变异体要**真的抠掉留痕**：把 `if _empty_votes:` 关成 `if False:`。
#   第一版把前缀改名（`[三态多票]`→`[三态多票-NOLEAK]`）—— 判据找的是
#   「票可用」四个字，改名后**仍然命中** ⇒ 判据不判红、变异体没意义。
# ★ 换行一律 chr(10) 拼 —— 字面 "\n" 在这里是**两个字符**，永远匹配不上
#   （工具链多级转义，本项目已踩第 6 次）。
# ★ 锚点随实现更新（v1.23.3 把条件扩成
#   `_empty_votes or _id_shift or _id_bad`）—— 判据意图不变：
#   抠掉留痕本身。
_O_EMPTY = ('        if _empty_votes or _id_shift or _id_bad:' + chr(10) +
            '            _p1 = self.pools.get("1")',
            '        if False:' + chr(10) +
            '            _p1 = self.pools.get("1")')
if _src.count(_O_EMPTY[0]) == 1:
    _mp4 = _td / "mut_l1_empty.py"
    _mp4.write_bytes(_src.replace(*_O_EMPTY).replace("\n", "\r\n")
                     .encode("utf-8"))
    try:
        _spec4 = importlib.util.spec_from_file_location("mut_l1_empty",
                                                       str(_mp4))
        _mm4 = importlib.util.module_from_spec(_spec4)
        sys.modules["mut_l1_empty"] = _mm4
        _spec4.loader.exec_module(_mm4)
        _oA = object.__new__(_mm4.MetaDGTF)
        _oA.llm = _LLM3(1)
        _oA.config = _cfg(enabled=False)
        _oA.pools = {"1": _mm4.Pool()}
        _oA.vp = lambda *a, **k: None
        _oA._web_gate = None
        _oA._adjudicate_sub_tristate_multi(
            [{"id": 1, "question": "q", "decidability": "partial"}], "Q")
        _red4 = not any("票可用" in str(x)
                        for x in _oA.pools["1"].meta)
    except Exception:  # noqa: BLE001
        _red4 = True
    ck("L4.5 变异体「抠掉空票留痕」→ 判据判红", _red4, "")
else:
    ck("L4.5 变异体可构造", False, "锚点命中 %d 次" % _src.count(_O_EMPTY[0]))

# ============================================================ 汇总
_p = sum(1 for _, ok, _n in R if ok)
_f = len(R) - _p
for _t, _ok, _n in R:
    print(("  ✓ " if _ok else "  ✗ ") + _t + ("　" + _n if _n and not _ok else ""))
print("\nPASS %d / FAIL %d" % (_p, _f))
sys.exit(0 if _f == 0 else 1)
