# -*- coding: utf-8 -*-
"""[v1.22.2 P1] E2E（离线 mock）：两臂各跑一次，验产物头部**分口径**渲染。

用法：python _probe_v1222_p1_e2e.py
判据：
  · ON 臂（tri_multi_vote=True）→ 头部出现「**三态判决（多票）**」，口径=三票之间
  · OFF 臂（tri_multi_vote=False）→ 头部出现「**三态判决（单票）**」，口径=单票 vs 拆解原标签
  · 两臂都**不**出现旧的「**三态多票**：high … 一致率 0% ⚠️ unstable」
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


def _my_call(self, system, user, temperature=0.6, max_tokens=3000,
             json_mode=False, model=None, thinking=None, stage=None):
    """三态判决 / 拆解两档给真产出；其余交回冒烟原桩。"""
    if stage in ("adjudicate_sub_tristate",
                 "adjudicate_sub_tristate_multi"):
        n = sum(1 for ln in (user or "").splitlines()
                if re.match(r"^\s{2}\d+\.", ln))
        n = max(1, min(n, 8))
        j = []
        for i in range(1, n + 1):
            # 1,3,5… 判 decidable（与原标签一致→high）；2 判 undecidable（→low）
            d = "decidable" if i % 2 == 1 else "undecidable"
            j.append({"id": i, "reason": "冒烟", "decidability": d})
        return json.dumps({"judgments": j}, ensure_ascii=False)
    if "sub_questions" in (system or ""):
        # 冒烟原桩不认拆解 prompt（返回 "{}"）→ 研究层永远 0 子问题，
        # 两臂都没得判。这里补上，让研究层真的有子问题。
        return json.dumps({"sub_questions": [
            {"id": 1, "question": "老城区现有排水管网的设计重现期是多少",
             "weight": 0.5, "decidability": "decidable", "source": "P1"},
            {"id": 2, "question": "整体提标改造的财政承接主体是谁",
             "weight": 0.5, "decidability": "decidable", "source": "T1"},
            {"id": 3, "question": "改造后运维责任如何划转",
             "weight": 0.5, "decidability": "partial", "source": "T2"},
        ]}, ensure_ascii=False)
    return _fake(self, system, user, temperature, max_tokens, json_mode,
                 model, thinking, stage)


mod.LLM.call = _my_call

Q = "老城区排水管网的现有设计标准是多少年一遇？该不该整体提标改造？"
R = []
for multi in (True, False):
    tag = "ON(多票)" if multi else "OFF(单票)"
    cfg = hm.build_cfg(False)
    cfg.setdefault("actions", {})["tri_multi_vote"] = multi
    cfg["output"]["save_dir"] = tempfile.mkdtemp(prefix="v1222p1_")
    meta = mod.MetaDGTF(cfg)
    res = meta.run(Q, route=["0", "1"], rounds={"0": 2, "1": 2},
                   parallel_mode="serial")
    subs = ((res.get("pools") or {}).get("1") or {}).get("sub_questions") or []
    st = [s.get("stability") for s in subs]
    vm = {s.get("_vote_mode") for s in subs}
    md = mod.save_result(res, cfg["output"]["save_dir"]).read_text(encoding="utf-8")
    _line = ""
    for ln in md.split("\n"):
        if "三态判决（" in ln or "三态多票**：" in ln:
            _line = ln.strip()
            break
    print("── %s ──" % tag)
    print("   stability =", st)
    print("   _vote_mode =", vm)
    print("   头部行 =", _line)
    R.append((tag, st, vm, _line, md))

print("═══ 判据 ═══")
ok = True
for tag, st, vm, line, md in R:
    _want_mode = "multi" if "ON" in tag else "single"
    c1 = vm == {_want_mode}
    c2 = all(x in ("high", "medium", "low", "abstained") for x in st)
    c3 = ("三态判决（多票）" in line) if _want_mode == "multi" \
        else ("三态判决（单票）" in line)
    c4 = ("口径=三票之间" in line) if _want_mode == "multi" \
        else ("口径=单票 vs 拆解原标签" in line)
    c5 = "**三态多票**：high" not in line
    for _n, _c in (("vote_mode", c1), ("stability 合法", c2),
                   ("标题分口径", c3), ("口径标注", c4),
                   ("旧行已消失", c5)):
        print(("  ✓ " if _c else "  ✗ ") + tag + " / " + _n)
        ok = ok and _c

print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
