# -*- coding: utf-8 -*-
"""mx batch01 全链路自动编排（无人值守）。

阶段：
  0. 探活：直到 chat completions 通道恢复（连续 2 次成功才认定恢复）
  1. pilot：跑 1 个批次成员作为试点，按耗时决定主批并发
  2. effort 探针：回答「effort low/high 怎么选」
  3. 主批：剩余任务并行跑
  4. 补跑：日志不齐的任务补 2 轮
  5. 分析：跑 _mx_analyze.py 出预注册判据结论

所有阶段写 _auto_pipeline.log。中途任一阶段失败不整体崩，写清楚原因继续。
"""
import os
import re
import sys
import time
import glob
import json
import datetime
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_auto_pipeline.log")

# ★ 成本安全网：单跑 max_calls 硬上限。正常跑 ~200 calls（A/5=205、
#   B/6555=187），设 240 留 20% 余量，只拦失控，不碰正常自然停。
MAX_CALLS_SAFETY = "240"
# ★ 余额红线：低于此值停主批，保底不出负数。余额目前 ¥156，正常用不到。
BALANCE_FLOOR = 30.0


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def w(msg):
    line = f"[{stamp()}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_env():
    env = {}
    p = os.path.join(HERE, ".env")
    for ln in open(p, encoding="utf-8"):
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", ln)
        if m and not ln.strip().startswith("#"):
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def check_balance(env):
    """查余额（CNY），失败返回 None。跑批前/后各查一次，超红线停。"""
    base = env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    try:
        req = urllib.request.Request(
            base + "/user/balance",
            headers={"Authorization": "Bearer " + env.get("DGTF_API_KEY", "")})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        bi = (d.get("balance_infos") or [{}])[0]
        return float(bi.get("total_balance") or 0)
    except Exception as e:
        w(f"  余额查询失败: {type(e).__name__} {str(e)[:80]}")
        return None


def read_tasks(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        # 格式：[V60_THINKING=...|]<mode> <rounds> <tag> <question>
        # ★ 必须先把 `|` 前的 env 覆盖段切掉，否则 mode 会被污染成
        #   "V60_THINKING=...|A"，直接传给 _run_v60.py 会当成模式名炸掉。
        envpre = ""
        if "|" in s:
            envpre, _, s = s.partition("|")
            envpre = envpre.strip()
        parts = s.split(" ", 3)
        if len(parts) < 4:
            continue
        mode, rounds, tag, question = parts
        out.append({"raw": ln.strip(), "mode": mode, "rounds": rounds,
                    "tag": tag, "question": question, "envpre": envpre})
    return out


def log_exists(tag):
    return bool(glob.glob(os.path.join(HERE, f"v60_{tag}_r*.log")))


def clean_env(extra=None):
    """去掉所有 V60_* 覆盖，保证 pilot / 探针跑在干净配置上。"""
    e = dict(os.environ)
    for k in list(e):
        if k.startswith("V60_"):
            e.pop(k, None)
    e.setdefault("PYTHONIOENCODING", "utf-8")
    if extra:
        e.update(extra)
    return e


def run(cmd, timeout=None, env=None):
    """跑子进程，返回 (exit_code, elapsed_sec)。"""
    if env is None:
        env = clean_env()
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=HERE, timeout=timeout, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace")
        el = time.time() - t0
        tail = (r.stdout or "").strip().splitlines()[-6:]
        for ln in tail:
            w(f"      | {ln}")
        return r.returncode, el
    except subprocess.TimeoutExpired as e:
        el = time.time() - t0
        w(f"      | 超时 {el/60:.1f}min —— 已终止")
        return -9, el


# ── 阶段 0：探活 ────────────────────────────────────────────────
def probe_once(env, timeout=25):
    code = (
        "import os,sys,time\n"
        "sys.path.insert(0,'.')\n"
        "from openai import OpenAI\n"
        "cli=OpenAI(api_key=os.environ['_K'],base_url=os.environ['_B'],"
        f"timeout={timeout},max_retries=0)\n"
        "t=time.time()\n"
        "r=cli.chat.completions.create(model='deepseek-flash',"
        "messages=[{'role':'user','content':'回复两个字：可用'}],max_tokens=16,"
        "extra_body={'thinking':{'type':'disabled'}})\n"
        "print(f'OK {time.time()-t:.1f}s {r.usage.completion_tokens}tok')\n"
    )
    e = dict(os.environ)
    e["_K"] = env["DGTF_API_KEY"]
    e["_B"] = env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1")
    e.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        r = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=e,
                           timeout=timeout + 15, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode == 0:
            return True, (r.stdout or "").strip()
        return False, (r.stdout or "").strip()[-120:]
    except subprocess.TimeoutExpired:
        return False, "子进程超时"


def stage_probe(env, max_wait_min=360):
    w("阶段0 探活：等待 chat completions 通道恢复")
    deadline = time.time() + max_wait_min * 60
    streak = 0
    n = 0
    while time.time() < deadline:
        n += 1
        ok, info = probe_once(env)
        if ok:
            streak += 1
            w(f"  探活#{n} OK  {info}")
            if streak >= 2:
                w(f"  ✓ 通道已恢复（连续 2 次成功），耗时观测 {(time.time()-(deadline-max_wait_min*60))/60:.1f}min")
                return True
        else:
            streak = 0
            w(f"  探活#{n} FAIL {info[:80]}")
        time.sleep(60)
    w(f"  ✗ 等待 {max_wait_min} 分钟仍未恢复，放弃本轮")
    return False


# ── 阶段 1：pilot ───────────────────────────────────────────────
PILOT_TAG_RE = re.compile(r"^mx_\w+_A_r5_t0$")


def stage_pilot(tasks):
    pilot = None
    for t in tasks:
        if PILOT_TAG_RE.match(t["tag"]):
            pilot = t
            break
    if pilot is None:
        pilot = tasks[0]
    w(f"阶段1 pilot：{pilot['tag']}（mode={pilot['mode']} rounds={pilot['rounds']}）")
    # ★ 成本控制：pilot 若已有完整日志（前一轮跑过），不重跑，直接用。
    if log_exists(pilot["tag"]):
        w("  pilot 日志已存在，跳过重跑（省一次全跑）")
        # 并发可被环境变量 V60_BATCH_CONC 覆盖（默认 2 保守）。
        conc = int(os.environ.get("V60_BATCH_CONC", "2"))
        return {"pilot": pilot, "conc": conc, "elapsed": None}, 0
    penv = clean_env()
    # ★ mx batch01 是预注册对照批，必须在**旧档位**下跑完（与已完成那跑可比）。
    #   逐环节思考全关，避免「改档位」污染「测旋钮」的实验。
    penv["V60_STAGE_THINKING"] = "off"
    # ★ 成本安全网：单跑 max_calls 硬上限，拦失控不碰自然停。
    penv["V60_MAX_CALLS"] = MAX_CALLS_SAFETY
    for seg in (pilot.get("envpre") or "").split(","):
        if "=" in seg:
            k, v = seg.split("=", 1)
            penv[k.strip()] = v.strip()
    code, el = run([sys.executable, "-u", "_run_v60.py", pilot["mode"],
                    pilot["rounds"], pilot["tag"], pilot["question"]],
                   timeout=45 * 60, env=penv)
    ok = (code == 0) and log_exists(pilot["tag"])
    w(f"  pilot exit={code} 耗时 {el/60:.1f}min 日志={'有' if log_exists(pilot['tag']) else '无'}")
    if not ok:
        return None, el
    # 按耗时定并发
    if el < 15 * 60:
        conc = 3
    elif el < 25 * 60:
        conc = 2
    else:
        conc = 1
    w(f"  按耗时 {el/60:.1f}min → 主批并发定为 {conc}")
    return {"pilot": pilot, "conc": conc, "elapsed": el}, el


# ── 阶段 2：effort 探针 ────────────────────────────────────────
def stage_effort():
    w("阶段2 effort 探针：三档 effort 的正确率 / 成本 / 耗时")
    code, el = run([sys.executable, "-u", "_effort_probe.py"],
                   timeout=60 * 60)
    w(f"  effort 探针 exit={code} 耗时 {el/60:.1f}min")
    return code == 0


# ── 阶段 3/4：主批 + 补跑 ──────────────────────────────────────
def stage_batch(tasks, conc):
    remain = [t for t in tasks if not log_exists(t["tag"])]
    if not remain:
        w("阶段3 主批：任务已全部完成，跳过")
        return True
    tf = "_mx_batch_remain.txt"
    with open(os.path.join(HERE, tf), "w", encoding="utf-8") as f:
        for t in remain:
            f.write(t["raw"] + "\n")
    w(f"阶段3 主批：{len(remain)} 跑，并发 {conc}")
    # ★ 主批同样在旧档位下跑（V60_STAGE_THINKING=off 由父进程继承给子进程）
    #   + max_calls 硬上限安全网。
    code, el = run([sys.executable, "-u", "_run_parallel_batch.py",
                    "--max-concurrency", str(conc), "--task-file", tf],
                   timeout=8 * 60 * 60,
                   env=clean_env({"V60_STAGE_THINKING": "off",
                                  "V60_MAX_CALLS": MAX_CALLS_SAFETY}))
    w(f"  主批 exit={code} 耗时 {el/60:.1f}min")
    return code == 0


def stage_retry(tasks, conc, rounds=2):
    for i in range(1, rounds + 1):
        miss = [t for t in tasks if not log_exists(t["tag"])]
        if not miss:
            w(f"阶段4 补跑：第{i-1}轮后已齐，无需补")
            return True
        w(f"阶段4 补跑第{i}轮：缺 {len(miss)} 跑 {[t['tag'] for t in miss]}")
        tf = f"_mx_batch_retry{i}.txt"
        with open(os.path.join(HERE, tf), "w", encoding="utf-8") as f:
            for t in miss:
                f.write(t["raw"] + "\n")
        # 补跑降并发，避免再次互相挤
        c = max(1, conc - 1)
        code, el = run([sys.executable, "-u", "_run_parallel_batch.py",
                        "--max-concurrency", str(c), "--task-file", tf],
                       timeout=5 * 60 * 60,
                       env=clean_env({"V60_STAGE_THINKING": "off",
                                      "V60_MAX_CALLS": MAX_CALLS_SAFETY}))
        w(f"  补跑第{i}轮 exit={code} 耗时 {el/60:.1f}min")
    return not [t for t in tasks if not log_exists(t["tag"])]


# ── 阶段 5：分析 ───────────────────────────────────────────────
def stage_analyze():
    w("阶段5 分析：跑 _mx_analyze.py")
    code, el = run([sys.executable, "-u", "_mx_analyze.py"],
                   timeout=6 * 60 * 60)
    w(f"  分析 exit={code} 耗时 {el/60:.1f}min")
    return code == 0


def main():
    open(LOG, "w", encoding="utf-8").write(
        f"# 自动编排启动 {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
    env = load_env()
    tasks = read_tasks("mx_batch01.txt")
    w(f"载入 {len(tasks)} 个任务，已完成 {sum(log_exists(t['tag']) for t in tasks)} 个")

    # ★ 成本控制：跑批前查余额，低于红线直接停。
    bal = check_balance(env)
    w(f"余额 = {bal if bal is not None else '查询失败'} CNY"
      f"（红线 {BALANCE_FLOOR}）")
    if bal is not None and bal < BALANCE_FLOOR:
        w(f"  ✗ 余额 {bal} 低于红线 {BALANCE_FLOOR}，中止（请充值）")
        return 1

    if not stage_probe(env):
        w("编排中止：通道未恢复")
        return 1

    pi, _el = stage_pilot(tasks)
    conc = pi["conc"] if pi else 2
    if pi is None:
        w("  ⚠️ pilot 失败（或超时），主批并发退回默认 2 —— 继续，但需人工确认")

    ok_effort = stage_effort()
    ok_batch = stage_batch(tasks, conc)
    ok_retry = stage_retry(tasks, conc)

    done = sum(log_exists(t["tag"]) for t in tasks)
    missing = [t for t in tasks if not log_exists(t["tag"])]
    w(f"收尾：{done}/{len(tasks)} 份日志到位")
    if missing:
        w("  仍缺：" + ", ".join(t["tag"] for t in missing))
    stage_analyze()
    # ★ 跑批后查一次余额，留痕花了多少
    bal2 = check_balance(env)
    w(f"跑后余额 = {bal2 if bal2 is not None else '查询失败'} CNY")

    # ★ 堵静默失败：把各阶段结果汇总，日志缺失则以非 0 退出。
    #   原来无论 pilot 失败/主批失败/补跑失败，这里都 return 0 ——
    #   编排脚本"永远报成功"，即使主批一个没跑出来。这是静默失败。
    w(f"编排结果汇总：pilot={'OK' if pi else 'FAIL'} "
      f"effort={'OK' if ok_effort else 'FAIL'} "
      f"batch={'OK' if ok_batch else 'FAIL'} "
      f"retry={'OK' if ok_retry else 'FAIL'} "
      f"日志 {done}/{len(tasks)}")
    if missing:
        w(f"  ✗ 仍有 {len(missing)} 份日志缺失，编排以失败退出（exit=2）")
        return 2
    w("编排结束（全部日志到位）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
