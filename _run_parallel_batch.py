# -*- coding: utf-8 -*-
"""[v1.21.60] 并行跑批 runner。

按任务清单，多个 run 并发执行（每个独立 subprocess、独立日志落盘），
用 --max-concurrency 控制并发上限（默认 3）。

用法：
  python _run_parallel_batch.py --max-concurrency 3 \
    "serial 6 koan1 人生的意义是什么" \
    "serial 12 reclass 复杂问题被拆成几个部分分别研究之后，剩下的那个整体到底是什么？"

任务项格式：`<mode> <rounds> <tag> <question...>`（空格分隔，question 可含空格）。

每个 run 由 _run_v60.py 执行（它负责 load_dotenv → run → 日志落盘 → 产物落盘）。
本 runner 只负责并发调度 + 汇总一行摘要；verbose 各自进 v60_<tag>_r<rounds>_<mode>.log。
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent


def parse_task(spec: str):
    """任务项格式：`<mode> <rounds> <tag> <question...>`

    ★ 也支持**逐任务环境变量**（用于逐实验臂覆盖配置）：
        `V60_THINKING=default=disabled,reasoner=enabled|A 5 tag1 问题是……`
      即以 `|` 分隔，左边（第一个 `|` 之前）是 `K=V;K2=V2` 形式的覆盖项，
      右边是原来的四段任务。
      —— 因为 thinking 档位是**每个实验臂一个值**，而 _run_v60 只认环境
      变量；批跑若共用一个环境，所有臂会被压成同一档，实验就白做了。
    """
    envs = {}
    body = spec.strip()
    if "|" in spec and "=" in spec.split("|", 1)[0]:
        head, body = spec.split("|", 1)
        for seg in head.split(";"):
            if "=" in seg:
                k, v = seg.split("=", 1)
                envs[k.strip()] = v.strip()
    parts = body.strip().split(" ", 3)
    if len(parts) < 4:
        raise ValueError(f"任务项格式错误（需 mode rounds tag question）：{spec!r}")
    mode, rounds, tag, question = parts
    if not question.strip():
        raise ValueError(f"任务项缺 question：{spec!r}")
    return mode, rounds, tag, question, envs


def run_one(task):
    mode, rounds, tag, question, envs = task
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    for k, v in envs.items():
        env[k] = v          # ★ 逐任务覆盖，不能是 setdefault
    cmd = [sys.executable, "-u", str(HERE / "_run_v60.py"),
           mode, rounds, tag, question]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(HERE), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    dt = time.time() - t0
    body = (p.stdout or "").strip().splitlines()
    if p.returncode != 0:
        err = (p.stderr or "").strip().splitlines()
        return (f"✗ [{tag}/{mode}] rc={p.returncode} ({dt/60:.1f}min)\n"
                + "\n".join(f"    {x}" for x in (body[-3:] + err[-5:])))
    return f"✓ [{tag}/{mode}] {dt/60:.1f}min\n" + "\n".join(
        f"    {x}" for x in body[-2:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-concurrency", type=int, default=3,
                    help="并发上限（默认 3；第一次并行跑别设太高，先摸限流）")
    ap.add_argument("tasks", nargs="*", help="任务项：mode rounds tag question")
    ap.add_argument("--task-file", default="",
                    help="从文件逐行读任务项（空行/# 开头忽略）。"
                         "推荐：任务清单本身就是实验设计的一部分，"
                         "落成文件才复查得了，也不会被 shell 转义吃掉。")
    args = ap.parse_args()
    if args.task_file:
        lines = [ln.strip() for ln in
                 Path(args.task_file).read_text(encoding="utf-8").splitlines()]
        specs = [x for x in lines if x and not x.startswith("#")]
        print(f"=== 任务文件 {args.task_file}：{len(specs)} 项 ===", flush=True)
    else:
        specs = args.tasks
    if not specs:
        ap.error("没给任务：要么传位置参数，要么给 --task-file")
    tasks = [parse_task(t) for t in specs]
    print(f"=== 并行跑批 {len(tasks)} 个 run，并发上限 {args.max_concurrency} ===",
          flush=True)
    print(f"=== 开始 {time.strftime('%F %T')} ===", flush=True)
    with ThreadPoolExecutor(max_workers=args.max_concurrency) as ex:
        futs = {ex.submit(run_one, t): t for t in tasks}
        for f in as_completed(futs):
            print(f.result(), flush=True)
    print(f"=== 结束 {time.strftime('%F %T')} ===", flush=True)


if __name__ == "__main__":
    sys.exit(main())
