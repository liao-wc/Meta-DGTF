# -*- coding: utf-8 -*-
"""A/B 基准 + 预算守门（Lead 专用，真跑前必用）。

为什么要有：账户余额只剩几十元，每次全量真跑约 ¥2~4。真跑必须在
「同一问题、同一配置、只改一个变量」下成对比较，并且把真实花费记下来，
否则无法证明「只变好不变坏」，也无法给下一轮做预算分配。

三个子命令：
  scan  扫描 outputs/*.packed.json，输出可配对的历史运行清单（含配置指纹、
        质量/成本/时延读数与分阶段 token 分布）。
  run   受控真跑：先查余额 → 通过 run_engine_instrumented.py 注入用量探针
        （含 prompt cache 命中率）→ 记录墙钟/真实花费 → 抽取 packed 指标
        → 追加到 docs/ab_results.jsonl。余额低于门槛直接拒绝。
  pair  取两次运行做逐项差（质量/calls/tokens/墙钟/花费/分阶段），并给出
        「是否只变好不变坏」的判定结果。

用法示例：
  python scripts/ab_bench.py scan --limit 20
  python scripts/ab_bench.py scan --question 热岛 --json
  python scripts/ab_bench.py run --tag base-B-1017 --question "为什么城市热岛
      效应在夜间比白天更明显？" --route 0,1,both,all --rounds 2 --parallel B
  python scripts/ab_bench.py pair --a base-B-1017 --b selfcheck-auto
  python scripts/ab_bench.py pair --a-file A.packed.json --b-file B.packed.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

AB_RESULTS = ROOT / "docs" / "ab_results.jsonl"
# ★ [Round 87] 真跑并发锁：dgtf_memory/real_run.lock（pid/tag/start/est/ttl）
REAL_RUN_LOCK = ROOT / "dgtf_memory" / "real_run.lock"
COST_ATTRIBUTION = "not_attributable_concurrent_runs"
COST_NOTE = ("账户窗口差（balance_before - balance_after）：并发/连续跑次会共享同一段"
             "余额下降，不可相加、不可归因到单跑；精确成本需按 API usage 单价结算。")


def _lock_check() -> dict:
    """返回仍有效的锁内容（无锁/过期锁返回 {}）。"""
    try:
        if not REAL_RUN_LOCK.exists():
            return {}
        data = json.loads(REAL_RUN_LOCK.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    try:
        age = time.time() - float(data.get("start_ts") or 0)
        ttl = float(data.get("ttl_s") or 1800)
    except Exception:  # noqa: BLE001
        return {}
    if age < ttl:
        return data
    try:
        REAL_RUN_LOCK.unlink()
    except Exception:  # noqa: BLE001
        pass
    return {}


def _lock_write(tag: str, est_cost) -> None:
    try:
        REAL_RUN_LOCK.parent.mkdir(parents=True, exist_ok=True)
        REAL_RUN_LOCK.write_text(json.dumps({
            "pid": os.getpid(),
            "tag": str(tag),
            "start_ts": time.time(),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "estimated_cny": est_cost,
            "ttl_s": 1800,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _lock_release() -> None:
    try:
        data = json.loads(REAL_RUN_LOCK.read_text(encoding="utf-8"))
        if int(data.get("pid") or -1) == os.getpid():
            REAL_RUN_LOCK.unlink()
    except Exception:  # noqa: BLE001
        pass
OUTPUTS = ROOT / "outputs"
MIN_BALANCE_DEFAULT = 4.0


# ── 基础读数 ─────────────────────────────────────────────────────
def read_env() -> dict:
    out = {}
    p = ROOT / ".env"
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get_balance() -> float | None:
    """查 DeepSeek 余额（CNY）；失败返回 None，不阻断。"""
    import urllib.request
    env = read_env()
    base = env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    # base 可能是 .../v1，余额端点在域根
    root = base[:-3] if base.endswith("/v1") else base
    try:
        req = urllib.request.Request(
            root + "/user/balance",
            headers={"Authorization": "Bearer " + env.get("DGTF_API_KEY", "")})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read().decode(
            "utf-8", "replace"))
        bi = (d.get("balance_infos") or [{}])[0]
        return float(bi.get("total_balance") or 0)
    except Exception:  # noqa: BLE001
        return None


def find_engine() -> Path:
    """与 App 同规则：取 engine 目录下版本号最大的 Meta-DGTF*.py。"""
    import re
    d = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
    cands = list(d.glob("Meta-DGTF*-V*.py")) + list(d.glob("元DGTF-V*.py"))
    if not cands:
        raise SystemExit("找不到引擎文件")

    def ver(p: Path):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    return sorted(cands, key=ver)[-1]


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _load_pack(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))


def stage_map(pack: dict) -> dict:
    return {str(s.get("stage")): {"calls": int(s.get("calls") or 0),
                                  "tokens": int(s.get("tokens") or 0),
                                  "ms": int(s.get("ms") or 0)}
            for s in (pack.get("llm_by_stage") or [])}


def fingerprint(pack: dict) -> dict:
    """从 packed 的 _config / _runtime 抽配置指纹（判配对方便）。"""
    cfg = pack.get("_config") or {}
    act = cfg.get("actions") or {}
    rt = cfg.get("runtime") or {}
    out = cfg.get("output") or {}
    api = cfg.get("api") or {}
    bf = pack.get("behavior_fusion") or {}
    return {
        "route": pack.get("route"),
        "rounds": pack.get("rounds"),
        "parallel_mode": act.get("parallel_mode"),
        "web_requested": rt.get("web"),
        "web_enabled": (pack.get("api_usage") or {}).get("web_enabled"),
        "thinking_requested": rt.get("thinking"),
        "effort": rt.get("effort"),
        "self_check": out.get("self_check"),
        "dual_judge": act.get("dual_judge"),
        "merge_expand": act.get("merge_expand"),
        "all_v2": act.get("all_v2"),
        "one_v2": act.get("one_v2"),
        "both_v2": act.get("both_v2"),
        "zero_v2": act.get("zero_v2"),
        "behavior_arm": bf.get("arm") or bf.get("chosen"),
        "model": api.get("default_model"),
    }


def pack_row(path: Path) -> dict:
    from dgtf_v2.pareto_flow import extract_flow_metrics
    try:
        pack = _load_pack(path)
    except Exception as e:  # noqa: BLE001
        return {"file": str(path), "error": str(e)}
    m = extract_flow_metrics(pack)
    q = pack.get("quality") or {}
    m.update({
        "file": str(path.relative_to(ROOT)),
        "mtime": path.stat().st_mtime,
        "stage": stage_map(pack),
        "fingerprint": fingerprint(pack),
        "quality_flags": list(q.get("flags") or []),
        "decision_flags": list((pack.get("decision_trace") or {}).get("flags") or []),
        "layout": pack.get("layout"),
        "engine": pack.get("engine") or pack.get("engine_version"),
        "budget": pack.get("budget") or {},
    })
    return m


def all_pack_paths(include_subdirs: bool = False) -> list[Path]:
    pats = ["**/*.packed.json"] if include_subdirs else ["*.packed.json"]
    out: list[Path] = []
    for pat in pats:
        out.extend(OUTPUTS.glob(pat))
    return sorted(out, key=lambda p: p.stat().st_mtime)


def _fmt(v, nd=4):
    if v is None:
        return "-"
    if isinstance(v, float):
        return ("%%.%df" % nd) % v
    return str(v)


# ── scan ─────────────────────────────────────────────────────────
def cmd_scan(args) -> int:
    paths = all_pack_paths(args.include_subdirs)
    rows = [pack_row(p) for p in paths]
    if getattr(args, "question", ""):
        rows = [r for r in rows if args.question in str(r.get("question", ""))]
    rows = [r for r in rows if "error" not in r]
    rows.sort(key=lambda r: r.get("mtime") or 0, reverse=not args.oldest)
    if args.limit:
        rows = rows[:args.limit]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print("%-4s %-18s %-9s %8s %9s %4s %-10s %-9s %s"
          % ("#", "id", "quality", "tokens", "calls", "sq", "aq/ready", "selfchk", "question"))
    for i, r in enumerate(rows, 1):
        fp = r.get("fingerprint") or {}
        st = r.get("stage") or {}
        sc = st.get("self_check", {}).get("calls", 0)
        dj = st.get("dual_judge", {}).get("calls", 0)
        print("%-4d %-18s %-9s %8s %9s %4s %-10s %-9s %s"
              % (i, str(r.get("id"))[:18], _fmt(r.get("quality")),
                 r.get("tokens"), r.get("calls"), len(r.get("quality_flags") or []),
                 "%s/%s" % (str(r.get("answer_quality"))[:8], r.get("answer_ready")),
                 "sc=%s dj=%s" % (sc, dj),
                 str(r.get("question", ""))[:26]))
    print("\n合计 %d 份；selfchk/dj 为分阶段调用数（sc=0 说明该跑关过 self_check）"
          % len(rows))
    return 0


# ── run ──────────────────────────────────────────────────────────
def _build_engine_args(args) -> list[str]:
    out: list[str] = []
    if args.config:
        out += ["--config", str(args.config)]
    simple = [("route", "--route"), ("keep", "--keep"), ("rounds", "--rounds"),
              ("parallel", "--parallel"), ("web", "--web"),
              ("thinking", "--thinking"), ("effort", "--effort"),
              ("actions_off", "--actions-off"),
              ("actions_on", "--actions-on"),
              ("behavior_fusion", "--behavior-fusion"),
              ("history_fusion", "--history-fusion"),
              ("landing", "--landing"), ("decidability", "--decidability"),
              ("orientation", "--orientation")]
    for key, flag in simple:
        v = getattr(args, key.replace("-", "_"), None)
        if v not in (None, "", "auto"):
            out += [flag, str(v)]
    if args.no_self_check:
        out.append("--no-self-check")
    for extra in args.extra or []:
        out.append(extra)
    return out


def _newest_pack_since(t0: float) -> Path | None:
    cands = [p for p in OUTPUTS.glob("*.packed.json") if p.stat().st_mtime >= t0]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def _pack_from_log(logp: Path) -> Path | None:
    """从本 run 日志里解析「已保存: outputs/xxx.md」→ 对应 .packed.json。

    并行 A/B 时各 run 的 packed 会互相盖过 mtime 法，这个入口是主判据。
    """
    try:
        text = logp.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    import re
    hits = re.findall(r"已保存[:：]\s*(outputs[\\/][^\r\n]+?\.md)", text)
    if not hits:
        return None
    p = ROOT / hits[-1].replace("\\", "/")
    pk = p.with_suffix("").with_suffix(".packed.json")
    if pk.exists():
        return pk
    return None


def _norm_question(q: str) -> str:
    import re as _re
    return _re.sub(r"[\s？?。.!！,，、;；:：]+", "", str(q or ""))


def _find_verified_duplicate(question: str, web=None) -> dict | None:
    """[Round 132] 同题 verified 结果（valid & quality>=0.9）→ 拒绝重复真跑省钱。

    历史产物里 64.2% tokens 花在重复问题；该守卫默认拒绝同题重跑，
    确需对照/复跑时显式 `--allow-repeat`。
    """
    if not AB_RESULTS.exists():
        return None
    qn = _norm_question(question)
    if not qn:
        return None
    rows = []
    for ln in AB_RESULTS.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            continue
    for r in reversed(rows):
        if _norm_question(r.get("question")) != qn:
            continue
        if not r.get("valid"):
            continue
        try:
            q = float(r.get("quality") or 0)
        except (TypeError, ValueError):
            q = 0.0
        if q < 0.90:
            continue
        if web is not None:
            ea = [str(x) for x in (r.get("engine_args") or [])]
            have = ""
            for i2, x2 in enumerate(ea):
                if x2 == "--web" and i2 + 1 < len(ea):
                    have = ea[i2 + 1].lower()
                    break
                if x2.startswith("--web="):
                    have = x2.split("=", 1)[1].lower()
                    break
            want_on = str(web).lower() in ("on", "1", "true")
            have_on = have in ("on", "1", "true")
            if have and have_on != want_on:
                continue
        return r
    return None


def cmd_run(args) -> int:
    engine = Path(args.engine).resolve() if args.engine else find_engine()
    bal0 = get_balance()
    print("引擎：%s" % engine)
    print("余额：%s CNY" % ("?" if bal0 is None else "%.2f" % bal0))
    if bal0 is not None and bal0 < args.min_balance:
        print("拒绝真跑：余额 %.2f < 门槛 %.2f（可用 --min-balance 覆盖，但请先想清楚）"
              % (bal0, args.min_balance))
        return 2
    if not getattr(args, "allow_repeat", False):
        _hit = _find_verified_duplicate(args.question, web=getattr(args, "web", None))
        if _hit:
            print("拒绝重复真跑：该问题已有 verified 结果 tag=%s quality=%s ts=%s；"
                  "重复问题历史消耗 64.2%% tokens。确需复跑请加 --allow-repeat"
                  % (_hit.get("tag"), _hit.get("quality"), _hit.get("ts")))
            return 4
    eng_args = _build_engine_args(args)
    probe = ROOT / "docs" / ("probe_%s.json" % (args.tag or time.strftime("%H%M%S")))
    instr = ROOT / "scripts" / "run_engine_instrumented.py"
    if args.no_instrument or not instr.exists():
        cmd = [sys.executable, "-u", str(engine)] + eng_args + [args.question]
    else:
        # run_engine_instrumented.py 的 REMAINDER 参数：-- 之后的都交给引擎
        cmd = ([sys.executable, "-u", str(instr), "--engine", str(engine),
                "--probe-out", str(probe), "--"] + eng_args + [args.question])
    print("命令：%s" % " ".join(cmd))
    if args.dry_run:
        return 0
    # ★ [Round 87] 并发锁：有活跃真跑则拒绝（--force-concurrent 显式覆盖）
    _holder = _lock_check()
    if _holder and not getattr(args, "force_concurrent", False):
        print("拒绝真跑：检测到活跃真跑 pid=%s tag=%s started=%s（TTL 内）；"
              "等待结束后重试，或 --force-concurrent 显式覆盖"
              % (_holder.get("pid"), _holder.get("tag"),
                 _holder.get("started_at")))
        return 3
    if _holder:
        print("警告：--force-concurrent 覆盖活跃真跑（pid=%s tag=%s）"
              % (_holder.get("pid"), _holder.get("tag")))
    _lock_write(args.tag, getattr(args, "est_cost", 0.0))

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # 引擎可能按需 import dgtf_v2.* 模块（mode_fusion / quality_predictor 等）
    env["PYTHONPATH"] = (str(ROOT) + os.pathsep
                         + str(ROOT / "dgtf_engine") + os.pathsep
                         + env.get("PYTHONPATH", ""))
    t0 = time.time()
    logp = ROOT / "docs" / ("abrun_%s.log" % (args.tag or t0))
    logf = open(logp, "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=env)
        tail = []
        for line in proc.stdout:
            logf.write(line)
            tail.append(line.rstrip("\n"))
            if len(tail) > 60:
                tail.pop(0)
            if args.verbose:
                print(line.rstrip("\n"))
        code = proc.wait()
    finally:
        logf.close()
        _lock_release()
    wall = time.time() - t0
    bal1 = get_balance()
    # ★ [Round 87] 成本 = 账户窗口差；保留 cost_cny 兼容，新增明确字段
    cost_window = (None if (bal0 is None or bal1 is None)
                   else round(bal0 - bal1, 4))
    cost = cost_window
    # 并行真跑时「最新 packed」可能属于另一个 run ⇒ 优先从本 run 的日志里
    # 解析引擎自己打印的「已保存: outputs/xxx.md」，再回退到 mtime 法。
    pack = _pack_from_log(logp) or _newest_pack_since(t0 - 5)
    row = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tag": args.tag,
        "question": args.question,
        "engine": str(engine.relative_to(ROOT)) if engine.is_relative_to(ROOT) else str(engine),
        "engine_args": eng_args,
        "note": args.note,
        "wall_s": round(wall, 1),
        "exit_code": code,
        "balance_before": bal0,
        "balance_after": bal1,
        "cost_cny": cost,
        "cost_window_cny": cost_window,
        "cost_attribution": COST_ATTRIBUTION,
        "cost_note": COST_NOTE,
        "probe": json.loads(probe.read_text(encoding="utf-8")) if probe.exists() else {},
        "packed": str(pack.relative_to(ROOT)) if pack else None,
        "log": str(logp.relative_to(ROOT)),
        "git_head": git_head(),
    }
    if pack:
        pr = pack_row(pack)
        row.update({k: pr.get(k) for k in
                    ("id", "quality", "tokens", "calls", "answer_quality",
                     "answer_ready", "quality_flags", "stage", "fingerprint",
                     "budget")})
    # 有效性标记：预算硬顶截断 / 引擎非零退出 / 无产物 ⇒ 该次真跑不能进质量对照
    _hard = bool((row.get("budget") or {}).get("hard_hit"))
    row["budget_hard_hit"] = _hard
    row["valid"] = bool(code == 0 and pack is not None and not _hard)
    AB_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with AB_RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("\n== 本次真跑 ==")
    print("tag=%s exit=%s wall=%.1fs cost_window=%s CNY（窗口差，不可归因）"
          % (args.tag, code, wall,
             cost if cost is not None else "?"))
    print("quality=%s tokens=%s calls=%s aq=%s ready=%s"
          % (row.get("quality"), row.get("tokens"), row.get("calls"),
             row.get("answer_quality"), row.get("answer_ready")))
    print("packed=%s\n结果已追加 %s" % (row.get("packed"), AB_RESULTS))
    if code != 0:
        print("引擎非零退出；日志尾部：")
        print("\n".join(tail))
    return code


# ── pair ─────────────────────────────────────────────────────────
def _find_result(key: str) -> dict | None:
    if not AB_RESULTS.exists():
        return None
    last = None
    for ln in AB_RESULTS.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if key in (str(r.get("tag")), str(r.get("id"))):
            last = r
    return last


def _row_from_pack(path: str) -> dict:
    pr = pack_row(Path(path) if Path(path).is_absolute() else ROOT / path)
    return {"tag": pr.get("id"), "id": pr.get("id"), **pr}


def cmd_pair(args) -> int:
    a = _find_result(args.a) if not args.a_file else _row_from_pack(args.a_file)
    b = _find_result(args.b) if not args.b_file else _row_from_pack(args.b_file)
    if not a or not b:
        print("找不到配对项：a=%r b=%r（用 run 的 --tag 或 --a-file/--b-file）"
              % (args.a, args.b))
        return 2
    keys = [("quality", "max", 4), ("tokens", "min", 0), ("calls", "min", 0),
            ("wall_s", "min", 1), ("cost_window_cny", "min", 4)]
    print("%-10s %-20s %-20s %-12s %s" % ("指标", "A", "B", "Δ(B-A)", "方向"))
    verdict = {"better": 0, "worse": 0, "same": 0}
    for k, direction, nd in keys:
        av, bv = a.get(k), b.get(k)
        if av is None or bv is None:
            print("%-10s %-20s %-20s %-12s %s" % (k, _fmt(av, nd), _fmt(bv, nd), "-", "缺读数"))
            continue
        d = round(float(bv) - float(av), nd if nd else 4)
        if abs(d) < (10 ** (-nd) if nd else 1e-9):
            tagv = "same"; verdict["same"] += 1
        elif (direction == "max" and d > 0) or (direction == "min" and d < 0):
            tagv = "better"; verdict["better"] += 1
        else:
            tagv = "worse"; verdict["worse"] += 1
        print("%-10s %-20s %-20s %-12s %s" % (k, _fmt(av, nd), _fmt(bv, nd), d, tagv))
    for k in ("answer_quality", "answer_ready", "quality_flags"):
        print("%-10s %-20s %-20s" % (k, a.get(k), b.get(k)))
    sa, sb = a.get("stage") or {}, b.get("stage") or {}
    print("\n分阶段调用/ token 差（B-A）：")
    for name in sorted(set(sa) | set(sb)):
        ca = sa.get(name, {}).get("calls", 0)
        cb = sb.get(name, {}).get("calls", 0)
        ta = sa.get(name, {}).get("tokens", 0)
        tb = sb.get(name, {}).get("tokens", 0)
        if ca != cb or ta != tb:
            print("  %-28s calls %+d  tokens %+d" % (name, cb - ca, tb - ta))
    print("\n判定：better=%d worse=%d same=%d（worse 必须为 0 才符合“只变好不变坏”）"
          % (verdict["better"], verdict["worse"], verdict["same"]))
    print("注：cost_window 为账户窗口差，并发/连续跑次不可相加、不可归因到单跑。")
    return 0


# ── main ─────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="A/B 基准 + 预算守门")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--question", default="")
    p.add_argument("--include-subdirs", action="store_true")
    p.add_argument("--oldest", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("run")
    p.add_argument("--question", required=True)
    p.add_argument("--tag", default="")
    p.add_argument("--est-cost", type=float, default=0.0,
                   help="预估成本（写入 real_run.lock，便于并发审计）")
    p.add_argument("--allow-repeat", action="store_true",
                   help="显式允许同题重复真跑（默认同题 verified 结果会拒绝）")
    p.add_argument("--force-concurrent", action="store_true",
                   help="显式覆盖 real_run.lock（默认拒绝并发展开）")
    p.add_argument("--note", default="")
    p.add_argument("--engine", default="")
    p.add_argument("--config", default="")
    p.add_argument("--route", default=None)
    p.add_argument("--keep", default=None)
    p.add_argument("--rounds", default=None)
    p.add_argument("--parallel", default=None)
    p.add_argument("--web", default=None)
    p.add_argument("--thinking", default=None)
    p.add_argument("--effort", default=None)
    p.add_argument("--actions-off", dest="actions_off", default="")
    p.add_argument("--actions-on", dest="actions_on", default="")
    p.add_argument("--behavior-fusion", dest="behavior_fusion", default=None)
    p.add_argument("--history-fusion", dest="history_fusion", default=None)
    p.add_argument("--landing", default=None)
    p.add_argument("--decidability", default=None)
    p.add_argument("--orientation", default=None)
    p.add_argument("--no-self-check", action="store_true")
    p.add_argument("--extra", action="append", default=[], help="透传引擎参数（可多次）")
    p.add_argument("--min-balance", type=float, default=MIN_BALANCE_DEFAULT)
    p.add_argument("--no-instrument", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("pair")
    p.add_argument("--a", default="")
    p.add_argument("--b", default="")
    p.add_argument("--a-file", default="")
    p.add_argument("--b-file", default="")
    p.set_defaults(fn=cmd_pair)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
