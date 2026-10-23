# -*- coding: utf-8 -*-
"""F2 · all 元层 ClosurePackage 判据。"""
import glob
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dgtf_v2.layers_all import (assemble_closure, validate_closure,
                                ClosurePackage, ACTION_FIELDS)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  OK  " if ok else "  FAIL") + " " + name +
          (("  — " + str(detail)) if detail else ""))


def act(**kw):
    a = {"owner": "o", "deadline": "d", "acceptance": "a", "rollback": "r"}
    a.update(kw)
    return a


def main():
    full = {"decision": "决", "actions": [act()], "not_do": [{"what": "n"}],
            "residual_risks": ["r"], "provenance": ["p"], "confidence": 0.8}
    p = assemble_closure(full, {}, {"tri_ratio": 0.8})
    check("完整闭合包通过", p.ok and p.closure_completeness == 1.0, p.to_dict())
    check("动作四字段 1/1", p.action_quality["complete"] == 1, p.action_quality)

    noact = dict(full); noact["actions"] = []
    p2 = assemble_closure(noact, {}, {})
    check("缺 actions 判 gap", any("缺 actions" in x for x in p2.gaps), p2.gaps)

    bad = dict(full); bad["actions"] = [{"owner": "o"}]
    p3 = assemble_closure(bad, {}, {})
    check("动作四字段不全判 gap", any("四字段" in x for x in p3.gaps), p3.gaps)

    rv = {"decidable_product": {"actions": [act()], "not_do": [{"what": "x"}]}}
    p4 = assemble_closure({"decision": "决", "residual_risks": ["r"],
                           "provenance": ["p"], "confidence": 0.5}, rv, {})
    check("继承 actions 标 origin=1", p4.actions_origin == "1", p4.actions_origin)
    check("继承 not_do 标 origin=1", p4.not_do_origin == "1", p4.not_do_origin)

    p5 = assemble_closure({}, {}, {})
    check("空 all 记 gaps", not p5.ok and len(p5.gaps) >= 3, p5.gaps)

    try:
        validate_closure(p5)
        raised = False
    except ValueError:
        raised = True
    check("validate 对不合规包抛错", raised)

    fs = sorted(glob.glob("outputs/*.packed.json"), key=os.path.getmtime)
    if fs:
        d = json.load(open(fs[-1], encoding="utf-8"))
        p6 = assemble_closure(d.get("views", {}).get("all") or {},
                              d.get("views", {}).get("1") or {},
                              d.get("quality") or {})
        check("真实 packed 闭合包可组装", "closure_completeness" in p6.to_dict(),
              p6.to_dict())
    else:
        check("真实 packed 闭合包可组装", False, "no packed")

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
