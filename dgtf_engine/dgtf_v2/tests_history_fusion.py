# -*- coding: utf-8 -*-
"""V2.1.0 历史谱系融合层判据（12 项）。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2 import history_fusion as hf  # noqa: E402


def case_manifest_loaded():
    m = hf.load_manifest()
    assert m.get("versions"), "manifest empty"
    assert len(m["versions"]) >= 150, len(m["versions"])
    got = {str(v.get("version")) for v in m["versions"]}
    for v in ("1.0", "1.21.32", "1.30.4", "2.0.0", "2.1.0"):
        assert v in got, (v, sorted(got)[:5])


def case_plan_ready():
    p = hf.build_plan()
    assert p["continuity_ok"] is True
    assert p["readiness"] == 1.0
    assert not p["missing"]
    assert p["total_versions"] >= 150
    assert p["target"] == "2.1.0"


def case_axes_complete():
    p = hf.build_plan()
    axes = p["axes"]
    keys = {a["key"] for a in axes}
    for k in ("spiral_core", "evidence_anchor", "auto_scheduler",
              "eml_bitemporal", "four_layer_contracts", "l0_generation",
              "app_workbench", "history_fusion"):
        assert k in keys, k
    for a in axes:
        assert a["status"] in ("native", "bridged", "retired"), a
        assert a["v1_origin"] and a["v2_implementation"] and a["tests"], a
    assert len(axes) == 17


def case_profile_fact():
    r = hf.select_profile("GPT5 是什么时候发布的？")
    assert r["profile"] == "contract-first", r
    assert "factual" in r["reason"] or "high" in r["reason"], r


def case_profile_decision():
    r = hf.select_profile("如何设计一个可靠的分布式系统？")
    assert r["profile"] == "contract-first", r


def case_profile_open():
    r = hf.select_profile("聊聊宇宙")
    assert r["profile"] == "exploration-first", r


def case_apply_metadata_only():
    cfg = {"actions": {"zero_v2": True, "one_v2": False},
           "max_tokens": 1000}
    before = json.dumps(cfg, ensure_ascii=False, sort_keys=True)
    s = hf.apply_history_fusion(cfg, "如何设计一个系统？")
    assert s["enabled"] and s["target"] == "2.1.0"
    assert s["axes_covered"] == s["axes_total"] == 17
    assert cfg["_history_fusion"] is s
    # 不修改答案相关配置
    cfg2 = dict(cfg)
    cfg2.pop("_history_fusion")
    assert json.dumps(cfg2, ensure_ascii=False, sort_keys=True) == before
    assert cfg["actions"] == {"zero_v2": True, "one_v2": False}


def case_audit_full():
    s = hf.apply_history_fusion({}, "GPT5 是什么时候发布的？")
    pack = {"route": ["0", "1", "both", "all"],
            "views": {k: {} for k in ("0", "1", "both", "all")},
            "llm_calls": 1}
    a = hf.audit_run(pack, s)
    assert a["continuity_ok"] is True, a
    assert a["route"] == ["0", "1", "both", "all"]
    assert a["views_present"] == ["0", "1", "both", "all"]
    assert a["profile"] == "contract-first"
    assert "answer" not in json.dumps(a, ensure_ascii=False)


def case_audit_partial():
    s = hf.apply_history_fusion({}, "聊聊宇宙")
    pack = {"route": ["0"], "views": {"0": {}}}
    a = hf.audit_run(pack, s)
    assert a["continuity_ok"] is True
    assert a["profile"] == "exploration-first"
    assert a["views_present"] == ["0"]


def case_render_markdown():
    md = hf.render_markdown()
    assert "# Meta-DGTF-道生三阶模型" in md
    assert "历史版本" in md
    assert "能力轴" in md
    assert "V2.1" in md


def case_digest():
    d = hf.manifest_digest()
    assert len(d) == 16 and all(c in "0123456789abcdef" for c in d), d


def case_fallback():
    p = hf.build_plan(hf.load_manifest("Z:/definitely/not/here.json"))
    assert p["total_versions"] >= 9
    assert p["continuity_ok"] is True
    assert p["readiness"] == 1.0


CASES = [case_manifest_loaded, case_plan_ready, case_axes_complete,
         case_profile_fact, case_profile_decision, case_profile_open,
         case_apply_metadata_only, case_audit_full, case_audit_partial,
         case_render_markdown, case_digest, case_fallback]


def main():
    bad = []
    for fn in CASES:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:  # noqa: BLE001
            bad.append((fn.__name__, e))
            print("FAIL", fn.__name__, type(e).__name__, e)
    print("\nPASS %d / FAIL %d" % (len(CASES) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
