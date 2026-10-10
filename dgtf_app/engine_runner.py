# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 引擎任务管理器。

把引擎（默认取项目根下版本号最高的 `元DGTF-V*.py`，纯 CLI）当成子进程跑：

- 从项目根 `.env` 注入凭据（**只注入环境变量，不打印、不落日志**）
- stdout/stderr 实时落到 `dgtf_app/runs/<id>.log`，前端按字节偏移增量 tail
- 轮询退出码；跑完在 `outputs/` 里定位本次新增的产物
- 内存态任务表 + 线程，纯标准库，无外部依赖

`mock` 模式（任务 opts 带 `mock:true`，或环境变量 `DGTF_APP_MOCK=1`）改用
`mock_engine.py`：零 API 花费跑通整条链路，用于开发验证与界面演示。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
RUNS_DIR = APP_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(APP_DIR))
import outputs_index as oi  # noqa: E402

MAX_CONCURRENT = int(os.environ.get("DGTF_APP_MAX_CONCURRENT", "3"))

# opts 键 → 引擎命令行 flag（值为空 / "auto" 时不透传，交给引擎 auto 自决）
_ARG_SPEC = {
    "route": "--route",
    "keep": "--keep",
    "channels": "--channels",
    "rounds": "--rounds",
    "parallel": "--parallel",
    "appendix": "--appendix",
    "landing": "--landing",
    "decidability": "--decidability",
    "orientation": "--orientation",
    "web": "--web",
    "thinking": "--thinking",
    "effort": "--effort",
    "actions-off": "--actions-off",
    "actions-on": "--actions-on",
}
_BOOL_FLAGS = {"no-self-check": "--no-self-check", "quiet": "--quiet", "debug": "--debug"}

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


# ── 引擎定位 / 配置 ──────────────────────────────────────────────
def find_engine() -> Path:
    """项目根下版本号最高的 元DGTF-V*.py；可用 DGTF_APP_ENGINE 覆盖。"""
    env = os.environ.get("DGTF_APP_ENGINE")
    if env:
        p = Path(env)
        return p if p.is_absolute() else PROJECT_ROOT / p
    cands = list(PROJECT_ROOT.glob("元DGTF-V*.py"))

    def ver(p: Path) -> tuple:
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    cands.sort(key=ver)
    return cands[-1] if cands else PROJECT_ROOT / "元DGTF-V1.23.19.py"


def load_dotenv() -> dict:
    out: dict[str, str] = {}
    p = PROJECT_ROOT / ".env"
    if not p.exists():
        return out
    try:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip().startswith("#"):
                continue
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", ln)
            if m:
                out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def credential_status() -> dict:
    """给前端看的凭据状态——只报「有没有」，绝不回传值。"""
    env = load_dotenv()
    return {
        "api_key": bool(env.get("DGTF_API_KEY")),
        "base_url": env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1"),
        "tavily": bool(env.get("TAVILY_API_KEY")),
    }


# ── 命令行构造 ───────────────────────────────────────────────────
def _is_mock(opts: dict) -> bool:
    return bool(opts.get("mock")) or os.environ.get("DGTF_APP_MOCK") == "1"


def build_cmd(question: str, opts: dict) -> list[str]:
    if _is_mock(opts):
        cmd = [sys.executable, "-u", str(APP_DIR / "mock_engine.py"), question]
    else:
        cmd = [sys.executable, "-u", str(find_engine()), question]
    for key, flag in _ARG_SPEC.items():
        v = opts.get(key)
        if v not in (None, "", "auto"):
            cmd += [flag, str(v)]
    for key, flag in _BOOL_FLAGS.items():
        if opts.get(key):
            cmd.append(flag)
    return cmd


# ── 产物定位 ─────────────────────────────────────────────────────
def _snapshot_outputs() -> dict:
    if not oi.OUTPUTS_DIR.is_dir():
        return {}
    snap = {}
    for p in oi.OUTPUTS_DIR.glob("*.md"):
        try:
            snap[p.name] = p.stat().st_mtime
        except OSError:
            pass
    return snap


def _find_new_output(before: dict, since: float) -> str | None:
    best, best_t = None, 0.0
    for p in oi.OUTPUTS_DIR.glob("*.md"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if (p.name not in before or before[p.name] < m) and m >= since - 5 and m > best_t:
            best, best_t = p.name, m
    return best


# ── 日志过滤（应用层）────────────────────────────────────────────
# 引擎在 output.verbose / show_ing / show_manifest 打开时会打两类"大块"，
# 后台只想看进度，故在应用层折叠（原始全文仍完整留在 runs/<id>.log，并归档）：
#   ╔═══「圈全量留痕 / 收尾留痕」═══╗ + 字段正文（以「└ 全量留痕结束」收）
#   ┌───「│ 【ing 全文】/【view 全文】」───└
# ★ 不用引擎的 --quiet：它连每圈进度条（也在 verbose 块里）一起关掉，后台会全空。
_SKIP_LINE_LIMIT = 30000  # 兜底：留痕若异常没打完结束标记，防止 skip 卡死


def _filter_lines(text: str, st: dict) -> tuple[str, int]:
    """按行过滤；st 跨增量持有 {'skip','kind','n'}。返回 (保留文本, 折叠行数)。"""
    out: list[str] = []
    hidden = 0
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    for line in lines:
        ls = line.lstrip()
        head = ls[:1]
        if st["skip"]:
            end = False
            if st["kind"] == "box" and head == "└":
                end = True
            elif st["kind"] == "hn" and (head == "└" or "全量留痕结束" in line):
                end = True
            if not end and head in ("━", "╔", "┌"):     # 下一个块/进度 → 软退出
                end = True
            if not end and st.get("n", 0) > _SKIP_LINE_LIMIT:
                end = True
            hidden += 1
            if not end:
                st["n"] = st.get("n", 0) + 1
                continue
            st["skip"], st["kind"], st["n"] = False, None, 0
            if head in ("╔", "┌"):                       # 立刻开新块
                st.update(skip=True, kind=("hn" if head == "╔" else "box"), n=1)
            elif head == "━":                            # 进度行保留
                out.append(line)
            continue
        if head == "╔":
            st.update(skip=True, kind="hn", n=1)
            hidden += 1
            continue
        if head == "┌":
            st.update(skip=True, kind="box", n=1)
            hidden += 1
            continue
        out.append(line)
    res = "\n".join(out)
    return (res + "\n" if res else ""), hidden


def _archive(task: dict) -> None:
    """跑完把「完整运行日志」与「运行元信息」单独落到 outputs/。"""
    if not oi.OUTPUTS_DIR.is_dir():
        return
    name = task.get("output_name") or ""
    stamp = name[:-3] if name.endswith(".md") else (
        name or (time.strftime("%Y%m%d_%H%M%S") + "_" + task["id"]))
    try:
        src = Path(task["log"])
        if src.exists():
            dst = oi.OUTPUTS_DIR / f"{stamp}.run.log"
            dst.write_bytes(src.read_bytes())
            task["archive_log"] = dst.name
        meta = {
            "id": task["id"], "question": task["question"],
            "status": task["status"], "exit_code": task["exit_code"],
            "mock": task["mock"],
            "engine": "mock_engine" if task["mock"] else find_engine().name,
            "opts": task["opts"],
            "created_at": task["created_at"], "started_at": task["started_at"],
            "ended_at": task["ended_at"],
            "duration_sec": (round(task["ended_at"] - task["started_at"], 1)
                             if task["started_at"] and task["ended_at"] else None),
            "output_name": task.get("output_name"),
            "error": task.get("error", ""), "cmd": task["cmd"],
        }
        dstj = oi.OUTPUTS_DIR / f"{stamp}.run.json"
        dstj.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        task["archive_json"] = dstj.name
    except OSError:
        pass


# ── 任务生命周期 ─────────────────────────────────────────────────
def start_task(question: str, opts: dict | None = None) -> str:
    question = (question or "").strip()
    if not question:
        raise ValueError("question 不能为空")
    opts = dict(opts or {})

    running = sum(1 for t in _tasks.values() if t["status"] in ("running", "queued"))
    tid = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    log_path = RUNS_DIR / f"{tid}.log"
    status = "queued" if running >= MAX_CONCURRENT else "running"

    task = {
        "id": tid,
        "question": question,
        "opts": opts,
        "status": status,
        "mock": _is_mock(opts),
        "created_at": time.time(),
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "log": str(log_path),
        "output_name": None,
        "error": "",
        "cmd": build_cmd(question, opts),
        "before_outputs": _snapshot_outputs(),
        "pid": None,
    }
    with _tasks_lock:
        _tasks[tid] = task

    threading.Thread(target=_run, args=(tid,), daemon=True).start()
    return tid


def _run(tid: str) -> None:
    with _tasks_lock:
        task = _tasks.get(tid)
    if task is None:
        return
    # 排队等待并发位
    while task["status"] == "queued":
        with _tasks_lock:
            running = sum(1 for t in _tasks.values()
                          if t["status"] == "running" and t["id"] != tid)
        if running < MAX_CONCURRENT:
            task["status"] = "running"
        else:
            time.sleep(1.0)
    if task["status"] == "error":  # 排队期间被取消
        return

    env = dict(os.environ)
    env.update(load_dotenv())
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    task["started_at"] = time.time()
    log_path = Path(task["log"])
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
            proc = subprocess.Popen(
                task["cmd"], cwd=str(PROJECT_ROOT), env=env,
                stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            )
            task["pid"] = proc.pid
            code = proc.wait()
        task["exit_code"] = code
    except Exception as e:  # noqa: BLE001
        task["status"] = "error"
        task["error"] = f"{type(e).__name__}: {e}"
        task["ended_at"] = time.time()
        return

    task["ended_at"] = time.time()
    out = _find_new_output(task["before_outputs"], task["started_at"] or task["created_at"])
    if out:
        task["output_name"] = out
    if code == 0:
        task["status"] = "done"
    else:
        task["status"] = "error"
        if not task["error"]:
            task["error"] = f"引擎退出码 {code}"
    _archive(task)  # 完整 log + 运行元信息 → outputs/


def cancel_task(tid: str) -> bool:
    with _tasks_lock:
        task = _tasks.get(tid)
    if not task or task["status"] not in ("running", "queued"):
        return False
    task["error"] = "已手动取消"
    task["status"] = "error"
    task["ended_at"] = time.time()
    pid = task.get("pid")
    if pid:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True)
            else:
                os.kill(pid, 15)
        except Exception:  # noqa: BLE001
            pass
    return True


# ── 读取接口（给 HTTP 层）────────────────────────────────────────
def get_task(tid: str) -> dict | None:
    with _tasks_lock:
        task = _tasks.get(tid)
        if not task:
            return None
        return {k: v for k, v in task.items() if not k.startswith("_")}


def list_tasks() -> list[dict]:
    with _tasks_lock:
        items = list(_tasks.values())
    items.sort(key=lambda t: t["created_at"], reverse=True)
    out = []
    for t in items:
        out.append({k: v for k, v in t.items()
                    if not k.startswith("_") and k != "before_outputs"})
    return out


def read_log(tid: str, offset: int = 0, mode: str = "filtered",
             max_bytes: int = 400_000) -> dict | None:
    """按字节偏移增量读日志。

    mode="raw"      原始全文（**运行中**用它，过程看得见）；
    mode="filtered" 折叠「留痕 / ing·view 全文框」（**跑完**用它，干净）；
                    filtered 且 offset=0 时从头一次性过滤（状态机须从文件头开始）。
    只在完整行边界消费，避免把半行喂给过滤器；`hidden` = 本次折叠行数。
    """
    with _tasks_lock:
        task = _tasks.get(tid)
    if task is None:
        return None
    done = task["status"] not in ("running", "queued")
    path = Path(task["log"])
    if not path.exists():
        return {"text": "", "offset": 0, "size": 0, "done": done,
                "hidden": 0, "mode": mode}
    size = path.stat().st_size
    if offset < 0 or offset > size:
        offset = 0

    if mode == "raw":
        with open(path, "rb") as f:
            f.seek(offset)
            buf = f.read(max_bytes)
        nl = buf.rfind(b"\n")
        consumed = nl + 1 if nl >= 0 else (len(buf) if len(buf) >= max_bytes else 0)
        return {"text": buf[:consumed].decode("utf-8", "replace"),
                "offset": offset + consumed, "size": size, "done": done,
                "hidden": 0, "mode": "raw"}

    if offset == 0:                      # 过滤模式从头 → 一次性全量
        data = path.read_bytes()
        st = {"skip": False, "kind": None, "n": 0}
        task["_fstate"] = st
        text, hidden = _filter_lines(data.decode("utf-8", "replace"), st)
        return {"text": text, "offset": len(data), "size": size, "done": done,
                "hidden": hidden, "mode": "filtered"}

    st = task.setdefault("_fstate", {"skip": False, "kind": None, "n": 0})
    with open(path, "rb") as f:
        f.seek(offset)
        buf = f.read(max_bytes)
    nl = buf.rfind(b"\n")
    consumed = nl + 1 if nl >= 0 else (len(buf) if len(buf) >= max_bytes else 0)
    text, hidden = _filter_lines(buf[:consumed].decode("utf-8", "replace"), st)
    return {"text": text, "offset": offset + consumed, "size": size,
            "done": done, "hidden": hidden, "mode": "filtered"}


def read_archive(name: str) -> str | None:
    """读 outputs/ 下的归档文件（只允许 .run.log / .run.json）。"""
    n = Path(name).name
    if not (n.endswith(".run.log") or n.endswith(".run.json")):
        return None
    try:
        return (oi.OUTPUTS_DIR / n).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


if __name__ == "__main__":
    # 冒烟：mock 跑一个任务并等待
    tid = start_task("应用自检：mock 引擎端到端", {"mock": True})
    print("task:", tid)
    while True:
        t = get_task(tid)
        if t["status"] in ("done", "error"):
            print("status:", t["status"], "output:", t["output_name"], "err:", t["error"])
            break
        time.sleep(0.5)
