# -*- coding: utf-8 -*-
"""V2.2.3 机制层判据：确定性自省核 / 自省档位 / 环节 thinking 覆盖 / 双判档位。

分四组（≥15 项）：
  A. fine_check 纯函数契约（可离线回放、JSON 可序列化、trace/决策投影）；
  B. 默认零行为差（V2.2.3 默认档 = V2.2.2 逐字 prompt）；
  C. 自省档位（auto_narr 收窄 / auto 跳过 / local 回退 / off / 失败回退）；
  D. 配置与 CLI 键存在 + 环节 thinking 优先级 + 双判模式分发。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.3.py"
ENGINE_OLD = HERE / "engine" / "Meta-DGTF-V2.2.2.py"

sys.path.insert(0, str(HERE.parent))    # 让 `dgtf_v2.fine_check` 可导入
from dgtf_v2 import fine_check as FC  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n
          + (" :: " + str(info) if info and not ok else ""))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ENG = _load(ENGINE, "metadgtf_v223")


# ============================================================
# 桩：记录调用的 LLM（区分「全量自省」与「收窄判定档」）
# ============================================================
class StubLLM:
    def __init__(self, full_payload=None, narrow_payload=None,
                 fail_full=False, fail_narrow=False):
        self.calls = []          # [(kind, system, user)]
        self.full_payload = full_payload or {
            "suspicious_candidates": [2], "suspicious_amps": [1],
            "ing_rephrased": False, "honest_about_empty": True,
            "unsaid_count": 0, "unsaid_is_escape": False,
            "notes": "stub", "flow_verdict": "f", "view_verdict": "v",
            "amp_ratio_verdict": "a", "unsaid_where": "",
        }
        self.narrow_payload = narrow_payload or {
            "suspicious_candidates": [1], "suspicious_amps": [],
            "ing_rephrased": False, "unsaid_is_escape": False,
            "notes": "narrow-stub",
        }
        self.fail_full = fail_full
        self.fail_narrow = fail_narrow

    def _kind(self, system):
        return "narrow" if "判定档" in system else "full"

    def call(self, system, user, temperature=0.3, max_tokens=1000,
             json_mode=False, model=None, thinking=None, stage=None,
             images=None, history=None, tools=None, tool_choice=None,
             return_message=False):
        kind = self._kind(system)
        self.calls.append((kind, system, user, stage, history))
        if kind == "narrow" and self.fail_narrow:
            raise RuntimeError("stub narrow failure")
        if kind == "full" and self.fail_full:
            raise RuntimeError("stub full failure")
        payload = self.narrow_payload if kind == "narrow" else self.full_payload
        return json.dumps(payload, ensure_ascii=False)

    def parse_json(self, raw):
        try:
            return json.loads(raw)
        except Exception:
            return {}


def _make_engine(mod, mode="llm", stub=None, entry="0", local_url=None):
    """不跑 __init__（避免真 LLM 客户端），只装配 _self_check 需要的属性。

    ★ `_self_check` 在按层的 `DGTF` 类上（不是 MetaDGTF）。
    """
    eng = object.__new__(mod.DGTF)
    eng.config = {"output": {"self_check": True, "self_check_mode": mode},
                  "api": {"thinking": {"stages": {}}}, "spiral": {}}
    eng.self_check_mode = mode
    eng.dual_judge_mode = "llm"
    eng.show_dual = False
    eng.verbose = False
    eng.entry = entry
    eng.sp = {}
    eng.local_llm_cfg = {"url": local_url or "http://127.0.0.1:9/generate",
                         "timeout": 0.3, "fallback": "llm",
                         "min_confidence": 0.6}
    eng.self_check_calls = {"llm_full": 0, "llm_narrow": 0,
                            "local": 0, "skipped": 0}
    eng.local_llm_errors = 0
    eng._local_llm_last_error = ""
    eng.use_self = False
    eng.self_memory = ""
    eng.phase = SimpleNamespace(view_focus="本层只看证据是否落地")
    eng.llm = stub or StubLLM()
    return eng


def _make_view(mod, clean=True, suspicious_tail=True):
    """造一个可预测的 view：clean=True 时确定性核应判「无可疑/无复述/无静默」。

    ★ 关键构造：候选 desc 逐字出现在 ing 里 ⇒ sim_ing 高（有展开出处）；
      候选 kind 用 concept（不在框架 kind 集合）；无上游文本（复述比 None）；
      无结构异常旗；expanded_descs 覆盖全部候选（新增候选=0）。
    """
    v = mod.View(entry="0")
    descs = ["夜间城乡温差被相对量掩盖，白天郊区升温也快",
             "城市储热在夜间释放，边界层稳定使浓度累积",
             "观测高度与站点代表性决定温差口径"]
    v.candidates = [
        {"desc": d, "kind": "concept", "source": "阴" if i % 2 else "阳",
         "attribute": "0" if i % 2 else "1", "position": "0",
         "why_position": "锚点指向该侧", "is_amp_candidate": False}
        for i, d in enumerate(descs)]
    v.collision = "。".join(descs) + "。另外，这一圈没有新发现，保持未生。"
    v.manifest = "## 一、已判定\n夜间城乡温差由站点口径决定。"
    v.amps = []
    v.threads = []
    v.quality_flags = []
    v.quality_verdict = ""
    v.upstream_texts = []
    v.rephrase_ratio = None
    v.undecidable_product = {}
    v.meta = []
    v.amp_calibration = {}
    v.both_quota = {}
    v._expanded_descs = list(descs)   # 运行时 provenance：全部候选都长自展开
    return v


# ============================================================
# A. fine_check 纯函数契约
# ============================================================
def group_a():
    _fc_src = Path(FC.__file__).read_text(encoding="utf-8")
    ck("fine_check 未 import 引擎（纯函数）",
       "Meta-DGTF" not in _fc_src and "import dgtf_v2.engine" not in _fc_src
       and "openai" not in _fc_src,
       "fine_check 源码含引擎依赖")
    ck("schema 约定", FC.SCHEMA == "dgtf.fine_check.v1", FC.SCHEMA)
    ck("字符 n-gram Jaccard 基本性质",
       abs(FC.jaccard("城乡温差", "城乡温差") - 1.0) < 1e-9
       and FC.jaccard("城乡温差", "完全无关") == 0.0
       and abs(FC.jaccard("ab", "abc", 2) - FC.jaccard("abc", "ab", 2)) < 1e-9)

    # 复述比：100% 复述上游 ⇒ >=0.5；无上游 ⇒ None（缺输入不给读数）
    up = ["夜间城乡温差确实比白天更大。城市储热释放使夜间降温更慢。"
          "郊区辐射冷却更快让城乡温差被拉大。边界层稳定会抑制污染扩散。"]
    coll = ("夜间城乡温差确实比白天更大。城市储热释放使夜间降温更慢。"
            "郊区辐射冷却更快让城乡温差被拉大。")
    r = FC.ngram_rephrase_ratio(coll, up)
    ck("复述比：强复述被测出", r is not None and r >= 0.5, r)
    ck("复述比：无上游返回 None",
       FC.ngram_rephrase_ratio(coll, []) is None)
    ck("复述比：ing 有效句<3 返回 None",
       FC.ngram_rephrase_ratio("一句话而已", up) is None)

    # unsaid 计数：五桶 + 候选宽口径
    vd = {"collision": "此处未生。另：此处未生。",
          "manifest": "此处未生",
          "candidates": [{"desc": "候选里的此处未生"}],
          "threads": [], "amps": []}
    n0, w0 = FC.count_unsaid(vd)
    n1, w1 = FC.count_unsaid(vd, include_candidates=True)
    ck("unsaid 计数（引擎同口径）", n0 == 3 and "ing×2" in w0 and "view×1" in w0, (n0, w0))
    ck("unsaid 宽口径防漏（含候选）", n1 == 4 and "候选×1" in w1, (n1, w1))

    # audit：纯 dict 输入、JSON 可序列化、返回键完整
    view = {"entry": "0",
            "candidates": [{"desc": "甲乙丙丁" * 10, "kind": "concept",
                            "source": "阴", "attribute": "0",
                            "position": "0"}],
            "collision": "甲乙丙丁" * 10 + "。第二句话在这里。第三句话也在这里。",
            "manifest": "## view", "amps": [], "threads": [],
            "quality_flags": [], "upstream_texts": []}
    a = FC.audit(view)
    json.dumps(a, ensure_ascii=False)
    ck("audit 返回键完整",
       all(k in a for k in ("schema", "unsaid_count", "ing_rephrase_ratio",
                            "suspicious_candidates", "suspicious_amps",
                            "honest_about_empty", "triggers", "decision",
                            "trace", "cfg_used", "notes")),
       sorted(a.keys()))
    ck("audit 缺字段不抛异常（防御式）", isinstance(FC.audit({}), dict))

    # 决策投影：8 条可疑 ⇒ 应挂回填旗；3 条 ⇒ 不挂
    many = dict(view)
    many["collision"] = "（此处未生）"
    many["candidates"] = [{"desc": f"候选内容{i}号", "kind": "concept",
                           "source": "阴", "attribute": "0",
                           "position": "0"} for i in range(8)]
    am = FC.audit(many)
    ck("空展开 ⇒ 候选全部可疑（保守）", len(am["suspicious_candidates"]) == 8,
       am["suspicious_candidates"])
    ck("回填旗决策：>=8 强源触发", am["decision"]["backfill_flag"] is True,
       am["decision"])
    few = dict(many)
    few["candidates"] = few["candidates"][:3]
    af = FC.audit(few)
    ck("回填旗决策：3 条不触发", af["decision"]["backfill_flag"] is False,
       af["decision"])

    # trace 契约
    ck("trace 条数/字段契约",
       len(a["trace"]) == 1
       and all(k in a["trace"][0] for k in ("idx", "sim_ing", "sim_view",
                                           "sim_upstream", "source", "kind",
                                           "reason", "grown_from_upstream")),
       a["trace"])

    # 触发器：运行时 provenance 全覆盖 ⇒ 不因 new_candidates 触发
    tr = FC.audit(_make_view(ENG).to_dict() | {}) if hasattr(ENG.View, "to_dict") else None
    vdict = {"entry": "0", "candidates": [{"desc": "甲乙丙丁" * 10, "kind": "concept",
                                          "source": "阴", "position": "0",
                                          "attribute": "0"}],
             "collision": "甲乙丙丁" * 10 + "。第二句话。第三句话。",
             "manifest": "", "amps": [], "quality_flags": [],
             "expanded_descs": ["甲乙丙丁" * 10]}
    at = FC.audit(vdict)
    ck("触发器：有 provenance 且全覆盖 ⇒ 无 new_candidates",
       "new_candidates" not in (at["triggers"]["reasons"] or []),
       at["triggers"])
    vd2 = dict(vdict)
    vd2["quality_flags"] = ["position_all_same(0)"]
    ck("触发器：结构异常命中",
       "structural" in FC.audit(vd2)["triggers"]["reasons"])

    # 一致性校验：语义缺失 ⇒ 升级
    c1 = FC.consistency_check(a, None)
    ck("一致性校验：语义缺失 ⇒ 升级", c1["escalate"] is True, c1)
    c2 = FC.consistency_check(FC.audit(view),
                              {"suspicious_candidates": [],
                               "ing_rephrased": False})
    ck("一致性校验：无分歧不升级", c2["escalate"] is False, c2)


# ============================================================
# B. 默认零行为差
# ============================================================
def group_b():
    ck("版本号 2.2.3", ENG.__version__ == "2.2.3", ENG.__version__)
    out = ENG.DEFAULT_CONFIG.get("output") or {}
    ck("默认 self_check_mode=llm", out.get("self_check_mode") == "llm", out.get("self_check_mode"))
    ck("默认 dual_judge_mode=llm", out.get("dual_judge_mode") == "llm", out.get("dual_judge_mode"))
    ck("默认 thinking_stage_overrides 为空", out.get("thinking_stage_overrides") == {},
       out.get("thinking_stage_overrides"))

    # 默认档与 V2.2.2 的 self_check prompt 逐字一致
    old = _load(ENGINE_OLD, "metadgtf_v222_for_diff")
    stub_new, stub_old = StubLLM(), StubLLM()
    e_new = _make_engine(ENG, mode="llm", stub=stub_new)
    e_old = _make_engine(old, mode="llm", stub=stub_old)
    v_new = _make_view(ENG)
    v_old = _make_view(old)
    r_new = e_new._self_check(v_new)
    r_old = e_old._self_check(v_old)
    same_prompt = (stub_new.calls and stub_old.calls
                   and stub_new.calls[0][1] == stub_old.calls[0][1]
                   and stub_new.calls[0][2] == stub_old.calls[0][2])
    ck("零行为差：默认档 self_check prompt 与 V2.2.2 逐字一致",
       bool(same_prompt), "prompt 不一致")
    ck("零行为差：默认档返回结构一致",
       set(r_new.keys()) == set(r_old.keys()), (sorted(r_new), sorted(r_old)))
    v_new2, v_old2 = _make_view(ENG), _make_view(old)
    ck("零行为差：默认档不改质量旗",
       (r_new.get("unsaid_is_escape") == r_old.get("unsaid_is_escape"))
       and (v_new2.quality_flags == v_old2.quality_flags),
       (v_new2.quality_flags, v_old2.quality_flags))


# ============================================================
# C. 自省档位
# ============================================================
def group_c():
    # auto_narr：1 次收窄调用，字段来自收窄 payload，叙述本地化
    stub = StubLLM()
    eng = _make_engine(ENG, mode="auto_narr", stub=stub)
    view = _make_view(ENG)
    r = eng._self_check(view)
    ck("auto_narr：只发 1 次收窄调用",
       len(stub.calls) == 1 and stub.calls[0][0] == "narrow",
       [(c[0], c[3]) for c in stub.calls])
    ck("auto_narr：决策字段来自收窄判定",
       r["suspicious_candidates"] == [1] and r["_llm_used"] is True, r)
    ck("auto_narr：无 multi-turn 历史（token 收窄）",
       stub.calls[0][4] in (None, []) or stub.calls[0][4] == [], stub.calls[0][4])
    ck("auto_narr：叙述字段本地化（不来自 LLM）",
       "自省核" in r["flow_verdict"] and r["_kernel"] == FC.SCHEMA, r["flow_verdict"])

    # auto：确定性核判「无可疑/无复述/无静默」⇒ 跳过 LLM
    stub2 = StubLLM()
    eng2 = _make_engine(ENG, mode="auto", stub=stub2)
    view2 = _make_view(ENG, clean=True)
    r2 = eng2._self_check(view2)
    ck("auto：clean 圈跳过 LLM（0 次调用）",
       len(stub2.calls) == 0 and eng2.self_check_calls["skipped"] == 1,
       [(c[0]) for c in stub2.calls])
    ck("auto：跳过时决策字段由确定性核给出",
       isinstance(r2.get("suspicious_candidates"), list)
       and r2["_llm_used"] is False and "跳过 LLM" in " ".join(view2.meta), r2.get("_audit"))

    # off：不调用、不产出决策
    stub3 = StubLLM()
    eng3 = _make_engine(ENG, mode="off", stub=stub3)
    r3 = eng3._self_check(_make_view(ENG))
    ck("off：0 次调用且标注关闭",
       len(stub3.calls) == 0 and r3.get("_mode") == "off", r3)

    # local：端点不可达 ⇒ 升级收窄 LLM（不抛异常）+ 错误计数/留痕
    stub4 = StubLLM()
    eng4 = _make_engine(ENG, mode="local", stub=stub4,
                        local_url="http://127.0.0.1:9/generate")
    view4 = _make_view(ENG)
    r4 = eng4._self_check(view4)
    ck("local：端点失败 ⇒ 升级 LLM 且不抛异常",
       len(stub4.calls) == 1 and stub4.calls[0][0] == "narrow"
       and r4["_llm_used"] is True, r4.get("_mode"))
    ck("local：失败计数/留痕（local_llm_errors=1）",
       eng4.local_llm_errors == 1 and r4.get("_local_errors") == 1
       and any("[SC-local]" in m for m in view4.meta),
       (eng4.local_llm_errors, getattr(eng4, "_local_llm_last_error", "")))

    # local：端点按契约返回 ⇒ 采信本地结果，不调云 LLM
    import http.server
    import threading

    class _H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(n)
            body = json.dumps({
                "ok": True,
                "confidence": 0.9,
                "text": json.dumps({
                    "suspicious_candidates": [2],
                    "suspicious_amps": [],
                    "ing_rephrased": False,
                    "unsaid_is_escape": False,
                    "notes": "local-ok"}, ensure_ascii=False),
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    stub6 = StubLLM()
    url6 = "http://127.0.0.1:%d/generate" % srv.server_address[1]
    eng6 = _make_engine(ENG, mode="local", stub=stub6, local_url=url6)
    r6 = eng6._self_check(_make_view(ENG))
    srv.shutdown()
    ck("local：契约 200{ok,text,confidence} ⇒ 采信本地判定且 0 云调用",
       len(stub6.calls) == 0 and r6["suspicious_candidates"] == [2]
       and r6["_mode"] == "local" and eng6.local_llm_errors == 0,
       (len(stub6.calls), r6.get("suspicious_candidates"),
        eng6.local_llm_errors))

    # auto_narr：收窄调用失败 ⇒ 整段回退原 llm 自省（质量优先）
    stub5 = StubLLM(fail_narrow=True)
    eng5 = _make_engine(ENG, mode="auto_narr", stub=stub5)
    view5 = _make_view(ENG)
    r5 = eng5._self_check(view5)
    kinds = [c[0] for c in stub5.calls]
    ck("auto_narr：收窄失败回退全量自省",
       kinds == ["narrow", "full"] and r5.get("suspicious_candidates") == [2],
       (kinds, r5.get("suspicious_candidates")))


# ============================================================
# D. 配置 / CLI / thinking 覆盖 / 双判分发
# ============================================================
def group_d():
    src = ENGINE.read_text(encoding="utf-8")
    for flag in ("--self-check-mode", "--dual-judge-mode", "--stage-thinking"):
        ck("CLI 参数存在：%s" % flag, flag in src)
    ck("源码含确定性核接线", "_fine_check()" in src and "_self_check_fine" in src)
    ck("源码含双判分发", "_dual_judge_llm" in src and "dual_judge_mode" in src)

    # 环节 thinking 优先级：显式 > 覆盖 > stages > default
    cfg = {"api": {"thinking": {"default": "enabled",
                                "stages": {"self_check": "enabled"}}},
           "output": {"thinking_stage_overrides": {"self_check": "disabled"}}}
    ck("_thinking_stage：override 声明的环节也算已声明",
       ENG._thinking_stage({"api": {"thinking": {"stages": {}}},
                            "output": {"thinking_stage_overrides":
                                       {"judge_x": "disabled"}}},
                           "judge_x") == "judge_x")
    os.environ.setdefault("DGTF_API_KEY", "stub-key-for-tests")
    llm = ENG.LLM(cfg)
    captured = []

    class _Stop(Exception):
        pass

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    captured.append(kw)
                    raise _Stop()

    llm.client = _Client()
    llm.max_retries = 1

    def _th_of(**kw):
        captured.clear()
        try:
            llm.call("s", "u", **kw)
        except Exception:
            pass
        if not captured:
            return None
        return ((captured[0].get("extra_body") or {})
                .get("thinking") or {}).get("type")

    ck("thinking：override 盖住 stages（disabled）",
       _th_of(stage="self_check") == "disabled", _th_of(stage="self_check"))
    ck("thinking：显式参数 > override",
       _th_of(stage="self_check", thinking="enabled") == "enabled")
    ck("thinking：未覆盖环节仍读 stages",
       _th_of(stage="other_stage") == "enabled")

    # 双判分发：llm 档原样调用原实现；cache 档全覆盖时不调 LLM
    eng = object.__new__(ENG.DGTF)
    eng.dual_judge_mode = "llm"
    eng.config = {}
    calls = {"llm": 0}

    def _fake_llm_judge(cands, inp, anchor, view=None, diversity_hint="",
                        allow_retry=True):
        calls["llm"] += 1
        return cands

    eng._dual_judge_llm = _fake_llm_judge
    eng._dual_judge([], None, "a")
    ck("双判：llm 档走原实现", calls["llm"] == 1, calls)

    eng2 = object.__new__(ENG.DGTF)
    eng2.dual_judge_mode = "cache"
    eng2.config = {}
    eng2.entry = "0"
    eng2.show_dual = False
    eng2.verbose = False
    eng2._dj_cache = {"entries": {}}
    eng2._dj_prior = {}
    eng2._last_dual_jmap = None
    eng2.vp = lambda *a, **k: None
    c1 = ENG.Candidate(desc="甲乙丙", kind="concept", source="阴",
                       attribute="0", position="0")
    k = eng2._dj_candidate_key(
        eng2._dj_static_key("0", "锚点"), c1, "锚点")
    eng2._dj_cache = {"entries": {k: {
        "position": "1", "why_position": "cached",
        "provenance": {"entry": "0"}}}}
    called = {"n": 0}
    eng2._dual_judge_llm = lambda *a, **kw: called.__setitem__("n", called["n"] + 1)
    out = eng2._dual_judge([c1], SimpleNamespace(pool=None), "锚点")
    ck("双判：cache 全命中 ⇒ 不调 LLM 且位置来自缓存",
       called["n"] == 0 and out[0].position == "1", (called, out[0].position))
    ck("双判：结构复采样（diversity_hint）强制走 LLM",
       (eng2._dual_judge([c1], SimpleNamespace(pool=None), "锚点",
                         diversity_hint="hint") or True)
       and called["n"] == 1, called)


def main():
    group_a()
    group_b()
    group_c()
    group_d()
    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
