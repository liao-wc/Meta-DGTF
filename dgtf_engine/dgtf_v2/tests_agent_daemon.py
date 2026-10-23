# -*- coding: utf-8 -*-
"""agent_daemon 离线判据（不联网、不调 LLM；全部落临时目录）。

覆盖任务书要求的三件事 + 健壮性：

- once：单轮消费队列（run_once + write_proposals + 日志）；
- 去重：同一队列跑第二次不重复 triage（worker 按 results.task_id 去重）；
- stop-file：文件存在 ⇒ 不消费、直接优雅退出；轮询中途出现也一样；
- 轮询参数：--interval / --max-runs / --once 只跑一轮；
- 异常不崩：队列不可读 / 日志不可写时退出码仍 0，且日志有 cycle_error；
- 日志只追加不覆盖；默认参数指向生产路径。
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "dgtf_app"))

import agent_daemon as D  # noqa: E402

P = []
F = []


def ck(name, ok, note=""):
    (P if ok else F).append(name)
    print(("PASS " if ok else "FAIL ") + name
          + (("  " + str(note)[:180]) if note and not ok else ""))


def _dir():
    return Path(tempfile.mkdtemp(prefix="agent_daemon_"))


def _write_queue(d, items):
    (d / "q.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items),
        encoding="utf-8")


def _args(d, extra):
    return ["--queue", str(d / "q.jsonl"),
            "--results", str(d / "r.jsonl"),
            "--proposals", str(d / "p.md"),
            "--log", str(d / "d.log"),
            "--stop-file", str(d / "stop")] + list(extra)


def _lines(path):
    p = Path(path)
    if not p.exists():
        return []
    return [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _log(d):
    p = d / "d.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _tasks(n=2):
    kinds = ["audit_gap", "eml_candidate", "quality_flag"]
    return [{"id": "t%d" % i, "kind": kinds[i % len(kinds)],
             "title": "任务 %d" % i, "severity": "high"} for i in range(n)]


# ---------------------------------------------------------------- once
def case_once():
    d = _dir()
    _write_queue(d, _tasks(2))
    rc = D.main(_args(d, ["--once"]))
    ck("once: 退出码 0", rc == 0, rc)
    rs = _lines(d / "r.jsonl")
    ck("once: 两条任务都被 triage", len(rs) == 2, len(rs))
    ids = {json.loads(x).get("task_id") for x in rs}
    ck("once: task_id 正确", ids == {"t0", "t1"}, ids)
    txt = (d / "p.md").read_text(encoding="utf-8") if (d / "p.md").exists() else ""
    ck("once: 生成修复提案（只提案不自动 apply）",
       "Agent 修复提案" in txt and "不自动" in txt, txt[:40])
    lg = _log(d)
    ck("once: 日志含 start / cycle / triaged=2",
       " start " in lg and "] cycle " in lg and "triaged=2" in lg, lg[-160:])
    ck("once: 只跑一轮（不进入轮询）",
       sum(1 for ln in lg.splitlines() if "] cycle " in ln) == 1)


def case_once_no_poll():
    d = _dir()
    _write_queue(d, _tasks(1))
    rc = D.main(_args(d, ["--once", "--interval", "999", "--max-runs", "9"]))
    lg = _log(d)
    ck("once: 忽略 interval/max-runs（只 1 轮且无 max_runs 停止）",
       rc == 0 and sum(1 for ln in lg.splitlines() if "] cycle " in ln) == 1
       and "reason=max_runs" not in lg, lg[-120:])


# ---------------------------------------------------------------- 去重
def case_dedupe():
    d = _dir()
    _write_queue(d, _tasks(2))
    D.main(_args(d, ["--once"]))
    first = _lines(d / "r.jsonl")
    rc = D.main(_args(d, ["--once"]))
    second = _lines(d / "r.jsonl")
    ck("去重: 第二次不新增结果行", rc == 0 and len(first) == 2
       and len(second) == len(first), (len(first), len(second)))
    ids = [json.loads(x).get("task_id") for x in second]
    ck("去重: 结果里没有重复 task_id", len(ids) == len(set(ids)), ids)
    lg = _log(d)
    ck("去重: 第二次日志 triaged=0", "triaged=0" in lg, lg[-160:])
    # 队列里加一个新任务 ⇒ 只新增它
    _write_queue(d, _tasks(3))
    D.main(_args(d, ["--once"]))
    third = _lines(d / "r.jsonl")
    new_ids = [json.loads(x).get("task_id") for x in third[len(second):]]
    ck("去重: 新任务单独追加", len(third) == 3 and new_ids == ["t2"], new_ids)


# ---------------------------------------------------------------- stop-file
def case_stop_file():
    d = _dir()
    _write_queue(d, _tasks(1))
    stop = d / "stop"
    stop.write_text("stop", encoding="utf-8")
    cfg = D.build_config(_args(d, ["--once"]))
    ck("stop-file: should_stop=True", D.should_stop(cfg) is True)
    rc = D.main(_args(d, ["--once"]))
    ck("stop-file: 退出码 0", rc == 0, rc)
    ck("stop-file: 不消费（results 不存在）", not (d / "r.jsonl").exists())
    ck("stop-file: 不生成提案", not (d / "p.md").exists())
    lg = _log(d)
    ck("stop-file: 日志 reason=stop_file", "reason=stop_file" in lg, lg[-120:])
    # 负对照：没有 stop 文件 ⇒ 不停止
    stop.unlink()
    ck("stop-file 负对照: 文件不在 ⇒ should_stop=False",
       D.should_stop(D.build_config(_args(d, ["--once"]))) is False)
    # 空 stop-file 路径 = 不启用停止文件
    cfg2 = D.build_config(_args(d, ["--once", "--stop-file", ""]))
    ck("stop-file 负对照: 空路径不触发停止", D.should_stop(cfg2) is False)


def case_stop_mid_loop():
    d = _dir()
    _write_queue(d, _tasks(1))
    orig = D._sleep
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        (d / "stop").write_text("x", encoding="utf-8")

    D._sleep = fake_sleep
    try:
        rc = D.main(_args(d, ["--interval", "5", "--max-runs", "5"]))
    finally:
        D._sleep = orig
    lg = _log(d)
    ck("stop 中途出现: 退出码 0", rc == 0, rc)
    ck("stop 中途出现: 只消费 1 轮",
       sum(1 for ln in lg.splitlines() if "] cycle " in ln) == 1)
    ck("stop 中途出现: 日志 reason=stop_file", "reason=stop_file" in lg)
    ck("stop 中途出现: 轮询确实经过 sleep 缝", calls["n"] == 1, calls)


# ---------------------------------------------------------------- 轮询参数
def case_max_runs_loop():
    d = _dir()
    _write_queue(d, _tasks(1))
    rc = D.main(_args(d, ["--interval", "0", "--max-runs", "3"]))
    lg = _log(d)
    n_cycle = sum(1 for ln in lg.splitlines() if "] cycle " in ln)
    ck("max-runs: 退出码 0", rc == 0, rc)
    ck("max-runs: 正好 3 轮", n_cycle == 3, n_cycle)
    ck("max-runs: 结果只 1 行（第 2/3 轮去重）",
       len(_lines(d / "r.jsonl")) == 1)
    ck("max-runs: 日志 reason=max_runs", "reason=max_runs" in lg)


# ---------------------------------------------------------------- 异常不崩
def case_exception_no_crash():
    d = _dir()
    qdir = d / "qdir"
    qdir.mkdir()
    rc = D.main(["--queue", str(qdir), "--results", str(d / "r.jsonl"),
                 "--proposals", str(d / "p.md"), "--log", str(d / "d.log"),
                 "--stop-file", str(d / "stop"), "--once"])
    lg = _log(d)
    ck("异常: 退出码 0（不崩）", rc == 0, rc)
    ck("异常: 日志记 cycle_error / ERROR",
       "cycle_error" in lg and "[ERROR]" in lg, lg[-200:])
    ck("异常: 未产出 results", not (d / "r.jsonl").exists())


def case_log_failure_swallowed():
    d = _dir()
    _write_queue(d, _tasks(1))
    blocker = d / "blocker"
    blocker.write_text("x", encoding="utf-8")
    bad_log = blocker / "sub" / "d.log"   # 父路径是文件 ⇒ 日志写不出去
    rc = D.main(["--queue", str(d / "q.jsonl"),
                 "--results", str(d / "r.jsonl"),
                 "--proposals", str(d / "p.md"),
                 "--log", str(bad_log),
                 "--stop-file", str(d / "stop"), "--once"])
    ck("日志不可写: 不崩（退出码 0）", rc == 0, rc)
    ck("日志不可写: 任务照常处理", len(_lines(d / "r.jsonl")) == 1)


# ---------------------------------------------------------------- 配置 / 日志 / 单轮契约
def case_config_defaults():
    cfg = D.build_config([])
    ck("默认: queue=dgtf_memory/agent_tasks.jsonl",
       cfg.queue == "dgtf_memory/agent_tasks.jsonl", cfg.queue)
    ck("默认: log=dgtf_memory/agent_daemon.log",
       cfg.log_path == "dgtf_memory/agent_daemon.log", cfg.log_path)
    ck("默认: stop-file=dgtf_memory/agent_daemon.stop",
       cfg.stop_file == "dgtf_memory/agent_daemon.stop", cfg.stop_file)
    ck("默认: interval=5.0 / max_runs=0 / once=False",
       cfg.interval == 5.0 and cfg.max_runs == 0 and cfg.once is False)
    cfg2 = D.build_config(["--once", "--interval", "0.5", "--max-runs", "2",
                           "--stop-file", "x.stop"])
    ck("参数: 解析 --once/--interval/--max-runs/--stop-file",
       cfg2.once is True and cfg2.interval == 0.5 and cfg2.max_runs == 2
       and cfg2.stop_file == "x.stop")
    ck("参数: max_runs 负数钳成 0（不限）",
       D.build_config(["--max-runs", "-3"]).max_runs == 0)


def case_log_append():
    d = _dir()
    _write_queue(d, _tasks(1))
    D.main(_args(d, ["--once"]))
    n1 = len(_log(d).splitlines())
    D.main(_args(d, ["--once"]))
    n2 = len(_log(d).splitlines())
    ck("日志: 追加不覆盖", n2 >= n1 + 2, (n1, n2))
    ck("日志: 两次 start 都在",
       sum(1 for ln in _log(d).splitlines() if " start " in ln) == 2)


def case_run_cycle_contract():
    d = _dir()
    _write_queue(d, _tasks(2))
    cfg = D.build_config(_args(d, ["--once"]))
    r1 = D.run_cycle(cfg, cycle=7)
    ck("run_cycle: 返回契约 ok/triaged/cycle",
       isinstance(r1, dict) and r1.get("ok") is True
       and r1.get("triaged") == 2 and r1.get("cycle") == 7, r1)
    r2 = D.run_cycle(cfg, cycle=8)
    ck("run_cycle: 第二轮去重 triaged=0",
       r2.get("ok") is True and r2.get("triaged") == 0, r2)


CASES = [
    case_once,
    case_once_no_poll,
    case_dedupe,
    case_stop_file,
    case_stop_mid_loop,
    case_max_runs_loop,
    case_exception_no_crash,
    case_log_failure_swallowed,
    case_config_defaults,
    case_log_append,
    case_run_cycle_contract,
]


def main():
    for fn in CASES:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            F.append(fn.__name__)
            print("FAIL %s 异常 %s: %s" % (fn.__name__, type(e).__name__, e))
    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    if F:
        print("失败项：" + "、".join(F))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
