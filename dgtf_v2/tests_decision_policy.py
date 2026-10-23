# -*- coding: utf-8 -*-
"""决策仲裁（decision_policy）离线判据：模式语义 / 四层硬约束 / 安全否决 /
回滚留痕 / packed 序列化 / 纯离线。全部为确定性反例驱动，不调 LLM、不联网。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.decision_policy import (DecisionPolicy, proposal_from_engine,  # noqa: E402
                                     Veto, estimate_tokens)

ROUTE = ["0", "1", "both", "all"]
CAPS = {"0": 5, "1": 5, "both": 5, "all": 5}
V1 = dict(order=ROUTE, rounds={"0": 3, "1": 2, "both": 2, "all": 1},
          stop="four_layers_done", quality=0.5, run_id="20261020_001")


def _v1():
    return proposal_from_engine(**V1)


def _v2(order=None, rounds=None, stop="four_layers_done", run_id="20261020_001",
        **extra):
    return proposal_from_engine(
        order=order or ROUTE,
        rounds=rounds if rounds is not None else {"0": 2, "1": 2, "both": 1, "all": 1},
        stop=stop, quality=0.6, run_id=run_id, source="v2", **extra)


def _policy(mode, **kw):
    base = dict(route=ROUTE, rounds_cap=CAPS, allow_anon=True)
    base.update(kw)
    return DecisionPolicy(mode, **base)


def case_shadow_zero_diff():
    r = _policy("shadow").decide(_v1(), _v2())
    assert r["action"] == "shadow" and r["policy"] == "v1_with_v2_shadow"
    assert r["effective"]["order"] == V1["order"]
    assert r["effective"]["rounds"] == V1["rounds"]
    assert r["changed"] is False


def case_shadow_invalid_v2_not_applied():
    bad = _v2(order=["0", "1", "both"])  # 缺 all：反例
    r = _policy("shadow").decide(_v1(), bad)
    assert r["action"] == "shadow"
    assert r["effective"]["order"] == V1["order"]
    assert any(v["code"] == "H1_route_mismatch" for v in r["vetoes"])


def case_advisory_is_non_binding():
    bad = _v2(order=["0", "1", "both"])
    r = _policy("advisory").decide(_v1(), bad)
    assert r["action"] == "advisory" and r["policy"] == "v2_advisory"
    assert r["effective"]["order"] == V1["order"]
    codes = [a["code"] for a in r["advisories"]]
    assert "H1_route_mismatch" in codes and "advisory_only" in codes
    assert r["changed"] is False


def case_takeover_adopts_valid():
    r = _policy("takeover").decide(_v1(), _v2())
    assert r["action"] == "takeover" and r["policy"] == "v2_takeover"
    assert r["effective"]["rounds"] == {"0": 2, "1": 2, "both": 1, "all": 1}
    assert r["changed"] is True
    json.dumps(r, ensure_ascii=False)


def case_takeover_veto_missing_layer():
    r = _policy("takeover").decide(_v1(), _v2(order=["0", "1", "both"]))
    assert r["action"] == "fallback_v1" and r["policy"] == "v1_auto_plan"
    assert r["effective"] == {"order": V1["order"], "rounds": V1["rounds"],
                              "stop": V1["stop"]}
    assert any(v["code"] == "H1_route_mismatch" for v in r["vetoes"])


def case_takeover_veto_unknown_and_duplicate():
    bad = _v2(order=["0", "1", "both", "all", "x", "0"])
    r = _policy("takeover").decide(_v1(), bad)
    codes = {v["code"] for v in r["vetoes"]}
    assert {"H1_unknown_layer", "H1_duplicate_layer"} <= codes
    assert r["action"] == "fallback_v1"


def case_takeover_veto_bad_rounds():
    bad = _v2(rounds={"0": 0, "1": 99, "both": 2, "all": 1})
    r = _policy("takeover").decide(_v1(), bad)
    codes = {v["code"] for v in r["vetoes"]}
    assert "H3_rounds_below_1" in codes and "H3_rounds_over_cap" in codes
    assert r["action"] == "fallback_v1"


def case_takeover_veto_dependency_order():
    bad = _v2(order=["1", "0", "both", "all"])  # 1 早于 0：反例
    r = _policy("takeover").decide(_v1(), bad)
    assert any(v["code"] == "H2_dependency_order" for v in r["vetoes"])
    assert r["action"] == "fallback_v1"


def case_takeover_veto_budget_guard():
    r = _policy("takeover").decide(
        _v1(), _v2(), budget={"max_tokens": 50_000, "spent_tokens": 0})
    codes = {v["code"] for v in r["vetoes"]}
    assert "safe_budget_guard" in codes
    assert r["action"] == "fallback_v1"


def case_takeover_veto_contract_block():
    r = _policy("takeover").decide(_v1(), _v2(), state={"contract_ok": False})
    assert any(v["code"] == "safe_contract_block" for v in r["vetoes"])
    assert r["action"] == "fallback_v1"


def case_takeover_veto_anon_run():
    bad = _v2(run_id="test_20261020")
    pol = DecisionPolicy("takeover", route=ROUTE, rounds_cap=CAPS,
                         allow_anon=False)
    r = pol.decide(_v1(), bad)
    assert any(v["code"] == "safe_anon_run" for v in r["vetoes"])
    assert r["action"] == "fallback_v1"
    # 负对照：allow_anon=True 时同一提案可接管
    pol2 = DecisionPolicy("takeover", route=ROUTE, rounds_cap=CAPS,
                          allow_anon=True)
    r2 = pol2.decide(_v1(), bad)
    assert r2["action"] == "takeover"


def case_rollback_sticky_and_reentry():
    pol = _policy("takeover", fallback_limit=2)
    bad = _v2(order=["0", "1", "both"])
    r1 = pol.decide(_v1(), bad)
    assert r1["action"] == "fallback_v1" and pol.rolled_back is False
    r2 = pol.decide(_v1(), bad)
    assert r2["action"] == "rollback" and pol.rolled_back is True
    r3 = pol.decide(_v1(), _v2())  # 合法提案也不再生效（粘性）
    assert r3["action"] == "rollback_hold"
    assert r3["effective"]["order"] == V1["order"]
    try:
        pol.reset()
        raise AssertionError("无 reentry_ok 必须报错")
    except ValueError:
        pass
    assert pol.reset(reentry_ok=True)["rolled_back"] is False
    r4 = pol.decide(_v1(), _v2())
    assert r4["action"] == "takeover"


def case_joint_rounds_capped_by_v1():
    v1 = proposal_from_engine(order=ROUTE,
                              rounds={"0": 3, "1": 4, "both": 2, "all": 1},
                              stop="", quality=0.5, run_id="20261020_001")
    v2 = _v2(rounds={"0": 2, "1": 5, "both": 2, "all": 1})
    r = _policy("joint").decide(v1, v2)
    assert r["action"] == "joint" and r["policy"] == "joint_v1_v2"
    assert r["effective"]["rounds"] == {"0": 2, "1": 4, "both": 2, "all": 1}
    assert any(a["code"] == "joint_rounds_capped" for a in r["advisories"])
    assert r["changed"] is True


def case_joint_invalid_v2_uses_v1():
    r = _policy("joint").decide(_v1(), _v2(order=["0", "1", "both"]))
    assert r["action"] == "joint_fallback_v1" and r["policy"] == "joint_v1_only"
    assert r["effective"]["order"] == V1["order"]


def case_content_field_never_adopted():
    secret = "机密答案：先裁员再砍产线"
    bad = _v2()
    bad_dict = bad.to_dict()
    bad_dict["answer"] = secret
    bad_dict["meta"] = {"rendered": secret}
    r = _policy("takeover").decide(_v1(), bad_dict)
    assert any(v["code"] == "H5_content_field" for v in r["vetoes"])
    assert r["action"] == "fallback_v1"
    assert secret not in json.dumps(r, ensure_ascii=False)
    assert any("answer" in k for k in r["v2"]["content_keys"])


def case_stop_soft_veto_keeps_adoption():
    bad_stop = "这是一段很长的结论正文，不应该被当成停止代码" * 2
    r = _policy("takeover").decide(_v1(), _v2(stop=bad_stop))
    assert r["action"] == "takeover"  # soft 否决不阻断，但归一化为空
    assert r["effective"]["stop"] == ""
    assert any(v["code"] == "H4_stop_not_code" and v["severity"] == "soft"
               for v in r["vetoes"])


def case_packed_roundtrip():
    pol = _policy("takeover", fallback_limit=2)
    pol.decide(_v1(), _v2(order=["0", "1", "both"]))
    pol.decide(_v1(), _v2(order=["0", "1", "both"]))
    packed = pol.to_packed()
    blob = json.dumps(packed, ensure_ascii=False)
    assert "contains_content" in packed and packed["contains_content"] is False
    pol2 = DecisionPolicy.from_packed(json.loads(blob))
    assert pol2.rolled_back is True
    assert pol2.stats()["rollbacks"] == 1
    assert pol2.mode == "takeover"
    r = pol2.decide(_v1(), _v2())
    assert r["action"] == "rollback_hold"


def case_v1_authoritative_not_rewritten():
    weird = proposal_from_engine(order=["1", "0", "both", "all"],
                                 rounds={"0": 3, "1": 2, "both": 2, "all": 1},
                                 stop="体力耗尽", run_id="20261020_001")
    r = _policy("shadow").decide(weird, _v2())
    assert r["effective"]["order"] == ["1", "0", "both", "all"]
    assert r["effective"]["stop"] == "体力耗尽"
    assert any(a["code"] == "v1_noncanonical" for a in r["advisories"])


def case_determinism():
    a = _policy("joint").decide(_v1(), _v2())
    b = _policy("joint").decide(_v1(), _v2())
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == \
        json.dumps(b, ensure_ascii=False, sort_keys=True)


def case_invalid_mode_rejected():
    try:
        DecisionPolicy("chaos")
        raise AssertionError("未知模式必须报错")
    except ValueError:
        pass


def case_estimator_monotonic():
    assert estimate_tokens({"0": 1}) > 0
    assert estimate_tokens({"0": 2}) > estimate_tokens({"0": 1})
    assert estimate_tokens({}) == 0


def case_offline_no_llm_no_net():
    src = (HERE / "decision_policy.py").read_text(encoding="utf-8")
    bad = ("openai", "requests", "httpx", "urllib", "socket",
           "aiohttp", "litellm", "http.client", "anthropic")
    hits = [b for b in bad if b in src]
    assert not hits, hits
    assert "time.time" not in src and "datetime.now" not in src


def case_veto_dataclass_serializable():
    v = Veto("H1_empty_order", "空 order")
    assert json.loads(json.dumps(v.to_dict()))["code"] == "H1_empty_order"


CASES = [case_shadow_zero_diff, case_shadow_invalid_v2_not_applied,
         case_advisory_is_non_binding, case_takeover_adopts_valid,
         case_takeover_veto_missing_layer, case_takeover_veto_unknown_and_duplicate,
         case_takeover_veto_bad_rounds, case_takeover_veto_dependency_order,
         case_takeover_veto_budget_guard, case_takeover_veto_contract_block,
         case_takeover_veto_anon_run, case_rollback_sticky_and_reentry,
         case_joint_rounds_capped_by_v1, case_joint_invalid_v2_uses_v1,
         case_content_field_never_adopted, case_stop_soft_veto_keeps_adoption,
         case_packed_roundtrip, case_v1_authoritative_not_rewritten,
         case_determinism, case_invalid_mode_rejected,
         case_estimator_monotonic, case_offline_no_llm_no_net,
         case_veto_dataclass_serializable]


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
