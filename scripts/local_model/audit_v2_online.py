# -*- coding: utf-8 -*-
"""[V2.2.85] v2_online 契约审计（纯函数，零 API）。

背景（V2.2.77 真 bug）：v2_online.choose 返回结构化 route=list / rounds=dict，
App 直接写 opts 后旧 build_cmd 用 str(v) 透传 ⇒ 引擎收到 Python repr，四层全跳过。
本审计验证：
  1) ARMS 常量与 choose 输出都是合法 route/rounds；
  2) 经 engine_runner.cli_value 规范化后可被 daosheng 解析器**无损**还原；
  3) 任何臂都不会产生非法入口/非法圈数键。
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
import v2_online as VO  # noqa: E402

QUESTIONS = [
    "HTTP 404 状态码表示什么？",
    "为什么城市热岛效应在夜间比白天更明显？",
    "以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气",
]


def check_arm(tag: str, route, rounds) -> list:
    bad = []
    _r = DS._norm_route(route)
    if not _r:
        bad.append("%s: route 无法解析 %r" % (tag, route))
    _rs = ER.cli_value("route", route)
    if not _rs:
        bad.append("%s: cli_value(route) 为空" % tag)
    if DS._norm_route(_rs) != _r:
        bad.append("%s: route 经 CLI 串后丢失（%r -> %r）" % (tag, _r, _rs))
    _d = DS._norm_rounds(rounds)
    if not _d:
        bad.append("%s: rounds 无法解析 %r" % (tag, rounds))
    _ds = ER.cli_value("rounds", rounds)
    if not _ds:
        bad.append("%s: cli_value(rounds) 为空" % tag)
    if DS._norm_rounds(_ds) != _d:
        bad.append("%s: rounds 经 CLI 串后丢失（%r -> %r）" % (tag, _d, _ds))
    return bad


def main() -> int:
    rows, bad = [], []
    for name, arm in VO.ARMS.items():
        bad += check_arm("arm:" + name, arm.get("route"), arm.get("rounds"))
        rows.append({"tag": "arm:" + name, "route": arm.get("route"),
                     "rounds": arm.get("rounds")})
    for q in QUESTIONS:
        try:
            picked = VO.choose(q, {}, force=True)
        except Exception as e:  # noqa: BLE001
            bad.append("choose(%r) 异常：%s: %s" % (q[:12], type(e).__name__, e))
            continue
        if not isinstance(picked, dict) or not picked.get("id"):
            bad.append("choose(%r) 返回非法：%r" % (q[:12], picked))
            continue
        bad += check_arm("choose:" + q[:10], picked.get("route"),
                         picked.get("rounds"))
        rows.append({"tag": "choose:" + q[:10], "id": picked.get("id"),
                     "arm": picked.get("arm"),
                     "route": picked.get("route"),
                     "rounds": picked.get("rounds")})
    out = {"schema": "metadgtf.v2_online_contract.v1", "rows": rows,
           "violations": bad, "n": len(rows), "n_bad": len(bad)}
    ev = ROOT / "docs" / "v2_online_contract_20261030.json"
    ev.write_text(json.dumps(out, ensure_ascii=False, indent=1) + chr(10),
                  encoding="utf-8")
    for r in rows:
        print("OK  %-24s route=%s rounds=%s" % (r["tag"], r["route"],
                                                r["rounds"]))
    for b in bad:
        print("BAD", b)
    print("violations:", len(bad), "| evidence ->", ev.relative_to(ROOT))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
