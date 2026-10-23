# -*- coding: utf-8 -*-
"""[v1.22.2 P1] 探针：两臂是否都产出 stability（含失败路径）。

用法：python _probe_v1222_p1.py 元DGTF-V1.22.2.py
改前跑（对 v1.22.1）应当**假**：单票臂完全没有 stability 键。
"""
import importlib.util
import json
import sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.2.py")
if not SRC.is_absolute():
    SRC = Path(__file__).resolve().parent / SRC

spec = importlib.util.spec_from_file_location("dgtf_probe", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe"] = mod
spec.loader.exec_module(mod)


class _LLM:
    """打桩：按 stage 返回不同 judgments；`fail=True` 时整支抛错。"""

    def __init__(self, fail=False, empty=False):
        self.fail = fail
        self.empty = empty
        self.calls = 0

    def call(self, system, user, temp, mx, json_mode=False, stage=""):
        self.calls += 1
        if self.fail:
            raise RuntimeError("打桩：网络炸了")
        if self.empty:
            return '{"judgments": []}'
        # 单票：第 1 条判 decidable（原标签 decidable → 一致=high）
        #       第 2 条判 undecidable（原标签 decidable → 不一致=low）
        #       第 3 条**不返回** → 弃权=abstained
        return json.dumps({"judgments": [
            {"id": 1, "reason": "有位置", "decidability": "decidable"},
            {"id": 2, "reason": "空槽", "decidability": "undecidable"},
        ]}, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


def mk(subs, llm, multi):
    m = object.__new__(mod.MetaDGTF)
    m.llm = llm
    m.config = {"actions": {"tri_multi_vote": multi}}
    m.vp = lambda *a, **k: None
    return m


def new_subs():
    return [{"id": 1, "question": "子问一（可判）", "decidability": "decidable"},
            {"id": 2, "question": "子问二（可判）", "decidability": "decidable"},
            {"id": 3, "question": "子问三（未返回）", "decidability": "partial"}]


R = []


def ck(tag, cond, note):
    R.append((tag, bool(cond), note))


has_fn = hasattr(mod, "_single_vote_stability")
ck("P1.1 口径函数存在", has_fn,
   "_single_vote_stability" + ("已定义" if has_fn else "**缺失**"))
has_w = hasattr(mod.MetaDGTF, "_write_tri_stability")
ck("P1.2 写入口存在", has_w, "MetaDGTF._write_tri_stability")

# --- 单票臂（OFF）正常 ---
subs = new_subs()
mk(subs, _LLM(), False)._adjudicate_sub_tristate(subs, "Q")
_modes = {s.get("_vote_mode") for s in subs}
_has = all("stability" in s for s in subs)
ck("P1.3 单票臂：每条都有 stability", _has,
   "stabilities=" + repr([s.get("stability") for s in subs]))
ck("P1.4 单票臂：_vote_mode=single", _modes == {"single"}, repr(_modes))
_st = [s.get("stability") for s in subs]
ck("P1.5 单票臂：一致=high / 不一致=low / 弃权=abstained",
   _st[0] == "high" and _st[1] == "low" and _st[2] == "abstained",
   "expected [high, low, abstained] got " + repr(_st))
ck("P1.6 单票臂：弃权条不落 high/low",
   _st[2] not in ("high", "low"), "第3条=" + repr(_st[2]))

# --- 多票臂（ON）正常 ---
subs2 = new_subs()
mk(subs2, _LLM(), True)._adjudicate_sub_tristate(subs2, "Q")
_has2 = all("stability" in s for s in subs2)
ck("P1.7 多票臂：每条都有 stability", _has2,
   "stabilities=" + repr([s.get("stability") for s in subs2]))
ck("P1.8 多票臂：_vote_mode=multi",
   {s.get("_vote_mode") for s in subs2} == {"multi"},
   repr({s.get("_vote_mode") for s in subs2}))

# --- 失败路径（关键：早退也必须写）---
for _name, _m, _kw in (("单票", False, {}), ("多票", True, {})):
    subs3 = new_subs()
    mk(subs3, _LLM(fail=True), _m)._adjudicate_sub_tristate(subs3, "Q")
    _all = all(s.get("stability") == "abstained" for s in subs3)
    ck(f"P1.9 失败路径({_name})：全部 abstained", _all,
       "stabilities=" + repr([s.get("stability") for s in subs3]))

# --- 空 judgments 路径 ---
subs4 = new_subs()
mk(subs4, _LLM(empty=True), False)._adjudicate_sub_tristate(subs4, "Q")
ck("P1.10 空 judgments：全部 abstained",
   all(s.get("stability") == "abstained" for s in subs4),
   "stabilities=" + repr([s.get("stability") for s in subs4]))

# --- 口径函数负对照 ---
if has_fn:
    ck("P1.11 负对照：未判条→abstained",
       mod._single_vote_stability({}) == "abstained",
       repr(mod._single_vote_stability({})))
    ck("P1.12 负对照：有判无原标签→medium",
       mod._single_vote_stability({"_tri_judged": True,
                                   "decidability": "partial"}) == "medium",
       repr(mod._single_vote_stability({"_tri_judged": True,
                                        "decidability": "partial"})))
    ck("P1.13 负对照：一致→high，不一致→low",
       mod._single_vote_stability({"_tri_judged": True, "first_label": "partial",
                                   "decidability": "partial"}) == "high"
       and mod._single_vote_stability({"_tri_judged": True,
                                       "first_label": "decidable",
                                       "decidability": "partial"}) == "low",
       "ok")

# --- 渲染口径（源串级，轻量）---
_txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
ck("P1.14 渲染按 _vote_mode 分口径",
   "三态判决（" in _txt and '"_vote_mode"' in _txt,
   "头部标题已改为「三态判决（单票/多票）」")
ck("P1.15 渲染分母只数已判条", "_voted = _hi + _me + _lo" in _txt, "")
ck("P1.16 渲染弃权单列", '== "abstained"' in _txt, "")

print("═══ probe v1222 P1 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
print(f"PASS {sum(1 for _,o,_ in R if o)} / FAIL {sum(1 for _,o,_ in R if not o)}")
sys.exit(0 if all(o for _, o, _ in R) else 1)
