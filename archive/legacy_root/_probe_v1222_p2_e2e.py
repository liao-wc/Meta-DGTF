# -*- coding: utf-8 -*-
"""[v1.22.2 P2] E2E（离线 mock）：not_do 从模型产出 → packed → rubric 3/3。

判据：
  · 正对照：桩给 not_do → packed._not_do 非空且 _source=schema，
            rubric = 3/3，产物 md 印出「不做什么」条目，且**无** not_do_missing；
  · 负对照：桩不给 not_do → not_do_missing 亮起，rubric ≤ 2/3。
用法：python _probe_v1222_p2_e2e.py [src]
"""
import json
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = (Path(sys.argv[1]) if len(sys.argv) > 1
          else HERE / "元DGTF-V1.22.2.py")
if not TARGET.is_absolute():
    TARGET = HERE / TARGET

_src = (HERE / "smoke_test.py").read_text(encoding="utf-8")
_pat = re.compile(r'SRC = HERE / "元DGTF-V1\.22\.\d+\.py"')
assert len(_pat.findall(_src)) == 1, "SRC 行不是 1 行"
_src = _pat.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), _src)
hm = types.ModuleType("harness")
hm.__file__ = str(HERE / "smoke_test.py")
sys.modules["harness"] = hm
exec(compile(_src, str(HERE / "smoke_test.py"), "exec"), hm.__dict__)
mod = hm.mod
_fake = hm.fake_call

sys.path.insert(0, str(HERE / "bench"))
from bench_score import score_actions  # noqa: E402

GIVE_NOTDO = {"on": True}

_ACTIONS = [
    {"id": "A1", "verb": "核查", "object": "老城区排水管网现状重现期",
     "owner_role": "区水务局排水科", "deadline_hint": "汛期前 30 天",
     "acceptance": "出具现状核查表并签字", "fallback": "委托第三方勘测"},
    {"id": "A2", "verb": "编制", "object": "提标改造分期方案",
     "owner_role": "市规划设计院", "deadline_hint": "下一次汛期结束后 60 天",
     "acceptance": "方案通过专家评审", "fallback": "先出应急方案"},
    {"id": "A3", "verb": "报审", "object": "改造投资概算",
     "owner_role": "区发改委投资科", "deadline_hint": "次年预算编制窗口",
     "acceptance": "概算批复下达", "fallback": "申请专项资金"},
]


def _my_call(self, system, user, temperature=0.6, max_tokens=3000,
             json_mode=False, model=None, thinking=None, stage=None):
    s = system or ""
    if stage in ("adjudicate_sub_tristate",
                 "adjudicate_sub_tristate_multi"):
        n = max(1, sum(1 for ln in (user or "").splitlines()
                       if re.match(r"^\s{2}\d+\.", ln)))
        return json.dumps({"judgments": [
            {"id": i, "reason": "冒烟", "decidability": "decidable"}
            for i in range(1, min(n, 8) + 1)]}, ensure_ascii=False)
    if "sub_questions" in s:
        return json.dumps({"sub_questions": [
            {"id": 1, "question": "老城区现有管网的设计重现期是多少",
             "weight": 0.5, "decidability": "decidable", "source": "P1"},
            {"id": 2, "question": "整体提标改造的财政承接主体是谁",
             "weight": 0.5, "decidability": "decidable", "source": "T1"},
        ]}, ensure_ascii=False)
    if "双通道融合】（研究层）" in s:
        _dp = {"answer": "先核查现状重现期，再按回收期分期提标",
               "answered_sub_ids": [1, 2], "evidence": ["桩证据"],
               "distance": 0.3, "actions": _ACTIONS}
        if GIVE_NOTDO["on"]:
            _dp["not_do"] = [
                {"what": "不在成因判定缺席时启动物探",
                 "why": "成因未立，物探结论不可核对"},
                {"what": "不优先改造非瓶颈管段",
                 "why": "瓶颈段未定，先改非瓶颈会浪费预算"},
            ]
        return json.dumps({
            "amps": [], "threads": [], "meta": [],
            "decidable_product": _dp,
            "undecidable_product": {"why_undecidable": "桩",
                                    "structural_amps": [], "aligned_amps": [],
                                    "clarity": 0.0, "distance": 1.0},
            "covered_aspects": [], "uncovered_aspects": [],
            "distance_to_question": 0.3}, ensure_ascii=False)
    return _fake(self, system, user, temperature, max_tokens, json_mode,
                 model, thinking, stage)


mod.LLM.call = _my_call

Q = "老城区排水管网的设计标准该不该整体提标改造？该怎么做？"
R = []


def _run(tag, give):
    GIVE_NOTDO["on"] = give
    cfg = hm.build_cfg(False)
    cfg["output"]["save_dir"] = tempfile.mkdtemp(prefix="v1222p2_")
    meta = mod.MetaDGTF(cfg)
    res = meta.run(Q, route=["0", "1", "both", "all"],
                   rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                   parallel_mode="serial", orientation="decision")
    v1 = (res.get("views") or {}).get("1") or {}
    nd = v1.get("_not_do") or []
    acts = v1.get("_actions") or []
    flags = list(v1.get("quality_flags") or [])
    md = mod.save_result(res, cfg["output"]["save_dir"]).read_text(encoding="utf-8")
    rb = score_actions(acts, nd)
    print("── %s ──" % tag)
    print("   _not_do =", json.dumps(nd, ensure_ascii=False)[:200])
    print("   n_actions =", len(acts), " rubric =", rb)
    print("   not_do_missing =", "not_do_missing" in flags)
    print("   产物含「不做什么」段 =", "不做什么" in md)
    return nd, acts, flags, md, rb


nd1, acts1, fl1, md1, rb1 = _run("正对照（桩给 not_do）", True)
nd2, acts2, fl2, md2, rb2 = _run("负对照（桩不给 not_do）", False)

R.append(("正对照 _not_do 非空", len(nd1) >= 1, repr(len(nd1))))
R.append(("正对照 _source=schema",
          all(x.get("_source") == "schema" for x in nd1 if isinstance(x, dict)),
          ""))
R.append(("正对照 rubric=3/3", rb1["score"] == 3, repr(rb1)))
R.append(("正对照 无 not_do_missing",
          "not_do_missing" not in fl1, repr([f for f in fl1 if "not_do" in f])))
R.append(("正对照 产物印出不做条目",
          "不在成因判定缺席时启动物探" in md1, ""))
R.append(("负对照 not_do_missing 亮起",
          "not_do_missing" in fl2, repr([f for f in fl2 if "not_do" in f])))
R.append(("负对照 rubric ≤ 2/3", rb2["score"] <= 2, repr(rb2)))

print("═══ 判据 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
_all = all(o for _, o, _ in R)
print("RESULT:", "PASS" if _all else "FAIL")
sys.exit(0 if _all else 1)
