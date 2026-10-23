# -*- coding: utf-8 -*-
"""[v1.23.0 W2] 探针：研究层接入 + W# 编号 + 引用门 + W# 硬约束。

用法：python _probe_v123_w2.py [元DGTF-V1.23.0.py]

三段：
  A 结构判据（含负对照）
  B 行为判据（走生产入口）
  C **变异测试**：把关键实现抠掉后，同一批判据**必须判红**
    （结构不变式在现版必然通过 ⇒「通过」不构成判别力证据）
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.0.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC, "dgtf_w2")
txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

# ============================================================ A 结构
ck("A1 Pool 有 web_results/web_errors/web_as_evidence",
   all(hasattr(mod.Pool(), _k) for _k in
       ("web_results", "web_errors", "web_as_evidence")), "")
ck("A2 助手函数齐",
   all(hasattr(mod, _k) for _k in
       ("_next_web_id", "_web_evidence_gate", "_research_decompose_queries",
        "_research_evidence_queries", "_research_precedent_queries",
        "_web_digest_block")), "")
ck("A3 MetaDGTF 方法齐",
   all(hasattr(mod.MetaDGTF, _k) for _k in
       ("_web_search", "_research_web_prep", "_research_decompose_with_web",
        "_web_evidence_hook")), "")
ck("A4 W# 进 _citation_table（授权门）",
   'if getattr(pool, "web_as_evidence", False):' in txt
   and 'for _w in (getattr(pool, "web_results", None) or []):' in txt, "")
ck("A5 W# 硬约束在 apply_decidability_change 里",
   'str(r.get("resolved_to", "")).startswith("W")' in txt
   and "只能支撑 →partial" in txt, "")
ck("A6 两条通道共用一个拆解实现（负对照：不该再有第二份）",
   txt.count("_research_decompose_with_web(") == 3
   and txt.count("d0._decompose_from_pool(") == 1
   and txt.count("d0._decompose_question(") == 1,
   "_research_decompose_with_web 调用 3 处（1 定义 + 2 调用）")
ck("A7 update_deferrals 有 web_hook 形参 + 两处调用点接上",
   "web_hook=None) -> dict:" in txt
   and txt.count("web_hook=self._web_evidence_hook") == 2, "")
ck("A8 摘要只进 prompt（4 处注入：normal/hybrid/from_pool/koan）",
   txt.count('getattr(self, "_web_digest", "")') == 4, "")

# ============================================================ B 行为
Pool, View = mod.Pool, mod.View


def _mkpool(init_dec="undecidable", **kw):
    """★ `init_dec` 必须与待迁目标态**不同** —— 否则 apply 会走
    「与当前判定相同，无需变更」提前返回，判据变成**空过**（变异测试抓到的）。"""
    p = Pool()
    p.sub_questions = [{"id": 1, "question": "老城区管网重现期是多少",
                        "decidability": init_dec}]
    for k, v in kw.items():
        setattr(p, k, v)
    return p


# --- B1 引用门 ---
_p = _mkpool(web_results=[{"id": "W1", "claim": "GB50014 规定重现期 3~5 年"}],
             web_as_evidence=True)
_t = dict(mod._citation_table(None, _p))
ck("B1.a 授权时 W# 进表", "W1" in _t, repr(sorted(_t)[:6]))
ck("B1.b _resolve_citation 能解析 W1",
   bool(mod._resolve_citation("W1", None, _p)), "")
_p2 = _mkpool(web_results=[{"id": "W1", "claim": "x"}], web_as_evidence=False)
ck("B1.c 负对照：未授权时不进表", "W1" not in dict(mod._citation_table(None, _p2)),
   "")

# --- B2 apply_decidability_change：W# 只许 →partial ---
def _apply(pool, to):
    v = View(entry="1")
    sbi = {s["id"]: s for s in pool.sub_questions}
    return mod.apply_decidability_change(pool, v, sbi, 1, to, 3, "冒烟", ["W1"])


# ★ 每条都要给一个**与目标态不同**的初态，且断言**不是**「与当前判定相同」
#   —— 否则判据会以「无需变更」空过（变异测试已抓到过这一格）。
for _to, _init, _want in (("partial", "undecidable", "applied"),
                          ("decidable", "partial", "rejected"),
                          ("undecidable", "decidable", "rejected")):
    _r = _apply(_mkpool(init_dec=_init,
                        web_results=[{"id": "W1", "claim": "重现期 3~5 年"}],
                        web_as_evidence=True), _to)
    _vacu = "与当前判定相同" in str(_r.get("why", ""))
    ck("B2.W#→%s = %s（初态 %s，且非空过）" % (_to, _want, _init),
       _r["status"] == _want and not _vacu,
       (_r.get("why", "") or "")[:70])

# 负对照：池内编号（A1）支撑 decidable 仍应放行（W# 规则不能误伤）
_p3 = _mkpool(amps=[{"desc": "运维责任在移交后断点"}], web_as_evidence=True)
_p3.sub_questions[0]["decidability"] = "decidable"
_v3 = View(entry="1")
_sbi3 = {s["id"]: s for s in _p3.sub_questions}
_r3 = mod.apply_decidability_change(_p3, _v3, _sbi3, 1, "partial", 3, "冒烟", ["A1"])
ck("B2 负对照：池内编号不受 W# 规则影响",
   _r3["status"] == "applied", _r3.get("why", "")[:70])

# --- B3 _web_search：默认关 → 零调用 ---
class _StubClient:
    def __init__(self):
        self.calls = 0
        self.cache_hits = 0

    def search(self, q, max_n=8):
        self.calls += 1
        return [{"claim": "桩：" + q, "url": "u", "source": "s", "tier": 3}], ""


def _mkmeta(enabled, **over):
    """造一个能调 _web_search 的 MetaDGTF 壳（不跑 run）。"""
    cfg = {"web_search": dict(mod.DEFAULT_CONFIG["web_search"]),
           "external_anchor": dict(mod.DEFAULT_CONFIG["external_anchor"])}
    cfg["web_search"]["quota"] = dict(cfg["web_search"]["quota"])
    cfg["web_search"]["stages"] = dict(cfg["web_search"]["stages"])
    cfg["web_search"].update({"enabled": enabled, **over})
    o = object.__new__(mod.MetaDGTF)
    o.config = cfg
    o.pools = {"1": Pool()}
    o.vp = lambda *a, **k: None
    o._web_gate = mod.WebSearchGate(cfg)
    o._web_client = _StubClient()
    o._web_prep_seq = 0
    o.decidability_result = {"undecidable_aspects": ["[外] 上游是否有官方标准"]}
    return o


_o = _mkmeta(False)
_r = _o._web_search("research_decompose", ["q1"], 1)
ck("B3.a 负对照：默认关 → 返回 []", _r == [], repr(_r))
ck("B3.b 负对照：默认关 → 一次网络都没打", _o._web_client.calls == 0,
   repr(_o._web_client.calls))
ck("B3.c 默认关 → 池里没有 W#",
   not (getattr(_o.pools["1"], "web_results", None) or []), "")

# --- B4 _web_search：开启 → 编号/入池/留痕 ---
_o2 = _mkmeta(True, as_evidence="evidence")
_r2 = _o2._web_search("research_decompose", ["q1", "q2"], 1)
_ids = [x["id"] for x in _r2]
ck("B4.a 编号 W1/W2", _ids == ["W1", "W2"], repr(_ids))
ck("B4.b 入池条数一致", len(_o2.pools["1"].web_results) == 2, "")
ck("B4.c 授权门被同步（as_evidence=evidence → True）",
   _o2.pools["1"].web_as_evidence is True, "")
ck("B4.d used_as 落进条目", all(x["used_as"] == "evidence" for x in _r2), "")
ck("B4.f ★ 成功也留痕 [W-OK]（否则产物里看不出收了几条）",
   any("[W-OK]" in str(m) for m in _o2.pools["1"].meta),
   repr([m for m in _o2.pools["1"].meta if "[W-" in str(m)][:2]))
# 本圈配额 2：第三条应被拦
_r2b = _o2._web_search("research_decompose", ["q3"], 1)
ck("B4.e 本圈配额拦住（per_stage_round=2）", _r2b == []
   and any("[W-SKIP]" in str(m) for m in _o2.pools["1"].meta),
   repr([m for m in _o2.pools["1"].meta if "W-" in m][:3]))

# --- B5 失败留痕 + 不可用后降级 ---
class _FailClient(_StubClient):
    def search(self, q, max_n=8):
        self.calls += 1
        return [], "timeout"


_o3 = _mkmeta(True)
_o3._web_client = _FailClient()
for _i in range(3):
    _o3._web_search("research_decompose", ["q%d" % _i], 10 + _i)
_pl = _o3.pools["1"]
ck("B5.a 失败进 pool.meta", any("[W-TIMEOUT]" in str(m) for m in _pl.meta),
   repr([m for m in _pl.meta if "W-" in m][:3]))
ck("B5.b 失败进 pool.web_errors", len(_pl.web_errors) >= 3, repr(len(_pl.web_errors)))
ck("B5.c 连续 3 次失败 → gate 降级", _o3._web_gate.disabled is True, "")
ck("B5.d 降级后允许判据拒绝",
   _o3._web_gate.allow("research_decompose", 99)[0] is False, "")

# --- B6 空结果是终态、不算失败 ---
class _EmptyClient(_StubClient):
    def search(self, q, max_n=8):
        self.calls += 1
        return [], "empty"


_o4 = _mkmeta(True)
_o4._web_client = _EmptyClient()
for _i in range(5):
    _o4._web_search("research_decompose", ["e%d" % _i], 20 + _i)
ck("B6.a 空结果不降级", _o4._web_gate.disabled is False, "")
ck("B6.b 空结果进 pool.meta（[W-EMPTY]）",
   any("[W-EMPTY]" in str(m) for m in _o4.pools["1"].meta), "")
ck("B6.c 空结果**不**进 web_errors",
   not [e for e in _o4.pools["1"].web_errors if e.get("kind") == "empty"], "")

# --- B7 摘要块 ---
ck("B7.a 空 → 空串（加性）", mod._web_digest_block([]) == ""
   and mod._web_digest_block(None) == "", "")
_dg = mod._web_digest_block([{"id": "W1", "stage": "research_decompose",
                              "claim": "重现期 3~5 年", "tier": 3}])
ck("B7.b 非空 → 带【外部检索摘要】+ 「参照」字样",
   "【外部检索摘要】" in _dg and "参照" in _dg and "W1" in _dg, "")

# --- B8 三个 query 构造函数 ---
ck("B8.a decompose 取原问题（含空池）",
   mod._research_decompose_queries("Q", None) == ["Q"], "")
ck("B8.b evidence 只对 →partial 发",
   mod._research_evidence_queries({"to": "undecidable"}) == []
   and mod._research_evidence_queries(
       {"to": "partial", "_sq_text": "重现期是多少"}) == ["重现期是多少"], "")
ck("B8.c precedent 只认 [外] 标签",
   mod._research_precedent_queries(["无标签方面", "[外] 官方标准"]) != []
   and all("官方标准" in x
           for x in mod._research_precedent_queries(["[外] 官方标准"])), "")
ck("B8.d precedent 负对照：无 [外] → 空",
   mod._research_precedent_queries(["普通方面", "另一个"]) == [], "")

# --- B9 拆解：摘要在 prompt 里、**不在**子问题文本里（宪法级）---
class _CapLLM:
    def __init__(self):
        self.seen = []

    def call(self, system, user, temp, mx, json_mode=False, stage=None,
             **_k):
        self.seen.append((system or "") + "\n@@@\n" + (user or ""))
        return json.dumps({"sub_questions": [
            {"id": 1, "question": "重现期是多少", "weight": 0.5,
             "decidability": "decidable", "source": "P1"}]},
            ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


_d0 = object.__new__(mod.DGTF)
_d0.llm = _CapLLM()
_d0.verbose = False
_d0._web_digest = "【外部检索摘要】（★ **参照**，不是内容）\n- W1：重现期 3~5 年"
_d0._self_block = lambda: ""
_d0.config = {"actions": {}}
_subs = _d0._decompose_normal("原始问题", ["方面A"], ["方面B"])
_joined = "\n".join(_d0.llm.seen)
ck("B9.a 摘要出现在 prompt 里", "【外部检索摘要】" in _joined, "")
ck("B9.b 负对照：子问题文本**不含**摘要（输入是形状不是数据）",
   all("外部检索摘要" not in str(s.get("question", "")) for s in _subs),
   repr([s.get("question") for s in _subs]))

# ============================================================ C 变异测试
MUT = {
    "M1 抠掉 W# 硬约束": (
        '    if ent["to"] != "partial" and all(\n'
        '            str(r.get("resolved_to", "")).startswith("W")\n'
        '            for r in resolved):\n'
        '        return _reject("联网编号（W#）只能支撑 →partial，不能支撑 "\n'
        '                       f"→{ent[\'to\']}（网络检索质量不稳；"\n'
        '                       "且「能查到」证明不了「答不出」）")\n', ""),
    # ★ [v1.23.2] 锚点改为**尾段**：本版在这块中间插了 W# tier 门
    #   （`if not _web_enters_citation(...): continue`）⇒ 原来从
    #   `if getattr(pool, ...)` 到 `break` 的连续锚已不连续（命中 0 次）。
    #   变异体改 `pass`：删掉 append 后 W# 同样进不了引用表，
    #   M2 的判据意图（「W# 有没有进表」）一字未改。
    "M2 抠掉 W# 进表": (
        '            _wi += 1\n'
        '            out.append((str(_w.get("id") or ("W" + str(_wi))),\n'
        '                        str(_w.get("claim", ""))[:120]))\n'
        '            if _wi >= 20:\n'
        '                break\n',
        '            pass\n'),
    # ★ normal 与 hybrid 的 user 块逐字相同 ⇒ 锚点命中 2 次，两处一起抠。
    "M3 抠掉 prompt 里的摘要注入": (
        '                # [v1.23.0 W2] 外部检索摘要（**参照**）。未开联网时\n'
        '                #   它是空串 ⇒ prompt 逐字不变（加性）。\n'
        '                + (getattr(self, "_web_digest", "") or ""))\n',
        '                )\n'),
}

_tmpd = Path(tempfile.mkdtemp())
for _name, (_o, _n) in MUT.items():
    _exp = 2 if _name.startswith("M3") else 1
    _cnt = txt.count(_o)
    if _cnt != _exp:
        ck("C.%s 变异体可构造" % _name[:2], False,
           "锚点命中 %d 次（应 %d）" % (_cnt, _exp))
        continue
    _mp = _tmpd / ("mut_%s.py" % _name[:2])
    _mp.write_bytes(txt.replace(_o, _n).replace("\n", "\r\n").encode("utf-8"))
    try:
        _mm = load(_mp, "dgtf_mut_%s" % _name[:2])
    except Exception as e:  # noqa: BLE001
        ck("C.%s 可加载" % _name[:2], False, type(e).__name__ + ": " + str(e))
        continue
    _red = False
    _note = ""
    try:
        if _name.startswith("M1"):
            _pm = Pool()
            # ★ 初态必须与目标态不同，否则变异体也走「无需变更」→ 假绿
            _pm.sub_questions = [{"id": 1, "question": "q",
                                  "decidability": "decidable"}]
            _pm.web_results = [{"id": "W1", "claim": "c"}]
            _pm.web_as_evidence = True
            _vm = View(entry="1")
            _rm = _mm.apply_decidability_change(
                _pm, _vm, {1: _pm.sub_questions[0]}, 1, "undecidable", 3,
                "冒烟", ["W1"])
            _red = (_rm["status"] == "applied")
            _note = "变异体下 W#→undecidable = " + _rm["status"]
        elif _name.startswith("M2"):
            _pm = Pool()
            _pm.web_results = [{"id": "W1", "claim": "c"}]
            _pm.web_as_evidence = True
            _red = "W1" not in dict(_mm._citation_table(None, _pm))
            _note = "变异体下表里没有 W1"
        else:
            _d = object.__new__(_mm.DGTF)
            _d.llm = _CapLLM()
            _d.verbose = False
            _d._web_digest = "【外部检索摘要】（★ **参照**）"
            _d._self_block = lambda: ""
            _d.config = {"actions": {}}
            _d._decompose_normal("原始问题", ["a"], ["b"])
            _red = "【外部检索摘要】" not in "\n".join(_d.llm.seen)
            _note = "变异体下 prompt 里没有摘要"
    except Exception as e:  # noqa: BLE001
        _red, _note = True, "变异体抛错（等价于判红）：" + type(e).__name__
    ck("C.%s → 判据判红" % _name[:2], _red, _note)

print("═══ probe v123 W2 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
print("PASS %d / FAIL %d" % (sum(1 for _, o, _ in R if o),
                             sum(1 for _, o, _ in R if not o)))
sys.exit(0 if all(o for _, o, _ in R) else 1)
