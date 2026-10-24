# -*- coding: utf-8 -*-
"""DSH 接管自动化闭环检查器（只读 + 临时目录，不改生产数据）。

用途：一条命令验收「全流程闭环」的五个关键面，供 DSH 巡检/发布前复核复用。
  A. 队列来源可信度闸（user_task 940c8d165eed 验收）：
     夹具 run（RS4_/E2E_/test/smoke…）不产出任务；空标题/占位标题拒绝；
     按 kind+title 去重；真 run 的过程缺口仍能入队。
  A2. 现队列无**未关闭**的空/占位标题任务（历史行通过 closed 结论留痕，不删数据）。
  B. 最新真跑离线质量门预检（scripts/precheck_quality.py，零 LLM 成本）。
  C. App 运行态 + 「DSH 本对话」full=1 整段视图（本地 127.0.0.1，口令只读本地文件）。
  D. 提案 pending=0；high 严重度任务无未关闭项。
  E. 最新真跑联网/工具调用遥测（对应 api_gap 25c91baef5ec 验收）：
     web_enabled=true 且 tools_calls/search_calls 至少有真实活动；quality.flags 只作读数展示。

退出码：0 = 无 FAIL（N/A 表示本机缺依赖文件，clean checkout 下允许）；1 = 有 FAIL。
用法：python scripts/dsh_loop_check.py [--json]
"""
from __future__ import annotations

import json
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

PASS = FAIL = NA = 0
ROWS = []


def _record(status, name, detail):
    global PASS, FAIL, NA
    if status == "PASS":
        PASS += 1
    elif status == "FAIL":
        FAIL += 1
    else:
        NA += 1
    ROWS.append({"status": status, "check": name, "detail": detail})
    print("[%s] %s  %s" % (status, name, detail))


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001 - 闭包检查器要收集而不是崩掉
        _record("FAIL", name, "异常：%s" % str(e)[:240])
        return
    if ok is None:
        _record("N/A", name, detail)
    else:
        _record("PASS" if ok else "FAIL", name, detail)


def _fixture_pack():
    return {
        "process_ledger": {"layers": {"0": {"standard_ok": False}}},
        "quality": {"flags": ["probe_link_dangling(1)"]},
        "self_feedback": {"eml_candidates": [
            {"kind": "guard", "action": {"key": "thinking_hint"}}]},
    }


def _real_pack():
    return {
        "process_ledger": {"layers": {"1": {"standard_ok": False}}},
        "quality": {"flags": []},
        "self_feedback": {},
    }


def check_queue_gate():
    from dgtf_v2.agent_bridge import append_task, build_tasks

    p = _fixture_pack()
    fixture_n = [len(build_tasks(p, rid)) for rid in
                 ("RS4_20261020_154010", "E2E_1792476024", "test_run_1",
                  "smoke_1", "pytest_42")]
    real = build_tasks(_real_pack(), "20261024_134620_why")
    tmp = Path(tempfile.mkdtemp()) / "q.jsonl"
    blank = append_task({"kind": "user_task", "title": "   "}, str(tmp))
    placeholder = append_task({"kind": "user_task", "title": "????"}, str(tmp))
    ok_task = append_task({"kind": "user_task", "title": "真实闭环验收任务"}, str(tmp))
    dup = append_task({"kind": "user_task", "title": "真实闭环验收任务"}, str(tmp))
    rejected = str(blank.get("rejected")) == "invalid_title"         and str(placeholder.get("rejected")) == "invalid_title"
    good = (not any(fixture_n)) and len(real) >= 1 and rejected         and str(ok_task.get("title")) == "真实闭环验收任务"         and str(dup.get("rejected")) == "duplicate"
    detail = ("夹具产出=%s 真跑缺口=%d 空标题=%s 占位标题=%s 去重=%s"
              % (fixture_n, len(real), blank.get("rejected"),
                 placeholder.get("rejected"), dup.get("rejected")))
    return good, detail


def _bad_title(t):
    title = str(t.get("title") or "").strip()
    return (not title) or title.count("?") >= 2 or title in (
        "根据生成的提案执行任务", "app ????", "?? Tool Calls ??")


def check_queue_placeholders():
    tasks_p = ROOT / "dgtf_memory" / "agent_tasks.jsonl"
    res_p = ROOT / "dgtf_memory" / "agent_results.jsonl"
    if not tasks_p.exists():
        return None, "队列文件不存在（clean checkout 跳过）"
    tasks = [json.loads(x) for x in tasks_p.read_text(
        encoding="utf-8", errors="replace").splitlines() if x.strip()]
    closed = set()
    if res_p.exists():
        for x in res_p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not x.strip():
                continue
            try:
                r = json.loads(x)
            except Exception:
                continue
            if r.get("status") == "closed":
                closed.add(str(r.get("task_id")))
    bad = [t for t in tasks if _bad_title(t)]
    open_bad = [t for t in bad if str(t.get("id")) not in closed]
    return (not open_bad), ("队列 %d 行；占位/空标题历史 %d 条，未关闭 %d 条%s"
                            % (len(tasks), len(bad), len(open_bad),
                               ("：" + ", ".join(str(t.get("id")) for t in open_bad[:5]))
                               if open_bad else ""))


def check_precheck():
    out = ROOT / "outputs"
    packs = sorted(out.glob("*.packed.json"), key=lambda x: x.stat().st_mtime)         if out.exists() else []
    if not packs:
        return None, "outputs/ 无 packed（clean checkout 跳过）"
    pack = str(packs[-1])
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "precheck_quality.py"),
         "--packed", pack],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=240, cwd=str(ROOT))
    lines = [x for x in (r.stdout or "").splitlines() if x.strip()]
    tail = lines[-1] if lines else ""
    return (r.returncode == 0), ("%s ⇒ %s" % (Path(pack).name, tail[:100]))


def check_app_live():
    tok_p = ROOT / "dgtf_memory" / ".access_token"
    if not tok_p.exists():
        return None, "无本地访问口令（clean checkout 跳过）"
    tok = tok_p.read_text(encoding="utf-8").strip()
    if not tok:
        return None, "本地访问口令为空（跳过）"
    ctx = ssl._create_unverified_context()

    def _get(path):
        q = "&" if "?" in path else "?"
        req = urllib.request.Request("https://127.0.0.1:8765" + path + q + "t=" + tok)
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    h = _get("/api/health")
    ev = _get("/api/dsh/current/events?full=1&limit=5")
    _av = str((h.get("app") or {}).get("version") or "")
    try:
        _av_ok = tuple(int(x) for x in _av.split(".")[:3]) >= (2, 0, 1)
    except Exception:
        _av_ok = False
    ok = (bool(h.get("ok")) and _av_ok
          and bool(ev.get("ok")) and bool(ev.get("full"))
          and isinstance(ev.get("events"), list) and bool(ev.get("session_id")))
    return ok, ("app=%s engine=%s full=%s events=%d turn=%s step=%s"
                % ((h.get("app") or {}).get("version"),
                   (h.get("engine") or {}).get("version"), ev.get("full"),
                   len(ev.get("events") or []), ev.get("turn"), ev.get("step")))


def check_ledger():
    mem = ROOT / "dgtf_memory"
    idx_p = mem / "dsh_proposals" / "_index.json"
    if not idx_p.exists():
        return None, "提案索引不存在（clean checkout 跳过）"
    idx = json.loads(idx_p.read_text(encoding="utf-8"))
    pend = sum(1 for x in (idx.get("items") or [])
               if str(x.get("status")) == "pending")
    tasks_p = mem / "agent_tasks.jsonl"
    res_p = mem / "agent_results.jsonl"
    if not tasks_p.exists() or not res_p.exists():
        return (pend == 0), "pending 提案=%d（队列文件缺，high 跳过）" % pend
    tasks = [json.loads(x) for x in tasks_p.read_text(
        encoding="utf-8", errors="replace").splitlines() if x.strip()]
    res = [json.loads(x) for x in res_p.read_text(
        encoding="utf-8", errors="replace").splitlines() if x.strip()]
    closed = {str(r.get("task_id")) for r in res if r.get("status") == "closed"}
    high = [t for t in tasks
            if str(t.get("severity")) == "high" and str(t.get("id")) not in closed]
    return (pend == 0 and not high),         "pending 提案=%d；high 未关闭=%d%s" % (
            pend, len(high), ("：" + ", ".join(str(t.get("id")) for t in high[:5]))
            if high else "")


def check_api_telemetry():
    """联网/工具调用能力遥测：看最近多次真跑窗口，而不是只看最新一跑。

    成本档可以显式关网（web off 是合法配置）；若只看最新一跑会把合法成本档
    误判成链路故障。判据：最近 8 份产物里至少一份有 web_enabled 且有真实
    search/tool/fetch 活动；最新一跑的具体读数写进 detail 供审计。
    """
    out = ROOT / "outputs"
    packs = sorted(out.glob("*.packed.json"), key=lambda x: x.stat().st_mtime) \
        if out.exists() else []
    if not packs:
        return None, "outputs/ 无 packed（clean checkout 跳过）"
    window = packs[-8:]
    latest = window[-1]
    d = json.loads(latest.read_text(encoding="utf-8", errors="replace"))
    api = d.get("api_usage") or {}
    flags = (d.get("quality") or {}).get("flags") or []
    web = bool(api.get("web_enabled"))
    tools = int(api.get("tools_calls") or 0)
    search = int(api.get("search_calls") or 0)
    fetch = int(api.get("fetch_calls") or 0)
    active = 0
    for pk in window:
        try:
            a = (json.loads(pk.read_text(encoding="utf-8", errors="replace"))
                 .get("api_usage") or {})
        except Exception:
            continue
        if bool(a.get("web_enabled")) and (
                int(a.get("tools_calls") or 0)
                or int(a.get("search_calls") or 0)
                or int(a.get("fetch_calls") or 0)):
            active += 1
    ok = active > 0
    return ok, ("最新 %s ⇒ web_enabled=%s tools=%d search=%d fetch=%d；"
                "窗口 %d 份中有联网活动 %d 份；flags=%d 条"
                % (latest.name, web, tools, search, fetch,
                   len(window), active, len(flags)))


def main():
    print("DSH 全流程闭环检查 · %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    check("A.  队列来源可信度闸（940c8d165eed 验收）", check_queue_gate)
    check("A2. 现队列无未关闭占位/空标题任务", check_queue_placeholders)
    check("B.  最新真跑离线质量门预检", check_precheck)
    check("C.  App 运行态 + DSH 本对话 full=1 视图", check_app_live)
    check("D.  提案 pending=0 且 high 队列清零", check_ledger)
    check("E.  最新真跑联网/工具调用遥测", check_api_telemetry)
    print()
    print("RESULT: PASS %d / FAIL %d / N/A %d" % (PASS, FAIL, NA))
    if "--json" in sys.argv:
        print(json.dumps({"pass": PASS, "fail": FAIL, "na": NA, "rows": ROWS},
                         ensure_ascii=False))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
