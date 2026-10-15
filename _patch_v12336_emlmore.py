# -*- coding: utf-8 -*-
"""「所有可配置行为纳入 EML + 与调度融合」——第二部分：新 key 与分支。

## 承接第一部分（`_patch_v12336_allcfg.py`，已应用）
① `_action_on` 已加**运行时覆盖**（运行时 > actions 段 > output 别名 > 默认）；
② `MetaDGTF.run` 已把 `self._control` 挂进 `config["_control"]`；
③ 控制面白名单已扩到 `actions.` / `thinking.` / `stop.` / `duty.`。

## 本部分
④ `eml_candidates_from_result` 新增两条候选：
   · **`thinking_hint`** —— 三态一致率低 ⇒ 该题型的三态环节**开思考**（更深推理）；
   · **`action_hint`**  —— 成本高于 p75 且职责未升 ⇒ **关并行展开**（省开销）。
⑤ `_eml_apply` 新增两个分支（**都接真实消费方**）：
   · `thinking_hint` ⇒ `thinking.<stage>` + **同步写 `llm.thinking_stages`**
     （消费方 = `LLM.call` 的思考档查表）；
   · `action_hint`  ⇒ `actions.<名>`（消费方 = `_action_on`，经 ① 的运行时覆盖）。
⑥ 判据「五分支」→「七分支」。
⑦ 变异体 M73~M75。

★ 零行为差：两条候选只在**特定读数**成立时才生成；生成的条目要等
  `mode=="on"` 才应用；应用的键进的是**内存态控制面**，不写配置。
"""
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "元DGTF-V1.23.36.py"
SM = HERE / "smoke_test.py"
MU = HERE / "_mut_v12332.py"

# ── ④ 候选生成（插在 `for c in out:` 之前）──
OLD_GEN = '''    for c in out:
        c["evidence"] = [ep.get("run_id") or ""]
        c["source"] = "engine"
    return out'''
NEW_GEN = '''    # ⑤ [与调度融合 · 扩面] 三态一致率低 ⇒ 该题型的三态环节**开思考**
    #   （更深推理），而不是只在记忆库里记一笔 —— 这才叫"纳入学习范围"。
    if _tr is not None and float(_tr) < 0.33:
        out.append({"kind": "guard",
                    "cond": {"issue": "tri_unstable_think"},
                    "action": {"key": "thinking_hint",
                               "stages": ["adjudicate_sub_tristate",
                                          "assess_decidability"],
                               "value": "enabled"},
                    "readings": {"before": {"tri_rate": round(_tr, 3),
                                            "thinking": "按配置"},
                                 "after": {"tri_rate": "期望上升"}},
                    "why": "三态一致率低 ⇒ 该环节加深推理（思考档 opened）"})
    # ⑥ [与调度融合 · 扩面] 成本高于 p75 且职责未升 ⇒ **关并行展开**
    #   （并行有线程/重复调用开销；串行更省，且这一跑本来"只贵不好"）。
    if _p75 and _c > float(_p75) and (_dmed is None or float(_dmed) < 0.35):
        out.append({"kind": "schedule",
                    "cond": {"issue": "cost_no_gain_serial"},
                    "action": {"key": "action_hint",
                               "name": "parallel_expand", "value": False},
                    "readings": {"before": {"tokens": _c, "parallel": True},
                                 "after": {"tokens": "期望下降"}},
                    "why": "成本超 p75 且职责未升 ⇒ 关并行展开（省线程开销）"})
    for c in out:
        c["evidence"] = [ep.get("run_id") or ""]
        c["source"] = "engine"
    return out'''

# ── ⑤ `_eml_apply` 两分支（接在 `note_cost_no_gain` 分支之后）──
OLD_AP = '''                if _done2:
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layers": _done2})'''
NEW_AP = '''                if _done2:
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layers": _done2})
            elif _key == "thinking_hint":
                # ★ [与调度融合 · 扩面] 逐环节思考档：经控制面 + **同步写
                #   `llm.thinking_stages`**（消费方 = `LLM.call` 里那句
                #   `th = self.thinking_stages.get(stage)`）⇒ 学到的**立刻生效**。
                _val = str(_a.get("value") or "")
                _ts = getattr(getattr(self, "llm", None), "thinking_stages", None)
                _done3 = []
                for _st in (_a.get("stages") or []):
                    _st = str(_st)
                    if self._control.write(
                            "thinking.%s" % _st, _val,
                            why="EML thinking_hint：%s ⇒ 该环节思考档设为 %s"
                                "（条目 %s）" % (_it.get("why") or "经验",
                                                _val, _it.get("id")),
                            trace_ref=_it.get("id")):
                        if isinstance(_ts, dict):
                            _ts[_st] = _val
                        _done3.append(_st)
                if _done3:
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "thinking": _done3, "value": _val})
            elif _key == "action_hint":
                # ★ [与调度融合 · 扩面] 动作开关：经控制面 ⇒ 由 `_action_on`
                #   的**运行时覆盖**读到（消费方就在那儿）⇒ 本跑后续圈立即生效。
                _nm = str(_a.get("name") or "")
                if _nm:
                    _ok = self._control.write(
                        "actions.%s" % _nm, bool(_a.get("value")),
                        why="EML action_hint：%s ⇒ %s = %r（条目 %s）"
                            % (_it.get("why") or "经验", _nm,
                               bool(_a.get("value")), _it.get("id")),
                        trace_ref=_it.get("id"))
                    if _ok:
                        _it["applied"] = True
                        _applied.append({"id": _it["id"], "key": _key,
                                         "name": _nm,
                                         "value": bool(_a.get("value"))})'''

# ── ⑥ 判据：五分支 → 七分支 ──
SM_OLD = '''    for _k in ("rounds_delta", "duty_floor", "carve_first",
               "tri_advisory_only", "note_cost_no_gain"):'''
SM_NEW = '''    for _k in ("rounds_delta", "duty_floor", "carve_first",
               "tri_advisory_only", "note_cost_no_gain",
               "thinking_hint", "action_hint"):'''

# ── ⑦ 变异体 ──
MU_OLD = '''    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''
MU_NEW = '''    #   ★ M73 打在**「所有可配置行为纳入学习」的接线**上：
    #     `action_hint` 不写控制面 ⇒ 它就成了"只记账不生效"（判据的功能性断言抓）。
    ("M73 action_hint 不写控制面（新的学了不做）",
     "                        \\"actions.%s\\" % _nm, bool(_a.get(\\"value\\")),",
     "                        \\"actions_DISABLED.%s\\" % _nm, True,"),
    #   ★ M74 打在**思考档的同步**上：只写控制面、不写 `llm.thinking_stages`
    #     ⇒ 开关记了但**消费方读不到**（功能性断言应抓）。
    ("M74 thinking_hint 不同步到 llm.thinking_stages（消费方读不到）",
     "                        if isinstance(_ts, dict):\\n"
     "                            _ts[_st] = _val",
     "                        if False:\\n"
     "                            _ts[_st] = _val"),
    #   ★ M75 打在**「可运行时调」的根**上：`_action_on` 去掉运行时覆盖
    #     ⇒ 所有 actions.* 又变回"改了也不生效"（判据应抓）。
    ("M75 _action_on 去掉运行时覆盖（所有 actions.* 不可运行时调）",
     "    _s = (config or {}).get(\\"_control\\")",
     "    _s = None"),

    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD_GEN, NEW_GEN, "④ 候选生成"),
                          (OLD_AP, NEW_AP, "⑤ 两分支")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    _ap = s[s.find("def _eml_apply"):s.find("\n    def ",
                                            s.find("def _eml_apply"))]
    assert '_key == "thinking_hint"' in _ap and '_key == "action_hint"' in _ap
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 主文件：两候选 + 两分支；行数 %d" % out.count(b"\n"))

    sm = SM.read_text(encoding="utf-8")
    assert sm.count(SM_OLD) == 1, "判据锚点 %d 次" % sm.count(SM_OLD)
    sm = sm.replace(SM_OLD, SM_NEW, 1)
    SM.write_text(sm, encoding="utf-8")
    print("OK 判据：五分支 → 七分支")

    m = MU.read_text(encoding="utf-8")
    if "M73 action_hint 不写控制面" in m:
        print("M73~M75 已存在")
    else:
        assert m.count(MU_OLD) == 1, "变异体锚点 %d 次" % m.count(MU_OLD)
        m = m.replace(MU_OLD, MU_NEW, 1)
        MU.write_text(m, encoding="utf-8")
        print("OK M73~M75 已加（随后用 _mk_v12336_mutsort.py 排序）")


main()
