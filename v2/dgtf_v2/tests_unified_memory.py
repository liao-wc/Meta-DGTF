# -*- coding: utf-8 -*-
"""统一记忆（unified_memory）离线判据：V1 playbook + V2 events 合读合写 /
跨源去重 / 无答案正文 / 写保护与测试隔离 / 容错 / 纯离线。"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.unified_memory import (PROD_MEMORY_DIR, V1_PLAYBOOK_FILE,  # noqa: E402
                                    V2_EVENTS_FILE, UnifiedMemory)

SECRET = "机密答案：应该先裁员再砍产线"


def _ev(run_id="20261020_001", template="0:r1", quality=0.5, calls=3,
        tokens=100, success=True, eid="evt-000001"):
    return {
        "id": eid, "run_id": run_id, "plane": "procedural",
        "layer": "scheduler", "kind": "schedule_outcome",
        "key": "schedule:" + template,
        "payload": {"template": template, "quality": quality, "calls": calls,
                    "tokens": tokens, "success": success},
        "event_time": 1.0, "ingest_time": 1.0, "valid_from": 1.0,
        "valid_to": None, "tx_time": 1.0,
        "provenance": [], "confidence": 0.6,
        "support": [], "defeaters": [], "supersedes": None,
    }


def _pb_outcome(run_id="20261020_001", template="0:r1", quality=0.5,
                calls=3, tokens=100, success=True, pid="U0001"):
    return {"id": pid, "kind": "schedule_outcome",
            "cond": {"run_id": run_id, "template": template},
            "action": {"key": template},
            "readings": {"before": 0.0, "quality": quality, "calls": calls,
                         "tokens": tokens, "success": success},
            "evidence": [run_id], "n_evidence": 1, "status": "shadow",
            "weight": 1.0, "source": "unified_memory"}


def _pb_active(key="rounds_delta", pid="L0001", n_evidence=3, weight=1.0,
               quality_delta=0.1, cost_delta=-0.05):
    return {"id": pid, "kind": "schedule", "cond": {"layer": "1"},
            "action": {"key": key, "layer": "1", "delta": 1},
            "readings": {"before": 0.0}, "evidence": ["r1", "r2", "r3"],
            "n_evidence": n_evidence, "status": "active", "weight": weight,
            "quality_delta": quality_delta, "cost_delta": cost_delta}


def case_from_records_priors():
    m = UnifiedMemory.from_records(v2_events=[_ev(template="0:r1")],
                                   playbook=[_pb_active()])
    p = m.read_priors()
    assert p["contains_content"] is False
    assert p["templates"]["0:r1"]["n"] == 1
    assert p["templates"]["0:r1"]["mean_success"] == 1.0
    assert p["templates"]["0:r1"]["mean_tokens"] == 100.0
    assert p["playbook"]["rounds_delta"]["n"] == 1
    assert p["playbook"]["rounds_delta"]["mean_evidence"] == 3.0
    json.dumps(p, ensure_ascii=False)


def case_v1_active_only():
    pb = [_pb_active(pid="L0001"),
          dict(_pb_active(pid="L0002"), status="shadow")]
    m = UnifiedMemory.from_records(playbook=pb)
    p = m.read_priors()
    assert p["sources"]["v1_active"] == 1
    assert p["playbook"]["rounds_delta"]["n"] == 1


def case_dedup_across_sources():
    m = UnifiedMemory.from_records(v2_events=[_ev()],
                                   playbook=[_pb_outcome()])
    p = m.read_priors()
    assert p["dedup"]["rows_raw"] == 2
    assert p["dedup"]["rows_deduped"] == 1
    assert p["dedup"]["duplicates_dropped"] == 1
    assert p["templates"]["0:r1"]["n"] == 1
    assert p["templates"]["0:r1"]["sources"] == ["v2"]


def case_dedup_prefers_v2_and_flags_conflict():
    m = UnifiedMemory.from_records(
        v2_events=[_ev(quality=0.9, calls=9, tokens=900)],
        playbook=[_pb_outcome(quality=0.1, calls=1, tokens=10)])
    p = m.read_priors()
    assert p["templates"]["0:r1"]["mean_quality"] == 0.9
    assert p["dedup"]["conflicts"] >= 1


def case_dedup_same_source():
    m = UnifiedMemory.from_records(v2_events=[_ev(eid="evt-000001"),
                                              _ev(eid="evt-000002")])
    p = m.read_priors()
    assert p["templates"]["0:r1"]["n"] == 1
    assert p["dedup"]["duplicates_dropped"] == 1


def case_forbidden_answer_key():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td)
        try:
            m.record_outcome(run_id="r1", template="0:r1", quality=0.5,
                             calls=1, tokens=10, success=True,
                             extra={"answer": SECRET})
            raise AssertionError("答案正文必须被拒写")
        except ValueError:
            pass
        assert not (Path(td) / V2_EVENTS_FILE).exists()


def case_forbidden_nested_key():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td)
        try:
            m.record_outcome(run_id="r1", template="0:r1", quality=0.5,
                             calls=1, tokens=10, success=True,
                             extra={"meta": {"rendered": SECRET}})
            raise AssertionError("嵌套答案正文必须被拒写")
        except ValueError:
            pass


def case_template_must_be_code():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td)
        for bad in ("答案正文：先裁员", "a b c", "长" * 80, ""):
            try:
                m.record_outcome(run_id="r1", template=bad, quality=0.5,
                                 calls=1, tokens=10, success=True)
                raise AssertionError("坏 template 必须报错：%r" % bad)
            except ValueError:
                pass
        assert m.record_outcome(run_id="r1", template="0:r1", quality=0.5,
                                calls=1, tokens=10, success=True)["recorded"]


def case_numeric_validation():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td)
        for kw in ({"quality": "abc"}, {"calls": None}, {"tokens": "1x"}):
            args = dict(run_id="r1", template="0:r1", quality=0.5, calls=1,
                        tokens=10, success=True)
            args.update(kw)
            try:
                m.record_outcome(**args)
                raise AssertionError("非数值读数必须报错：%r" % (kw,))
            except ValueError:
                pass


def case_anon_skip():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td, allow_anon=False)
        res = m.record_outcome(run_id="test_20261020", template="0:r1",
                               quality=0.5, calls=1, tokens=10, success=True)
        assert res["recorded"] is False and res["skipped"] == "anon"
        assert not (Path(td) / V2_EVENTS_FILE).exists()
        m2 = UnifiedMemory.for_tests(td, allow_anon=True)
        assert m2.record_outcome(run_id="test_20261020", template="0:r1",
                                 quality=0.5, calls=1, tokens=10,
                                 success=True)["recorded"] is True


def case_production_guard():
    v2p = PROD_MEMORY_DIR / V2_EVENTS_FILE
    pbp = PROD_MEMORY_DIR / V1_PLAYBOOK_FILE

    def snap(p):
        return (p.stat().st_size, p.stat().st_mtime) if p.exists() else None

    before = (snap(v2p), snap(pbp))
    m = UnifiedMemory(v2_events_path=v2p, playbook_path=pbp,
                      enabled=True, allow_production=False)
    try:
        m.record_outcome(run_id="20261020_999", template="0:r1", quality=0.5,
                         calls=1, tokens=10, success=True,
                         mirror_playbook=True)
        raise AssertionError("未 allow_production 时写生产必须被拒")
    except PermissionError:
        pass
    assert (snap(v2p), snap(pbp)) == before


def case_malformed_lines_tolerated():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        (base / V2_EVENTS_FILE).write_text(
            "not-json\n" + json.dumps(_ev()) + "\n",
            encoding="utf-8")
        (base / V1_PLAYBOOK_FILE).write_text(
            "broken\n" + json.dumps(_pb_active()) + "\n", encoding="utf-8")
        m = UnifiedMemory.for_tests(td)
        s = m.stats()
        assert s["skipped_v2_lines"] == 1 and s["skipped_v1_lines"] == 1
        assert s["v2_events"] == 1 and s["v1_playbook"] == 1
        assert m.read_priors()["templates"]["0:r1"]["n"] == 1


def case_disabled_no_writes():
    m = UnifiedMemory.from_records(enabled=False)
    res = m.record_outcome(run_id="r1", template="0:r1", quality=0.5,
                           calls=1, tokens=10, success=True)
    assert res["recorded"] is False and res["enabled"] is False
    assert m.stats()["v2_events"] == 0


def case_mirror_playbook_and_reload():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td)
        res = m.record_outcome(run_id="20261020_002", template="1:r2",
                               quality=0.7, calls=4, tokens=200, success=True,
                               mirror_playbook=True)
        assert res["sources"] == ["v2_events", "v1_playbook"]
        assert (Path(td) / V2_EVENTS_FILE).exists()
        assert (Path(td) / V1_PLAYBOOK_FILE).exists()
        m2 = UnifiedMemory.for_tests(td)  # 重新装载
        p = m2.read_priors()
        assert p["templates"]["1:r2"]["n"] == 1
        assert p["templates"]["1:r2"]["mean_quality"] == 0.7
        assert p["dedup"]["duplicates_dropped"] == 1  # 跨源同键
        again = m2.record_outcome(run_id="20261020_002", template="1:r2",
                                  quality=0.7, calls=4, tokens=200,
                                  success=True)
        assert again["deduped"] is True and again["recorded"] is False


def case_persistence_readback():
    with tempfile.TemporaryDirectory() as td:
        m = UnifiedMemory.for_tests(td)
        m.record_outcome(run_id="20261020_003", template="both:r2",
                         quality=0.8, calls=5, tokens=300, success=False)
        m2 = UnifiedMemory.for_tests(td)
        p = m2.read_priors()
        assert p["templates"]["both:r2"]["n"] == 1
        assert p["templates"]["both:r2"]["mean_success"] == 0.0
        assert p["templates"]["both:r2"]["mean_calls"] == 5.0


def case_priors_contain_no_answer_text():
    m = UnifiedMemory.from_records(v2_events=[_ev()], playbook=[_pb_active()])
    blob = json.dumps(m.read_priors(), ensure_ascii=False)
    assert SECRET not in blob
    assert "answer" not in blob and "rendered" not in blob


def case_in_memory_record():
    m = UnifiedMemory.from_records(enabled=True)
    res = m.record_outcome(run_id="r1", template="0:r1", quality=0.5,
                           calls=1, tokens=10, success=True)
    assert res["recorded"] is True
    assert m.stats()["v2_events"] == 1
    assert m.v2_events_path is None and m.playbook_path is None


def case_playbook_non_dict_ignored():
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / V1_PLAYBOOK_FILE).write_text(
            "[1,2,3]\n" + json.dumps(_pb_active()) + "\n", encoding="utf-8")
        m = UnifiedMemory.for_tests(td)
        assert m.stats()["v1_playbook"] == 1


def case_offline_no_llm_no_net():
    src = (HERE / "unified_memory.py").read_text(encoding="utf-8")
    bad = ("openai", "requests", "httpx", "urllib", "socket",
           "aiohttp", "litellm", "http.client", "anthropic")
    hits = [b for b in bad if b in src]
    assert not hits, hits
    assert "time.time" not in src and "datetime.now" not in src


CASES = [case_from_records_priors, case_v1_active_only,
         case_dedup_across_sources, case_dedup_prefers_v2_and_flags_conflict,
         case_dedup_same_source, case_forbidden_answer_key,
         case_forbidden_nested_key, case_template_must_be_code,
         case_numeric_validation, case_anon_skip, case_production_guard,
         case_malformed_lines_tolerated, case_disabled_no_writes,
         case_mirror_playbook_and_reload, case_persistence_readback,
         case_priors_contain_no_answer_text, case_in_memory_record,
         case_playbook_non_dict_ignored, case_offline_no_llm_no_net]


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
