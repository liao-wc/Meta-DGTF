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
import urllib.request
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
RUNS_DIR = APP_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(APP_DIR))
import layers  # noqa: E402
import outputs_index as oi  # noqa: E402

MAX_CONCURRENT = int(os.environ.get("DGTF_APP_MAX_CONCURRENT", "3"))
CONFIG_DIR = PROJECT_ROOT / "configs"

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
    "behavior_fusion": "--behavior-fusion",
    # ★ T3 道生专属模式：V2.2.3 新机制键（默认 llm=零行为差）。
    #   透传前必须过**引擎能力探测**（见下方 _GATED_FLAGS）——
    #   engine-mech 的 V2.2.3 还没落地时透传会让 argparse 直接报错、任务当场失败。
    "history_fusion": "--history-fusion",
    "self_check_mode": "--self-check-mode",
    "dual_judge_mode": "--dual-judge-mode",
}
_BOOL_FLAGS = {"no-self-check": "--no-self-check", "quiet": "--quiet", "debug": "--debug"}

#: ★ 能力门控 flag：引擎源码里**没出现**该长 flag 就不透传（= 缺省，交给引擎默认）。
#: 对应新机制：self_check_mode/dual_judge_mode 由 engine-mech 在 V2.2.3 增加；
#: history_fusion 在 V2.2.2 已有（探测通过后照常透传）。
_GATED_FLAGS = {"--history-fusion", "--self-check-mode", "--dual-judge-mode"}

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


# ── 引擎定位 / 配置 ──────────────────────────────────────────────
def find_engine() -> Path:
    """V2 物理分类：优先 dgtf_engine/dgtf_v2/engine/；可用 DGTF_APP_ENGINE 覆盖。"""
    env = os.environ.get("DGTF_APP_ENGINE")
    if env:
        p = Path(env)
        return p if p.is_absolute() else PROJECT_ROOT / p
    _eng_dir = PROJECT_ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
    cands = list(_eng_dir.glob("Meta-DGTF*-V*.py"))
    cands += list(_eng_dir.glob("元DGTF-V*.py"))  # 兼容旧文件名
    cands += list(PROJECT_ROOT.glob("元DGTF-V*.py"))

    def ver(p: Path) -> tuple:
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    cands.sort(key=ver)
    #: 兜底仅在候选 glob 全空时生效（正常路径永远取 engines 目录里最高版本）。
    return cands[-1] if cands else (PROJECT_ROOT / "dgtf_engine" / "dgtf_v2" /
                                     "engine" / "Meta-DGTF-V2.2.3.py")


# ── 引擎能力探测（新机制 CLI 能力门控）────────────────────────────
#: 能力名 → 长 flag。键名与 `_ARG_SPEC` 的 opts 键一一对应，便于 App/文档对账。
_CAPABILITY_FLAGS = {
    "self_check_mode": "--self-check-mode",
    "dual_judge_mode": "--dual-judge-mode",
    "history_fusion": "--history-fusion",
}
#: 能力名 → 引擎 **config 键**（DEFAULT_CONFIG 里的字面 key）。
#: V2.2.3 先落 config 键、CLI 参数稍后；App 预设走 `--config` 时以 config 键为准，
#: 所以两条通道要分开探测（CLI flag ≠ config 键）。
_CAPABILITY_CONFIG_KEYS = {
    "self_check_mode": '"self_check_mode"',
    "dual_judge_mode": '"dual_judge_mode"',
    "history_fusion": '"history_fusion"',
}
_CAP_LOCK = threading.Lock()
_CAP_CACHE: dict = {"stamp": None, "data": None}


def engine_capabilities(force: bool = False) -> dict:
    """探测当前引擎源码支持哪些新机制（CLI flag / config 键分开报）。

    返回 {ok, path, version, mock, supports:{CLI flag}, supports_config:{config 键}, error}。
    App 侧据此决定「透传 CLI / 依赖预设 config 键 / 缺省」——engine-mech 交付
    V2.2.3 后本函数自动从「不支持」翻成「支持」，**App 不需要再改代码**。
    """
    env_mock = os.environ.get("DGTF_APP_MOCK") == "1"
    try:
        p = find_engine()
        st = p.stat()
        stamp = (str(p), int(st.st_mtime_ns), int(st.st_size))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "path": "", "version": "", "mock": bool(env_mock),
                "supports": {k: False for k in _CAPABILITY_FLAGS},
                "supports_config": {k: False for k in _CAPABILITY_CONFIG_KEYS},
                "error": "%s: %s" % (type(exc).__name__, exc)}
    with _CAP_LOCK:
        if (not force and _CAP_CACHE.get("stamp") == stamp
                and isinstance(_CAP_CACHE.get("data"), dict)):
            return dict(_CAP_CACHE["data"])
    supports = {k: False for k in _CAPABILITY_FLAGS}
    supports_cfg = {k: False for k in _CAPABILITY_CONFIG_KEYS}
    err = ""
    try:
        src = p.read_text(encoding="utf-8", errors="replace")
        for key, flag in _CAPABILITY_FLAGS.items():
            supports[key] = flag in src
        for key, literal in _CAPABILITY_CONFIG_KEYS.items():
            supports_cfg[key] = literal in src
    except OSError as exc:
        err = "%s: %s" % (type(exc).__name__, exc)
    m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
    data = {"ok": bool(not err), "path": str(p), "mock": bool(env_mock),
            "version": (".".join(m.groups()) if m else ""),
            "supports": supports, "supports_config": supports_cfg, "error": err}
    with _CAP_LOCK:
        if len(_CAP_CACHE) > 8:
            _CAP_CACHE.clear()
        _CAP_CACHE.update(stamp=stamp, data=dict(data))
    return data


def engine_supports_flag(flag: str) -> bool:
    """该引擎是否支持某个长 flag（未知 flag 一律按不支持处理）。"""
    for key, f in _CAPABILITY_FLAGS.items():
        if f == flag:
            return bool((engine_capabilities().get("supports") or {}).get(key))
    return True



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
        "web_search": bool(env.get("DGTF_API_KEY")),  # 默认官方检索/抓取共用 DGTF_API_KEY
        "tavily": bool(env.get("TAVILY_API_KEY")),
    }


# ── 余额 / token 读数（给运行状态条）────────────────────────────
_BAL: dict = {"t": 0.0, "val": None}


def current_balance() -> float | None:
    """查账户余额（CNY）。带 15s 缓存；失败返回 None（不抛、不阻断任务）。"""
    now = time.time()
    if now - _BAL["t"] < 15 and _BAL["val"] is not None:
        return _BAL["val"]
    env = load_dotenv()
    base = env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    try:
        req = urllib.request.Request(
            base + "/user/balance",
            headers={"Authorization": "Bearer " + env.get("DGTF_API_KEY", "")})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        bi = (d.get("balance_infos") or [{}])[0]
        val = float(bi.get("total_balance") or 0)
        _BAL.update(t=now, val=val)
        return val
    except Exception:  # noqa: BLE001
        return None


_TOK_RE = re.compile(r"\[tok\]\s*calls=(\d+)\s+tokens=(\d+)")


def parse_tok(text: str) -> tuple[int, int]:
    """从日志里取**最后一条** `[tok] calls=N tokens=M`（即当前累计）。"""
    c = t = 0
    for a, b in _TOK_RE.findall(text or ""):
        c, t = int(a), int(b)
    return c, t


# ── 命令行构造 ───────────────────────────────────────────────────
def _is_mock(opts: dict) -> bool:
    return bool(opts.get("mock")) or os.environ.get("DGTF_APP_MOCK") == "1"


def profile_path(name: str):
    """安全解析 configs/<basename>；只允许 .yaml/.yml，拒绝路径穿越。"""
    raw = str(name or "").strip()
    if not raw or "/" in raw or chr(92) in raw or ".." in raw:
        return None
    if not raw.lower().endswith((".yaml", ".yml")):
        raw += ".yaml"
    p = CONFIG_DIR / raw
    return p if p.is_file() else None


def build_cmd(question: str, opts: dict) -> list[str]:
    # 项目上下文只进引擎 argv，不污染任务标题/产物文件名。
    _prefix = str(opts.get("_prompt_prefix") or "")
    _qarg = (_prefix + question) if _prefix else question
    if _is_mock(opts):
        cmd = [sys.executable, "-u", str(APP_DIR / "mock_engine.py"), _qarg]
    else:
        cmd = [sys.executable, "-u", str(find_engine()), _qarg]
        _cfg = opts.get("_config")          # 参数面板改过 → 用临时配置
        if _cfg:
            cmd += ["--config", str(_cfg)]
    for key, flag in _ARG_SPEC.items():
        v = opts.get(key)
        if v not in (None, "", "auto"):
            # ★ 能力门控：V2.2.3 新机制 flag 在旧引擎上不透传（= 缺省），
            #   否则 argparse 会因未知参数直接让整个任务失败。
            if flag in _GATED_FLAGS and not engine_supports_flag(flag):
                continue
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


# ── 运行中的「活痕迹」：任务一起跑就落盘，服务崩了也留得下 ────────────
# ★★ 为什么需要它（用户报障）：「后台服务崩的时候或者其他异常终止任务时，数据没有记录，
#   本来已经运行一段时间，突然没了，没用痕迹」。根因是任务表 `_tasks` 是**进程内存**，
#   服务被强杀/崩溃时它与「还没归档的进度」一起消失 ⇒ `outputs/` 里既没有 `.run.json`
#   也没有 `.run.log` ⇒ 历史对话 / 产物库 / 最近跑过**三处都查不到**。
#   解法：起跑就写一份 **以任务 id 命名**的活痕迹（`<tid>.run.json` + `<tid>.run.log`），
#   正常跑完由 `_archive()` 落最终归档并**删掉它**；异常/崩溃则留着，
#   下次服务启动由 `recover_orphans()` 回填成 `interrupted` + 原因。
_LIVE_MARK = "_live"          # task dict 上的内部标记（对外会被过滤掉）


def live_stamp(tid: str) -> str:
    """活痕迹的戳 = 任务 id（不含问题名 —— 起跑时还没有产物名可用）。"""
    return str(tid or "")


def _live_paths(tid: str) -> tuple[Path, Path]:
    st = live_stamp(tid)
    return (oi.OUTPUTS_DIR / f"{st}.run.json", oi.OUTPUTS_DIR / f"{st}.run.log")


def _write_live_run(task: dict) -> None:
    """把「正在运行」的元信息与日志落一份到 `outputs/`（可被强杀后幸存）。

    ★ 只在**起跑那一刻**写一次元信息（`status="running"`）：之后每次轮询都重写
      只会徒增 IO，而它要表达的本来就只是「这条任务起跑过、还没收尾」。
      日志那份则**由引擎的日志文件实时喂**，靠 `sync_live_log()` 增量同步。
    """
    if not oi.OUTPUTS_DIR.is_dir():
        return
    jp, lp = _live_paths(task["id"])
    meta = {
        "id": task["id"], "question": task["question"],
        "status": "running", "exit_code": None,
        "partial": False, "mock": task["mock"],
        "engine": "mock_engine" if task["mock"] else find_engine().name,
        "opts": task["opts"],
        "mode": task.get("mode") or {},
        "created_at": task["created_at"], "started_at": task["started_at"],
        "ended_at": None, "duration_sec": None,
        "output_name": None, "error": "", "cmd": task["cmd"],
        # ★ 写入 app 进程 pid：多实例/重启时只回填自己进程遗留的活痕迹。
        "app_pid": os.getpid(),
        "live": True,            # ★ 标记：这条是「活痕迹」，正常收尾时会被删掉
    }
    try:
        jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                      encoding="utf-8")
        lp.touch(exist_ok=True)
        task[_LIVE_MARK] = True
    except OSError:
        pass


def sync_live_log(task: dict) -> None:
    """把引擎日志的当前内容同步到 `<tid>.run.log`（崩溃时它就是唯一的日志痕迹）。

    ★ 用**字节复制**而不是逐行 append：引擎日志文件是唯一的真相源，
      直接 `write_bytes` 整份覆盖最简单、也不会因为重启/截断而产生错位。
      代价是任务全程会反复重写这个文件，但它的体量是「一次任务的日志」（百 KB 级），
      而同步频率 = 前端轮询频率，完全可接受。
    """
    if not task.get(_LIVE_MARK):
        return
    try:
        src = Path(task["log"])
        if not src.exists():
            return
        _, lp = _live_paths(task["id"])
        lp.write_bytes(src.read_bytes())
    except OSError:
        pass


def _clear_live_run(task: dict) -> None:
    """正常收尾后收掉「活痕迹」—— **仅当最终归档另起了文件名**时才删。

    ★★ 这里有个必须绕开的自噬陷阱：无产物时 `_archive()` 的 stamp 就取任务 id，
      写的正是 `<tid>.run.json` 这个**同一个文件**。此时若还去 `unlink` 它，
      等于把刚归档好的终态记录**当场删掉** —— 现象是「任务明明失败了却查不到」。
      ⇒ 判据用「归档的文件名是不是活痕迹那个」：是同一个就**留着**（它已被改成终态）。
    """
    if not task.get(_LIVE_MARK):
        return
    jp, lp = _live_paths(task["id"])
    if task.get("archive_json") and Path(task["archive_json"]).name == jp.name:
        task[_LIVE_MARK] = False      # 归档就地覆盖了活痕迹，别删
        return
    for p in (jp, lp):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass
    task[_LIVE_MARK] = False


def _pid_alive(pid) -> bool:
    """Windows/POSIX 通用：进程是否仍存在（只查询，不终止）。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            try:
                code = ctypes.c_ulong(0)
                if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                k32.CloseHandle(h)
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def recover_orphans() -> list[dict]:
    """★ 服务启动时回填「孤儿任务」：有活痕迹、但本次进程里没有对应任务的那些。

    典型来源：服务被强杀 / 崩溃 / 机器重启 —— `_tasks` 连同未归档的进度一起没了，
    而上一轮 `_write_live_run()` 落的 `<tid>.run.json` 还在盘上。
    ⇒ 把它们的状态改成 `interrupted` 并写明原因，让历史对话 / 产物库 / 最近跑过
      **三处都能看到这条「被中断的任务」**，而不是凭空消失。

    返回被回填的记录（供日志/自检读数）。幂等：已是 `interrupted` 的不会再改。
    """
    out: list[dict] = []
    if not oi.OUTPUTS_DIR.is_dir():
        return out
    with _tasks_lock:
        alive = set(_tasks.keys())
    for jp in oi.OUTPUTS_DIR.glob("*.run.json"):
        try:
            meta = json.loads(jp.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        if not meta.get("live"):
            continue                       # 只认「活痕迹」，正常归档的不动
        tid = str(meta.get("id") or jp.name[: -len(".run.json")])
        if tid in alive:
            continue                       # 本进程里还在跑（理论上不该有，防御而已）
        _owner = meta.get("app_pid")
        if _owner and int(_owner) != os.getpid() and _pid_alive(_owner):
            continue                       # 另一 app 实例仍存活，不能误判为孤儿
        if str(meta.get("status") or "") not in ("running", "queued"):
            continue
        meta["status"] = "interrupted"
        meta["live"] = False
        meta["error"] = "服务中断（进程异常退出 / 重启），本任务未正常收尾"
        if not meta.get("ended_at"):
            meta["ended_at"] = jp.stat().st_mtime
        try:
            if not meta.get("started_at"):
                meta["started_at"] = meta.get("created_at")
            if meta.get("started_at") and meta.get("ended_at"):
                meta["duration_sec"] = round(
                    float(meta["ended_at"]) - float(meta["started_at"]), 1)
        except (TypeError, ValueError):
            pass
        try:
            jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        except OSError:
            continue
        out.append({"id": tid, "question": meta.get("question"),
                    "status": "interrupted"})
    return out


# ── 手动终止：把「已经跑到的部分」落成一份部分产物 ──────────────────
def _safe_name(q: str, n: int = 20) -> str:
    """问题 → 可安全落盘的文件名片段（与引擎 / mock 同一套规则）。"""
    s = "".join(c for c in (q or "") if c not in r'\/:*?"<>|').strip()
    return s[:n] or "run"


def _clean_prefixed_output(task: dict) -> None:
    """项目上下文以 prompt_prefix 进入 argv 后，引擎会按整段问题命名产物。
    这里在收尾前把旧文件名统一改成「时间戳 + 原问题」，保持任务标题/产物名干净。"""
    old = str(task.get("output_name") or "")
    opts = task.get("opts") or {}
    if not old or not opts.get("_prompt_prefix"):
        return
    try:
        p = oi.OUTPUTS_DIR / old
        if not p.exists():
            return
        import re as _re
        m = _re.match(r"^(\d{8}_\d{6})_", p.name)
        ts = m.group(1) if m else time.strftime("%Y%m%d_%H%M%S")
        clean_stem = ts + "_" + _safe_name(task.get("question", ""))
        old_stem = p.name[:-3] if p.name.lower().endswith(".md") else p.stem
        if clean_stem == old_stem:
            return
        moved = {}
        for q in sorted(oi.OUTPUTS_DIR.glob(old_stem + "*")):
            suffix = q.name[len(old_stem):]
            new_name = clean_stem + suffix
            j = 1
            while (oi.OUTPUTS_DIR / new_name).exists():
                new_name = clean_stem + "_" + str(j) + suffix
                j += 1
            q.rename(oi.OUTPUTS_DIR / new_name)
            moved[q.name] = new_name
        if moved:
            first = moved.get(p.name)
            if first:
                task["output_name"] = first
    except Exception:
        pass


def _build_partial_md(task: dict, raw: str) -> str:
    """被手动终止时，用**运行日志**重建一份部分产物；一层都没跑到的返回空串。

    引擎只在**跑完**才写产物 md（实测 V1.23.20 / V1.23.22 都是收尾一次性写出），
    中途被终止则 outputs/ 下什么都没有。所以这里由应用层把「进行到哪」落下：
    每层的正文取自该层的日志段（引擎 verbose 会把层内容打进日志）。
    头部显式写上 `**状态**：已终止（部分）`，产物库与详情页据此标注。
    """
    parts_log = layers.split_log(raw or "")

    def _reached(seg: str) -> bool:
        """这一段是否「真的跑到了」——只有层界那一行（`━━━ 修行 · …` / `[修行层] 停止：…`）
        不算，必须有层界之外的正文行。否则会把「刚要开始就被终止」的层误报成已完成。"""
        return any(l.strip() and not layers.layer_of_line(l)
                   for l in (seg or "").splitlines())

    done = [n for n in layers.LAYER_NAMES if _reached(parts_log.get(n, ""))]
    if not done:
        return ""                       # 一层都没跑到 ⇒ 不落空壳产物（别往产物库里塞垃圾）
    head = [
        f"# 元 DGTF · {task.get('question', '')}",
        "",
        f"**时间**: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        "**状态**: 已终止（部分 · 手动停止）",
        f"**已完成层**: {'、'.join(done)} / 共 {len(layers.LAYER_NAMES)} 层",
        "**停止**: 手动终止",
        "",
        "> ⚠️ 本次运行由用户**手动终止**。下面是终止前已经产生的分层内容（取自运行日志），",
        "> **不是完整产物**，请勿当作最终结论使用。",
        "",
        "## 附：逐层明细",
        "",
    ]
    body: list[str] = []
    for n in layers.LAYER_NAMES:
        seg = parts_log.get(n, "")
        if not _reached(seg):
            continue                      # 没真跑到的层：不落
        body += [f"### {n}层 `{layers.ENTRY_OF_LAYER[n]}`", "", "```", seg.rstrip(), "```", ""]
    return "\n".join(head + body) + "\n"


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
        if ls.startswith("[tok]"):
            hidden += 1          # 读数行：只喂状态条，不进卡片日志
            continue
        out.append(line)
    res = "\n".join(out)
    return (res + "\n" if res else ""), hidden


def _archive(task: dict, status: str | None = None) -> None:
    """跑完把「完整运行日志」与「运行元信息」单独落到 outputs/。

    `status`：本轮跑完的**最终状态**。归档发生在 `task["status"]` 落定**之前**
    （见 `_finalize` 里的调用），所以元信息不能现读 task["status"]
    （那时还是 running），必须由调用方显式传进来。

    ★ 无产物（异常 / 被终止且一层都没跑到）时，stamp 取**任务 id** ——
      正好与「活痕迹」`<tid>.run.json` **同名**，于是这次归档就地把痕迹覆盖成终态，
      不会在多出一份重复记录（也不会留下一个永远 running 的孤儿）。
    """
    if not oi.OUTPUTS_DIR.is_dir():
        return
    name = task.get("output_name") or ""
    stamp = name[:-3] if name.endswith(".md") else (name or str(task["id"]))
    try:
        src = Path(task["log"])
        if src.exists():
            dst = oi.OUTPUTS_DIR / f"{stamp}.run.log"
            dst.write_bytes(src.read_bytes())
            task["archive_log"] = dst.name
        meta = {
            "id": task["id"], "question": task["question"],
            "status": status or task["status"], "exit_code": task["exit_code"],
            "partial": bool(task.get("partial")),
            "mock": task["mock"],
            "engine": "mock_engine" if task["mock"] else find_engine().name,
            "opts": task["opts"],
            # ★ T3：模式/计划随归档落盘 —— 服务重启 / resume / 历史对话都能看到当时的选择。
            "mode": task.get("mode") or {},
            "created_at": task["created_at"], "started_at": task["started_at"],
            "ended_at": task["ended_at"],
            "duration_sec": (round(task["ended_at"] - task["started_at"], 1)
                             if task["started_at"] and task["ended_at"] else None),
            "output_name": task.get("output_name"),
            "error": task.get("error", ""), "cmd": task["cmd"],
            "live": False,          # ★ 终态归档：`recover_orphans()` 不再认它
        }
        dstj = oi.OUTPUTS_DIR / f"{stamp}.run.json"
        dstj.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        task["archive_json"] = dstj.name
    except OSError:
        pass
    _archive_layers(task, stamp, status)


def _archive_layers(task: dict, stamp: str, status: str | None = None) -> None:
    """按层落盘：`<stamp>.<层>.md` / `.<层>.run.log` / `.<层>.json`。

    - md = 共有头部 + 该层段（头部与原总产物 md **逐字一致**）；
    - log = 该层那一段日志（原始，含层出现前的空窗不算）；
    - json = 该层的元信息与统计。
    没跑到的层**不落盘**（面板上也是「静默等待」）。
    """
    try:
        src = Path(task["log"])
        raw = src.read_text(encoding="utf-8", errors="replace") if src.exists() else ""
        name = task.get("output_name") or ""
        md = oi.read_body(name) if name else ""
        parts_log = layers.split_log(raw)
        parts_md = layers.split_md(md)
        head = parts_md.get("__head__", "")
        stats = layers.layer_stats(raw, md)
        written = []
        for n in layers.LAYER_NAMES:
            seg = parts_md.get(n, "")
            if not seg.strip():
                continue                      # 没跑到的层：静默
            base = f"{stamp}.{n}"
            (oi.OUTPUTS_DIR / f"{base}.md").write_text(
                head + seg, encoding="utf-8", newline="")
            lg = parts_log.get(n, "")
            if lg.strip():
                (oi.OUTPUTS_DIR / f"{base}.run.log").write_text(
                    lg + "\n", encoding="utf-8", newline="")
            meta = {
                "layer": n, "entry": layers.ENTRY_OF_LAYER[n],
                "task_id": task["id"], "question": task["question"],
                "status": status or task["status"], "output_name": name,
                "layer_md": f"{base}.md",
                "layer_log": f"{base}.run.log",
                "stats": stats.get(n, {}),
            }
            (oi.OUTPUTS_DIR / f"{base}.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8", newline="")
            written.append(n)
        task["layer_artifacts"] = written
    except OSError:
        pass


# ── 任务生命周期 ─────────────────────────────────────────────────
def start_task(question: str, opts: dict | None = None,
               mode_info: dict | None = None) -> str:
    question = (question or "").strip()
    if not question:
        raise ValueError("question 不能为空")
    opts = dict(opts or {})

    running = sum(1 for t in _tasks.values() if t["status"] in ("running", "queued"))
    tid = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    log_path = RUNS_DIR / f"{tid}.log"
    status = "queued" if running >= MAX_CONCURRENT else "running"

    # 参数面板传上来的 yaml 覆盖 → 生成一份临时配置（原 dgtf_config.yaml 不动）
    _profile = opts.pop("profile", None)
    if _profile:
        _pp = profile_path(str(_profile))
        if _pp is None:
            raise ValueError("未知调度 profile：%s" % _profile)
        opts["_config"] = str(_pp)
    overrides = opts.pop("overrides", None)
    if isinstance(overrides, dict) and overrides:
        import params as _P
        _cfg = _P.build_temp_config(overrides, RUNS_DIR / f"{tid}.yaml")
        if _cfg:
            opts["_config"] = _cfg

    # ★★ R38：CLM（任务级）参数的默认值 = 用户配置 `cli:` 段里**保存**的那份。
    #    用户要求「不然就按照用户参数面板的参数运行」—— 面板没在这次任务里传的键，
    #    用他上次保存的值；本次显式传的（`opts` 里已有）优先。
    #    （跑完 `_finalize` 会把 `cli:` 段清空 ⇒ 下下轮又回到「未指定」。）
    try:
        import params as _P2
        for _ck, _cv in (_P2.load_cli_saved() or {}).items():
            if _ck in _ARG_SPEC and not opts.get(_ck):
                opts[_ck] = _cv
    except Exception:  # noqa: BLE001
        pass

    task = {
        "id": tid,
        "question": question,
        "opts": opts,
        # ★ T3：模式/计划回显（POST 响应 + GET 单任务 + 重试/resume 都不丢）
        "mode": dict(mode_info) if isinstance(mode_info, dict) else {},
        "status": status,
        "mock": _is_mock(opts),
        "created_at": time.time(),
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "cancelled": False,                  # 用户是否手动终止过
        "partial": False,                    # 产物是否为「部分产物」
        "log": str(log_path),
        "output_name": None,
        "error": "",
        "cmd": build_cmd(question, opts),
        "before_outputs": _snapshot_outputs(),
        "pid": None,
        "timeout_s": float(opts.get("timeout_s") or opts.get("max_seconds") or 0),
        "timeout": False,
        "start_balance": current_balance(),   # 起始余额（花费用差额算）
        "tok_calls": 0,
        "tok_tokens": 0,
    }
    with _tasks_lock:
        _tasks[tid] = task

    # ★★ 起跑就落「活痕迹」（`outputs/<tid>.run.json`）—— 服务此刻被强杀也留得下。
    #    放在起线程**之前**：`_run` 一开跑就可能因为并发等待/崩溃而中断，
    #    痕迹必须在那之前就已经在盘上。
    _write_live_run(task)

    threading.Thread(target=_run, args=(tid,), daemon=True).start()
    return tid


def start_cached_task(question: str, opts: dict | None = None,
                      source: dict | None = None,
                      mode_info: dict | None = None) -> str:
    """创建一个“已完成”的缓存任务（不启动引擎，复用已验证产物）。"""
    question = (question or "").strip()
    source = dict(source or {})
    tid = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    task = {
        "id": tid,
        "question": question,
        "opts": dict(opts or {}),
        "mode": dict(mode_info) if isinstance(mode_info, dict) else {},
        "status": "done",
        "mock": False,
        "created_at": time.time(),
        "started_at": time.time(),
        "ended_at": time.time(),
        "exit_code": 0,
        "cancelled": False,
        "partial": False,
        "log": str(source.get("log") or ""),
        "output_name": str(source.get("output_name") or ""),
        "error": "",
        "cmd": [],
        "before_outputs": {},
        "pid": None,
        "timeout_s": float((opts or {}).get("timeout_s") or 0),
        "timeout": False,
        "start_balance": current_balance(),
        "tok_calls": 0,
        "tok_tokens": 0,
        "cached_from": str(source.get("id") or ""),
        "cache_hit": True,
    }
    with _tasks_lock:
        _tasks[tid] = task
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
    if task["status"] in ("error", "cancelled"):  # 排队期间被取消 / 终止
        return

    env = dict(os.environ)
    env.update(load_dotenv())
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    task["started_at"] = time.time()
    log_path = Path(task["log"])
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
            _no_win = 0x08000000 if os.name == "nt" else 0
            proc = subprocess.Popen(
                task["cmd"], cwd=str(PROJECT_ROOT), env=env,
                stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                # ★ [V2.2.0] App 发起的引擎任务必须无控制台窗口；
                #   否则用户每跑一题都看到黑窗弹出。
                creationflags=_no_win,
            )
            task["pid"] = proc.pid
            # ★ 用轮询代替 `proc.wait()`：每轮把引擎日志同步进「活痕迹」文件，
            #   这样服务**中途**被强杀时，`outputs/<tid>.run.log` 里已经有跑过的日志
            #   （`proc.wait()` 期间不同步的话，崩溃那一刻日志就全丢了）。
            _deadline = (time.time() + float(task.get("timeout_s") or 0)
                         if float(task.get("timeout_s") or 0) > 0 else 0)
            while True:
                try:
                    code = proc.wait(timeout=2.0)
                    break
                except subprocess.TimeoutExpired:
                    sync_live_log(task)
                    if _deadline and time.time() >= _deadline:
                        task["timeout"] = True
                        task["cancelled"] = True
                        task["error"] = "任务超过 timeout_s=%s 秒，已自动终止" % task.get("timeout_s")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        code = proc.wait(timeout=10)
        task["exit_code"] = code
    except Exception as e:  # noqa: BLE001
        # ★★ 异常路径也必须留痕：原来这里置 error 后**直接 return，不归档**
        #    ⇒ 历史对话 / 产物库 / 最近跑过三处都查不到这条任务。
        #    现在按中断处理：同步一次日志 + 落归档（status=error + 原因）。
        task["status"] = "error"
        task["error"] = f"{type(e).__name__}: {e}"
        task["ended_at"] = time.time()
        sync_live_log(task)
        try:
            _finalize(task, "error")
        except Exception:  # noqa: BLE001
            pass
        return

    task["ended_at"] = time.time()
    cancelled = bool(task.get("cancelled"))
    out = _find_new_output(task["before_outputs"], task["started_at"] or task["created_at"])
    if out:
        task["output_name"] = out
    elif cancelled:
        # ★ 引擎只在跑完才写产物；中途被终止 ⇒ 由应用层按日志重建「部分产物」，
        #   这样「进行到哪」的那部分也留在 outputs/ 里、并在产物库可见。
        #   （一层都没跑到则不落壳产物 —— 别把空跑也塞进产物库。）
        try:
            raw = Path(task["log"]).read_text(encoding="utf-8", errors="replace")
            partial = _build_partial_md(task, raw)
            if partial:
                name = (time.strftime("%Y%m%d_%H%M%S") + "_"
                        + _safe_name(task.get("question", "")) + ".md")
                (oi.OUTPUTS_DIR / name).write_text(partial, encoding="utf-8", newline="")
                task["output_name"] = name
                task["partial"] = True
        except OSError:
            pass
    _clean_prefixed_output(task)
    if cancelled:
        final = "cancelled"
    elif code == 0:
        final = "done"
    else:
        final = "error"
        if not task["error"]:
            task["error"] = f"引擎退出码 {code}"
    _finalize(task, final)


def _finalize(task: dict, final: str) -> None:
    """收尾：先落最终归档，**再**对外宣布跑完，最后收掉「活痕迹」。

    ★ 顺序要紧：**先落盘归档，再改 status**。
      反过来的话，前端有可能在 status 还是 done 的那一次轮询就停掉轮询，
      归档链接（archive_log / archive_json / layer_artifacts）就永远不出现了。
    ★★ R38：收尾时**清掉 CLM 参数**（用户要求「除了 CLM 参数每执行一次任务清零外，
      其他保留原保存的值」）—— 见 `_clear_cli_after_run`。放在最后，
      归档里已经用掉了这一次的值，清不清都不影响本次结果。
    """
    sync_live_log(task)
    _archive(task, final)
    task["status"] = final
    _clear_live_run(task)
    _clear_cli_after_run(task)


def _clear_cli_after_run(task: dict) -> None:
    """★ R38：任务跑完 ⇒ 把用户配置里 `cli:` 段（CLM/任务级参数）**清空**。

    ★ 用户原话：「除了 CLM 参数每执行一次任务清零外，其他保留原保存的值」
      —— CLM 参数是「随机任务传」的一次性指令（路由组合 / 圈数 / 通道…），
      跑完就该回到「未指定、交给引擎 auto 自决」，而不是粘在下次任务上。
    ★ 只清 `cli:` 段 —— 其余用户保存的键（模型 / 联网配置…）**原样保留**
      （同一个文件里的其他行不动，走 params.clear_cli_saved 的「重写且保留其余」实现）。
    ★ 清完后**同步 task 上的 opts**：本次任务的命令行已经发出去了，不影响它；
      这里清的是「下一次任务的默认值」。
    """
    try:
        import params as _P           # 延迟导入（engine_runner 与 params 无循环依赖）
        out = _P.clear_cli_saved()
        task["cli_cleared"] = bool(out.get("ok"))
        if not out.get("ok"):
            task["cli_clear_error"] = str(out.get("error"))
    except Exception as e:  # noqa: BLE001
        # ★ 失败必须留痕（红线）：字段进 task ⇒ API 可查；堆栈进服务日志。
        #   清不掉不该影响任务状态（本次已经跑完了）。
        task["cli_cleared"] = False
        task["cli_clear_error"] = f"{type(e).__name__}: {e}"
        import traceback
        traceback.print_exc()


def cancel_task(tid: str) -> bool:
    """手动终止：杀进程树，并把「已跑到的部分」落成部分产物（由 _run 收尾完成）。"""
    pid = None
    with _tasks_lock:
        task = _tasks.get(tid)
        if not task or task["status"] not in ("running", "queued"):
            return False
        task["cancelled"] = True
        task["error"] = "已手动终止"
        if task["status"] == "queued":
            # 还没起进程：直接落定；_run 的排队循环据此退出（不会跑到归档）
            task["status"] = "cancelled"
            task["ended_at"] = time.time()
        else:
            pid = task.get("pid")
    if pid:
        try:
            if os.name == "nt":
                _flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               creationflags=_flags, capture_output=True)
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
    # queue_pos：仅 status=='queued' 的任务有，1-based，按**入队顺序**
    # （created_at 升序；同一时刻用 id 兜底保证确定性）。只加在返回副本上，
    # 不改 _tasks 里的原任务，也不影响其它字段。
    queued = sorted((t for t in items if t.get("status") == "queued"),
                    key=lambda t: (float(t.get("created_at") or 0),
                                   str(t.get("id") or "")))
    queue_pos = {str(t.get("id")): i + 1 for i, t in enumerate(queued)}
    items.sort(key=lambda t: t["created_at"], reverse=True)
    out = []
    for t in items:
        row = {k: v for k, v in t.items()
               if not k.startswith("_") and k != "before_outputs"}
        # ★ T3：列表接口只回 mode 摘要（完整 plan 走单任务接口），避免每次轮询
        #   /api/tasks 把每条任务的 plan 都吐一遍。
        _mode = row.get("mode")
        if isinstance(_mode, dict) and _mode:
            _full = _mode.get("plan") if isinstance(_mode.get("plan"), dict) else {}
            row["mode"] = {
                "id": _mode.get("id") or _full.get("mode_id") or "",
                "requested": _mode.get("requested") or "",
                "tier": _mode.get("tier") or _full.get("tier") or "",
                "policy": _mode.get("policy") or _full.get("policy") or "",
                "engine_mode": _mode.get("engine_mode") or _full.get("engine_mode") or "",
                "quality_policy": (_mode.get("quality_policy")
                                   or _full.get("quality_policy") or ""),
                "budget_decision": ((_mode.get("budget_guard") or {}).get("decision")
                                    if isinstance(_mode.get("budget_guard"), dict) else ""),
                "reason": str(_mode.get("reason")
                              or _full.get("reason") or "")[:300],
                "has_plan": bool(_full),
            }
        if row.get("status") == "queued":
            row["queue_pos"] = queue_pos.get(str(t.get("id")), 0)
        out.append(row)
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
    """读 outputs/ 下的归档文件（只允许 .run.log / .run.json / .packed.json）。"""
    n = os.path.basename(str(name).replace("\\", "/"))
    # ★ R40：「json」胶囊要能直接打开 `<stamp>.packed.json`（引擎的 packed 原文）。
    if not (n.endswith(".run.log") or n.endswith(".run.json")
            or n.endswith(".packed.json")):
        return None
    try:
        return (oi.OUTPUTS_DIR / n).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_layers(tid: str) -> dict | None:
    """四层各自的日志（**已过滤**）+ 统计，给运行台的四层面板用。

    「有运行到就显示，没运行到就静默」——空层返回空字符串，前端自行显示占位。
    """
    with _tasks_lock:
        task = _tasks.get(tid)
    if task is None:
        return None
    done = task["status"] not in ("running", "queued")
    path = Path(task["log"])
    raw = ""
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
    # 与 read_log 同一把过滤器（丢留痕 / ing·view 全文框 / [tok] 读数行）
    filtered, hidden = _filter_lines(raw, {"skip": False, "kind": None, "n": 0})
    parts = layers.split_log(filtered)       # 显示用：不含 [tok]
    parts_raw = layers.split_log(raw)        # 统计用：含 [tok]，能按层算增量
    md = oi.read_body(task["output_name"]) if task.get("output_name") else ""
    calls, tokens = parse_tok(raw)

    # 每层消耗 = 该层区间内 [tok] 末值 − 进入该层前的 [tok] 末值
    seg_tok: dict[str, int] = {}
    _prev = 0
    for _n in layers.LAYER_NAMES:
        _c, _t = parse_tok(parts_raw.get(_n, ""))
        seg_tok[_n] = max(0, _t - _prev) if _t else 0
        if _t:
            _prev = _t

    # 每层起始：**首次**观测到该层有内容时记一次（内存态；服务重启后重记）
    _since = task.setdefault("_layer_since", {})
    _now = time.time()
    for _n in layers.LAYER_NAMES:
        if _n not in _since and parts.get(_n, "").strip():
            _since[_n] = _now

    _stats = layers.layer_stats(filtered, md)
    for _n in layers.LAYER_NAMES:
        _stats[_n]["tokens"] = seg_tok.get(_n, 0)
        _stats[_n]["since"] = _since.get(_n)

    _id_map = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}
    return {
        "head": parts.get("__head__", ""),
        "layers": {n: parts.get(n, "") for n in layers.LAYER_NAMES},
        # ★ 规范层 id ↔ 中文层名：app/健康检查/外部 API 用规范 id，UI 仍可读中文。
        "layer_ids": dict(_id_map),
        "layers_by_id": {k: parts.get(v, "") for k, v in _id_map.items()},
        "stats": _stats,
        "stats_by_id": {k: _stats.get(v) for k, v in _id_map.items()},
        "hidden": hidden,
        "done": done,
        "status": task["status"],
        "started_at": task.get("started_at"),
        "tok": {"calls": calls, "tokens": tokens},
    }


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
