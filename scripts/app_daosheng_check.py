# -*- coding: utf-8 -*-
"""T3 契约实测：`POST /api/tasks` 的道生专属模式（mock，零 API 花费）。

用途：独立于 selftest 的「接口契约」冒烟证据，可直接粘进汇报/文档。
需要一个已在跑的 app server（建议 mock 环境）：

    $env:DGTF_APP_MOCK="1"          # 推荐：整服务 mock
    python dgtf_app/server.py --port 8765 --http --no-agent-daemon
    python scripts/app_daosheng_check.py --base http://127.0.0.1:8765

判据（全部通过才 exit 0）：
  ① mode=daosheng + mock 任务 → 201，响应含 mode/plan/reason/context_injected/budget_guard；
  ② GET 单任务仍带完整 mode.plan，opts 记 _mode_request（resume/重试可复原）；
  ③ mode=auto：项目题 → daosheng；通用事实题 → standard（既有链路）；
  ④ 非法 mode → HTTP 400；
  ⑤ 任务确认走 mock_engine（不触发真实引擎/API），并打印 plan 关键字段 JSON。
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_DEFAULT = os.environ.get("DGTF_APP", "http://127.0.0.1:8765")
TOKEN = (os.environ.get("DGTF_ACCESS_TOKEN", "").strip()
         or (ROOT / "dgtf_memory" / ".access_token").read_text(
             encoding="utf-8").strip() if (ROOT / "dgtf_memory" / ".access_token").is_file()
         else "")
CTX = ssl._create_unverified_context()

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (("  — " + detail) if detail else ""))


def _headers() -> dict:
    h = {"Content-Type": "application/json; charset=utf-8"}
    if TOKEN:
        h["Cookie"] = "dgtf_token=" + TOKEN
        h["X-DGTF-Token"] = TOKEN
    return h


def req(base: str, path: str, obj=None, method=None):
    url = base + path
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8") if obj is not None else None
    r = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(r, timeout=30, context=CTX) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            body = {"_raw": "non-json"}
        return int(exc.code), body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--json", action="store_true", help="同时打印 plan 关键字段 JSON")
    ap.add_argument("--keep", action="store_true", help="不自动取消/清理创建的 mock 任务")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    print("T3 道生专属模式契约实测 · base=%s" % base)

    # ① mode=daosheng 端到端
    s, r = req(base, "/api/tasks", {
        "question": "Meta-DGTF 道生三阶模型的项目当前状态如何？",
        "mode": "daosheng", "opts": {"mock": True}})
    tid = str(r.get("id") or "")
    mode = r.get("mode") or {}
    plan = mode.get("plan") or {}
    check("POST mode=daosheng → 201", s == 201 and bool(tid), "status=%s id=%s" % (s, tid))
    check("响应回显 mode.id=daosheng", mode.get("id") == "daosheng",
          json.dumps({k: mode.get(k) for k in ("id", "requested", "tier", "policy")},
                     ensure_ascii=False))
    check("响应回显 plan.policy=daosheng.v1 + route + quality_policy",
          plan.get("policy") == "daosheng.v1" and bool(plan.get("route"))
          and bool(plan.get("quality_policy")),
          "route=%s rounds=%s qp=%s" % (plan.get("route"), plan.get("rounds"),
                                        plan.get("quality_policy")))
    check("响应回显 reason/context_injected/budget_guard",
          bool(mode.get("reason")) and bool(mode.get("context_injected"))
          and (mode.get("budget_guard") or {}).get("decision") in ("ok", "degrade", "warn"),
          "；".join(mode.get("context_injected") or []))
    if args.json:
        print("PLAN_KEYS", json.dumps({
            "mode": {k: mode.get(k) for k in
                     ("id", "tier", "engine_mode", "quality_policy", "reason")},
            "plan": {k: plan.get(k) for k in
                     ("policy", "route", "rounds", "parallel", "web", "thinking",
                      "self_check_mode", "dual_judge_mode", "history_fusion",
                      "quality_policy", "context_injected")},
            "budget_guard": plan.get("budget_guard"),
            "local_llm": {k: (plan.get("local_llm") or {}).get(k)
                          for k in ("available", "source", "route")},
            "m4": {k: (plan.get("m4") or {}).get(k) for k in
                   ("ok", "first_mode", "quality_prediction")},
            "cache": plan.get("cache"),
        }, ensure_ascii=False, indent=1))

    # ② GET 单任务（轮询/resume 不丢 mode）
    if tid:
        s2, t2 = req(base, "/api/tasks/" + tid)
        m2 = t2.get("mode") or {}
        check("GET 单任务带完整 mode.plan（resume 不丢）",
              m2.get("id") == "daosheng"
              and ((m2.get("plan") or {}).get("policy") == "daosheng.v1"),
              "id=%s" % m2.get("id"))
        check("任务 opts 记 _mode_request（重试可复原档位）",
              (t2.get("opts") or {}).get("_mode_request") == "daosheng")
        check("mock 任务确认走 mock_engine（不触发真实引擎/API）",
              bool(t2.get("mock"))
              and any("mock_engine" in str(x) for x in (t2.get("cmd") or [])),
              "mock=%s" % t2.get("mock"))
        if not args.keep:
            try:
                req(base, "/api/tasks/%s/cancel" % tid, {})
            except Exception:  # noqa: BLE001
                pass

    # ③ mode=auto 分流
    s3, r3 = req(base, "/api/tasks", {
        "question": "1+1等于几？", "mode": "auto", "opts": {"mock": True}})
    m3 = r3.get("mode") or {}
    check("mode=auto 非项目题 → standard（既有链路）",
          s3 == 201 and m3.get("id") == "standard"
          and str(r3.get("quality_policy") or "").startswith("auto:"),
          "id=%s qp=%s" % (m3.get("id"), r3.get("quality_policy")))
    s4, r4 = req(base, "/api/tasks", {
        "question": "Meta-DGTF 项目背景注入是否重复？", "mode": "auto",
        "opts": {"mock": True}})
    m4 = r4.get("mode") or {}
    check("mode=auto 项目题 → daosheng（自动分流）",
          s4 == 201 and m4.get("id") in ("daosheng", "daosheng_fast"),
          "id=%s" % m4.get("id"))
    for _r in (r3, r4):
        _tid = str(_r.get("id") or "")
        if _tid and not args.keep:
            try:
                req(base, "/api/tasks/%s/cancel" % _tid, {})
            except Exception:  # noqa: BLE001
                pass

    # ④ 非法 mode → 400
    s5, b5 = req(base, "/api/tasks", {"question": "x", "mode": "bogus",
                                      "opts": {"mock": True}})
    check("非法 mode → HTTP 400（带白名单）",
          s5 == 400 and bool(b5.get("allowed")), "status=%s" % s5)

    print("\n结果：PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：" + ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
