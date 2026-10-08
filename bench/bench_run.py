#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1 G1.10] bench 跑批。

用法：
    python bench/bench_run.py                       # 跑全部 20 题（真模型）
    python bench/bench_run.py --only eng_001,biz_001
    python bench/bench_run.py --limit 3 --jobs 4
    python bench/bench_run.py --mock                # 离线桩（不花钱，验通路）

产物：
    bench/runs/<ts>/<id>/stdout.log
    bench/runs/<ts>/<id>/meta.json
    bench/runs/<ts>/<id>/<ts>_<q>.md
    bench/runs/<ts>/index.json
    bench/runs/LATEST            （文本，指向最新 ts 目录）
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent
BENCH = HERE / "bench"


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_engine(src: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dgtf_bench", HERE / src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_bench"] = mod
    spec.loader.exec_module(mod)
    return mod


def load_mock_engine(src: str):
    """读 smoke_test.py 源码、只换 SRC 那一行再 exec —— 不复制 harness。"""
    st = (HERE / "smoke_test.py").read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.2[12]\.\d+(-rc\d+)?\.py"')
    if len(pat.findall(st)) != 1:
        raise SystemExit("smoke_test.py 的 SRC 行不唯一，无法安全改指向")
    st = pat.sub(lambda _m: 'SRC = Path(r"%s")' % str(HERE / src), st, count=1)
    hm = types.ModuleType("bench_harness")
    hm.__file__ = str(HERE / "smoke_test.py")
    sys.modules["bench_harness"] = hm
    exec(compile(st, str(HERE / "smoke_test.py"), "exec"), hm.__dict__)
    return hm.mod, hm


def route_for(ori: str):
    """[v122] 任务书 Step 1.10：统一传 `--route 0,1,both,all`。

    砍层交给引擎自己的 `_route_by_decidability(orientation=...)` ——
    那是唯一实现，harness 里再写一份就是第 8 次「同一条逻辑两条通道
    各写一份」。
    """
    return ["0", "1", "both", "all"]


def rounds_arg(b):
    """任务书里 rounds 是 CLI 字符串 `"0:5,1:5,both:5,all:6"`；老字典形态也认。"""
    r = (b or {}).get("rounds")
    if isinstance(r, str):
        return r
    if isinstance(r, dict):
        return ",".join(f"{k}:{v}" for k, v in r.items())
    return r or 0


def run_one(q, mod, src, tag, mock, orientation_override=None,
            profile_override="", rounds_override=""):
    qid = q["id"]
    ori = orientation_override or q.get("orientation") or "auto"
    b = q.get("budget") or {}
    route = route_for(ori)
    rounds = rounds_override or rounds_arg(b)
    out = BENCH / "runs" / tag / qid
    out.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    t0 = time.time()
    info = {"id": qid, "domain": q.get("domain"), "question": q.get("question"),
            "orientation": ori, "route": route, "rounds": rounds,
            "mock": bool(mock), "ok": False, "error": ""}
    try:
        if mock:
            cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
            cfg["api"]["key"] = "sk-bench-mock"
        else:
            cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
        cfg["output"]["verbose"] = False
        cfg["output"]["save_dir"] = str(out)
        if b.get("profile"):
            cfg["cost_profile"] = b["profile"]
        if profile_override:
            cfg["cost_profile"] = profile_override
        with contextlib.redirect_stdout(buf):
            meta = mod.MetaDGTF(cfg)
            res = meta.run(q["question"], route=route, rounds=rounds,
                           parallel_mode=b.get("mode", "serial"),
                           orientation=ori)
            md = mod.save_result(res, str(out))
        info["ok"] = True
        info["md"] = str(md)
        try:
            (out / "packed.json").write_bytes(json.dumps(
                res, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
        except Exception as _e:
            info["packed_error"] = str(_e)[:120]
        info["calls"] = int(getattr(meta.llm, "total_calls", 0) or 0)
        info["tokens"] = int(getattr(meta.llm, "total_tokens", 0) or 0)
        info["layers_seen"] = sorted((res.get("views") or {}).keys())
        info["missing"] = list((res.get("dispatch") or {}).get("missing") or [])
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    info["elapsed_s"] = round(time.time() - t0, 1)
    info["elapsed"] = info["elapsed_s"]  # 任务书 Step 1.10 / bench_diff 口径
    _log = buf.getvalue()
    if info.get("md"):
        info["objective_lines"] = _objective_lines(Path(info["md"]))
        info["objective_block"] = _objective_block(Path(info["md"]))
        # 任务书 Step 1.5 验收：`grep -c "分层目标" "$d/stdout.log"` ≥ 1。
        # 引擎 --quiet 只打「已保存」，头部在产物里；这里把产物头部那段
        # 摘录进 stdout.log（带来源标注），让日志自洽、可直接 grep。
        if info["objective_block"]:
            _log += ("\n# [bench] 以下摘录自产物头部："
                     f"{Path(info['md']).name}\n" + info["objective_block"])
    (out / "stdout.log").write_bytes(_log.encode("utf-8", "replace"))
    (out / "meta.json").write_bytes(
        json.dumps(info, ensure_ascii=False, indent=2).encode("utf-8"))
    return info


def _objective_lines(md: Path):
    try:
        t = md.read_text(encoding="utf-8")
    except Exception:
        return 0
    head = t.split("\n\n")[:8]
    return sum(1 for l in "\n".join(head).splitlines()
               if l.strip().startswith("- ") and "层" in l and "：" in l
               and ("objective=" in l or "覆盖率" in l or "clean" in l))


def _objective_block(md: Path):
    """抠出产物里的「分层目标」那几行（含标题行），供日志摘录用。"""
    try:
        lines = md.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    try:
        i = next(k for k, l in enumerate(lines) if "分层目标" in l)
    except StopIteration:
        return ""
    return "\n".join(lines[i:i + 5]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="元DGTF-V1.22.0-rc1.py")
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--orientation", default="")
    ap.add_argument("--profile", default="",
                    help="覆盖每题 budget.profile（F.1 预算受限时用；"
                         "用了要在报告里写明是降档跑）")
    ap.add_argument("--rounds", default="",
                    help="覆盖每题 budget.rounds（同上，如实写进报告）")
    ap.add_argument("--skip-existing", action="store_true",
                    help="该 tag 下已有 ok=true 的 meta.json 就跳过该题"
                         "（续跑用，避免重复花钱）")
    a = ap.parse_args()

    load_dotenv(HERE / ".env")
    qs = []
    for f in sorted((BENCH / "questions").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if d.get("id"):
            qs.append(d)
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        qs = [q for q in qs if q["id"] in want]
    if a.limit:
        qs = qs[:a.limit]
    if not qs:
        print("没有题目可跑")
        return 1

    tag = a.tag or time.strftime("%Y%m%d_%H%M%S")
    run_dir = BENCH / "runs" / tag
    run_dir.mkdir(parents=True, exist_ok=True)
    if a.skip_existing:
        keep = []
        skipped = []
        for q in qs:
            mf = run_dir / q["id"] / "meta.json"
            try:
                ok = mf.is_file() and json.loads(
                    mf.read_text(encoding="utf-8")).get("ok")
            except Exception:
                ok = False
            (skipped if ok else keep).append(q["id"])
        if skipped:
            print(f"  · 续跑：跳过已完成 {len(skipped)} 题 {skipped}")
        qs = [q for q in qs if q["id"] in set(keep)]
        if not qs:
            print("全部题目都已完成，无需重跑")
            return 0
    print(f"═══ bench_run · src={a.src} · mock={a.mock} · {len(qs)} 题"
          f" · jobs={a.jobs} · tag={tag} ═══")

    if a.mock:
        mod, _hm = load_mock_engine(a.src)
    else:
        mod = load_engine(a.src)
    print(f"  模块 __version__={getattr(mod, '__version__', '?')}")

    results = []
    if a.jobs > 1 and not a.mock:
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {ex.submit(run_one, q, mod, a.src, tag, a.mock,
                              a.orientation or None, a.profile,
                              a.rounds): q["id"] for q in qs}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                print(f"  [{r['id']}] ok={r['ok']} calls={r.get('calls')}"
                      f" {r['elapsed_s']}s {r['error'][:60]}")
    else:
        for q in qs:
            r = run_one(q, mod, a.src, tag, a.mock, a.orientation or None,
                        a.profile, a.rounds)
            results.append(r)
            print(f"  [{r['id']}] ok={r['ok']} calls={r.get('calls')}"
                  f" {r['elapsed_s']}s {r['error'][:60]}")

    results.sort(key=lambda x: x["id"])
    (run_dir / "index.json").write_bytes(json.dumps(
        {"tag": tag, "src": a.src, "mock": a.mock, "n": len(results),
         "ok": sum(1 for r in results if r["ok"]),
         "profile_override": a.profile, "rounds_override": a.rounds,
         "items": results},
        ensure_ascii=False, indent=2).encode("utf-8"))
    (BENCH / "runs" / "LATEST").write_bytes(tag.encode("utf-8"))
    nok = sum(1 for r in results if r["ok"])
    print(f"完成：{nok}/{len(results)} 题成功 → bench/runs/{tag}/")
    return 0 if nok == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
