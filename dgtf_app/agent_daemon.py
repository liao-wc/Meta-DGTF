# -*- coding: utf-8 -*-
"""Agent 后台消费循环：轮询任务队列 → triage → 修复提案（只提案，不自动改源码）。

职责很窄：**只是把 agent_worker 的「跑一次」串成循环**，不新增业务逻辑：

1. 每轮调 dgtf_v2.agent_worker.run_once(queue, results)（worker 侧按
   agent_results.jsonl 里的 task_id 去重，重复任务不会重复消费）；
2. 每轮调 dgtf_v2.agent_worker.write_proposals(queue, proposals)
   （刷新 dgtf_memory/agent_repair_proposals.md，只提案不 apply）；
3. 支持 --once（单轮，给 cron/定时任务）、--interval（轮询间隔秒）、
   --max-runs（最多几轮，0=不限）、--stop-file（文件出现即优雅退出）；
4. **异常不崩**：单轮任何异常只写 dgtf_memory/agent_daemon.log 并继续
   （日志写失败也吞掉，绝不让「记日志失败」把守护进程打死）。

用法：
    python dgtf_app/agent_daemon.py --once
    python dgtf_app/agent_daemon.py --interval 5 --max-runs 10
    python dgtf_app/agent_daemon.py --stop-file dgtf_memory/agent_daemon.stop

★ 只写 dgtf_memory/ 下的运行产物（两处 worker 输出 + 本模块日志），
  不碰引擎/app/源码；不联网、不调 LLM。
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# 允许在仓库根之外启动（导入同仓内核）。
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_HERE), str(_ROOT), str(_ROOT / "dgtf_engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dgtf_v2 import agent_worker  # noqa: E402

DEFAULT_QUEUE = agent_worker.DEFAULT_QUEUE          # dgtf_memory/agent_tasks.jsonl
DEFAULT_RESULTS = agent_worker.DEFAULT_RESULTS      # dgtf_memory/agent_results.jsonl
DEFAULT_PROPOSALS = agent_worker.DEFAULT_PROPOSALS  # dgtf_memory/agent_repair_proposals.md
DEFAULT_LOG = "dgtf_memory/agent_daemon.log"
DEFAULT_STOP = "dgtf_memory/agent_daemon.stop"
DEFAULT_INTERVAL = 5.0
DEFAULT_LIMIT = 50


# ============================================================ 配置
@dataclass
class DaemonConfig:
    """守护进程的**全部**可调项（测试可绕开 CLI 直接构造）。"""

    queue: str = DEFAULT_QUEUE
    results: str = DEFAULT_RESULTS
    proposals: str = DEFAULT_PROPOSALS
    log_path: str = DEFAULT_LOG
    stop_file: str = DEFAULT_STOP
    interval: float = DEFAULT_INTERVAL
    max_runs: int = 0          # 0 = 不限
    limit: int = DEFAULT_LIMIT
    once: bool = False
    knowledge_every: int = 0   # >0：每 N 轮 Search+Fetch 刷新技术知识

    def to_dict(self) -> dict:
        return {"queue": self.queue, "results": self.results,
                "proposals": self.proposals, "log_path": self.log_path,
                "stop_file": self.stop_file,
                "interval": round(float(self.interval), 3),
                "max_runs": int(self.max_runs), "limit": int(self.limit),
                "once": bool(self.once),
                "knowledge_every": int(self.knowledge_every)}


def build_config(argv=None) -> DaemonConfig:
    """解析命令行 → DaemonConfig（测试可直接传 argv 列表）。"""
    ap = argparse.ArgumentParser(
        description="元DGTF Agent 后台消费循环（轮询队列，只提案不改源码）")
    ap.add_argument("--once", action="store_true",
                    help="只消费一轮后退出（默认持续轮询）")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                    help="轮询间隔秒数（默认 %(default)s）")
    ap.add_argument("--max-runs", type=int, default=0,
                    help="最多消费几轮；0=不限（默认 %(default)s）")
    ap.add_argument("--stop-file", default=DEFAULT_STOP,
                    help="停止文件路径：文件存在即优雅退出（默认 %(default)s）")
    # 以下为运维/测试用的路径覆盖（默认值即生产路径）
    ap.add_argument("--queue", default=DEFAULT_QUEUE, help="任务队列 JSONL")
    ap.add_argument("--results", default=DEFAULT_RESULTS, help="处理结果 JSONL")
    ap.add_argument("--proposals", default=DEFAULT_PROPOSALS,
                    help="修复提案 Markdown")
    ap.add_argument("--log", dest="log_path", default=DEFAULT_LOG,
                    help="守护进程日志路径")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="每轮最多读多少条任务（默认 %(default)s）")
    ap.add_argument("--knowledge-every", type=int, default=0,
                    help="每 N 轮 Search+Fetch 刷新技术知识；0=关（默认）")
    a = ap.parse_args(argv)
    return DaemonConfig(
        queue=str(a.queue), results=str(a.results),
        proposals=str(a.proposals), log_path=str(a.log_path),
        stop_file=str(a.stop_file), interval=float(a.interval),
        max_runs=max(0, int(a.max_runs)), limit=max(1, int(a.limit)),
        once=bool(a.once),
        knowledge_every=max(0, int(a.knowledge_every)))


# ============================================================ 日志 / 停止判定
def _kv(fields) -> str:
    """日志尾部的 k=v 串（值压成单行、截断，保证一条事件一行）。"""
    out = []
    for k, v in fields.items():
        s = str(v).replace("\r", " ").replace("\n", " ").strip()
        out.append("%s=%s" % (k, s[:300]))
    return " ".join(out)


def log_event(cfg: DaemonConfig, level: str, event: str, **fields) -> None:
    """写一行日志；**任何写日志失败都吞掉**（日志不能把守护进程打死）。"""
    try:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        line = "%s [%s] %s" % (ts, level, event)
        tail = _kv(fields)
        if tail:
            line += " " + tail
        p = Path(cfg.log_path)
        if str(p.parent):
            p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001 —— 日志失败不阻断守护进程
        pass


def should_stop(cfg: DaemonConfig) -> bool:
    """停止文件存在 ⇒ 该退出了。空路径 = 不启用停止文件。"""
    s = str(cfg.stop_file or "").strip()
    if not s:
        return False
    try:
        return Path(s).exists()
    except OSError:
        return False


def _sleep(seconds: float) -> None:
    """可替换的 sleep 缝（测试用来模拟「轮询期间用户放了停止文件」）。"""
    time.sleep(max(0.0, float(seconds)))


# ============================================================ 单轮
def run_cycle(cfg: DaemonConfig, cycle: int = 1) -> dict:
    """消费一轮：run_once + write_proposals。异常**只留痕、不抛出**。"""
    started = time.time()
    try:
        res = agent_worker.run_once(cfg.queue, cfg.results, limit=cfg.limit)
        triaged = int((res or {}).get("triaged") or 0)
        prop = agent_worker.write_proposals(cfg.queue, cfg.proposals)
        n_prop = int((prop or {}).get("n") or 0)
        elapsed = round(time.time() - started, 3)
        log_event(cfg, "INFO", "cycle", cycle=cycle, triaged=triaged,
                  proposals=n_prop, elapsed_s=elapsed)
        return {"ok": True, "cycle": int(cycle), "triaged": triaged,
                "proposals": n_prop, "elapsed_s": elapsed, "error": ""}
    except Exception as e:  # noqa: BLE001 —— 失败留痕，不中断循环
        elapsed = round(time.time() - started, 3)
        log_event(cfg, "ERROR", "cycle_error", cycle=cycle,
                  error="%s: %s" % (type(e).__name__, e),
                  elapsed_s=elapsed)
        return {"ok": False, "cycle": int(cycle), "triaged": 0,
                "proposals": 0, "elapsed_s": elapsed,
                "error": "%s: %s" % (type(e).__name__, e)}


# ============================================================ 主循环
def main(argv=None) -> int:
    """入口：返回进程退出码（正常退出恒 0；单轮异常已被 run_cycle 吞掉）。"""
    cfg = build_config(argv)
    log_event(cfg, "INFO", "start", queue=cfg.queue,
              interval=cfg.interval, max_runs=cfg.max_runs,
              once=cfg.once, stop_file=cfg.stop_file)
    if should_stop(cfg):
        log_event(cfg, "INFO", "stop", reason="stop_file", cycle=0)
        return 0
    if cfg.once:
        run_cycle(cfg, cycle=1)
        return 0
    runs = 0
    cycle = 0
    try:
        while True:
            if should_stop(cfg):
                log_event(cfg, "INFO", "stop", reason="stop_file",
                          cycle=cycle, runs=runs)
                break
            if cfg.max_runs > 0 and runs >= cfg.max_runs:
                log_event(cfg, "INFO", "stop", reason="max_runs", runs=runs)
                break
            cycle += 1
            run_cycle(cfg, cycle=cycle)
            runs += 1
            if cfg.max_runs > 0 and runs >= cfg.max_runs:
                log_event(cfg, "INFO", "stop", reason="max_runs", runs=runs)
                break
            _sleep(cfg.interval)
    except KeyboardInterrupt:  # 交互/被终止：优雅退出
        log_event(cfg, "INFO", "stop", reason="interrupted", runs=runs)
    return 0


__all__ = ["DEFAULT_QUEUE", "DEFAULT_RESULTS", "DEFAULT_PROPOSALS",
           "DEFAULT_LOG", "DEFAULT_STOP", "DEFAULT_INTERVAL", "DEFAULT_LIMIT",
           "DaemonConfig", "build_config", "log_event", "should_stop",
           "run_cycle", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
