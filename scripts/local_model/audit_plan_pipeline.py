# -*- coding: utf-8 -*-
"""[V2.2.86] App 计划 → opts → 引擎 CLI 的契约审计（纯函数，零 API）。

覆盖 build_plan → apply_plan → engine_runner.build_cmd 三段：
  1) route/rounds/web 等字段经 opts 落到 CLI 后与 plan 值一致；
  2) 结构化 route(list)/rounds(dict) 也必须无损转 CLI（V2.2.77 类 bug）；
  3) profile 通道：opts.profile 必须变成 --config <存在的文件>；
  4) 任何字段丢失/串味即 FAIL。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (str(ROOT), str(ROOT / "dgtf_engine"), str(ROOT / "dgtf_app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import daosheng_mode as DS  # noqa: E402
import engine_runner as ER  # noqa: E402

QUESTIONS = [
    ("fact", "HTTP 404 状态码表示什么？"),
    ("reasoning", "为什么城市热岛效应在夜间比白天更明显？"),
    ("choice", "以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气"),
    ("project", "Meta-DGTF 道生三阶模型的项目当前状态如何？"),
]
BALANCES = [0.5, 4.0, 8.0, 50.0]
_FLAGS = {v: k for k, v in ER._ARG_SPEC.items()}


def _args(cmd: list) -> dict:
    out = {}
    for i, tok in enumerate(cmd):
        if isinstance(tok, str) and tok.startswith("--"):
            out[tok] = cmd[i + 1] if i + 1 < len(cmd) else None
    return out


def check_one(kind: str, q: str, bal: float) -> list:
    bad = []
    plan = DS.build_plan(q, {}, requested="daosheng", project_related=(kind == "project"),
                         is_mock=False, balance_cny=bal)
    opts = {}
    DS.apply_plan(plan, opts)
    # 与 engine_runner.start_task 一致：profile → _config（预设 yaml 解析）
    _prof = opts.pop("profile", None)
    _cfg_expected = None
    if _prof:
        _pp = ER.profile_path(str(_prof))
        if _pp is None:
            bad.append("未知 profile：%s" % _prof)
        else:
            _cfg_expected = str(_pp)
            opts["_config"] = _cfg_expected
    cmd = ER.build_cmd(q, opts)
    args = _args(cmd)
    # 1) route
    _pr = str(plan.get("route") or "")
    _ar = args.get("--route")
    if _pr and _pr != "auto":
        if _ar is None:
            bad.append("route 丢失（plan=%s）" % _pr)
        elif DS._norm_route(_ar) != DS._norm_route(_pr):
            bad.append("route 不一致（plan=%s cli=%s）" % (_pr, _ar))
    # 2) rounds
    _pd = str(plan.get("rounds") or "")
    _ad = args.get("--rounds")
    if _pd and _pd != "auto":
        if _ad is None:
            bad.append("rounds 丢失（plan=%s）" % _pd)
        elif DS._norm_rounds(_ad) != DS._norm_rounds(_pd):
            bad.append("rounds 不一致（plan=%s cli=%s）" % (_pd, _ad))
    # 3) web
    _pw = str(plan.get("web") or "")
    _aw = args.get("--web")
    if _pw and _pw != "auto":
        if _aw != _pw:
            bad.append("web 不一致（plan=%s cli=%s）" % (_pw, _aw))
    # 4) profile → --config（按 start_task 同逻辑解析）
    if _cfg_expected:
        _cfg = args.get("--config")
        if not _cfg:
            bad.append("profile 无 --config（期望 %s）" % _cfg_expected)
        elif Path(_cfg).resolve() != Path(_cfg_expected).resolve():
            bad.append("--config 不一致（期望 %s 实际 %s）"
                       % (_cfg_expected, _cfg))
    # 5) 结构化 route/rounds 注入（模拟 v2_online 修复后的写法）
    opts2 = dict(opts)
    if plan.get("route"):
        opts2["route"] = list(DS._norm_route(plan.get("route")))
    if plan.get("rounds") and str(plan.get("rounds")) != "auto":
        opts2["rounds"] = dict(DS._norm_rounds(plan.get("rounds")))
    args2 = _args(ER.build_cmd(q, opts2))
    if opts2.get("route") and not str(args2.get("--route") or "").strip():
        bad.append("结构化 route 注入后 --route 为空")
    if opts2.get("rounds") and not str(args2.get("--rounds") or "").strip():
        bad.append("结构化 rounds 注入后 --rounds 为空")
    return bad


def main() -> int:
    rows, bad = [], []
    for kind, q in QUESTIONS:
        for bal in BALANCES:
            try:
                b = check_one(kind, q, bal)
            except Exception as e:  # noqa: BLE001
                b = ["异常：%s: %s" % (type(e).__name__, e)]
            rows.append({"kind": kind, "balance": bal, "violations": b})
            bad += ["%s@%s: %s" % (kind, bal, x) for x in b]
    out = {"schema": "metadgtf.plan_pipeline_contract.v1",
           "rows": rows, "violations": bad, "n": len(rows), "n_bad": len(bad)}
    ev = ROOT / "docs" / "plan_pipeline_contract_20261030.json"
    ev.write_text(json.dumps(out, ensure_ascii=False, indent=1) + chr(10),
                  encoding="utf-8")
    print("combos:", len(rows), "violations:", len(bad))
    for x in bad[:10]:
        print("BAD", x)
    print("evidence ->", ev.relative_to(ROOT))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
