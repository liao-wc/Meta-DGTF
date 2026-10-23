# -*- coding: utf-8 -*-
"""重加 M72~M75（**append 到末尾**）+ 判据补功能性断言。

## 为什么重加
上一次用「锚在 M56 前」的旧习惯插入 ⇒ ①位置错（`--only` 跑错靶子）；
②我的排序脚本又把**注释归错了条目** ⇒ 注释错位。已从 git 恢复，
本次**一律 append**（并顺手修排序脚本的归注释 bug —— 见
`_mk_v12336_mutsort2.py`）。

## 为什么判据要补功能性断言
`M73`（`action_hint` 不写控制面）与 `M74`（`thinking_hint` 不同步到
`llm.thinking_stages`）**都不会让源码级判据变红** ——
只有**真喂一条候选进 `_eml_apply`、再看消费方有没有变**才抓得到。
⇒ 给 `check_v12336_eml` 的功能性段补这两条。
"""
import io
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MU = HERE / "_mut_v12332.py"
SM = HERE / "smoke_test.py"

NEW_ENTRIES = '''    #   ★ M72 打在**真跑逮到的那处**上：合并路径去掉「已合并」标记
    #     ⇒ 判据（查 `self._quant_pending_yy = {` 与 `"merged": True` 同在）必判红。
    #     ★ 用**最小改动**（只删一行）而不是整块替换 ——
    #     整块替换会因缩进对不上而产生**语法错**，那样子进程直接崩、
    #     变异体报的是"崩溃"而不是"判红"，**理由就不对了**。
    ("M72 合并路径不记「已合并」档（真跑逮到的缺陷复现）",
     '                        "merged": True,\\n',
     ''),
    #   ★ M73 打在**「所有可配置行为纳入学习」的接线**上：
    #     `action_hint` 写到白名单外 ⇒ 控制面拒 ⇒ 它成了"只记账不生效"
    #     （★ 源码级判据仍绿，只有**功能性**断言能抓）。
    ("M73 action_hint 写到白名单外（新的学了不做）",
     '                        "actions.%s" % _nm, bool(_a.get("value")),',
     '                        "actionsXX.%s" % _nm, bool(_a.get("value")),'),
    #   ★ M74 打在**思考档的同步**上：只写控制面、不写 `llm.thinking_stages`
    #     ⇒ 开关记了但**消费方读不到**（同样只有功能性断言能抓）。
    ("M74 thinking_hint 不同步到 llm.thinking_stages（消费方读不到）",
     '                        if isinstance(_ts, dict):\\n'
     '                            _ts[_st] = _val',
     '                        if False:\\n'
     '                            _ts[_st] = _val'),
    #   ★ M75 打在**「可运行时调」的根**上：`_action_on` 去掉运行时覆盖
    #     ⇒ 所有 actions.* 又变回"改了也不生效"（判据源码级判红）。
    ("M75 _action_on 去掉运行时覆盖（所有 actions.* 不可运行时调）",
     '    _s = (config or {}).get("_control")',
     '    _s = None'),
'''

SM_OLD = '''        # 同一把尺子量第四个：`note_cost_no_gain` 应让圈数**变小**'''
SM_NEW = '''        # ★ [与调度融合 · 扩面] 同一把尺子量另外两个 ——
        #   `thinking_hint` 必须**真的**改到消费方（`llm.thinking_stages`）；
        #   `action_hint` 必须**真的**落进控制面（白名单内）。
        _mt_t3 = mod.MetaDGTF(build_cfg(False))
        _mt_t3._eml_mode = "on"
        _mt_t3._eml_used = [{"id": "T-THINK", "why": "判据探针",
                             "action": {"key": "thinking_hint",
                                        "stages": ["assess_decidability"],
                                        "value": "enabled"}}]
        _mt_t3._eml_apply({})
        _ts3 = getattr(getattr(_mt_t3, "llm", None), "thinking_stages", None)
        if not (isinstance(_ts3, dict)
                and _ts3.get("assess_decidability") == "enabled"):
            bad.append("[EML] `thinking_hint` **没能改到消费方**"
                       "（llm.thinking_stages 没变）⇒ 只是记账不是融合")
        _mt_t4 = mod.MetaDGTF(build_cfg(False))
        _mt_t4._eml_mode = "on"
        _mt_t4._eml_used = [{"id": "T-ACT", "why": "判据探针",
                             "action": {"key": "action_hint",
                                        "name": "parallel_expand",
                                        "value": False}}]
        _mt_t4._eml_apply({})
        _ap4 = [x.get("key") for x in (_mt_t4._control.applied or [])]
        if "actions.parallel_expand" not in _ap4:
            bad.append("[EML] `action_hint` **没落进控制面**：%r" % (_ap4,))
        # 同一把尺子量第四个：`note_cost_no_gain` 应让圈数**变小**'''


def main():
    # ① append 到 MUTS 末尾
    s = MU.read_text(encoding="utf-8")
    if "M72 合并路径不记" in s:
        print("M72~M75 已存在（跳过）")
    else:
        tail = s.rfind("\n]")
        assert tail > 0, "找不到列表结尾"
        s = s[:tail] + "\n" + NEW_ENTRIES.rstrip("\n") + s[tail:]
        MU.write_text(s, encoding="utf-8")
        _o = re.findall(r'"(M\d+) ', s)
        _n = [int(x[1:]) for x in _o]
        print("OK M72~M75 已 append；MUTS %d 条；非升序对 %r"
              % (len(_o), [(a, b) for a, b in zip(_n, _n[1:]) if b < a]))
        assert _n == sorted(_n), "不升序"

    # ② 判据补功能性
    sm = SM.read_text(encoding="utf-8")
    if "thinking_hint` **没能改到消费方**" in sm:
        print("判据功能性已存在（跳过）")
    else:
        assert sm.count(SM_OLD) == 1, "判据锚点 %d 次" % sm.count(SM_OLD)
        sm = sm.replace(SM_OLD, SM_NEW, 1)
        SM.write_text(sm, encoding="utf-8")
        print("OK 判据功能性命中已补")


main()
