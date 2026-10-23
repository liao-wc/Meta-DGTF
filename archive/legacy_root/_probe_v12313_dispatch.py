# -*- coding: utf-8 -*-
"""v1.23.13 探针：统一自适应调度器十二项 —— 逐项可单独接管 + 历史自适应 + 技术债。

用法：python _probe_v12313_dispatch.py <主文件.py>
零 LLM：全部走纯函数；`auto_plan` 两条路径用打桩 / 无 key 降级离线跑通。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.13.py")
if not SRC.is_absolute():
    SRC = HERE / SRC


def load(p):
    spec = importlib.util.spec_from_file_location("m_v12313", p)
    assert spec is not None and spec.loader is not None, "路径要以 .py 结尾"
    m = importlib.util.module_from_spec(spec)
    sys.modules["m_v12313"] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC)
out = {}
HAS = hasattr(mod, "auto_dispatch") and hasattr(mod, "_assemble_plan")
out["HAS_调度器"] = HAS
out["HAS_唯一装配器"] = hasattr(mod, "_assemble_plan")
out["HAS_取向唯一实现"] = hasattr(mod, "_normalize_orientation")

FACT = "新中国的成立时间是什么时候"
DEC = "这份方案怎么落地"
META = ("这本身算不算递归？如何界定，还是要靠整体，"
        "到底谁说了算，怎么验证，为什么")
_ORDER = ("route", "cost_profile", "mode", "rounds", "orientation",
          "web", "thinking", "effort", "stop", "web_downgrade",
          "decidability", "landing")


def pick(plan, k):
    return (plan.get("_items") or {}).get(k) or {}


def src_of(plan, k):
    return pick(plan, k).get("source")


def val_of(plan, k):
    return pick(plan, k).get("value")


if HAS:
    cfg0 = mod.load_config("")

    # ── A · 十二项齐全 + 事实短题的分支 ─────────────────────
    p = mod.auto_dispatch(FACT, cfg0)
    out["A_项数"] = len(mod._AUTO_ITEM_ORDER)
    out["A_每项都有留痕"] = all(k in (p.get("_items") or {}) for k in _ORDER)
    out["A_fact_cost"] = val_of(p, "cost_profile")
    out["A_fact_mode"] = val_of(p, "mode")
    out["A_fact_web"] = val_of(p, "web")
    out["A_fact_thinking"] = val_of(p, "thinking")
    out["A_fact_effort"] = val_of(p, "effort")
    out["A_fact_orientation"] = val_of(p, "orientation")
    out["A_fact_landing"] = val_of(p, "landing")
    out["A_fact_decidability"] = val_of(p, "decidability")
    out["A_fact_stop"] = val_of(p, "stop")
    out["A_全项都带理由"] = all(str(pick(p, k).get("reason") or "")
                                for k in _ORDER)

    # ── B · 决策题 / 元题分支 ───────────────────────────────
    d = mod.auto_dispatch(DEC, cfg0)
    out["B_dec_cost"] = val_of(d, "cost_profile")
    out["B_dec_orientation"] = val_of(d, "orientation")
    out["B_dec_landing"] = val_of(d, "landing")
    out["B_dec_decidability"] = val_of(d, "decidability")
    out["B_dec_effort"] = val_of(d, "effort")
    mx = mod.auto_dispatch(META, cfg0)
    out["B_meta_mode"] = val_of(mx, "mode")
    out["B_meta_stop"] = val_of(mx, "stop")
    out["B_meta_route"] = val_of(mx, "route")

    # ── C · 逐项显式接管：改一项，**只**改这一项 ────────────
    EX = {"route": ["0", "1"], "cost_profile": "quality", "mode": "A",
          "rounds": "0:9,1:9,both:9,all:9", "orientation": "decision",
          "web": "off", "thinking": "on", "effort": "max",
          "landing": "decision", "decidability": "off"}
    for k, v in EX.items():
        p1 = mod.auto_dispatch(FACT, cfg0, explicit={k: v})
        out["C_%s_source" % k] = src_of(p1, k)
        _others = [x for x in _ORDER if x != k and x not in ("stop",
                                                             "web_downgrade")]
        out["C_%s_只改一项" % k] = all(src_of(p1, x) == "auto"
                                      for x in _others)
    # 配置级接管（stop / web_downgrade 没有 CLI，靠配置）
    import copy
    cfg_s = copy.deepcopy(cfg0)
    cfg_s["spiral"]["round_stall_limit"] = 9
    ps = mod.auto_dispatch(FACT, cfg_s)
    out["C_stop_source"] = src_of(ps, "stop")
    cfg_w = copy.deepcopy(cfg0)
    cfg_w["web_search"]["auto_disable_after_failures"] = 7
    pw = mod.auto_dispatch(FACT, cfg_w)
    out["C_web_downgrade_source"] = src_of(pw, "web_downgrade")

    # ── D · 总开关：关掉 ⇒ 一项都不进 auto ──────────────────
    cfg_off = copy.deepcopy(cfg0)
    cfg_off["auto"]["enabled"] = False
    pf = mod.auto_dispatch(FACT, cfg_off)
    out["D_关时无auto"] = all(src_of(pf, k) != "auto" for k in _ORDER)
    out["D_关时成本档"] = val_of(pf, "cost_profile")

    # ── E · 历史自适应（合成 hist，不看真实 outputs）─────────
    H_BASE = {"n": 5, "tokens_med": 100000, "tri_rate": 0.8, "cut_rate": 0.1,
              "layer_rounds": {"0": 3, "1": 3, "both": 2, "all": 2},
              "modes": {}, "profiles": {}, "web_hit": 12, "web_fail": 0,
              "web_empty": 0, "mismatch": 0}
    ph = mod.auto_dispatch(FACT, cfg0, history=H_BASE)
    out["E_hist_rounds"] = val_of(ph, "rounds")
    out["E_hist_rounds_理由含中位"] = "中位" in str(pick(ph, "rounds")
                                                 .get("reason"))
    out["E_hist_route_砍层"] = val_of(ph, "route")
    _hf = dict(H_BASE, cut_rate=0.9)
    out["E_hist_route_截断高_不砍"] = val_of(
        mod.auto_dispatch(FACT, cfg0, history=_hf), "route")
    out["E_hist_cost_基线"] = val_of(
        mod.auto_dispatch(DEC, cfg0, history=H_BASE), "cost_profile")
    _hm = dict(H_BASE, tokens_med=900000)
    out["E_hist_cost_降档"] = val_of(
        mod.auto_dispatch(DEC, cfg0, history=_hm), "cost_profile")
    _hw = dict(H_BASE, web_fail=5)
    out["E_hist_降级阈值"] = val_of(
        mod.auto_dispatch(FACT, cfg0, history=_hw), "web_downgrade"
    ).get("auto_disable_after_failures")
    _he = dict(H_BASE, n=4, web_hit=0, web_empty=4)
    out["E_hist_联网不再接"] = val_of(
        mod.auto_dispatch(FACT, cfg0, history=_he), "web")
    _tr = dict(H_BASE, tri_rate=0.2)
    out["E_hist_低一致率不降档"] = val_of(
        mod.auto_dispatch(DEC, cfg0, history=_tr), "cost_profile")

    # ── F · 技术债：唯一实现 + 两条路径同 schema ────────────
    txt = SRC.read_text(encoding="utf-8")
    out["F_取向归一化定义数"] = txt.count("def _normalize_orientation(")
    out["F_归一化旧实现残留"] = sum(
        txt.count(p) for p in ('if _o not in ("boundary", "decision"):',
                               'if _ori not in ("decision", "boundary"):'))
    out["F_装配器定义数"] = txt.count("def _assemble_plan(")
    out["F_装配器调用数"] = txt.count("_assemble_plan(") - 1

    class _StubLLM:
        def __init__(self, payload):
            self.payload = payload

        def call(self, *a, **kw):
            return json.dumps(self.payload, ensure_ascii=False)

        def parse_json(self, raw):
            try:
                return json.loads(raw)
            except Exception:  # noqa: BLE001
                return {}

    _payload = {"mode": "A", "orientation": "boundary",
                "rounds": {"0": 5, "1": 5, "both": 5, "all": 5},
                "reason": "打桩", "confidence": 0.9}
    _p1 = mod.auto_plan(FACT, cfg0, llm=_StubLLM(_payload))
    _p2 = mod.auto_plan(FACT, cfg0)          # 无 key ⇒ 两段式降级出口
    out["F_路径1_键"] = sorted(_p1)
    out["F_路径2_键"] = sorted(_p2)
    out["F_两路 schema 相同"] = sorted(_p1) == sorted(_p2)
    out["F_路径1_route非空"] = bool(_p1.get("route"))
    out["F_路径1_cost"] = _p1.get("cost_profile")
    out["F_路径1_mode"] = _p1.get("mode")
    out["F_路径1_取向"] = _p1.get("orientation")

    # ── G · 产物渲染 ────────────────────────────────────────
    _res = {"_auto_dispatch": p}
    _ls = "".join(mod._auto_dispatch_lines(_res))
    out["G_表存在"] = "**自动调度**" in _ls
    out["G_十二行"] = sum(1 for l in _ls.split("\n")
                         if l.startswith("| ") and "来源" not in l) - 0
    out["G_含逐项来源说明"] = "显式 ＞ 配置 ＞ auto ＞ 默认" in _ls
    out["G_无plan时为空"] = mod._auto_dispatch_lines({}) == []

for _k in sorted(out):
    print("%-30s = %s" % (_k, out[_k]))
