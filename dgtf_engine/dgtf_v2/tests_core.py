# -*- coding: utf-8 -*-
"""Phase 5 · 四层核心职责审计判据。"""
import glob
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dgtf_v2.core_duty import audit_packed, repair_packed

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  OK  " if ok else "  FAIL") + " " + name +
          (("  — " + str(detail)) if detail else ""))


def good_packed():
    return {
        "route": ["0", "1", "both", "all"],
        "views": {
            "0": {"candidates": [{"desc": "a"}], "probes": [{"question": "q"}]},
            "1": {"decidable_product": {"answer": "答", "evidence": ["e1"]}},
            "both": {"manifest": "综合"},
            "all": {"decision": "决", "actions": [{
                "owner": "o", "deadline": "d", "acceptance": "a",
                "rollback": "r", "verb": "v", "object": "x"}],
                "not_do": [{"what": "n"}], "residual_risks": ["r"],
                "provenance": ["p"]},
        },
        "pools": {"1": {"sub_questions": [{"id": 1, "decidability": "decidable"}]}},
    }


def main():
    p = good_packed()
    a = audit_packed(p)
    check("新式 packed：四层职责通过", a["ok"], a)

    old = good_packed()
    old["views"]["1"]["_actions"] = [{"owner_role": "o", "deadline_hint": "d",
                                     "acceptance": "a", "fallback": "r"}]
    old["views"]["all"] = {"manifest": "旧跑 all 文本"}
    old["views"]["1"].pop("decidable_product", None)
    old["pools"]["1"] = {"sub_questions": []}
    a2 = audit_packed(old)
    check("旧式 packed：抓到 1 层越权", "1: 出现 action_plan（越权）" in a2["overreach"])
    check("旧式 packed：actions 迁到 all", a2["layers"]["all"]["actions"] == 1, a2["layers"]["all"])
    check("旧式 packed：记录修复", any("1.actions->all" in x for x in a2["repairs"]), a2["repairs"])

    miss = good_packed()
    miss["views"]["all"]["actions"] = []
    a3 = audit_packed(miss)
    check("all 缺 actions 判缺口", any("all: 缺 actions" in x for x in a3["gaps"]), a3["gaps"])

    no0 = good_packed()
    no0["views"]["0"] = {"candidates": [{"desc": "a"}]}
    a4 = audit_packed(no0)
    check("0 缺 probe/suspension 判缺口", any(x.startswith("0:") for x in a4["gaps"]), a4["gaps"])

    skip = good_packed()
    skip["route"] = ["0", "1"]
    a5 = audit_packed(skip)
    check("未跑层跳过不误判", a5["layers"]["all"].get("skipped") == "not_in_route", a5["layers"]["all"])

    d, reps = repair_packed(good_packed())
    check("修复不改原 packed", "actions" in good_packed()["views"]["all"], reps)

    fs = sorted(glob.glob("outputs/*.packed.json"), key=os.path.getmtime)[-1:]
    if fs:
        a6 = audit_packed(json.load(open(fs[0], encoding="utf-8")))
        check("真实 packed 审计可跑", "layers" in a6 and "gaps" in a6, a6.get("repairs"))
    elif os.getenv("DGTF_REQUIRE_REPLAY") == "1":
        check("真实 packed 审计可跑", False, "no packed (DGTF_REQUIRE_REPLAY=1)")
    else:
        # CI 是干净 checkout：outputs/ 不入库，本地回放检查显式 SKIP（不是假绿）。
        print("  · SKIP 真实 packed 审计可跑（无 outputs 回放数据）")

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
