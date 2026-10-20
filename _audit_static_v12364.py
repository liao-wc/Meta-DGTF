# -*- coding: utf-8 -*-
"""元DGTF 工程静态审计器（v1.23.64 引入）。

只读扫描「活跃代码面」，不扫 _archive / outputs / smoke_outputs / __pycache__。
输出按严重度分级的 JSON + 人读摘要。每条都给 文件:行号 + 证据片段。

★ 设计原则：只报**可复核的事实**，不做风格说教。
   - critical: 会在真实环境直接失败/被利用
   - major:    在特定输入/平台/并发下失败，或静默丢数据
   - minor:    性能/可维护性，有量化依据
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP_DIRS = {"_archive", "outputs", "smoke_outputs", "smoke55_outputs", "__pycache__",
             ".git", ".workbuddy", "cache", "runs", "bench_runs"}
ACTIVE_GLOBS = [
    "元DGTF-V1.23.63.py", "smoke_test.py", "_v122_verify.py", "_probe_v1232_audit.py",
    "_mut_v12332.py", "_run_gate.py", "_git_save.py", "_run_full_v12333.py",
    "_run_matrix_v12333.py", "bench/*.py", "dgtf_app/*.py", "_probe_gain_dist.py",
    "_probe_gain_live.py",
]

FINDINGS = []


def add(sev, cat, path, line, msg, ev=""):
    FINDINGS.append({"severity": sev, "category": cat, "file": str(path),
                     "line": line, "message": msg, "evidence": ev[:240]})


def iter_active():
    seen = set()
    for g in ACTIVE_GLOBS:
        for p in HERE.glob(g):
            if p.is_file() and p.suffix == ".py" and p not in seen:
                seen.add(p)
                yield p


def sl(txt, ln, pad=0):
    lines = txt.splitlines()
    i = max(0, ln - 1)
    return (lines[i] if i < len(lines) else "").strip()


def has_utf8_bootstrap(txt):
    return ("reconfigure(encoding=\"utf-8\"" in txt or
            "reconfigure(encoding='utf-8'" in txt or
            "PYTHONIOENCODING" in txt or
            "_force_utf8_streams()" in txt)


NONASCII_OUT = re.compile(r"print\((?:f)?[\"'][^\"']*[^\x00-\x7f]")


def audit_file(p: Path):
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(txt)
    except SyntaxError as e:
        add("critical", "syntax", p, e.lineno or 0, f"语法错误：{e.msg}", str(e))
        return
    rel = p.relative_to(HERE)

    # ---- A. 终端编码可移植性 ----
    if NONASCII_OUT.search(txt) and not has_utf8_bootstrap(txt):
        m = NONASCII_OUT.search(txt)
        ln = txt[:m.start()].count("\n") + 1
        add("critical", "encoding", rel, ln,
            "向 stdout 打印非 ASCII 但未做 UTF-8 兜底；Windows GBK 管道下必崩",
            sl(txt, ln))
    for m in re.finditer(r"subprocess\.(?:run|Popen|check_output|check_call)\(([^\n]*)", txt):
        seg = m.group(0)
        ln = txt[:m.start()].count("\n") + 1
        if ("encoding=" not in seg and "text=True" not in seg
                and "capture_output" in seg):
            add("major", "encoding", rel, ln,
                "subprocess 捕获输出但未固定 encoding，父进程会按 locale 解码，非 ASCII 必乱/必崩",
                seg)
        if "env=" not in seg and p.name == "smoke_test.py":
            add("major", "encoding", rel, ln,
                "subprocess 未注入 PYTHONUTF8/PYTHONIOENCODING，子进程继承 GBK 会崩",
                seg)

    for m in re.finditer(r"\bopen\(([^\n)]*)\)", txt):
        seg = m.group(1)
        ln = txt[:m.start()].count("\n") + 1
        if ("encoding" not in seg and "'b'" not in seg and '"b"' not in seg
                and "rb" not in seg and "wb" not in seg):
            add("minor", "encoding", rel, ln, "open() 未指定 encoding（依赖 locale）", seg)
    for m in re.finditer(r"\.(read_text|write_text)\(([^\n)]*)\)", txt):
        seg = m.group(0)
        ln = txt[:m.start()].count("\n") + 1
        if "encoding" not in seg:
            add("minor", "encoding", rel, ln, "read_text/write_text 未指定 encoding", seg)

    # ---- B. 异常处理 ----
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler):
            if n.type is None:
                add("major", "exception", rel, n.lineno, "裸 except：连 KeyboardInterrupt/SystemExit 一起吞",
                    sl(txt, n.lineno))
            elif isinstance(n.type, ast.Name) and n.type.id == "Exception":
                body = n.body
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    add("major", "exception", rel, n.lineno,
                        "except Exception: pass —— 静默吞错，违反『失败留痕』",
                        sl(txt, n.lineno))
                elif (len(body) <= 2 and isinstance(body[0], ast.Pass)
                      and isinstance(body[-1], ast.Return)):
                    add("minor", "exception", rel, n.lineno,
                        "except Exception 后直接 return 兜底值，无日志", sl(txt, n.lineno))

    # ---- C. 可变默认参数 ----
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pos = list(n.args.posonlyargs) + list(n.args.args)
            padded = [None] * (len(pos) - len(n.args.defaults)) + list(n.args.defaults)
            for a, d in zip(pos, padded):
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    add("major", "python", rel, n.lineno,
                        f"可变默认参数 {n.name}({a.arg}=...)，跨调用共享", n.name)
            for a, d in zip(n.args.kwonlyargs, n.args.kw_defaults):
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    add("major", "python", rel, n.lineno,
                        f"可变默认参数 {n.name}({a.arg}=...)，跨调用共享", n.name)

    # ---- D. 时间基准 ----
    for m in re.finditer(r"datetime\.now\(\)", txt):
        ln = txt[:m.start()].count("\n") + 1
        add("minor", "time", rel, ln, "datetime.now() 无时区，跨时区/夏令时不可比", sl(txt, ln))
    for m in re.finditer(r"time\.time\(\)", txt):
        ln = txt[:m.start()].count("\n") + 1
        add("minor", "time", rel, ln, "time.time() 非单调钟，用于时长会被时钟回拨影响", sl(txt, ln))

    # ---- E. 危险调用 ----
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fn = n.func
            name = ""
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            if name in ("eval", "exec"):
                add("critical", "security", rel, n.lineno, f"使用 {name}()，可执行任意代码", sl(txt, n.lineno))
            if name in ("load", "loads") and isinstance(fn, ast.Attribute):
                if isinstance(fn.value, ast.Name) and fn.value.id == "pickle":
                    add("critical", "security", rel, n.lineno, "pickle 反序列化不可信数据 = 任意代码执行",
                        sl(txt, n.lineno))
            if name in ("run", "Popen", "call") and isinstance(fn, ast.Attribute):
                if isinstance(fn.value, ast.Name) and fn.value.id == "subprocess":
                    for kw in n.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            add("critical", "security", rel, n.lineno, "subprocess(shell=True)", sl(txt, n.lineno))

    # ---- F. 无界缓存 ----
    for m in re.finditer(r"(self\.\w*(?:cache|_memo|_seen)\w*)\s*=\s*\{\}", txt):
        ln = txt[:m.start()].count("\n") + 1
        add("minor", "memory", rel, ln, "无界缓存字典（未见淘汰逻辑时会长跑泄漏）", m.group(1))

    # ---- G. 关键写入原子性 ----
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr in ("write_text", "write_bytes"):
                ln = n.lineno
                window = "\n".join(txt.splitlines()[max(0, ln - 4):ln + 2])
                if ("tmp" not in window and "temp" not in window
                        and "replace(" not in window and "rename(" not in window):
                    add("minor", "io", rel, ln,
                        "直接覆写文件，崩溃会留下半截文件（关键状态建议 tmp+os.replace）",
                        sl(txt, ln))

    # ---- H. 循环内重复编译正则 / 重复读文件 ----
    for n in ast.walk(tree):
        if isinstance(n, (ast.For, ast.While)):
            for sub in ast.walk(n):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    if sub.func.attr in ("compile", "read_text") and isinstance(sub.func.value, ast.Name) \
                            and sub.func.value.id == "re":
                        add("minor", "perf", rel, sub.lineno, "循环内重复 re.compile", sl(txt, sub.lineno))
                    if sub.func.attr == "read_text":
                        add("minor", "perf", rel, sub.lineno, "循环内重复读盘", sl(txt, sub.lineno))

    # ---- I. 全局可变状态 ----
    globals_mut = []
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and isinstance(n.value, (ast.List, ast.Dict, ast.Set)):
                    globals_mut.append((t.id, n.lineno))
    for name, ln in globals_mut:
        cnt = len(re.findall(r"\bglobal\s+[^\n]*\b" + re.escape(name) + r"\b", txt)) + \
            len(re.findall(r"\b" + re.escape(name) + r"\.(?:append|add|update|pop|clear)\(", txt))
        if cnt >= 2:
            add("minor", "concurrency", rel, ln,
                f"模块级可变全局 {name} 被多处原地修改（{cnt} 处），并行下有竞态风险", name)


def main():
    files = list(iter_active())
    for p in files:
        audit_file(p)

    sev_order = {"critical": 0, "major": 1, "minor": 2}
    FINDINGS.sort(key=lambda f: (sev_order[f["severity"]], f["category"], f["file"], f["line"]))
    counts = {}
    for f in FINDINGS:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    out = HERE / "audits" / "static_audit_v12364.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"files": len(files), "counts": counts,
                               "findings": FINDINGS}, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print(f"扫描 {len(files)} 个活跃文件")
    print("分级：", counts)
    for sev in ("critical", "major", "minor"):
        rows = [f for f in FINDINGS if f["severity"] == sev]
        if not rows:
            continue
        print(f"\n=== {sev.upper()} ({len(rows)}) ===")
        for f in rows[:25]:
            print(f"  {f['file']}:{f['line']}  [{f['category']}] {f['message']}")
            if f["evidence"]:
                print(f"      | {f['evidence'][:150]}")
        if len(rows) > 25:
            print(f"  ... 其余 {len(rows)-25} 条见 {out.name}")
    print(f"\n完整结果：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
